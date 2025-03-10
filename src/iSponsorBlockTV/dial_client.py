"""Send out an M-SEARCH request and listening for responses."""

import asyncio
import socket

import ssdp
import xmltodict
from ssdp import network

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


def get_ip():
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
        self.devices = []

    def clear(self):
        self.devices = []

    def __call__(self):
        return self

    def response_received(self, response: ssdp.messages.SSDPResponse, addr):
        headers = response.headers
        headers = {k.lower(): v for k, v in headers}
        # print(headers)
        if "location" in headers:
            self.devices.append(headers["location"])

    def request_received(self, request: ssdp.messages.SSDPRequest, addr):
        raise NotImplementedError(
            "Request received is not implemented, this is a client"
        )


async def find_youtube_app(web_session, url_location):
    async with web_session.get(url_location) as response:
        headers = response.headers
        response = await response.text()
    # print(headers)

    data = xmltodict.parse(response)
    name = data["root"]["device"]["friendlyName"]
    handler = Handler()
    handler.clear()
    app_url = headers["application-url"]
    youtube_url = app_url + "YouTube"
    # print(youtube_url)
    async with web_session.get(youtube_url) as response:
        status_code = response.status
        response = await response.text()
        # print(status_code)
    if status_code == 200:
        data = xmltodict.parse(response)
        data = data["service"]
        screen_id = data["additionalData"]["screenId"]
        return {"screen_id": screen_id, "name": name, "offset": 0}


async def discover(web_session):
    bind = None
    search_target = "urn:dial-multiscreen-org:service:dial:1"
    max_wait = 10
    handler = Handler()
    # Send out an M-SEARCH request and listening for responses
    family, _ = network.get_best_family(bind, network.PORT)
    loop = asyncio.get_event_loop()
    ip_address = get_ip()
    connect = loop.create_datagram_endpoint(
        handler, family=family, local_addr=(ip_address, None)
    )
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

    target = network.MULTICAST_ADDRESS_IPV4, network.PORT

    search_request.sendto(transport, target)

    try:
        await asyncio.sleep(4)
    finally:
        transport.close()

    devices = []
    for i in handler.devices:
        devices.append(await find_youtube_app(web_session, i))

    return devices
