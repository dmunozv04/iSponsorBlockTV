import asyncio
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from iSponsorBlockTV.ytlounge import YtLoungeApi


class AdEndUnmuteTests(unittest.IsolatedAsyncioTestCase):
    async def test_ad_end_does_not_unmute_when_mute_ads_is_disabled(self):
        config = SimpleNamespace(join_name="test", mute_ads=False, skip_ads=False, auto_play=True)
        lounge = YtLoungeApi(config=config, logger=logging.getLogger(__name__))
        lounge._command = AsyncMock()

        await lounge._process_event(
            "onAdStateChange", [{"adState": "0", "currentTime": "12", "isSkipEnabled": "false"}]
        )
        await asyncio.sleep(0)  # Allow any scheduled mute command to run.

        lounge._command.assert_not_awaited()

    async def test_ad_end_still_unmutes_when_mute_ads_is_enabled(self):
        config = SimpleNamespace(join_name="test", mute_ads=True, skip_ads=False, auto_play=True)
        lounge = YtLoungeApi(config=config, logger=logging.getLogger(__name__))
        lounge._command = AsyncMock()

        await lounge._process_event(
            "onAdStateChange", [{"adState": "0", "currentTime": "12", "isSkipEnabled": "false"}]
        )
        await asyncio.sleep(0)

        lounge._command.assert_awaited_once_with("setVolume", {"volume": 100, "muted": "false"})


if __name__ == "__main__":
    unittest.main()
