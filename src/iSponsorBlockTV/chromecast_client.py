"""Chromecast discovery using Cast protocol via pychromecast."""

import asyncio
from typing import Any

import pychromecast
from pychromecast.controllers.youtube import YouTubeController
from pychromecast import Chromecast


def _build_device_from_cast(cast: Chromecast) -> dict[str, Any] | None:
    try:
        cast.wait(timeout=5)

        yt_controller = YouTubeController()
        cast.register_handler(yt_controller)
        yt_controller.update_screen_id()

        # Give the controller a moment to process status messages.
        cast.wait(timeout=2)
        screen_id = yt_controller._screen_id
        if not screen_id:
            return None

        try:
            cast_name = cast.cast_info.friendly_name
        except Exception:
            try:
                cast_name = cast.name
            except Exception:
                cast_name = "Chromecast"

        return {
            "screen_id": screen_id,
            "name": cast_name,
            "offset": 0,
        }
    except Exception:
        return None
    finally:
        try:
            cast.disconnect(timeout=1)
        except Exception:
            pass


async def discover(web_session, api_helper=None, active=True):
    """Discover Chromecast devices and yield YouTube MDX-capable screens.

    The signature mirrors the newer DIAL discovery generator so callers can
    consume both sources with the same `async for` pattern.
    """
    del web_session
    del api_helper

    loop = asyncio.get_running_loop()
    discovered_casts: asyncio.Queue = asyncio.Queue()

    def on_cast_discovered(cast) -> None:
        loop.call_soon_threadsafe(discovered_casts.put_nowait, cast)

    browser = pychromecast.get_chromecasts(
        timeout=5,
        blocking=False,
        callback=on_cast_discovered,
    )

    pending_tasks: set[asyncio.Task] = set()
    seen_screen_ids: set[str] = set()
    discovery_deadline = loop.time() + (5 if active else 15)

    try:
        while True:
            if not active and pending_tasks:
                pass
            elif loop.time() >= discovery_deadline and discovered_casts.empty() and not pending_tasks:
                break

            try:
                cast = await asyncio.wait_for(discovered_casts.get(), timeout=0.5)
                pending_tasks.add(asyncio.create_task(asyncio.to_thread(_build_device_from_cast, cast)))
                discovery_deadline = max(discovery_deadline, loop.time() + 1)
            except asyncio.TimeoutError:
                pass

            done_tasks = {task for task in pending_tasks if task.done()}
            for task in done_tasks:
                pending_tasks.discard(task)
                device = None
                try:
                    device = task.result()
                except Exception:
                    device = None
                if not device:
                    continue
                screen_id = device.get("screen_id")
                if not screen_id or screen_id in seen_screen_ids:
                    continue
                seen_screen_ids.add(screen_id)
                yield device
    finally:
        for task in pending_tasks:
            task.cancel()
        await asyncio.to_thread(browser.stop_discovery)
