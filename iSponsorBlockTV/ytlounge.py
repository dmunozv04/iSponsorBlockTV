import asyncio
import aiohttp
import pyytlounge
from . import log_helpers as log

create_task = asyncio.create_task


class YtLoungeApi(pyytlounge.YtLoungeApi):
    def __init__(self, screen_id, config=None, api_helper=None, device_name=None):
        super().__init__("iSponsorBlockTV")
        self.auth.screen_id = screen_id
        self.auth.lounge_id_token = None
        self.api_helper = api_helper
        self.device_name = device_name
        self.volume_state = {}
        self.subscribe_task = None
        self.subscribe_task_watchdog = None
        self.callback = None
        if config:
            self.mute_ads = config.mute_ads
            self.skip_ads = config.skip_ads

    # Ensures that we still are subscribed to the lounge
    async def _watchdog(self):
        await asyncio.sleep(35)  # YouTube sends at least a message every 30 seconds (no-op or any other)
        try:
            self.subscribe_task.cancel()
        except Exception as e:
            pass

    # Subscribe to the lounge and start the watchdog
    async def subscribe_monitored(self, callback):
        self.callback = callback
        try:
            self.subscribe_task_watchdog.cancel()
        except:
            pass  # No watchdog task
        self.subscribe_task = asyncio.create_task(super().subscribe(callback))
        self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        return self.subscribe_task

    # Process a lounge subscription event
    def _process_event(self, event_id: int, event_type: str, args):
        # log.info(f"YtLoungeApi.__process_event({event_id}, {event_type}, {args})")
        # (Re)start the watchdog
        try:
            self.subscribe_task_watchdog.cancel()
        except:
            pass
        finally:
            self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        # A bunch of events useful to detect ads playing, and the next video before it starts playing (that way we can get the segments)
        if event_type == "onStateChange":
            data = args[0]
            self.state.apply_state(data)
            self._update_state()
            # log.info(data)
            # Unmute when the video starts playing
            if self.mute_ads and data["state"] == "1":
                create_task(self.mute(False, override=True))
        elif event_type == "nowPlaying":
            data = args[0]
            self.state = pyytlounge.PlaybackState(self._logger, data)
            self._update_state()
            # Unmute when the video starts playing
            if self.mute_ads and data.get("state", "0") == "1":
                #log.info("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
        elif self.mute_ads and event_type == "onAdStateChange":
            data = args[0]
            if data["adState"] == '0':  # Ad is not playing
                #log.info("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
            else:  # Seen multiple other adStates, assuming they are all ads
                log.info("Ad has started, muting", self.device_name)
                create_task(self.mute(True, override=True))
        # Manages volume, useful since YouTube wants to know the volume when unmuting (even if they already have it)
        elif event_type == "onVolumeChanged":
            self.volume_state = args[0]
            pass
        # Gets segments for the next video before it starts playing
        elif event_type == "autoplayUpNext":
            if len(args) > 0 and (vid_id := args[0]["videoId"]):  # if video id is not empty
                log.info(f"Getting skippable segments for next video: {vid_id}",
                         self.device_name)
                create_task(self.api_helper.get_segments(vid_id))

        # #Used to know if an ad is skippable or not
        elif event_type == "adPlaying":
            data = args[0]
            # Gets segments for the next video (after the ad) before it starts playing
            if vid_id := data["contentVideoId"]:
                log.info(f"Getting skippable segments for next video: {vid_id}",
                         self.device_name)
                create_task(self.api_helper.get_segments(vid_id))

            if data["isSkippable"] == "true":  # YouTube uses strings for booleans
                if self.skip_ads:
                    create_task(self.skip_ad())
                    create_task(self.mute(False, override=True))
                elif self.mute_ads:
                    create_task(self.mute(True, override=True))
        elif event_type == "onAutoplayModeChanged":
            data = args[0]
            create_task(self.set_auto_play_mode(data["autoplayMode"] == "ENABLED"))
        else:
            super()._process_event(event_id, event_type, args)

    # Set the volume to a specific value (0-100)
    async def set_volume(self, volume: int) -> None:
        await super()._command("setVolume", {"volume": volume})

    # Mute or unmute the device (if the device already is in the desired state, nothing happens)
    # mute: True to mute, False to unmute
    # override: If True, the command is sent even if the device already is in the desired state
    # TODO: Only works if the device is subscribed to the lounge
    async def mute(self, mute: bool, override: bool = False) -> None:
        if mute:
            mute_str = "true"
        else:
            mute_str = "false"
        if override or not (self.volume_state.get("muted", "false") == mute_str):
            self.volume_state["muted"] = mute_str
            # YouTube wants the volume when unmuting, so we send it
            await super()._command("setVolume", {"volume": self.volume_state.get("volume", 100), "muted": mute_str})

    async def set_auto_play_mode(self, enabled: bool):
        await super()._command("setAutoplayMode", {"autoplayMode": "ENABLED" if enabled else "DISABLED"})