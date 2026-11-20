import asyncio
import json

import pytest

from iSponsorBlockTV.config_store import normalize_config, read_config, write_config
from iSponsorBlockTV.helpers import Config
from iSponsorBlockTV.main import run_listeners, wait_for_config


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"devices": "broken"},
        {"devices": [{"screen_id": ""}]},
        {"devices": [{"screen_id": "tv", "offset": True}]},
        {"devices": [{"screen_id": "tv"}, {"screen_id": "tv"}]},
        {"minimum_skip_length": -1},
        {"minimum_skip_length": float("nan")},
        {"minimum_skip_length": True},
        {"mute_ads": "false"},
        {"skip_categories": ["bogus"]},
        {"channel_whitelist": [{"id": "channel"}]},
        {"config_file": "/etc/passwd"},
        {"validate": "broken"},
        {"sponsorblock_api_url": "file:///etc/passwd"},
        {"sponsorblock_api_url": "https://sponsor.example:invalid/api"},
        {"sponsorblock_api_url": "https://sponsor.example:65536/api"},
    ],
)
def test_invalid_documents_never_replace_working_config(tmp_path, document):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "working"})
    before = path.read_bytes()
    with pytest.raises((ValueError, TypeError)):
        write_config(path, document)
    assert path.read_bytes() == before


def test_atomic_save_and_normalization(tmp_path, monkeypatch):
    path = tmp_path / "new" / "config.json"
    import os

    original_replace = os.replace
    calls = []

    def replace(source, destination):
        with open(source, encoding="utf-8") as stream:
            calls.append(json.load(stream))
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace)
    result = write_config(path, {"skip_categories": [], "devices": [{"screen_id": "tv"}]})
    assert calls == [result]
    assert read_config(path)["skip_categories"] == []
    assert list(path.parent.iterdir()) == [path]


def test_failed_replace_preserves_config_and_removes_temporary_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "working"})
    import os

    monkeypatch.setattr(os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        write_config(path, {"join_name": "new"})
    assert read_config(path)["join_name"] == "working"
    assert list(tmp_path.iterdir()) == [path]


def test_config_validation_is_repeatable_and_save_keeps_offsets(tmp_path):
    path = tmp_path / "config.json"
    write_config(path, {"devices": [{"screen_id": "tv", "offset": -250}]})
    config = Config(str(tmp_path))
    config.validate()
    config.validate()
    assert config.devices[0].offset == -0.25
    config.save()
    assert read_config(path)["devices"][0]["offset"] == -250
    assert config.config_file == str(path).replace("\\", "/") or config.config_file.endswith(
        "/config.json"
    )


@pytest.mark.asyncio
async def test_reload_survives_malformed_file_and_applies_rapid_atomic_saves(tmp_path):
    path = tmp_path / "config.json"
    write_config(path, {"join_name": "old", "mute_ads": True})
    config = Config(str(tmp_path))
    config.validate()
    waiter = asyncio.create_task(wait_for_config(config, interval=0.01))
    try:
        path.write_text('{"devices":', encoding="utf-8")
        await asyncio.sleep(0.03)
        assert not waiter.done()
        assert config.mute_ads is True
        write_config(path, {"join_name": "first"})
        candidate = await asyncio.wait_for(waiter, timeout=1)
        assert candidate.join_name == "first"
        assert candidate.mute_ads is False  # Removed fields revert to defaults.
        waiter = asyncio.create_task(wait_for_config(candidate, interval=0.01))
        write_config(path, {"join_name": "second"})
        assert (await asyncio.wait_for(waiter, timeout=1)).join_name == "second"
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.asyncio
async def test_empty_worker_waits_for_first_configuration_and_stops(tmp_path):
    config = Config(str(tmp_path))
    config.validate()
    stop = asyncio.Event()
    running = asyncio.create_task(run_listeners(config, False, False, stop, watch_config=True))
    await asyncio.sleep(0.03)
    assert not running.done()
    stop.set()
    assert await asyncio.wait_for(running, timeout=1) is None


@pytest.mark.asyncio
async def test_first_install_wait_does_not_repeat_logs_and_recovers_from_invalid_config(
    tmp_path, caplog
):
    import logging

    config = Config(str(tmp_path))
    config.validate()
    caplog.set_level(logging.INFO, logger="iSponsorBlockTV.main")
    waiter = asyncio.create_task(wait_for_config(config, interval=0.01))
    try:
        await asyncio.sleep(0.06)
        assert not waiter.done()
        assert [record.message for record in caplog.records] == [
            "Waiting for a configuration to be saved"
        ]
        (tmp_path / "config.json").write_text('{"devices":', encoding="utf-8")
        await asyncio.sleep(0.06)
        assert len(caplog.records) == 2
        assert caplog.records[-1].levelno == logging.WARNING
        write_config(tmp_path / "config.json", {"join_name": "configured"})
        assert (await asyncio.wait_for(waiter, timeout=1)).join_name == "configured"
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.asyncio
async def test_reload_cancels_device_tasks_and_closes_session(tmp_path, monkeypatch):
    from iSponsorBlockTV import main

    write_config(tmp_path / "config.json", {"devices": [{"screen_id": "tv"}]})
    config = Config(str(tmp_path))
    config.validate()
    sessions = []
    cancelled = []

    class FakeDevice:
        def __init__(self, api, config, entry, debug, session):
            sessions.append(session)

        @staticmethod
        async def initialize_web_session():
            pass

        @staticmethod
        async def loop():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        refresh_auth_loop = loop

        @staticmethod
        async def cancel():
            cancelled.append(True)

    monkeypatch.setattr(main, "DeviceListener", FakeDevice)
    running = asyncio.create_task(
        main.run_listeners(config, False, False, asyncio.Event(), watch_config=True)
    )
    await asyncio.sleep(0.03)
    write_config(tmp_path / "config.json", {"devices": []})
    candidate = await asyncio.wait_for(running, timeout=2)
    assert candidate.devices == []
    assert sessions[0].closed
    assert len(cancelled) == 3


def test_defaults_are_independent():
    config = normalize_config({})
    config["devices"].append({})
    assert normalize_config({})["devices"] == []


def test_null_and_empty_skip_categories_keep_upstream_semantics():
    assert normalize_config({"skip_categories": None})["skip_categories"] == ["sponsor"]
    assert normalize_config({"skip_categories": []})["skip_categories"] == []


@pytest.mark.asyncio
async def test_unchanged_paired_configuration_does_not_restart_listeners(tmp_path):
    write_config(tmp_path / "config.json", {"devices": [{"screen_id": "tv", "offset": 250}]})
    config = Config(str(tmp_path))
    config.validate()
    candidate = Config(str(tmp_path))
    candidate.validate()
    assert config == candidate
    waiter = asyncio.create_task(wait_for_config(config, interval=0.01))
    try:
        await asyncio.sleep(0.05)
        assert not waiter.done()
        config.save()  # Identical content written through an atomic replacement.
        await asyncio.sleep(0.05)
        assert not waiter.done()
        write_config(tmp_path / "config.json", {"devices": [{"screen_id": "tv", "offset": 300}]})
        assert (await asyncio.wait_for(waiter, timeout=1)).devices[0].offset == 0.3
    finally:
        waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


@pytest.mark.asyncio
async def test_device_cleanup_cancels_playback_tasks_even_if_disconnect_fails():
    from types import SimpleNamespace

    from iSponsorBlockTV.main import DeviceListener

    async def disconnect():
        raise asyncio.CancelledError()

    tasks = [asyncio.create_task(asyncio.Event().wait()) for _ in range(3)]
    device = object.__new__(DeviceListener)
    device.task = tasks[0]
    device.lounge_controller = SimpleNamespace(
        subscribe_task_watchdog=tasks[1], subscribe_task=tasks[2], disconnect=disconnect
    )
    with pytest.raises(asyncio.CancelledError):
        await device.cancel()
    assert device.cancelled
    assert all(task.cancelled() for task in tasks)


@pytest.mark.asyncio
async def test_config_reload_is_opt_in(tmp_path):
    write_config(tmp_path / "config.json", {"join_name": "original"})
    config = Config(str(tmp_path))
    config.validate()
    stop = asyncio.Event()
    running = asyncio.create_task(run_listeners(config, False, False, stop))
    try:
        write_config(tmp_path / "config.json", {"join_name": "changed"})
        await asyncio.sleep(0.06)
        assert not running.done()
        stop.set()
        assert await asyncio.wait_for(running, timeout=1) is None
    finally:
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)


@pytest.mark.parametrize("watch_config", [False, True])
def test_existing_cli_start_preserves_configuration_and_reload_requires_flag(
    tmp_path, monkeypatch, watch_config
):
    import logging

    from click.testing import CliRunner

    from iSponsorBlockTV import helpers

    path = tmp_path / "config.json"
    write_config(path, {"devices": [{"screen_id": "existing-tv", "offset": -125.5}]})
    before = path.read_bytes()
    calls = []
    monkeypatch.setattr(helpers.main, "main", lambda *args: calls.append(args))
    arguments = ["--data", str(tmp_path)]
    if watch_config:
        arguments.append("--watch-config")
    arguments.append("start")
    logger = logging.getLogger()
    handlers = logger.handlers[:]
    level = logger.level
    try:
        result = CliRunner().invoke(helpers.cli, arguments)
    finally:
        logger.handlers = handlers
        logger.setLevel(level)
    assert result.exit_code == 0, result.output
    assert calls[0][1:] == (False, False, watch_config)
    assert calls[0][0].devices[0].offset == -0.1255
    assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_non_container_start_does_not_run_container_healthcheck(tmp_path, monkeypatch):
    from iSponsorBlockTV import main

    monkeypatch.delenv("HEALTHCHECK_PATH", raising=False)
    calls = []

    async def heartbeat(*_):
        calls.append("heartbeat")

    async def run(*_):
        return None

    monkeypatch.setattr(main, "heartbeat", heartbeat)
    monkeypatch.setattr(main, "run_listeners", run)
    await main.main_async(Config(str(tmp_path)), False, False)
    assert calls == []


def test_existing_config_with_unknown_fields_still_loads(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "join_name": "Legacy",
                "legacy_flag": True,
                "devices": [{"screen_id": "tv", "name": "TV", "offset": 100, "extra": "ignored"}],
            }
        ),
        encoding="utf-8",
    )
    config = Config(str(tmp_path))
    config.validate()
    assert config.join_name == "Legacy"
    assert config.devices[0].screen_id == "tv"
    assert config.devices[0].offset == 0.1
    config.save()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "legacy_flag" not in saved
    assert "_has_deprecated_atvs" not in saved


def test_deprecated_atvs_config_exits_with_migration_notice(tmp_path, monkeypatch, capsys):
    from iSponsorBlockTV import helpers

    (tmp_path / "config.json").write_text(json.dumps({"atvs": ["old"]}), encoding="utf-8")
    monkeypatch.setattr(helpers.time, "sleep", lambda *_: None)
    config = Config(str(tmp_path))
    with pytest.raises(SystemExit):
        config.validate()
    assert "atvs config option is deprecated" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_heartbeat_survives_touch_oserror(tmp_path, monkeypatch, caplog):
    import logging

    from iSponsorBlockTV import main

    bad_path = tmp_path / "missing-dir" / "health"
    monkeypatch.setenv("HEALTHCHECK_PATH", str(bad_path))
    original_sleep = asyncio.sleep
    ticks = 0

    async def fast_sleep(_):
        nonlocal ticks
        ticks += 1
        if ticks >= 2:
            raise asyncio.CancelledError()
        await original_sleep(0)

    monkeypatch.setattr(main.asyncio, "sleep", fast_sleep)
    caplog.set_level(logging.WARNING, logger="iSponsorBlockTV.main")
    with pytest.raises(asyncio.CancelledError):
        await main.heartbeat()
    assert len(caplog.records) == 1
