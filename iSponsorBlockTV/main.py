import asyncio
import pyatv
import aiohttp
import time
import logging
from . import api_helpers


class MyPushListener(pyatv.interface.PushListener):
    task = None
    apikey = None
    rc = None

    web_session = None
    categories = ["sponsor"]
    whitelist = []

    def __init__(self, apikey, atv, categories, whitelist, web_session):
        self.apikey = apikey
        self.rc = atv.remote_control
        self.web_session = web_session
        self.categories = categories
        self.whitelist = whitelist
        self.atv = atv

    def playstatus_update(self, updater, playstatus):
        logging.debug("Playstatus update" + str(playstatus))
        try:
            self.task.cancel()
        except:
            pass
        time_start = time.time()
        self.task = asyncio.create_task(
            process_playstatus(
                playstatus,
                self.apikey,
                self.rc,
                self.web_session,
                self.categories,
                self.atv,
                time_start,
                self.whitelist
            )
        )

    def playstatus_error(self, updater, exception):
        logging.error(exception)
        print("stopped")


async def process_playstatus(
    playstatus, apikey, rc, web_session, categories, atv, time_start, whitelist
):
    logging.debug("App playing is:" + str(atv.metadata.app.identifier))
    if (
        playstatus.device_state == playstatus.device_state.Playing
        and atv.metadata.app.identifier == "com.google.ios.youtube"
    ):
        vid_id = await api_helpers.get_vid_id(
            playstatus.title, playstatus.artist, apikey, web_session
        )
        if vid_id:
            print(f"ID: {vid_id[0]}, Channel ID: {vid_id[1]}")
            for i in whitelist:
                if vid_id[1] == i["id"]:
                    print("Channel whitelisted, skipping.")
                    return
            segments = await api_helpers.get_segments(vid_id[0], web_session, categories)
            print(segments)
            await time_to_segment(
                segments, playstatus.position, rc, time_start, web_session
            )
        else:
            print("Could not find video id")


async def time_to_segment(segments, position, rc, time_start, web_session):
    position = position + (time.time() - time_start)
    for segment in segments:
        if position < 2 and (
            position >= segment["start"] and position < segment["end"]
        ):
            next_segment = [position, segment["end"]]
            break
        if segment["start"] > position:
            next_segment = segment
            break
    time_to_next = next_segment["start"] - position
    await skip(time_to_next, next_segment["end"], next_segment["UUID"], rc, web_session)


async def skip(time_to, position, UUID, rc, web_session):
    await asyncio.sleep(time_to)
    await rc.set_position(position)
    # await api_helpers.viewed_segments(UUID, web_session) DISABLED FOR NOW


async def connect_atv(loop, identifier, airplay_credentials):
    """Find a device and print what is playing."""
    print("Discovering devices on network...")
    atvs = await pyatv.scan(loop, identifier=identifier)

    if not atvs:
        print("No device found, will retry")
        return

    config = atvs[0]
    config.set_credentials(pyatv.Protocol.AirPlay, airplay_credentials)

    print(f"Connecting to {config.address}")
    return await pyatv.connect(config, loop)


async def loop_atv(event_loop, atv_config, apikey, categories, whitelist, web_session):
    identifier = atv_config["identifier"]
    airplay_credentials = atv_config["airplay_credentials"]
    atv = await connect_atv(event_loop, identifier, airplay_credentials)
    if atv:
        listener = MyPushListener(apikey, atv, categories, whitelist, web_session)

        atv.push_updater.listener = listener
        atv.push_updater.start()
        print("Push updater started")
    while True:
        await asyncio.sleep(20)
        try:
            atv.metadata.app
        except:
            print("Reconnecting to Apple TV")
            # reconnect to apple tv
            atv = await connect_atv(event_loop, identifier, airplay_credentials)
            if atv:
                listener = MyPushListener(apikey, atv, categories, whitelist, web_session)

                atv.push_updater.listener = listener
                atv.push_updater.start()
                print("Push updater started")


def main(atv_configs, apikey, categories, whitelist, debug):
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if debug:
        loop.set_debug(True)
    asyncio.set_event_loop(loop)
    web_session = aiohttp.ClientSession()
    for i in atv_configs:
        loop.create_task(loop_atv(loop, i, apikey, categories, whitelist, web_session))
    loop.run_forever()
