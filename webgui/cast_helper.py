"""Bounded helper process: mDNS discovery or a direct Cast screen-ID request."""

import ipaddress
import json
import sys
import threading
import time
from uuid import UUID


def scan():
    from zeroconf import Zeroconf, ServiceBrowser, IPVersion

    devices = {}
    lock = threading.Lock()

    class Listener:
        def add_service(self, zc, kind, name):
            info = zc.get_service_info(kind, name, timeout=1200)
            if info:
                props = info.properties
                for ip in info.parsed_addresses(IPVersion.V4Only):
                    with lock:
                        devices[ip] = dict(
                            ip=ip,
                            name=props.get(b"fn", b"Cast device").decode(errors="replace")[:80],
                            model=props.get(b"md", b"").decode(errors="replace")[:80],
                        )

        update_service = add_service

        def remove_service(self, *_):
            pass

    zc = Zeroconf(ip_version=IPVersion.V4Only)
    browser = ServiceBrowser(zc, "_googlecast._tcp.local.", Listener())
    try:
        time.sleep(6)
        with lock:
            return {"devices": list(devices.values())}
    finally:
        browser.cancel()
        zc.close()


def probe(host):
    import pychromecast
    from pychromecast.models import CastInfo, HostServiceInfo
    from pychromecast.const import CAST_TYPE_CHROMECAST
    from pychromecast.controllers.youtube import YouTubeController, YOUTUBE_NAMESPACE

    ipaddress.IPv4Address(host)
    # Supply Cast type to avoid extra discovery/HTTP probes. Connect only to the requested IP:8009.
    info = CastInfo(
        {HostServiceInfo(host, 8009)},
        UUID(int=0),
        None,
        host,
        host,
        8009,
        CAST_TYPE_CHROMECAST,
        None,
    )
    cast = pychromecast.get_chromecast_from_cast_info(info, None, tries=1, timeout=8)
    try:
        cast.wait(timeout=12)
        if YOUTUBE_NAMESPACE not in cast.socket_client.app_namespaces:
            return {
                "error": "Cast a YouTube video to this device first, then check again. The panel will not launch or interrupt another app."
            }
        youtube = YouTubeController()
        cast.register_handler(youtube)
        youtube.update_screen_id()
        if not youtube._screen_id:
            return {"error": "YouTube did not return a screen ID. Recast a video and try again."}
        return {"screen_id": youtube._screen_id, "name": cast.name or host}
    finally:
        cast.disconnect(timeout=3)


if __name__ == "__main__":
    try:
        result = scan() if sys.argv[1] == "scan" else probe(sys.argv[2])
    except Exception:
        result = {
            "error": "Could not reach the Cast receiver. Check TCP 8009, the device address, and active YouTube playback."
        }
    print(json.dumps(result))
