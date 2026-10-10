"""Local admin panel and child-process supervisor. No Docker socket required."""

import copy
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
CATEGORIES = {
    "sponsor": "Sponsors",
    "selfpromo": "Self promotion",
    "intro": "Intros",
    "outro": "Outros",
    "interaction": "Like / subscribe reminders",
    "music_offtopic": "Non-music sections",
    "preview": "Previews / recaps",
    "filler": "Filler",
    "exclusive_access": "Exclusive access",
    "hook": "Hooks / greetings",
}
BOOLEANS = ("mute_ads", "skip_ads", "skip_count_tracking")
DEFAULT = dict(
    devices=[],
    skip_categories=["sponsor"],
    mute_ads=True,
    skip_ads=True,
    skip_count_tracking=True,
    minimum_skip_length=1,
    auto_play=True,
    join_name="iSponsorBlockTV",
    apikey="",
    channel_whitelist=[],
    use_proxy=False,
)


class Problem(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def redact(line):
    # Upstream logs tokens at INFO. Never forward these lines to browser or Docker logs.
    if re.search(r"lounge.?id|auth(?:orization)?|token|api.?key|cookie", line, re.I):
        return "[authentication details hidden]"
    line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
    return re.sub(r"(?i)\b[0-9a-f]{26,128}\b", "[device-id]", line).strip()[:4000]


def validate_config(value):
    if not isinstance(value, dict):
        raise Problem("config.json must contain a JSON object. Restore or repair it first.", 409)
    for key in ("devices", "_web_disabled_devices"):
        devices = value.get(key, [])
        if not isinstance(devices, list) or any(
            not isinstance(d, dict) or not isinstance(d.get("screen_id"), str) or not d["screen_id"]
            for d in devices
        ):
            raise Problem("Invalid device list in config.json. No changes were made.", 409)
    if not isinstance(value.get("_web_device_hosts", {}), dict):
        raise Problem("Invalid saved device addresses.", 409)
    return value


class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "config.json"

    def read(self):
        try:
            raw = self.path.read_bytes()
            value = validate_config(json.loads(raw))
        except FileNotFoundError:
            raw, value = b"", copy.deepcopy(DEFAULT)
        except (UnicodeError, json.JSONDecodeError):
            raise Problem("config.json is unreadable JSON. It has been left untouched.", 409)
        return value, hashlib.sha256(raw).hexdigest()

    def write(self, value):
        validate_config(value)
        raw = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        backups = self.folder / "web-backups"
        backups.mkdir(exist_ok=True)
        if self.path.exists():
            target = backups / ("config-" + str(time.time_ns()) + ".json")
            with target.open("xb") as f:
                f.write(self.path.read_bytes())
            os.chmod(target, 0o600)
        temporary = self.folder / (".config-" + secrets.token_hex(8) + ".tmp")
        try:
            with temporary.open("xb") as f:
                os.chmod(temporary, 0o600)
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        for old in sorted(backups.glob("config-*.json"))[:-20]:
            old.unlink()


class Worker:
    def __init__(self, store, command=None, cwd="/app", emit=True):
        self.store = store
        self.command = command or [
            sys.executable,
            "-u",
            "/app/main.pyc",
            "--data",
            str(store.folder),
        ]
        self.cwd = cwd
        self.emit = emit
        self.process = None
        self.reader = None
        self.logs = deque(maxlen=1500)
        self.log_lock = threading.Lock()
        self.seq = 0
        self.started = None
        self.last_events = {}

    def log(self, text):
        text = redact(text)
        if not text:
            return
        with self.log_lock:
            self.seq += 1
            self.logs.append(dict(id=self.seq, time=time.time(), message=text))
        if self.emit:
            print(text, flush=True)

    def consume(self, process):
        for line in process.stdout:
            match = re.search(r"iSponsorBlockTV-([A-Za-z0-9_-]+)\s+-\s+\w+\s+-\s+(.*)", line)
            if match and not re.search(r"auth|token|lounge", match[2], re.I):
                with self.log_lock:
                    self.last_events[match[1]] = dict(message=redact(match[2]), time=time.time())
            self.log(line)
        process.stdout.close()

    def status(self):
        code = self.process.poll() if self.process else None
        return dict(
            running=self.process is not None and code is None, exit_code=code, started=self.started
        )

    def start(self):
        if self.status()["running"]:
            return
        config, _ = self.store.read()
        if config.get("_web_service_paused") or not config.get("devices"):
            return
        if not self.store.path.exists():
            return
        env = os.environ.copy()
        # Do not let helper dependencies or the panel password leak into the worker.
        env.pop("PYTHONPATH", None)
        env.pop("WEB_PASSWORD", None)
        env["iSPBTV_data_dir"] = str(self.store.folder)
        env["iSPBTV_docker"] = "True"
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        with self.log_lock:
            self.last_events = {}
        self.started = time.time()
        self.reader = threading.Thread(target=self.consume, args=(self.process,), daemon=True)
        self.reader.start()
        self.log("Service started.")

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.reader:
            self.reader.join(timeout=2)


class Panel:
    def __init__(self, store, worker, networks, password):
        self.store, self.worker, self.password = store, worker, password
        self.networks = [ipaddress.ip_network(n.strip()) for n in networks.split(",") if n.strip()]
        if not self.networks or any(n.version != 4 or not n.is_private for n in self.networks):
            raise ValueError("ALLOWED_NETWORKS must contain private IPv4 CIDRs.")
        self.lock = threading.RLock()
        self.probe_lock = threading.Lock()
        self.sessions = {}
        self.attempts = {}
        self.candidates = {}
        self.failures = 0
        self.last_retry = 0
        self.shutdown_event = threading.Event()

    def allowed_ip(self, host):
        try:
            address = ipaddress.ip_address(host)
            ok = (
                address.version == 4
                and address.is_private
                and not address.is_loopback
                and not address.is_link_local
                and not address.is_multicast
                and any(
                    address in n and address not in (n.network_address, n.broadcast_address)
                    for n in self.networks
                )
            )
            if ok:
                return str(address)
        except (ValueError, TypeError):
            pass
        raise Problem("Enter a device IPv4 address within ALLOWED_NETWORKS.")

    def state(self):
        with self.lock:
            config, revision = self.store.read()
            devices = []
            for key, enabled in (("devices", True), ("_web_disabled_devices", False)):
                for d in config.get(key, []):
                    sid = d["screen_id"]
                    with self.worker.log_lock:
                        event = copy.deepcopy(self.worker.last_events.get(sid))
                    devices.append(
                        dict(
                            id=sid,
                            name=d.get("name") or "YouTube device",
                            enabled=enabled,
                            ip=config.get("_web_device_hosts", {}).get(sid, ""),
                            event=event,
                        )
                    )
            defaults = {**DEFAULT, "mute_ads": False, "skip_ads": False}
            settings = {
                k: config.get(k, defaults[k])
                for k in BOOLEANS + ("minimum_skip_length", "skip_categories")
            }
            if settings["skip_categories"] is None:
                settings["skip_categories"] = ["sponsor"]
            return dict(
                revision=revision,
                devices=devices,
                settings=settings,
                categories=CATEGORIES,
                service={**self.worker.status(), "paused": bool(config.get("_web_service_paused"))},
                allowed_networks=[str(n) for n in self.networks],
            )

    def change(self, revision, fn):
        with self.lock:
            config, current = self.store.read()
            if revision != current:
                raise Problem("Settings changed in another window. Refresh and try again.", 409)
            fn(config)
            validate_config(config)
            self.worker.stop()
            try:
                self.store.write(config)
            finally:
                self.failures = 0
                self.worker.start()
            return self.state()

    def settings(self, body):
        def update(config):
            s = body.get("settings")
            if not isinstance(s, dict):
                raise Problem("Settings are required.")
            for key in BOOLEANS:
                if type(s.get(key)) is not bool:
                    raise Problem("Invalid setting: " + key)
            minimum = s.get("minimum_skip_length")
            if type(minimum) not in (int, float) or not 0 <= minimum <= 600:
                raise Problem("Minimum segment length must be between 0 and 600 seconds.")
            cats = s.get("skip_categories")
            if not isinstance(cats, list) or any(
                not isinstance(c, str) or c not in CATEGORIES for c in cats
            ):
                raise Problem("Invalid SponsorBlock category.")
            config.update({k: s[k] for k in BOOLEANS})
            # Retain categories introduced by a newer upstream version until this UI knows them.
            unknown = [c for c in (config.get("skip_categories") or []) if c not in CATEGORIES]
            config.update(
                minimum_skip_length=minimum, skip_categories=list(dict.fromkeys(cats + unknown))
            )

        return self.change(body.get("revision"), update)

    def device(self, body):
        def update(config):
            sid = body.get("id")
            active = config.setdefault("devices", [])
            disabled = config.setdefault("_web_disabled_devices", [])
            found = next((d for d in active + disabled if d["screen_id"] == sid), None)
            if found is None:
                raise Problem("Device not found.", 404)
            action = body.get("action")
            if action == "rename":
                name = body.get("name", "").strip()
                if not 1 <= len(name) <= 80:
                    raise Problem("Device name must be 1–80 characters.")
                found["name"] = name
                return
            if action not in ("enable", "disable", "remove"):
                raise Problem("Unknown action.")
            config["devices"] = [d for d in active if d["screen_id"] != sid]
            config["_web_disabled_devices"] = [d for d in disabled if d["screen_id"] != sid]
            if action != "remove":
                config["devices" if action == "enable" else "_web_disabled_devices"].append(found)
            else:
                config.setdefault("_web_device_hosts", {}).pop(sid, None)

        return self.change(body.get("revision"), update)

    def add(self, body):
        def update(config):
            candidate = self.candidates.get(body.get("candidate"))
            if not candidate or candidate["expires"] < time.time():
                raise Problem("Pairing result expired. Check the device again.")
            device = copy.deepcopy(candidate["device"])
            name = body.get("name", device["name"]).strip()
            if not 1 <= len(name) <= 80:
                raise Problem("Device name must be 1–80 characters.")
            device["name"] = name
            sid = device["screen_id"]
            config["devices"] = [d for d in config.get("devices", []) if d["screen_id"] != sid] + [
                device
            ]
            config["_web_disabled_devices"] = [
                d for d in config.get("_web_disabled_devices", []) if d["screen_id"] != sid
            ]
            config.setdefault("_web_device_hosts", {})[sid] = candidate["ip"]

        return self.change(body.get("revision"), update)

    def helper(self, mode, host=""):
        if not self.probe_lock.acquire(blocking=False):
            raise Problem("A device check is already running. Try again shortly.", 409)
        try:
            env = {k: v for k, v in os.environ.items() if k != "WEB_PASSWORD"}
            env["PYTHONPATH"] = "/paneldeps"
            result = subprocess.run(
                [sys.executable, str(ROOT / "cast_helper.py"), mode, host],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if result.returncode:
                raise Problem(
                    "Device check failed. Verify the address, TCP 8009 access, and that YouTube is casting.",
                    502,
                )
            data = json.loads(result.stdout)
            if "error" in data:
                raise Problem(data["error"], 502)
            return data
        except subprocess.TimeoutExpired:
            raise Problem("Device timed out. Check the VLAN ACL permits TCP 8009 from Unraid.", 504)
        finally:
            self.probe_lock.release()

    def scan(self):
        result = self.helper("scan")
        filtered = []
        for d in result["devices"]:
            try:
                d["ip"] = self.allowed_ip(d["ip"])
                filtered.append(d)
            except Problem:
                continue
        return dict(devices=filtered)

    def probe(self, body):
        host = self.allowed_ip(body.get("ip"))
        data = self.helper("probe", host)
        sid = data.get("screen_id")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", sid):
            raise Problem("The receiver did not return a usable YouTube screen ID.", 502)
        token = secrets.token_urlsafe(24)
        with self.lock:
            self.candidates = {
                k: v for k, v in self.candidates.items() if v["expires"] > time.time()
            }
            self.candidates[token] = dict(
                expires=time.time() + 600,
                ip=host,
                device=dict(screen_id=sid, name=data.get("name") or host, offset=0),
            )
        return dict(candidate=token, name=data.get("name") or host, ip=host)

    def supervise(self):
        while not self.shutdown_event.wait(3):
            with self.lock:
                try:
                    config, _ = self.store.read()
                    if config.get("_web_service_paused") or not config.get("devices"):
                        continue
                    status = self.worker.status()
                    if status["running"]:
                        if time.time() - (status["started"] or time.time()) > 60:
                            self.failures = 0
                    elif self.failures < 3 and time.time() - self.last_retry > 10:
                        self.failures += 1
                        self.last_retry = time.time()
                        self.worker.log(
                            f"Restarting service after exit (attempt {self.failures}/3)."
                        )
                        self.worker.start()
                except Exception as exc:
                    self.worker.log("Service needs attention: " + str(exc))


class Handler(BaseHTTPRequestHandler):
    server_version = "SponsorPanel"

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(40)

    @property
    def panel(self):
        return self.server.panel

    def respond(self, status, data, content_type="application/json", cookie=None):
        raw = json.dumps(data).encode() if content_type == "application/json" else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(raw)

    def session(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
            token = cookies["panel_session"].value
        except (KeyError, ValueError):
            raise Problem("Sign in to continue.", 401)
        with self.panel.lock:
            session = self.panel.sessions.get(token)
            if not session or session["expires"] < time.time():
                self.panel.sessions.pop(token, None)
                raise Problem("Sign in to continue.", 401)
            return token, session

    def body(self):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise Problem("JSON required.", 415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError()
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeError):
            raise Problem("Invalid request body.")

    def origin_check(self):
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            raise Problem("Cross-site requests are not allowed.", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise Problem("Cross-site requests are not allowed.", 403)

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, write):
        try:
            path = urlsplit(self.path).path
            if not write and path == "/health":
                return self.respond(200, {"ok": True})
            if not write and path in ("/", "/app.js", "/style.css"):
                name, mime = {
                    "/": ("index.html", "text/html; charset=utf-8"),
                    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                    "/style.css": ("style.css", "text/css; charset=utf-8"),
                }[path]
                return self.respond(200, (ROOT / "static" / name).read_bytes(), mime)
            if write:
                self.origin_check()
                body = self.body()
                if path == "/api/login":
                    now = time.time()
                    address = self.client_address[0]
                    with self.panel.lock:
                        self.panel.attempts = {
                            k: [t for t in v if t > now - 60]
                            for k, v in self.panel.attempts.items()
                            if any(t > now - 60 for t in v)
                        }
                        attempts = self.panel.attempts.setdefault(address, [])
                        if len(attempts) >= 5:
                            raise Problem("Too many attempts. Wait a minute.", 429)
                        supplied = body.get("password", "")
                        if not isinstance(supplied, str) or not hmac.compare_digest(
                            supplied.encode(), self.panel.password.encode()
                        ):
                            attempts.append(now)
                            raise Problem("Incorrect password.", 401)
                        self.panel.sessions = {
                            k: v for k, v in self.panel.sessions.items() if v["expires"] > now
                        }
                        token = secrets.token_urlsafe(32)
                        session = dict(csrf=secrets.token_urlsafe(32), expires=now + 43200)
                        self.panel.sessions[token] = session
                    secure = "; Secure" if os.getenv("COOKIE_SECURE") == "1" else ""
                    return self.respond(
                        200,
                        dict(csrf=session["csrf"]),
                        cookie=f"panel_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200{secure}",
                    )
            token, session = self.session()
            if not write:
                if path == "/api/session":
                    return self.respond(200, dict(csrf=session["csrf"]))
                if path == "/api/state":
                    return self.respond(200, self.panel.state())
                if path == "/api/logs":
                    try:
                        after = int(parse_qs(urlsplit(self.path).query).get("after", ["0"])[0])
                    except ValueError:
                        raise Problem("Invalid log cursor.")
                    with self.panel.worker.log_lock:
                        logs = [x for x in self.panel.worker.logs if x["id"] > after]
                        cursor = self.panel.worker.seq
                    return self.respond(200, dict(logs=logs, cursor=cursor))
            else:
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session["csrf"]):
                    raise Problem("Session verification failed. Sign in again.", 403)
                if path == "/api/logout":
                    with self.panel.lock:
                        self.panel.sessions.pop(token, None)
                    return self.respond(
                        200,
                        {},
                        cookie="panel_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict",
                    )
                methods = {
                    "/api/settings": self.panel.settings,
                    "/api/device": self.panel.device,
                    "/api/add": self.panel.add,
                    "/api/probe": self.panel.probe,
                }
                if path in methods:
                    return self.respond(200, methods[path](body))
                if path == "/api/scan":
                    return self.respond(200, self.panel.scan())
                if path == "/api/service":
                    if body.get("action") not in ("pause", "start", "restart"):
                        raise Problem("Unknown service action.")
                    result = self.panel.change(
                        body.get("revision"),
                        lambda c: c.update(_web_service_paused=body["action"] == "pause"),
                    )
                    return self.respond(200, result)
            raise Problem("Not found.", 404)
        except Problem as exc:
            self.respond(exc.code, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.panel.worker.log("Panel error: " + str(exc))
            self.respond(500, {"error": "The operation could not finish. Check the service logs."})


def main():
    password = os.getenv("WEB_PASSWORD", "")
    if len(password) < 12:
        raise SystemExit("Set WEB_PASSWORD to at least 12 characters before starting.")
    store = Store(os.getenv("DATA_DIR", "/app/data"))
    worker = Worker(store)
    panel = Panel(store, worker, os.getenv("ALLOWED_NETWORKS", "192.168.52.0/24"), password)
    server = ThreadingHTTPServer(
        (os.getenv("WEB_BIND", "0.0.0.0"), int(os.getenv("WEB_PORT", "1166"))), Handler
    )
    server.daemon_threads = True
    server.panel = panel
    try:
        worker.start()
    except Exception as exc:
        worker.log("Service needs attention: " + str(exc))
    threading.Thread(target=panel.supervise, daemon=True).start()

    def shutdown(*_):
        panel.shutdown_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    worker.log("Web panel ready on port " + str(server.server_port))
    try:
        server.serve_forever()
    finally:
        panel.shutdown_event.set()
        with panel.lock:
            worker.stop()
        server.server_close()


if __name__ == "__main__":
    main()
