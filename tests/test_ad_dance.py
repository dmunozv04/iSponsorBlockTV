"""Tests for the ad dance in YtLoungeApi: where the content resumes after an ad.

Lounge events are fed through _process_event like the subscription does, so
pyytlounge parses them and the real handlers run. Network commands are stubbed.
Run from the src directory: python -m unittest discover -s ../tests
"""

import asyncio
import logging
import types
import unittest

from iSponsorBlockTV.ytlounge import YtLoungeApi

VIDEO = "vid123"
CONTENT_DURATION = "3600"


def now_playing(current_time, state="1", duration=CONTENT_DURATION):
    return {
        "videoId": VIDEO,
        "currentTime": str(current_time),
        "duration": duration,
        "state": state,
        "cpn": "c",
        "loadedTime": "0",
        "seekableStartTime": "0",
        "seekableEndTime": duration,
        "listId": "",
    }


def state_change(current_time, state, duration=CONTENT_DURATION):
    return {
        "currentTime": str(current_time),
        "duration": duration,
        "state": state,
        "cpn": "c",
        "loadedTime": "0",
        "seekableStartTime": "0",
        "seekableEndTime": duration,
    }


def ad_playing(ad_current_time="0", skippable=False):
    flag = "true" if skippable else "false"
    return {
        "adVideoId": "ad1",
        "adVideoUri": "",
        "adTitle": "Ad",
        "isBumper": "false",
        "isSkippable": flag,
        "isSkipEnabled": flag,
        "clickThroughUrl": "",
        "adSystem": "",
        "adNextParams": "",
        "remoteSlotsData": "",
        "adState": "1",
        "contentVideoId": VIDEO,
        "duration": "15",
        "currentTime": str(ad_current_time),
    }


class LoungeTest(unittest.IsolatedAsyncioTestCase):
    stub_replay = True

    async def asyncSetUp(self):
        cfg = types.SimpleNamespace(
            join_name="test", mute_ads=True, skip_ads=True, auto_play=True
        )
        helper = types.SimpleNamespace(get_segments=self._noop)
        self.api = YtLoungeApi(
            screen_id="s",
            config=cfg,
            api_helper=helper,
            logger=logging.getLogger("test"),
        )
        self.commands = []
        self.replays = []

        async def fake_commands(commands):
            self.commands.extend(commands)
            return True

        async def fake_command(command, params=None):
            return await fake_commands([(command, params)])

        async def fake_replay(video_id, position, wait_time):
            self.replays.append((video_id, position, wait_time))

        self.api._commands = fake_commands
        self.api._command = fake_command
        if self.stub_replay:
            self.api._replay_video_after_ad = fake_replay

    @staticmethod
    async def _noop(*args, **kwargs):
        return None

    async def send(self, event_type, data):
        await self.api._process_event(event_type, [data])
        await asyncio.sleep(0)  # let created tasks run

    async def play_content(self, at=100):
        await self.send("nowPlaying", now_playing(at))
        await self.send("onStateChange", state_change(at, "1"))

    def command_names(self):
        return [name for name, _ in self.commands]

    def replay_position(self):
        self.assertEqual(
            len(self.replays), 1, f"expected one ad dance, got {self.replays}"
        )
        video, position, _ = self.replays[0]
        self.assertEqual(video, VIDEO)
        return position


class NormalPlayback(LoungeTest):
    async def test_ad_resumes_at_content_position(self):
        await self.play_content(at=100)
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 100, delta=1.0)

    async def test_no_commands_without_ads(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(101, "1"))
        self.assertEqual(self.replays, [])
        self.assertEqual(self.commands, [])


class FiveSeconds(LoungeTest):
    async def test_ad_dance_waits_until_five_seconds_into_the_ad(self):
        await self.play_content(at=100)
        await self.send("adPlaying", ad_playing(ad_current_time="1.5"))
        _, _, wait = self.replays[0]
        self.assertAlmostEqual(wait, 3.5, delta=0.01)

    async def test_skippable_ad_is_skipped_without_ad_dance(self):
        await self.play_content(at=100)
        await self.send("adPlaying", ad_playing(skippable=True))
        self.assertEqual(self.replays, [])
        self.assertIn("skipAd", self.command_names())


class AdDanceCommands(LoungeTest):
    stub_replay = False

    async def test_pauses_ad_then_replays_content_at_position(self):
        await self.play_content(at=100)
        await self.send("adPlaying", ad_playing(ad_current_time="5"))  # no wait
        for _ in range(5):
            await asyncio.sleep(0)
        names = self.command_names()
        self.assertEqual(names[:2], ["pause", "setPlaylist"], self.commands)
        params = self.commands[1][1]
        self.assertEqual(params["videoId"], VIDEO)
        self.assertAlmostEqual(float(params["currentTime"]), 100, delta=1.0)


class SeekForward(LoungeTest):
    async def test_seek_without_ad_sends_nothing(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(1500, "3"))
        await self.send("onStateChange", state_change(1500, "1"))
        self.assertEqual(self.replays, [])
        self.assertEqual(self.commands, [])

    async def test_ad_right_after_seek_resumes_at_seek_target(self):
        """Seek 100 -> 1500, the ad starts before the content plays at 1500."""
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(1500, "3"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 1500, delta=1.0)

    async def test_ad_right_after_seek_reported_as_buffering(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(1500, "0"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 1500, delta=1.0)

    async def test_seek_then_ad_state_signal_then_ad_playing(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(1500, "3"))
        await self.send("onStateChange", state_change(0, "1081", duration="15"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 1500, delta=1.0)

    async def test_seek_then_watch_then_ad(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(1500, "3"))
        await self.send("onStateChange", state_change(1500, "1"))
        await self.send("onStateChange", state_change(1560, "1"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 1560, delta=1.0)


class ResumeNotTooFar(LoungeTest):
    async def test_position_frozen_at_first_ad_signal(self):
        """adPlaying arrives seconds after the ad started; don't count that time."""
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(0, "1081", duration="15"))
        self.api._last_playback_info_time -= 3  # adPlaying comes 3 s later
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 100, delta=1.0)

    async def test_resumed_too_far_is_corrected(self):
        await self.play_content(at=100)
        self.api._pending_seek = (VIDEO, 100.0)  # set by the ad dance
        await self.send("onStateChange", state_change(105, "1"))
        self.assertIn(("seekTo", {"newTime": 100.0}), self.commands)

    async def test_new_ad_after_previous_ad_ended_uses_fresh_position(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(0, "1081", duration="15"))
        await self.send(
            "onAdStateChange",
            {"adState": "0", "currentTime": "0", "isSkipEnabled": "false"},
        )
        await self.play_content(at=700)
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 700, delta=1.0)


class AdEventsDontMoveThePosition(LoungeTest):
    async def test_loading_ad_with_its_own_duration_is_ignored(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(0, "3", duration="15"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 100, delta=1.0)

    async def test_loading_event_without_duration_is_ignored(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(0, "3", duration="0"))
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 100, delta=1.0)

    async def test_stale_start_position_during_pending_seek_is_ignored(self):
        await self.play_content(at=1500)
        self.api._pending_seek = (VIDEO, 1500.0)
        before = self.api._last_playback_position
        await self.send("onStateChange", state_change(100, "3"))
        self.assertEqual(self.api._last_playback_position, before)


class Pause(LoungeTest):
    async def test_position_does_not_advance_while_paused(self):
        await self.play_content(at=100)
        await self.send("onStateChange", state_change(200, "2"))
        self.api._last_playback_info_time -= 30  # 30 s later
        await self.send("adPlaying", ad_playing())
        self.assertAlmostEqual(self.replay_position(), 200, delta=1.0)


def ad_state(state, skippable=True):
    flag = "true" if skippable else "false"
    return {
        "adState": state,
        "currentTime": "0",
        "isSkipEnabled": flag,
        "isSkippable": flag,
    }


class ResumeAfterSkippedAd(LoungeTest):
    """YouTube resumes the content itself after a skipped ad, sometimes too early."""

    async def skip_ad_at(self, at=100, end_state="1082"):
        await self.play_content(at=at)
        await self.send("adPlaying", ad_playing(skippable=True))
        await self.send("onAdStateChange", ad_state(end_state))

    def seeks(self):
        return [params for name, params in self.commands if name == "seekTo"]

    async def test_resumed_early_after_skip_is_corrected(self):
        await self.skip_ad_at(100)
        await self.send("onStateChange", state_change(95, "1"))
        self.assertEqual(len(self.seeks()), 1, self.commands)
        self.assertAlmostEqual(self.seeks()[0]["newTime"], 100, delta=1.0)

    async def test_resumed_early_after_ad_ended_is_corrected(self):
        await self.skip_ad_at(100, end_state="0")
        await self.send("onStateChange", state_change(95, "1"))
        self.assertEqual(len(self.seeks()), 1, self.commands)

    async def test_resumed_at_the_right_position_is_left_alone(self):
        await self.skip_ad_at(100)
        await self.send("onStateChange", state_change(100.3, "1"))
        self.assertEqual(self.seeks(), [])

    async def test_resumed_later_is_left_alone(self):
        await self.skip_ad_at(100)
        await self.send("onStateChange", state_change(104, "1"))
        self.assertEqual(self.seeks(), [])

    async def test_big_jump_back_is_left_alone(self):
        await self.skip_ad_at(100)
        await self.send("onStateChange", state_change(40, "1"))
        self.assertEqual(self.seeks(), [])

    async def test_only_the_first_playing_event_is_checked(self):
        await self.skip_ad_at(100)
        await self.send("onStateChange", state_change(100, "1"))
        await self.send("onStateChange", state_change(95, "1"))  # user seeks back
        self.assertEqual(self.seeks(), [])

    async def test_check_expires(self):
        await self.skip_ad_at(100)
        video, position, since = self.api._resume_check
        self.api._resume_check = (video, position, since - 20)
        await self.send("onStateChange", state_change(95, "1"))
        self.assertEqual(self.seeks(), [])


class ResumeAfterAdDance(LoungeTest):
    stub_replay = False

    async def test_ad_dance_is_not_checked_twice(self):
        await self.play_content(at=100)
        await self.send("adPlaying", ad_playing(ad_current_time="5"))  # no wait
        for _ in range(5):
            await asyncio.sleep(0)
        await self.send("nowPlaying", now_playing(100))
        self.assertIsNone(self.api._resume_check)
        self.assertNotIn("seekTo", self.command_names())


class AdRightAfterAdDance(LoungeTest):
    """Seen on a TV: the ad dance replays at 325.95, another ad starts at once and the
    position was estimated at 332.89 (the ad time counted as content time)."""

    stub_replay = False

    async def test_ad_time_after_replay_is_not_counted(self):
        await self.play_content(at=325.95)
        await self.send("adPlaying", ad_playing(ad_current_time="5"))  # no wait
        for _ in range(5):
            await asyncio.sleep(0)
        await self.send("nowPlaying", now_playing(325.95, state="3"))  # content loading
        self.api._last_playback_info_time -= 7  # the next ad comes 7 s later
        await self.send("onStateChange", state_change(0, "1081", duration="15"))
        self.assertAlmostEqual(self.api._ad_started_position, 325.95, delta=1.0)


if __name__ == "__main__":
    unittest.main()
