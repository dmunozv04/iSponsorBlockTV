import asyncio
import json
import aiohttp
import pyytlounge
from .constants import youtube_client_blacklist

# Temporary imports
from pyytlounge.api import api_base
from pyytlounge.wrapper import NotLinkedException, desync

create_task = asyncio.create_task


class YtLoungeApi(pyytlounge.YtLoungeApi):
    def __init__(self, screen_id, config=None, api_helper=None):
        super().__init__("iSponsorBlockTV")
        self.auth.screen_id = screen_id
        self.auth.lounge_id_token = None
        self.api_helper = api_helper
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
        except Exception:
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
        # print(f"YtLoungeApi.__process_event({event_id}, {event_type}, {args})")
        # (Re)start the watchdog
        try:
            self.subscribe_task_watchdog.cancel()
        except:
            pass
        finally:
            self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        # A bunch of events useful to detect ads playing, and the next video before it starts playing (that way we
        # can get the segments)
        if event_type == "onStateChange":
            data = args[0]
            # print(data)
            # Unmute when the video starts playing
            if self.mute_ads and data["state"] == "1":
                create_task(self.mute(False, override=True))
        elif event_type == "nowPlaying":
            data = args[0]
            self.state = pyytlounge.PlaybackState(self._logger, data)
            self._update_state()
            # Unmute when the video starts playing
            if self.mute_ads and data.get("state", "0") == "1":
                # print("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
        elif self.mute_ads and event_type == "onAdStateChange":
            data = args[0]
            if data["adState"] == '0':  # Ad is not playing
                # print("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
            else:  # Seen multiple other adStates, assuming they are all ads
                print("Ad has started, muting")
                create_task(self.mute(True, override=True))
        # Manages volume, useful since YouTube wants to know the volume when unmuting (even if they already have it)
        elif event_type == "onVolumeChanged":
            self.volume_state = args[0]
            pass
        # Gets segments for the next video before it starts playing
        # Comment "fix" since it doesn't seem to work
        # elif event_type == "autoplayUpNext":
        #     if len(args) > 0 and (vid_id := args[0]["videoId"]):  # if video id is not empty
        #         print(f"Getting segments for next video: {vid_id}")
        #         create_task(self.api_helper.get_segments(vid_id))

        # #Used to know if an ad is skippable or not
        elif event_type == "adPlaying":
            data = args[0]
            # Gets segments for the next video (after the ad) before it starts playing
            if vid_id := data["contentVideoId"]:
                print(f"Getting segments for next video: {vid_id}")
                create_task(self.api_helper.get_segments(vid_id))

            if data["isSkippable"] == "true":  # YouTube uses strings for booleans
                if self.skip_ads:
                    create_task(self.skip_ad())
                    create_task(self.mute(False, override=True))
                elif self.mute_ads:
                    create_task(self.mute(True, override=True))

        elif event_type == "loungeStatus":
            data = args[0]
            devices = json.loads(data["devices"])
            for device in devices:
                if device["type"] == "LOUNGE_SCREEN":
                    device_info = json.loads(device.get("deviceInfo", ""))
                    if device_info.get("clientName", "") in youtube_client_blacklist:
                        self._sid = None
                        self._gsession = None  # Force disconnect
        # elif event_type == "onAutoplayModeChanged":
        #     data = args[0]
        #     create_task(self.set_auto_play_mode(data["autoplayMode"] == "ENABLED"))
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

    # Here just temporarily, will be removed once the PR is merged on YTlounge
    async def connect(self) -> bool:
        """Attempt to connect using the previously set tokens"""
        if not self.linked():
            raise NotLinkedException("Not linked")

        connect_body = {
            "app": "web",
            "mdx-version": "3",
            "name": self.device_name,
            "id": self.auth.screen_id,
            "device": "REMOTE_CONTROL",
            "capabilities": "que,dsdtr,atp",
            "method": "setPlaylist",
            "magnaKey": "cloudPairedDevice",
            "ui": "false",
            "deviceContext": "user_agent=dunno&window_width_points=&window_height_points=&os_name=android&ms=",
            "theme": "cl",
            "loungeIdToken": self.auth.lounge_id_token,
        }
        connect_url = (
            f"{api_base}/bc/bind?RID=1&VER=8&CVER=1&auth_failure_option=send_error"
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(url=connect_url, data=connect_body) as resp:
                try:
                    text = await resp.text()
                    if resp.status == 401:
                        self.auth.lounge_id_token = None
                        return False

                    if resp.status != 200:
                        self._logger.warning(
                            "Unknown reply to connect %i %s", resp.status, resp.reason
                        )
                        return False
                    lines = text.splitlines()
                    async for events in self._parse_event_chunks(desync(lines)):
                        self._process_events(events)
                    self._command_offset = 1
                    return self.connected()
                except Exception as ex:
                    self._logger.exception(ex, resp.status, resp.reason)
                    return False
