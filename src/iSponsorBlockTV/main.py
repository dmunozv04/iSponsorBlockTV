import asyncio
import aiohttp
import time
import logging
from . import api_helpers, ytlounge


class DeviceListener:
    def __init__(self, api_helper, config, device):
        self.task: asyncio.Task = None
        self.api_helper = api_helper
        self.lounge_controller = ytlounge.YtLoungeApi(
            device.screen_id, config, api_helper)
        self.offset = device.offset
        self.name = device.name
        self.cancelled = False

    # Ensures that we have a valid auth token
    async def refresh_auth_loop(self):
        while True:
            await asyncio.sleep(60 * 60 * 24)  # Refresh every 24 hours
            try:
                await self.lounge_controller.refresh_auth()
            except:
                # traceback.print_exc()
                pass

    async def is_available(self):
        try:
            return await self.lounge_controller.is_available()
        except:
            # traceback.print_exc()
            return False

    # Main subscription loop
    async def loop(self):
        lounge_controller = self.lounge_controller
        while not lounge_controller.linked():
            try:
                await lounge_controller.refresh_auth()
            except:
                # traceback.print_exc()
                await asyncio.sleep(10)
        while not self.cancelled:
            while not (await self.is_available()) and not self.cancelled:
                await asyncio.sleep(10)
            try:
                await lounge_controller.connect()
            except:
                pass
            while not lounge_controller.connected() and not self.cancelled:
                # Doesn't connect to the device if it's a kids profile (it's broken)
                await asyncio.sleep(10)
                try:
                    await lounge_controller.connect()
                except:
                    pass
            print(f"Connected to device {lounge_controller.screen_name} ({self.name})")
            try:
                # print("Subscribing to lounge")
                sub = await lounge_controller.subscribe_monitored(self)
                await sub
                await asyncio.sleep(10)
            except:
                pass

    # Method called on playback state change
    async def __call__(self, state):
        logging.debug("Playstatus update" + str(state))
        try:
            self.task.cancel()
        except:
            pass
        time_start = time.time()
        self.task = asyncio.create_task(self.process_playstatus(state, time_start))

    # Processes the playback state change
    async def process_playstatus(self, state, time_start):
        segments = []
        if state.videoId:
            segments = await self.api_helper.get_segments(state.videoId)
        if state.state.value == 1:  # Playing
            print(f"Playing {state.videoId} with {len(segments)} segments")
            if segments:  # If there are segments
                await self.time_to_segment(segments, state.currentTime, time_start)

    # Finds the next segment to skip to and skips to it
    async def time_to_segment(self, segments, position, time_start):
        start_next_segment = None
        next_segment = None
        for segment in segments:
            if position < 2 and (
                    segment["start"] <= position < segment["end"]
            ):
                next_segment = segment
                start_next_segment = position  # different variable so segment doesn't change
                break
            if segment["start"] > position:
                next_segment = segment
                start_next_segment = next_segment["start"]
                break
        if start_next_segment:
            time_to_next = start_next_segment - position - (time.time() - time_start) - self.offset
            await self.skip(time_to_next, next_segment["end"], next_segment["UUID"])

    # Skips to the next segment (waits for the time to pass)
    async def skip(self, time_to, position, UUID):
        await asyncio.sleep(time_to)
        await asyncio.gather(
            self.lounge_controller.seek_to(position),
            self.api_helper.mark_viewed_segments(UUID)
            )

    # Stops the connection to the device
    async def cancel(self):
        self.cancelled = True
        try:
            self.task.cancel()
        except Exception:
            pass


async def finish(devices):
    for i in devices:
        await i.cancel()


def main(config, debug):
    loop = asyncio.get_event_loop_policy().get_event_loop()
    tasks = []  # Save the tasks so the interpreter doesn't garbage collect them
    devices = []  # Save the devices to close them later
    if debug:
        loop.set_debug(True)
    asyncio.set_event_loop(loop)
    tcp_connector = aiohttp.TCPConnector(ttl_dns_cache=300)
    web_session = aiohttp.ClientSession(loop=loop, connector=tcp_connector)
    api_helper = api_helpers.ApiHelper(config, web_session)
    for i in config.devices:
        device = DeviceListener(api_helper, config, i)
        devices.append(device)
        tasks.append(loop.create_task(device.loop()))
        tasks.append(loop.create_task(device.refresh_auth_loop()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, cancelling tasks and exiting...")
        loop.run_until_complete(finish(devices))
    finally:
        loop.run_until_complete(web_session.close())