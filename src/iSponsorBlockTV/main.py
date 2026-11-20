import asyncio
import logging
import os
import time
from pathlib import Path
from signal import SIGINT, SIGTERM, signal

import aiohttp

from . import api_helpers, ytlounge
from .debug_helpers import AiohttpTracer


class DeviceListener:
    def __init__(self, api_helper, config, device, debug: bool, web_session):
        self.task: asyncio.Task | None = None
        self.api_helper = api_helper
        self.offset = device.offset
        self.name = device.name
        self.cancelled = False
        self.logger = logging.getLogger(f"iSponsorBlockTV-{device.screen_id}")
        self.web_session = web_session
        self.lounge_controller = ytlounge.YtLoungeApi(
            device.screen_id, config, api_helper, self.logger
        )

    # Ensures that we have a valid auth token
    async def refresh_auth_loop(self):
        while True:
            await asyncio.sleep(60 * 60 * 24)  # Refresh every 24 hours
            try:
                await self.lounge_controller.refresh_auth()
            except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
                self.logger.debug("TV request failed; retrying when available")

    async def is_available(self):
        try:
            return await self.lounge_controller.is_available()
        except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
            return False

    # Main subscription loop
    async def loop(self):
        lounge_controller = self.lounge_controller
        while not self.cancelled:
            while not lounge_controller.linked():
                try:
                    self.logger.debug("Refreshing auth")
                    await lounge_controller.refresh_auth()
                except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
                    await asyncio.sleep(10)
            while not (await self.is_available()) and not self.cancelled:
                self.logger.debug("Waiting for device to be available")
                await asyncio.sleep(10)
            try:
                await lounge_controller.connect()
            except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
                self.logger.debug("TV request failed; retrying when available")
            while not lounge_controller.connected() and not self.cancelled:
                # Doesn't connect to the device if it's a kids profile (it's broken)
                self.logger.debug("Waiting for device to be connected")
                await asyncio.sleep(10)
                try:
                    await lounge_controller.connect()
                except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
                    self.logger.debug("TV connection failed; retrying")
            self.logger.info(
                "Connected to device %s (%s)", lounge_controller.screen_name, self.name
            )
            try:
                self.logger.debug("Subscribing to lounge")
                sub = await lounge_controller.subscribe_monitored(self)
                await sub
            except Exception:  # noqa: BLE001 - Third-party TV failures must not block reconnection.
                self.logger.debug("TV request failed; retrying when available")

    # Method called on playback state change
    async def __call__(self, state):
        time_start = time.monotonic()
        if self.task is not None:
            self.task.cancel()
        self.task = asyncio.create_task(self.process_playstatus(state, time_start))

    # Processes the playback state change
    async def process_playstatus(self, state, time_start):
        segments = []
        if state.videoId:
            segments = await self.api_helper.get_segments(state.videoId)
        if state.state.value == 1:  # Playing
            self.logger.info("Playing video %s with %d segments", state.videoId, len(segments))
            if segments:  # If there are segments
                await self.time_to_segment(segments, state.currentTime, time_start)

    # Finds the next segment to skip to and skips to it
    async def time_to_segment(self, segments, position, time_start):
        start_next_segment = None
        next_segment = None
        for segment in segments:
            segment_start = segment["start"]
            segment_end = segment["end"]
            is_within_start_range = (
                position < 1 < segment_end and segment_start <= position < segment_end
            )
            is_beyond_current_position = segment_start > position

            if is_within_start_range or is_beyond_current_position:
                next_segment = segment
                start_next_segment = position if is_within_start_range else segment_start
                break
        if start_next_segment:
            time_to_next = (
                (start_next_segment - position - (time.monotonic() - time_start))
                / self.lounge_controller.playback_speed
            ) - self.offset
            await self.skip(time_to_next, next_segment["end"], next_segment["UUID"])

    # Skips to the next segment (waits for the time to pass)
    async def skip(self, time_to, position, uuids):
        await asyncio.sleep(time_to)
        self.logger.info("Skipping segment: seeking to %s", position)
        await asyncio.gather(
            asyncio.create_task(self.lounge_controller.seek_to(position)),
            asyncio.create_task(self.api_helper.mark_viewed_segments(uuids)),
        )

    async def cancel(self):
        self.cancelled = True
        pending = [
            task
            for task in (
                self.task,
                self.lounge_controller.subscribe_task_watchdog,
                self.lounge_controller.subscribe_task,
            )
            if task is not None
        ]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await self.lounge_controller.disconnect()

    async def initialize_web_session(self):
        await self.lounge_controller.change_web_session(self.web_session)


async def wait_for_config(config, interval=0.5):
    """Keep the current listeners until a complete, valid replacement is available."""
    logger = logging.getLogger(__name__)
    previous = None
    last_error = None
    config_cls = type(config)
    while True:
        await asyncio.sleep(interval)
        try:
            content = Path(config.config_file).read_bytes()
            if content == previous:
                continue
            previous = content
            candidate = config_cls(config.data_dir)
            candidate.validate()
            last_error = None
            if candidate != config:
                return candidate
        except FileNotFoundError:
            if last_error != "missing":
                logger.info("Waiting for a configuration to be saved")
            last_error = "missing"
            previous = None
        except (OSError, ValueError, TypeError):
            if last_error != "unreadable":
                logger.warning(
                    "Configuration update is invalid or unreadable; keeping current settings"
                )
            last_error = "unreadable"


async def run_listeners(config, debug, http_tracing, stop, watch_config=False):
    """Run all configured device listeners until stopped or reloaded."""
    loop = asyncio.get_running_loop()
    loop.set_debug(debug)
    tasks = []
    devices = []
    trace_configs = []
    if http_tracing:
        tracer = AiohttpTracer(logging.getLogger("aiohttp_trace"))
        trace = aiohttp.TraceConfig()
        trace.on_request_start.append(tracer.on_request_start)
        trace.on_response_chunk_received.append(tracer.on_response_chunk_received)
        trace.on_request_end.append(tracer.on_request_end)
        trace.on_request_exception.append(tracer.on_request_exception)
        trace_configs.append(trace)

    async with aiohttp.ClientSession(
        trust_env=config.use_proxy,
        connector=aiohttp.TCPConnector(ttl_dns_cache=300),
        trace_configs=trace_configs,
    ) as web_session:
        reload_task = asyncio.create_task(wait_for_config(config)) if watch_config else None
        stop_task = asyncio.create_task(stop.wait())
        try:
            api_helper = api_helpers.ApiHelper(config, web_session)
            for entry in config.devices:
                device = DeviceListener(api_helper, config, entry, debug, web_session)
                devices.append(device)
                await device.initialize_web_session()
                tasks.extend(
                    [
                        asyncio.create_task(device.loop()),
                        asyncio.create_task(device.refresh_auth_loop()),
                    ]
                )
            pending = [stop_task, *tasks]
            if reload_task is not None:
                pending.append(reload_task)
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            if stop_task in done:
                return None
            if reload_task in done:
                logging.getLogger(__name__).info("Applying updated configuration")
                return reload_task.result()
            for task in done:
                task.result()
            raise RuntimeError("A device listener stopped unexpectedly")
        finally:
            pending = [stop_task, *tasks]
            if reload_task is not None:
                pending.append(reload_task)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            cleanup = asyncio.gather(
                *(device.cancel() for device in devices), return_exceptions=True
            )
            try:
                await asyncio.wait_for(cleanup, timeout=5)
            except TimeoutError:
                logging.getLogger(__name__).warning("Timed out disconnecting devices")


async def heartbeat(healthcheck_path=None):
    """Periodically touch the configured healthcheck file for container probes."""
    raw_path = healthcheck_path or os.environ.get("HEALTHCHECK_PATH")
    if not raw_path:
        return
    path = Path(raw_path)
    logger = logging.getLogger(__name__)
    failed = False
    while True:
        try:
            path.touch()
            failed = False
        except OSError:
            if not failed:
                logger.warning("Failed to update healthcheck file %s", path)
                failed = True
        await asyncio.sleep(5)


async def main_async(config, debug, http_tracing, watch_config=False):
    """Manage signal handling, health heartbeat, and listener lifecycle."""
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    healthcheck_path = os.environ.get("HEALTHCHECK_PATH")
    health_task = asyncio.create_task(heartbeat(healthcheck_path)) if healthcheck_path else None
    previous_handlers = {}
    for signum in (SIGTERM, SIGINT):
        previous_handlers[signum] = signal(signum, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        while not stop.is_set():
            try:
                candidate = await run_listeners(config, debug, http_tracing, stop, watch_config)
                if candidate is None:
                    break
                config = candidate
            except Exception:
                logging.getLogger(__name__).exception("Listener failed; retrying in five seconds")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=5)
                except TimeoutError:
                    pass
    finally:
        if health_task is not None:
            health_task.cancel()
            await asyncio.gather(health_task, return_exceptions=True)
        for signum, handler in previous_handlers.items():
            signal(signum, handler)


def main(config, debug, http_tracing, watch_config=False):
    asyncio.run(main_async(config, debug, http_tracing, watch_config))
