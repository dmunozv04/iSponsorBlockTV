import asyncio
import contextlib
import logging
import os
import time
from signal import SIGINT, SIGTERM, signal
from typing import Optional

import aiohttp

from . import api_helpers, ytlounge
from .debug_helpers import AiohttpTracer

# pyytlounge State value -> friendly status for the playback_state sensor.
PLAYBACK_STATES = {
    -1: "stopped",
    0: "buffering",
    1: "playing",
    2: "paused",
    3: "starting",
    1081: "advertisement",
}


class DeviceListener:
    def __init__(self, api_helper, config, device, debug: bool, web_session, notifier=None):
        self.task: Optional[asyncio.Task] = None
        self.api_helper = api_helper
        self.offset = device.offset
        self.name = device.name
        self.screen_id = device.screen_id
        self.notifier = notifier
        self._current_video_id = ""
        self._last_title_id = ""
        self._last_playback_state = ""
        self._metadata_task: Optional[asyncio.Task] = None
        self.cancelled = False
        self.logger = logging.getLogger(f"iSponsorBlockTV-{device.screen_id}")
        self.web_session = web_session
        self.lounge_controller = ytlounge.YtLoungeApi(
            device.screen_id,
            config,
            api_helper,
            self.logger,
            notifier=notifier,
            device_name=device.name,
        )

    # Ensures that we have a valid auth token
    async def refresh_auth_loop(self):
        while True:
            await asyncio.sleep(60 * 60 * 24)  # Refresh every 24 hours
            try:
                await self.lounge_controller.refresh_auth()
            except BaseException:
                pass

    async def is_available(self):
        try:
            return await self.lounge_controller.is_available()
        except BaseException:
            return False

    # Main subscription loop
    async def loop(self):
        lounge_controller = self.lounge_controller
        while not self.cancelled:
            while not lounge_controller.linked():
                try:
                    self.logger.debug("Refreshing auth")
                    await lounge_controller.refresh_auth()
                except BaseException:
                    await asyncio.sleep(10)
            while not (await self.is_available()) and not self.cancelled:
                self.logger.debug("Waiting for device to be available")
                await asyncio.sleep(10)
            try:
                await lounge_controller.connect()
            except BaseException:
                pass
            while not lounge_controller.connected() and not self.cancelled:
                # Doesn't connect to the device if it's a kids profile (it's broken)
                self.logger.debug("Waiting for device to be connected")
                await asyncio.sleep(10)
                try:
                    await lounge_controller.connect()
                except BaseException:
                    pass
            self.logger.info(
                "Connected to device %s (%s)", lounge_controller.screen_name, self.name
            )
            if self.notifier:
                self.notifier.emit(
                    "device_connected",
                    self.screen_id,
                    self.name,
                    screen_name=lounge_controller.screen_name,
                )
            try:
                self.logger.debug("Subscribing to lounge")
                sub = await lounge_controller.subscribe_monitored(self)
                await sub
            except BaseException:
                pass
            if self.notifier and not self.cancelled:
                self.notifier.emit("device_disconnected", self.screen_id, self.name)
                self.notifier.set_title(self.screen_id, "")
                self.notifier.set_channel(self.screen_id, "")
                self._last_title_id = ""
                if self._last_playback_state != "stopped":
                    self._last_playback_state = "stopped"
                    self.notifier.set_playback_state(self.screen_id, "stopped")

    # Method called on playback state change
    async def __call__(self, state):
        time_start = time.monotonic()
        try:
            self.task.cancel()
        except BaseException:
            pass
        self.task = asyncio.create_task(self.process_playstatus(state, time_start))

    # Processes the playback state change
    async def process_playstatus(self, state, time_start):
        self._current_video_id = state.videoId or ""
        if self.notifier:
            playback_state = PLAYBACK_STATES.get(state.state.value, "unknown")
            if playback_state != self._last_playback_state:
                self._last_playback_state = playback_state
                self.notifier.set_playback_state(self.screen_id, playback_state)
        # Publish the title BEFORE the (network, cancellable) segment fetch, so it
        # isn't lost when this task is superseded by the next state change. Track the
        # id we've *published* - not every id seen - since a video first arrives in a
        # non-playing (buffering) state, which would otherwise dedupe it away.
        if (
            self.notifier
            and state.state.value == 1
            and state.videoId
            and state.videoId != self._last_title_id
        ):
            self._last_title_id = state.videoId
            # Show the id immediately; metadata resolution replaces it with the real
            # title once the YouTube API answers (a no-op without an API key).
            self.notifier.set_title(self.screen_id, state.videoId)
            self._start_metadata_resolution(state.videoId)
        elif (
            self.notifier
            and self._last_title_id
            and (state.state.value == -1 or not state.videoId)  # Stopped / no video
        ):
            # Playback stopped -> blank the title + channel sensors (empty = idle).
            self._last_title_id = ""
            self.notifier.set_title(self.screen_id, "")
            self.notifier.set_channel(self.screen_id, "")
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
            await self.skip(time_to_next, next_segment, start_next_segment)

    # Skips to the next segment (waits for the time to pass)
    async def skip(self, time_to, segment, start_position):
        await asyncio.sleep(time_to)
        end_position = segment["end"]
        self.logger.info("Skipping segment: seeking to %s", end_position)
        await asyncio.gather(
            asyncio.create_task(self.lounge_controller.seek_to(end_position)),
            asyncio.create_task(self.api_helper.mark_viewed_segments(segment["UUID"])),
        )
        if self.notifier:
            self.notifier.emit(
                "segment_skipped",
                self.screen_id,
                self.name,
                video_id=self._current_video_id or None,
                category=segment.get("category"),
                skipped_from=round(start_position, 3),
                skipped_to=round(end_position, 3),
            )

    def _start_metadata_resolution(self, video_id):
        # Resolve the video's title + channel in the background and update the
        # sensors. Its own task, so the API lookup is never cancelled with
        # process_playstatus and never blocks the skip path. No-op without an API key.
        if not (self.notifier and getattr(self.api_helper, "apikey", "")):
            return
        if self._metadata_task and not self._metadata_task.done():
            self._metadata_task.cancel()
        self._metadata_task = asyncio.create_task(self._resolve_metadata(video_id))

    async def _resolve_metadata(self, video_id):
        try:
            meta = await self.api_helper.get_video_metadata(video_id)
        except BaseException:
            meta = None
        # Only apply if this is still the current video (user may have moved on).
        if meta and self.notifier and video_id == self._last_title_id:
            if meta.get("title"):
                self.notifier.set_title(self.screen_id, meta["title"])
            if meta.get("channel"):
                self.notifier.set_channel(self.screen_id, meta["channel"])

    async def cancel(self):
        self.cancelled = True
        await self.lounge_controller.disconnect()
        if self.task:
            self.task.cancel()
        if self._metadata_task:
            self._metadata_task.cancel()
        if self.lounge_controller.subscribe_task_watchdog:
            self.lounge_controller.subscribe_task_watchdog.cancel()
        if self.lounge_controller.subscribe_task:
            self.lounge_controller.subscribe_task.cancel()
        await asyncio.gather(
            self.task,
            self.lounge_controller.subscribe_task_watchdog,
            self.lounge_controller.subscribe_task,
            return_exceptions=True,
        )

    async def initialize_web_session(self):
        await self.lounge_controller.change_web_session(self.web_session)


async def finish(devices, notifier, web_session, tcp_connector):
    for device in devices:
        device.cancelled = True
    await asyncio.gather(*(device.cancel() for device in devices), return_exceptions=True)
    if notifier:
        await notifier.stop()
    await web_session.close()
    await tcp_connector.close()


async def main_async(config, debug, http_tracing):
    loop = asyncio.get_running_loop()
    tasks = []  # Save the tasks so the interpreter doesn't garbage collect them
    devices = []  # Save the devices to close them later
    if debug:
        loop.set_debug(True)

    tcp_connector = aiohttp.TCPConnector(ttl_dns_cache=300)

    # Configure session with tracing if enabled
    if http_tracing:
        root_logger = logging.getLogger("aiohttp_trace")
        tracer = AiohttpTracer(root_logger)
        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_start.append(tracer.on_request_start)
        trace_config.on_response_chunk_received.append(tracer.on_response_chunk_received)
        trace_config.on_request_end.append(tracer.on_request_end)
        trace_config.on_request_exception.append(tracer.on_request_exception)
        web_session = aiohttp.ClientSession(
            trust_env=config.use_proxy, connector=tcp_connector, trace_configs=[trace_config]
        )
    else:
        web_session = aiohttp.ClientSession(trust_env=config.use_proxy, connector=tcp_connector)

    api_helper = api_helpers.ApiHelper(config, web_session)

    notifier = None
    if config.mqtt.get("enabled"):
        from .notifications import Notifier  # lazy import: only load aiomqtt when enabled

        notifier = Notifier(config, logging.getLogger("iSponsorBlockTV-mqtt"))
        await notifier.start()

    for i in config.devices:
        device = DeviceListener(api_helper, config, i, debug, web_session, notifier=notifier)
        devices.append(device)
        await device.initialize_web_session()
        tasks.append(loop.create_task(device.loop()))
        tasks.append(loop.create_task(device.refresh_auth_loop()))
    # Drive shutdown through the loop's signal handling and an explicit stop event.
    # (Raising KeyboardInterrupt from a handler is unreliable here: the device loops
    # catch BaseException, which swallows the interrupt and leaves the process
    # running - the "refused to stop" symptom.)
    stop_event = asyncio.Event()
    try:
        loop.add_signal_handler(SIGTERM, stop_event.set)
        loop.add_signal_handler(SIGINT, stop_event.set)
    except NotImplementedError:  # add_signal_handler is unavailable on Windows
        signal(SIGTERM, lambda *_: loop.call_soon_threadsafe(stop_event.set))
        signal(SIGINT, lambda *_: loop.call_soon_threadsafe(stop_event.set))

    runner = asyncio.gather(*tasks, return_exceptions=True)
    stop_wait = asyncio.ensure_future(stop_event.wait())
    await asyncio.wait({runner, stop_wait}, return_when=asyncio.FIRST_COMPLETED)

    print("Cancelling tasks and exiting...")
    stop_wait.cancel()
    runner.cancel()
    for task in tasks:
        task.cancel()
    # Bounded, best-effort graceful cleanup (incl. MQTT "offline"); a hung network
    # call can't block the exit.
    with contextlib.suppress(BaseException):
        await asyncio.wait_for(finish(devices, notifier, web_session, tcp_connector), timeout=8)
    print("Exited")
    # The device loops swallow cancellation, so the interpreter's own task cleanup
    # can still wedge on one that refuses to stop. We've cleaned up gracefully above;
    # guarantee the process actually terminates.
    os._exit(0)


def main(config, debug, http_tracing):
    asyncio.run(main_async(config, debug, http_tracing))
