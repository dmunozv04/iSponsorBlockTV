import asyncio
from types import SimpleNamespace

import pytest

from iSponsorBlockTV.ytlounge import YtLoungeApi

AD_VOLUME = 4


class FakeLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture
def lounge():
    config = SimpleNamespace(
        join_name="test",
        mute_ads=True,
        ad_volume=AD_VOLUME,
        skip_ads=True,
        auto_play=True,
    )
    api = YtLoungeApi("screen", config, api_helper=None, logger=FakeLogger())
    api.sent = []

    async def fake_command(command, command_parameters=None):
        api.sent.append((command, command_parameters))
        return True

    api._command = fake_command
    return api


async def event(api, event_type, payload):
    await api._process_event(event_type, [payload])
    for _ in range(5):
        await asyncio.sleep(0)


async def ad_starts(api):
    await event(api, "onAdStateChange", {"adState": "1", "currentTime": "0", "isSkipEnabled": "false"})


async def ad_ends(api):
    await event(api, "onStateChange", {"state": "1", "currentTime": "10", "duration": "100"})


async def device_reports(api, volume):
    await event(api, "onVolumeChanged", {"volume": str(volume), "muted": "false"})


def volumes_sent(api):
    return [params["volume"] for command, params in api.sent if command == "setVolume"]


@pytest.mark.asyncio
async def test_ad_is_lowered_then_user_volume_restored(lounge):
    await device_reports(lounge, 100)
    await ad_starts(lounge)
    await ad_ends(lounge)
    assert volumes_sent(lounge) == [AD_VOLUME, "100"]


@pytest.mark.asyncio
async def test_late_echo_of_ad_volume_does_not_become_restore_point(lounge):
    # Sequence seen on 2026-09-27 23:17:12: two ads back to back, the device's
    # echo of the first lowering lands after the restore and before the second ad.
    await device_reports(lounge, 100)
    await ad_starts(lounge)
    await ad_ends(lounge)
    await device_reports(lounge, AD_VOLUME)
    await ad_starts(lounge)
    await ad_ends(lounge)
    assert volumes_sent(lounge)[-1] == "100"


@pytest.mark.asyncio
async def test_volume_changed_by_user_between_ads_is_restored(lounge):
    await device_reports(lounge, 100)
    await ad_starts(lounge)
    await ad_ends(lounge)
    await device_reports(lounge, 60)
    await ad_starts(lounge)
    await ad_ends(lounge)
    assert volumes_sent(lounge)[-1] == "60"


@pytest.mark.asyncio
async def test_repeated_ad_start_events_do_not_move_restore_point(lounge):
    await device_reports(lounge, 100)
    await ad_starts(lounge)
    await device_reports(lounge, AD_VOLUME)
    await ad_starts(lounge)
    await ad_ends(lounge)
    assert volumes_sent(lounge)[-1] == "100"


@pytest.mark.asyncio
async def test_unknown_volume_falls_back_to_muted_flag(lounge):
    await ad_starts(lounge)
    assert lounge.sent[-1] == ("setVolume", {"volume": 100, "muted": "true"})


@pytest.mark.asyncio
async def test_device_already_at_ad_volume_on_connect_is_not_a_restore_point(lounge):
    # Left at the ad volume by a crash mid-ad: restoring to it would stick forever.
    await device_reports(lounge, AD_VOLUME)
    await ad_starts(lounge)
    assert lounge.sent[-1][1].get("muted") == "true"


@pytest.mark.asyncio
async def test_playback_resuming_outside_an_ad_does_not_resend_a_stale_volume(lounge):
    await device_reports(lounge, 100)
    await ad_starts(lounge)
    await ad_ends(lounge)
    await device_reports(lounge, AD_VOLUME)
    sent_before = len(lounge.sent)
    await ad_ends(lounge)
    assert lounge.sent[sent_before:] == []


@pytest.mark.asyncio
async def test_muted_fallback_is_undone_once_volume_becomes_known(lounge):
    await ad_starts(lounge)
    await event(lounge, "onVolumeChanged", {"volume": "100", "muted": "true"})
    await ad_ends(lounge)
    assert lounge.sent[-1] == ("setVolume", {"volume": "100", "muted": "false"})


@pytest.mark.asyncio
async def test_lowering_clears_a_muted_flag_left_by_the_fallback(lounge):
    await ad_starts(lounge)
    await event(lounge, "onVolumeChanged", {"volume": "100", "muted": "true"})
    await ad_starts(lounge)
    await ad_ends(lounge)
    assert lounge.sent[-2:] == [
        ("setVolume", {"volume": AD_VOLUME, "muted": "false"}),
        ("setVolume", {"volume": "100", "muted": "false"}),
    ]
