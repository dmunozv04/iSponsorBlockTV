"""Send out an M-SEARCH request and listening for responses."""

import asyncio
import logging
import secrets
import socket
from typing import TYPE_CHECKING, AsyncIterator, Dict, Any, Optional, Set, Tuple

import ssdp
import xmltodict
from ssdp import network
from yarl import URL

from aiohttp import ClientSession

if TYPE_CHECKING:
    from .api_helpers import ApiHelper


logger = logging.getLogger(__name__)

# Redistribution and use of the DIAL DIscovery And Launch protocol
# specification (the “DIAL Specification”), with or without modification,
# are permitted provided that the following conditions are met: ●
# Redistributions of the DIAL Specification must retain the above copyright
# notice, this list of conditions and the following disclaimer. ●
# Redistributions of implementations of the DIAL Specification in source code
# form must retain the above copyright notice, this list of conditions and the
# following disclaimer. ● Redistributions of implementations of the DIAL
# Specification in binary form must include the above copyright notice. ● The
# DIAL mark, the NETFLIX mark and the names of contributors to the DIAL
# Specification may not be used to endorse or promote specifications, software,
# products, or any other materials derived from the DIAL Specification without
# specific prior written permission. The DIAL mark is owned by Netflix and
# information on licensing the DIAL mark is available at
# www.dial-multiscreen.org.


# MIT License

# Copyright (c) 2018 Johannes Hoppe

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Modified code from
# https://github.com/codingjoe/ssdp/blob/main/ssdp/__main__.py


def get_ip() -> str:
    """Gets the local IP address of the machine by connecting to a non-routable address.
    Needed for SSDP discovery to work on windows and machines with multiple interfaces."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class Handler(ssdp.aio.SSDP):
    def __init__(self):
        super().__init__()
        self.devices_queue: asyncio.Queue[str] = asyncio.Queue()

    def clear(self):
        self.devices_queue = asyncio.Queue()

    def __call__(self):
        return self

    def response_received(self, response: ssdp.messages.SSDPResponse, addr):
        headers = response.headers
        headers = {k.lower(): v for k, v in headers}
        if "location" in headers:
            self.devices_queue.put_nowait(headers["location"])

    def request_received(self, request: ssdp.messages.SSDPRequest, addr):
        raise NotImplementedError("Request received is not implemented, this is a client")

    def connection_lost(self, exc):
        pass  # Don't log connection lost, expected on transport close


def _extract_screen_id(youtube_service_xml: str) -> Optional[str]:
    data = xmltodict.parse(youtube_service_xml)
    service_data = data.get("service", {})
    additional_data = service_data.get("additionalData", {})
    return additional_data.get("screenId")


def _generate_pairing_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(12))


async def find_youtube_app(
    web_session: ClientSession, api_helper: "ApiHelper", url_location: str, active: bool = True
) -> Optional[Dict[str, Any]]:
    """Discover and validate a YouTube app on a DIAL device.

    Args:
        web_session: aiohttp ClientSession for making requests
        api_helper: API helper instance for pairing operations
        url_location: Device location URL from DIAL discovery
        active: If True, attempt to launch YouTube app to obtain screen ID.
                If False, only try passive methods (direct service query).

    Returns:
        Device dict with screen_id, name, and offset, or None if not found/invalid.
    """
    async with web_session.get(url_location) as response:
        headers = response.headers
        response = await response.text()

    data = xmltodict.parse(response)
    name = data["root"]["device"]["friendlyName"]
    app_url = headers["application-url"]
    base_url = URL(app_url)
    youtube_url = str(base_url / "YouTube")
    request_headers = {"Origin": "https://www.youtube.com"}
    try:
        async with web_session.get(youtube_url, headers=request_headers) as response:
            youtube_service_xml = await response.text()
            screen_id = _extract_screen_id(youtube_service_xml)
            if screen_id:
                return {"screen_id": screen_id, "name": name, "offset": 0}
    except Exception:
        pass

    # If not active mode, don't try to launch the app
    if not active:
        return None

    # Couldn't get app info. Launch YouTube with a generated pairing code,
    # then pair using that same code.
    pairing_code = _generate_pairing_code()
    logger.debug("Launching YouTube app on %s with pairing code %s", name, pairing_code)
    launch_headers = {
        "Origin": "https://www.youtube.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    launch_data = {"pairingCode": pairing_code, "theme": "cl"}

    async with web_session.post(youtube_url, headers=launch_headers, data=launch_data) as response:
        if response.headers.get("Location"):
            logger.debug("Launched YouTube app on %s, waiting for it to pair...", name)
            for _ in range(10):
                paired_device = await api_helper.pair_with_code(pairing_code)
                if paired_device:
                    return {
                        "screen_id": paired_device["screen_id"],
                        "name": name,
                        "offset": 0,
                    }
                await asyncio.sleep(2)

    return None


async def _send_search_requests(
    search_request: ssdp.messages.SSDPRequest,
    transport: asyncio.DatagramTransport,
    target: Tuple[str, int],
    active: bool,
    discovery_complete_event: asyncio.Event,
) -> None:
    """Send M-SEARCH requests (active single run or passive polling)."""
    try:
        search_request.sendto(transport, target)
        if active:
            # Active mode: single discovery cycle
            await asyncio.sleep(4)
            discovery_complete_event.set()
        else:
            # Passive mode: poll indefinitely
            poll_interval = 15  # seconds between polls
            while True:
                await asyncio.sleep(poll_interval)
                logger.debug("Sending periodic M-SEARCH to discover new devices...")
                search_request.sendto(transport, target)
    except Exception:
        discovery_complete_event.set()


async def _process_devices(
    handler: Handler,
    web_session: ClientSession,
    api_helper: "ApiHelper",
    active: bool,
    pending_tasks: Set[asyncio.Task],
    result_queue: asyncio.Queue[Dict[str, Any]],
    discovery_complete_event: asyncio.Event,
    seen_screen_ids: Set[str],
) -> None:
    """Process devices from handler queue and validate them.

    This function creates tasks for `find_youtube_app` and pushes validated
    devices onto `result_queue`. `pending_tasks` is a shared mutable set so
    the caller can observe outstanding work.
    """
    while (
        not discovery_complete_event.is_set() or not handler.devices_queue.empty() or pending_tasks
    ):
        try:
            # Try to get a device from the queue with timeout
            url_location = await asyncio.wait_for(handler.devices_queue.get(), timeout=0.5)
            # Always create a task - we'll deduplicate by screen_id after we have it
            logger.debug("Discovered device at %s, processing...", url_location)
            coro = find_youtube_app(web_session, api_helper, url_location, active=active)
            task = asyncio.create_task(coro)
            pending_tasks.add(task)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

        # Process completed tasks
        done_tasks = {task for task in pending_tasks if task.done()}
        for task in done_tasks:
            pending_tasks.discard(task)
            try:
                device = await task
                # Only yield if we haven't seen this screen_id before
                if device and device["screen_id"] not in seen_screen_ids:
                    seen_screen_ids.add(device["screen_id"])
                    await result_queue.put(device)
            except Exception:
                pass


async def discover(
    web_session: ClientSession, api_helper: "ApiHelper", active: bool = True
) -> AsyncIterator[Dict[str, Any]]:
    """Discover YouTube-capable devices on the local network via DIAL protocol.

    Sends out M-SEARCH SSDP requests and listens for responses from DIAL devices.
    For each device found, attempts to discover its YouTube app and retrieves the
    screen ID. Devices are yielded as they complete, allowing for real-time usage
    without waiting for all devices to be processed.

    In active mode, performs a single discovery cycle and stops.
    In passive mode, polls indefinitely for new devices without launching apps.

    Args:
        web_session: aiohttp ClientSession for HTTP requests
        api_helper: API helper instance for pairing operations
        active: If True (default), attempt to launch YouTube app on devices that
                don't respond to passive queries. Performs single discovery cycle.
                If False, continuously poll for new devices without launching apps.

    Yields:
        Device dicts with screen_id, name, and offset fields as they are validated.
    """
    bind = None
    search_target = "urn:dial-multiscreen-org:service:dial:1"
    max_wait = 10
    handler = Handler()
    seen_screen_ids = set()
    pending_tasks = set()
    result_queue = asyncio.Queue()

    # Send out an M-SEARCH request and listening for responses
    family, _ = network.get_best_family(bind, network.PORT)
    loop = asyncio.get_event_loop()
    ip_address = get_ip()
    connect = loop.create_datagram_endpoint(handler, family=family, local_addr=(ip_address, None))
    transport, _ = await connect

    target = network.MULTICAST_ADDRESS_IPV4, network.PORT

    search_request = ssdp.messages.SSDPRequest(
        "M-SEARCH",
        headers={
            "HOST": f"{target[0]}:{target[1]}",
            "MAN": '"ssdp:discover"',
            "MX": str(max_wait),  # seconds to delay response [1..5]
            "ST": search_target,
        },
    )

    discovery_complete_event = asyncio.Event()

    # Start search request sender and device processor tasks
    search_task = asyncio.create_task(
        _send_search_requests(search_request, transport, target, active, discovery_complete_event)
    )
    process_task = asyncio.create_task(
        _process_devices(
            handler,
            web_session,
            api_helper,
            active,
            pending_tasks,
            result_queue,
            discovery_complete_event,
            seen_screen_ids,
        )
    )

    try:
        # Yield results as they become available
        while True:
            try:
                # Wait for results with timeout
                device = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                if device:
                    yield device
            except asyncio.TimeoutError:
                # Check if we're done
                if discovery_complete_event.is_set() and result_queue.empty() and not pending_tasks:
                    break
                continue
    finally:
        search_task.cancel()
        process_task.cancel()
        transport.close()
        try:
            await search_task
        except asyncio.CancelledError:
            pass
        try:
            await process_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    import aiohttp
    import sys
    from pathlib import Path

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.debug("Starting DIAL discovery test...")

    src_path = Path(__file__).resolve().parents[1]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from iSponsorBlockTV import api_helpers

    class _DebugConfig:
        apikey = None
        skip_categories = []
        channel_whitelist = []
        skip_count_tracking = False
        devices = []
        minimum_skip_length = 0

    async def main():
        async with aiohttp.ClientSession() as session:
            api_helper = api_helpers.ApiHelper(config=_DebugConfig(), web_session=session)
            devices = []
            async for device in discover(session, api_helper, active=True):
                logger.debug("%s", device)
                devices.append(device)
            logger.debug("Found %d YouTube devices", len(devices))
            logger.debug("Devices: %s", devices)

    asyncio.run(main())
