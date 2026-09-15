import asyncio
import json
import sys
import time
from typing import Any
from uuid import uuid4

import pyytlounge
from aiohttp import ClientSession
from pyytlounge.event_listener import EventListener
from pyytlounge.events import NowPlayingEvent, PlaybackStateEvent
from pyytlounge.models import State
from pyytlounge.wrapper import Dict, NotLinkedException, api_base, as_aiter

from .constants import youtube_client_blacklist

create_task = asyncio.create_task


class PlaybackState:
    def __init__(self):
        self.currentTime = 0.0
        self.duration = 0.0
        self.videoId = ""
        self.state = State.Stopped


class _CallbackListener(EventListener):
    def __init__(self, lounge: "YtLoungeApi"):
        super().__init__()
        self._lounge = lounge

    async def playback_state_changed(self, event: PlaybackStateEvent) -> None:
        await self._lounge._handle_playback_state_event(event)

    async def now_playing_changed(self, event: NowPlayingEvent) -> None:
        await self._lounge._handle_now_playing_event(event)


class YtLoungeApi(pyytlounge.YtLoungeApi):
    # An ad replaces the content player, so its duration is normally much
    # shorter than the duration previously reported for the content video.
    _AD_DURATION_RATIO = 0.5

    def __init__(
        self,
        screen_id=None,
        config=None,
        api_helper=None,
        logger=None,
    ):
        self._callback_listener = _CallbackListener(self)
        super().__init__(
            config.join_name if config else "iSponsorBlockTV",
            event_listener=self._callback_listener,
            logger=logger,
        )
        self.auth.screen_id = screen_id
        self.auth.lounge_id_token = None
        self.api_helper = api_helper
        self.volume_state = {}
        self.playback_speed = 1.0
        self.subscribe_task = None
        self.subscribe_task_watchdog = None
        self.callback = None
        self._state_callback = None
        self._playback_state = PlaybackState()
        self.logger = logger
        self.shorts_disconnected = False
        self.auto_play = True
        self.watchdog_running = False
        self.last_event_time = 0
        self._ad_active = False
        self._ad_dance_task = None
        self._last_video_id = ""
        self._last_content_duration = 0.0
        self._last_playback_position = 0.0
        self._last_content_playback_speed = 1.0
        self._last_playback_info_time = time.monotonic()
        self._has_content_playback_info = False
        if config:
            self.mute_ads = config.mute_ads
            self.skip_ads = config.skip_ads
            self.auto_play = config.auto_play
        self._command_mutex = asyncio.Lock()

    def _looks_like_ad_duration(self, duration: Any) -> bool:
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            return False
        return (
            duration > 0
            and self._last_content_duration > 0
            and duration < self._last_content_duration * self._AD_DURATION_RATIO
        )

    async def _handle_playback_state_event(self, event: PlaybackStateEvent) -> None:
        self._playback_state.currentTime = event.current_time
        self._playback_state.duration = event.duration
        self._playback_state.state = (
            State.Advertisement if self._ad_active else event.state
        )
        if not self._ad_active and event.state is State.Playing:
            self._last_playback_position = event.current_time
            self._last_content_playback_speed = self.playback_speed
            self._last_playback_info_time = time.monotonic()
            self._has_content_playback_info = True
            if event.duration > 0:
                self._last_content_duration = event.duration
        if self._state_callback:
            await self._state_callback(self._playback_state)

    async def _handle_now_playing_event(self, event: NowPlayingEvent) -> None:
        if event.current_time is not None:
            self._playback_state.currentTime = event.current_time
        if event.duration is not None:
            self._playback_state.duration = event.duration
        if event.video_id and event.video_id != self._last_video_id:
            self._last_video_id = event.video_id
            self._last_content_duration = 0.0
            self._last_playback_position = 0.0
            self._has_content_playback_info = False
        self._playback_state.videoId = self._last_video_id
        self._playback_state.state = (
            State.Advertisement if self._ad_active else event.state
        )
        if (
            not self._ad_active
            and event.current_time is not None
            and event.state is State.Playing
        ):
            self._last_playback_position = event.current_time
            self._last_content_playback_speed = self.playback_speed
            self._last_playback_info_time = time.monotonic()
            self._has_content_playback_info = True
            if event.duration is not None and event.duration > 0:
                self._last_content_duration = event.duration
        if self._state_callback:
            await self._state_callback(self._playback_state)

    def _position_before_ad(self) -> float:
        """Estimate the content position when the ad started."""
        if not self._has_content_playback_info:
            return 0.0
        elapsed = time.monotonic() - self._last_playback_info_time
        return max(
            0.0,
            self._last_playback_position
            + elapsed * self._last_content_playback_speed,
        )

    async def _replay_video_after_ad(
        self, video_id: str, position: float, wait_time: float
    ) -> None:
        try:
            await asyncio.sleep(wait_time)
            self.logger.info(
                "Replaying non-skippable ad content %s from %.2f seconds",
                video_id,
                position,
            )
            await self.play_video(video_id, position)
        except asyncio.CancelledError:
            pass

    # Ensures that we still are subscribed to the lounge
    async def _watchdog(self):
        """
        Continuous watchdog that monitors for connection health.
        If no events are received within the expected timeframe,
        it cancels the current subscription.
        """
        self.watchdog_running = True
        self.last_event_time = asyncio.get_running_loop().time()

        try:
            while self.watchdog_running:
                await asyncio.sleep(10)
                current_time = asyncio.get_running_loop().time()
                time_since_last_event = current_time - self.last_event_time

                # YouTube sends a message at least every 30 seconds
                if time_since_last_event > 60:
                    self.logger.debug(
                        f"Watchdog triggered: No events for {time_since_last_event:.1f} seconds"
                    )

                    # Cancel current subscription
                    if self.subscribe_task and not self.subscribe_task.done():
                        self.subscribe_task.cancel()
                        await asyncio.sleep(1)  # Give it time to cancel
        except asyncio.CancelledError:
            self.logger.debug("Watchdog task cancelled")
            self.watchdog_running = False
        except BaseException as e:
            self.logger.error(f"Watchdog error: {e}")
            self.watchdog_running = False

    # Subscribe to the lounge and start the watchdog
    async def subscribe_monitored(self, callback):
        self.callback = callback
        self._state_callback = callback

        # Stop existing watchdog if running
        if self.subscribe_task_watchdog and not self.subscribe_task_watchdog.done():
            self.watchdog_running = False
            self.subscribe_task_watchdog.cancel()
            try:
                await self.subscribe_task_watchdog
            except (asyncio.CancelledError, Exception):
                pass

        # Start new subscription
        if self.subscribe_task and not self.subscribe_task.done():
            self.subscribe_task.cancel()
            try:
                await self.subscribe_task
            except (asyncio.CancelledError, Exception):
                pass

        self.subscribe_task = asyncio.create_task(super().subscribe())
        self.subscribe_task_watchdog = asyncio.create_task(self._watchdog())
        return self.subscribe_task

    # Process a lounge subscription event
    # skipcq: PY-R1000
    async def _process_event(self, event_type: str, args: list[Any]):
        self.logger.debug(f"process_event({event_type}, {args})")
        # Update last event time for the watchdog
        self.last_event_time = asyncio.get_running_loop().time()

        # A bunch of events useful to detect ads playing,
        # and the next video before it starts playing
        # (that way we can get the segments)
        if event_type == "onStateChange":
            data = args[0]
            if (
                data.get("state") == str(State.Advertisement.value)
                or self._looks_like_ad_duration(data.get("duration"))
            ):
                self._ad_active = True
            # print(data)
            # Unmute when the video starts playing
            if self.mute_ads and not self._ad_active and data["state"] == "1":
                create_task(self.mute(False, override=True))
        elif event_type == "nowPlaying":
            data = args[0]
            if (
                data.get("adState") == "1"
                or data.get("adVideoId")
                or self._looks_like_ad_duration(data.get("duration"))
            ):
                self._ad_active = True
            elif data.get("videoId") and data.get("duration") not in (None, "0", 0):
                self._ad_active = False
            # Unmute when the video starts playing
            if self.mute_ads and not self._ad_active and data.get("state", "0") == "1":
                self.logger.info("Ad has ended, unmuting")
                create_task(self.mute(False, override=True))
        elif event_type == "onAdStateChange":
            data = args[0]
            if data["adState"] == "0":  # Ad is not playing
                self._ad_active = False
                if self._ad_dance_task and not self._ad_dance_task.done():
                    self._ad_dance_task.cancel()
                if data["currentTime"] != "0":
                    self.logger.info("Ad has ended, unmuting")
                    create_task(self.mute(False, override=True))
            elif (
                self.skip_ads and data["isSkipEnabled"] == "true"
            ):  # YouTube uses strings for booleans
                self.logger.info("Ad can be skipped, skipping")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif self.mute_ads:  # Seen multiple other adStates, assuming they are all ads
                self.logger.info("Ad has started, muting")
                create_task(self.mute(True, override=True))
        # Manages volume, useful since YouTube wants to know the volume
        # when unmuting (even if they already have it)
        elif event_type == "onVolumeChanged":
            self.volume_state = args[0]
        # Gets segments for the next video before it starts playing
        elif event_type == "autoplayUpNext":
            if len(args) > 0 and (vid_id := args[0]["videoId"]):  # if video id is not empty
                self.logger.info(f"Getting segments for next video: {vid_id}")
                create_task(self.api_helper.get_segments(vid_id))

        # #Used to know if an ad is skippable or not
        elif event_type == "adPlaying":
            data = args[0]
            self._ad_active = True
            # Gets segments for the next video (after the ad) before it starts playing
            if self._last_video_id:
                self.logger.info(f"Getting segments for next video: {self._last_video_id}")
                create_task(self.api_helper.get_segments(self._last_video_id))

            if (
                self.skip_ads and data["isSkipEnabled"] == "true"
            ):  # YouTube uses strings for booleans
                self.logger.info("Ad can be skipped, skipping")
                create_task(self.skip_ad())
                create_task(self.mute(False, override=True))
            elif self.skip_ads:  #and data["isSkippable"] == "false": # re-enable after testing
                if self._ad_dance_task and not self._ad_dance_task.done():
                    self._ad_dance_task.cancel()
                if self._last_video_id:
                    self.logger.info("Ad cannot be skipped, scheduling ad dance")
                    self._ad_dance_task = create_task(
                        self._replay_video_after_ad(
                            self._last_video_id,
                            self._position_before_ad(),
                            max(0.0, 5.0 - float(data["currentTime"])),
                        )
                    )
                if self.mute_ads:
                    create_task(self.mute(True, override=True))
            elif self.mute_ads:  # Seen multiple other adStates, assuming they are all ads
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
                        return

        elif event_type == "onSubtitlesTrackChanged":
            if self.shorts_disconnected:
                data = args[0]
                video_id_saved = data.get("videoId", None)
                self.shorts_disconnected = False
                create_task(self.play_video(video_id_saved))
        elif event_type == "loungeScreenDisconnected":
            if args:  # Sometimes it's empty
                data = args[0]
                if data["reason"] == "disconnectedByUserScreenInitiated":  # Short playing?
                    self.shorts_disconnected = True
        elif event_type == "onAutoplayModeChanged":
            create_task(self.set_auto_play_mode(self.auto_play))

        elif event_type == "onPlaybackSpeedChanged":
            data = args[0]
            self.playback_speed = float(data.get("playbackSpeed", "1"))

        await super()._process_event(event_type, args)

    # Set the volume to a specific value (0-100)
    async def set_volume(self, volume: int) -> None:
        await self._command("setVolume", {"volume": volume})

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
            await self._command(
                "setVolume",
                {"volume": self.volume_state.get("volume", 100), "muted": mute_str},
            )

    async def play_video(self, video_id: str, current_time: float | None = None) -> bool:
        parameters = {"videoId": video_id}
        if current_time is not None:
            parameters["currentTime"] = current_time
            print(f"XXXPlaying video {video_id} from {current_time} seconds")
        return await self._command("setPlaylist", parameters)

    async def get_now_playing(self):
        return await self._command("getNowPlaying")

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

    def _common_connection_parameters(self) -> Dict[str, Any]:
        return {
            "name": self.device_name,
            "loungeIdToken": self.auth.lounge_id_token,
            "SID": self._sid,
            "AID": self._last_event_id,
            "gsessionid": self._gsession,
            "device": "REMOTE_CONTROL",
            "app": "ytios-phone-20.15.1",
            "VER": "8",
            "v": "2",
        }

    async def connect(self) -> bool:
        """Attempt to connect using the previously set tokens"""
        if not self.linked():
            raise NotLinkedException("Not linked")

        connect_body = {
            "id": self.auth.screen_id,
            "mdx-version": "3",
            "TYPE": "xmlhttp",
            "theme": "cl",
            "sessionSource": "MDX_SESSION_SOURCE_UNKNOWN",
            "connectParams": '{"setStatesParams": "{"playbackSpeed":0}"}',
            "RID": "1",
            "CVER": "1",
            "capabilities": "que,dsdtr,atp,vsp",
            "ui": "false",
            "app": "ytios-phone-20.15.1",
            "pairing_type": "manual",
            "VER": "8",
            "loungeIdToken": self.auth.lounge_id_token,
            "device": "REMOTE_CONTROL",
            "name": self.device_name,
        }
        connect_url = f"{api_base}/bc/bind"
        async with self.session.post(url=connect_url, data=connect_body) as resp:
            try:
                text = await resp.text()
                if resp.status == 401:
                    if "Connection denied" in text:
                        self._logger.warning(
                            "Connection denied, attempting to circumvent the issue"
                        )
                        await self.connect_as_screen()
                    # self._lounge_token_expired()
                    return False

                if resp.status != 200:
                    self._logger.warning("Unknown reply to connect %i %s", resp.status, resp.reason)
                    return False
                lines = text.splitlines()
                async for events in self._parse_event_chunks(as_aiter(lines)):
                    await self._process_events(events)
                self._command_offset = 1
                return self.connected()
            except:
                self._logger.exception(
                    "Handle connect failed, status %s reason %s",
                    resp.status,
                    resp.reason,
                )
                raise

    async def connect_as_screen(self) -> bool:
        """Attempt to connect using the previously set tokens"""
        if not self.linked():
            raise NotLinkedException("Not linked")

        connect_body = {
            "id": str(uuid4()),
            "mdx-version": "3",
            "TYPE": "xmlhttp",
            "theme": "cl",
            "sessionSource": "MDX_SESSION_SOURCE_UNKNOWN",
            "connectParams": '{"setStatesParams": "{"playbackSpeed":0}"}',
            "sessionNonce": str(uuid4()),
            "RID": "1",
            "CVER": "1",
            "capabilities": "que,dsdtr,atp,vsp",
            "ui": "false",
            "app": "ytios-phone-20.15.1",
            "pairing_type": "manual",
            "VER": "8",
            "loungeIdToken": self.auth.lounge_id_token,
            "device": "LOUNGE_SCREEN",
            "name": self.device_name,
        }
        connect_url = f"{api_base}/bc/bind"
        async with self.session.post(url=connect_url, data=connect_body) as resp:
            try:
                await resp.text()
                self.logger.error(
                    "Connected as screen: please force close the app on the device for iSponsorBlockTV to work properly"
                )
                self.logger.warn("Exiting in 5 seconds")
                await asyncio.sleep(5)
                sys.exit(0)
            except:
                self._logger.exception(
                    "Handle connect failed, status %s reason %s",
                    resp.status,
                    resp.reason,
                )
                raise
