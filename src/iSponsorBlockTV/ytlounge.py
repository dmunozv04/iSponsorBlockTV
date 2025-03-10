import asyncio
import json
from typing import Any, List

import pyytlounge
from aiohttp import ClientSession

from .constants import youtube_client_blacklist

create_task = asyncio.create_task


class YtLoungeApi(pyytlounge.YtLoungeApi):
    def __init__(
        self,
        screen_id=None,
        config=None,
        api_helper=None,
        logger=None,
    ):
        super().__init__(
            config.join_name if config else "iSponsorBlockTV", logger=logger
        )
        self.auth.screen_id = screen_id
        self.auth.lounge_id_token = None
        self.api_helper = api_helper
        self.volume_state = {}
        self.playback_speed = 1.0
        self.subscribe_task = None
        self.subscribe_task_watchdog = None
        self.callback = None
        self.logger = logger
        self.shorts_disconnected = False
        self.auto_play = True
        if config:
            self.mute_ads = config.mute_ads
            self.skip_ads = config.skip_ads
            self.auto_play = config.auto_play
        self._command_mutex = asyncio.Lock()

    # Ensures that we still are subscribed to the lounge
    async def _watchdog(self):
        await asyncio.sleep(
            35
        )  # YouTube sends at least a message every 30 seconds (no-op or any other)
        try:
            self.subscribe_task.cancel()
        except BaseException:
            pass

    # Subscribe to the lounge and start the watchdog
    async def subscribe_monitored(self, callback):
        self.callback = callback
        try:
            self.subscribe_task_watchdog.cancel()
        except BaseException:
            pass  # No watchdog task
        self.subscribe_task = asyncio.create_task(super().subscribe(callback))
        self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        return self.subscribe_task

    # Process a lounge subscription event
    # skipcq: PY-R1000
    def _process_event(self, event_type: str, args: List[Any]):
        self.logger.debug(f"process_event({event_type}, {args})")
        # (Re)start the watchdog
        try:
            self.subscribe_task_watchdog.cancel()
        except BaseException:
            pass
        finally:
            self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        # A bunch of events useful to detect ads playing,
        # and the next video before it starts playing
        # (that way we can get the segments)
        if event_type == "onStateChange":
            data = args[0]
            # print(data)
            # Unmute when the video starts playing
            if self.mute_ads and data["state"] == "1":
                create_task(self.mute(False, override=True))
        elif event_type == "nowPlaying":
            data = args[0]
            # Unmute when the video starts playing
            if self.mute_ads and data.get("state", "0") == "1":
                self.logger.info("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
        elif event_type == "onAdStateChange":
            data = args[0]
            if data["adState"] == "0":  # Ad is not playing
                self.logger.info("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
            elif (
                self.skip_ads and data["isSkipEnabled"] == "true"
            ):  # YouTube uses strings for booleans
                self.logger.info("Ad can be skipped, skipping")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif (
                self.mute_ads
            ):  # Seen multiple other adStates, assuming they are all ads
                self.logger.info("Ad has started, muting")
                create_task(self.mute(True, override=True))
        # Manages volume, useful since YouTube wants to know the volume
        # when unmuting (even if they already have it)
        elif event_type == "onVolumeChanged":
            self.volume_state = args[0]
        # Gets segments for the next video before it starts playing
        elif event_type == "autoplayUpNext":
            if len(args) > 0 and (
                vid_id := args[0]["videoId"]
            ):  # if video id is not empty
                self.logger.info(f"Getting segments for next video: {vid_id}")
                create_task(self.api_helper.get_segments(vid_id))

        # #Used to know if an ad is skippable or not
        elif event_type == "adPlaying":
            data = args[0]
            # Gets segments for the next video (after the ad) before it starts playing
            if vid_id := data["contentVideoId"]:
                self.logger.info(f"Getting segments for next video: {vid_id}")
                create_task(self.api_helper.get_segments(vid_id))
            elif (
                self.skip_ads and data["isSkipEnabled"] == "true"
            ):  # YouTube uses strings for booleans
                self.logger.info("Ad can be skipped, skipping")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif (
                self.mute_ads
            ):  # Seen multiple other adStates, assuming they are all ads
                self.logger.info("Ad has started, muting")
                create_task(self.mute(True, override=True))

        elif event_type == "loungeStatus":
            data = args[0]
            devices = json.loads(data["devices"])
            for device in devices:
                if device["type"] == "LOUNGE_SCREEN":
                    device_info = json.loads(device.get("deviceInfo", "{}"))
                    if device_info.get("clientName", "") in youtube_client_blacklist:
                        self._sid = None
                        self._gsession = None  # Force disconnect

        elif event_type == "onSubtitlesTrackChanged":
            if self.shorts_disconnected:
                data = args[0]
                video_id_saved = data.get("videoId", None)
                self.shorts_disconnected = False
                create_task(self.play_video(video_id_saved))
        elif event_type == "loungeScreenDisconnected":
            if args:  # Sometimes it's empty
                data = args[0]
                if (
                    data["reason"] == "disconnectedByUserScreenInitiated"
                ):  # Short playing?
                    self.shorts_disconnected = True
        elif event_type == "onAutoplayModeChanged":
            create_task(self.set_auto_play_mode(self.auto_play))

        elif event_type == "onPlaybackSpeedChanged":
            data = args[0]
            self.playback_speed = float(data.get("playbackSpeed", "1"))
            create_task(self.get_now_playing())

        super()._process_event(event_type, args)

    # Set the volume to a specific value (0-100)
    async def set_volume(self, volume: int) -> None:
        await super()._command("setVolume", {"volume": volume})

    async def mute(self, mute: bool, override: bool = False) -> None:
        """
        Mute or unmute the device (if the device already
        is in the desired state, nothing happens)

        :param bool mute: True to mute, False to unmute
        :param bool override: If True, the command is sent even if the
        device already is in the desired state

        TODO: Only works if the device is subscribed to the lounge
        """
        if mute:
            mute_str = "true"
        else:
            mute_str = "false"
        if override or not self.volume_state.get("muted", "false") == mute_str:
            self.volume_state["muted"] = mute_str
            # YouTube wants the volume when unmuting, so we send it
            await super()._command(
                "setVolume",
                {"volume": self.volume_state.get("volume", 100), "muted": mute_str},
            )

    async def set_auto_play_mode(self, enabled: bool):
        await super()._command(
            "setAutoplayMode", {"autoplayMode": "ENABLED" if enabled else "DISABLED"}
        )

    async def play_video(self, video_id: str) -> bool:
        return await self._command("setPlaylist", {"videoId": video_id})

    async def get_now_playing(self):
        return await super()._command("getNowPlaying")

    # Test to wrap the command function in a mutex to avoid race conditions with
    # the _command_offset (TODO: move to upstream if it works)
    async def _command(self, command: str, command_parameters: dict = None) -> bool:
        async with self._command_mutex:
            return await super()._command(command, command_parameters)

    async def change_web_session(self, web_session: ClientSession):
        if self.session is not None:
            await self.session.close()
        if self.conn is not None:
            await self.conn.close()
        self.session = web_session
