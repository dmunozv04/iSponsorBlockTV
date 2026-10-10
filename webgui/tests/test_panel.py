import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Store, Worker, Panel, Handler, ThreadingHTTPServer, Problem, DEFAULT, redact

SID = "a" * 60


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name)
        config = copy.deepcopy(DEFAULT)
        config.update(
            devices=[dict(screen_id=SID, name="Test TV", offset=350)],
            apikey="preserved-secret",
            future_setting={"value": 42},
        )
        self.store.write(config)
        self.worker = Worker(self.store, emit=False)
        self.panel = Panel(self.store, self.worker, "192.168.52.0/24", "test-password-123")
        self.start = patch.object(self.worker, "start").start()
        self.stop = patch.object(self.worker, "stop").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.tmp.cleanup)

    def revision(self):
        return self.store.read()[1]

    def test_pause_resume_preserves_device_and_unknown_settings(self):
        self.panel.device(dict(revision=self.revision(), id=SID, action="disable"))
        config, _ = self.store.read()
        self.assertEqual(config["devices"], [])
        self.assertEqual(config["_web_disabled_devices"][0]["offset"], 350)
        self.panel.device(dict(revision=self.revision(), id=SID, action="enable"))
        config, _ = self.store.read()
        self.assertEqual(config["devices"][0]["offset"], 350)
        self.assertEqual(config["apikey"], "preserved-secret")
        self.assertEqual(config["future_setting"], {"value": 42})
        self.assertEqual(self.start.call_count, 2)
        self.assertEqual(self.stop.call_count, 2)
        backups = list((Path(self.tmp.name) / "web-backups").glob("*.json"))
        self.assertEqual(len(backups), 2)

    def test_stale_revision_does_not_stop_or_overwrite(self):
        original = self.store.path.read_bytes()
        with self.assertRaises(Problem) as error:
            self.panel.device(dict(revision="stale", id=SID, action="remove"))
        self.assertEqual(error.exception.code, 409)
        self.assertEqual(original, self.store.path.read_bytes())
        self.stop.assert_not_called()

    def test_invalid_json_is_left_untouched(self):
        self.store.path.write_text("{broken")
        with self.assertRaises(Problem):
            self.panel.state()
        self.assertEqual(self.store.path.read_text(), "{broken")

    def test_backups_are_bounded(self):
        for _ in range(23):
            self.store.write(self.store.read()[0])
        self.assertEqual(len(list((Path(self.tmp.name) / "web-backups").glob("*.json"))), 20)

    def test_state_does_not_expose_api_key(self):
        self.assertNotIn("preserved-secret", json.dumps(self.panel.state()))

    def test_imported_defaults_match_upstream(self):
        config, _ = self.store.read()
        config.pop("mute_ads")
        config.pop("skip_ads")
        config["skip_categories"] = None
        self.store.write(config)
        settings = self.panel.state()["settings"]
        self.assertFalse(settings["mute_ads"])
        self.assertFalse(settings["skip_ads"])
        self.assertEqual(settings["skip_categories"], ["sponsor"])

    def test_device_probe_restrictions(self):
        self.assertEqual(self.panel.allowed_ip("192.168.52.2"), "192.168.52.2")
        for value in (
            "8.8.8.8",
            "127.0.0.1",
            "169.254.1.2",
            "192.168.30.11",
            "192.168.52.255",
            "192.168.52.0",
            "::1",
            "example.com",
            None,
        ):
            with self.subTest(value=value), self.assertRaises(Problem):
                self.panel.allowed_ip(value)

    def test_probe_and_add_deduplicates_and_requires_recent_candidate(self):
        with patch.object(
            self.panel, "helper", return_value={"screen_id": SID, "name": "Found TV"}
        ):
            result = self.panel.probe({"ip": "192.168.52.2"})
        self.panel.add(
            dict(revision=self.revision(), candidate=result["candidate"], name="Basement")
        )
        config, _ = self.store.read()
        self.assertEqual(len(config["devices"]), 1)
        self.assertEqual(config["_web_device_hosts"][SID], "192.168.52.2")
        self.panel.candidates[result["candidate"]]["expires"] = 0
        with self.assertRaises(Problem):
            self.panel.add(dict(revision=self.revision(), candidate=result["candidate"]))

    def test_scan_filters_disallowed_networks(self):
        with patch.object(
            self.panel,
            "helper",
            return_value={
                "devices": [{"ip": "192.168.52.2"}, {"ip": "192.168.30.11"}, {"ip": "8.8.8.8"}]
            },
        ):
            self.assertEqual(self.panel.scan()["devices"], [{"ip": "192.168.52.2"}])

    def test_settings_validation_and_preservation(self):
        settings = {
            k: DEFAULT[k]
            for k in (
                "mute_ads",
                "skip_ads",
                "skip_count_tracking",
                "skip_categories",
                "minimum_skip_length",
            )
        }
        settings["minimum_skip_length"] = float("nan")
        with self.assertRaises(Problem):
            self.panel.settings(dict(revision=self.revision(), settings=settings))
        self.stop.assert_not_called()
        settings["minimum_skip_length"] = 2
        settings["skip_categories"] = []
        self.panel.settings(dict(revision=self.revision(), settings=settings))
        self.assertEqual(self.store.read()[0]["apikey"], "preserved-secret")
        self.assertEqual(self.panel.state()["settings"]["skip_categories"], [])

    def test_http_auth_csrf_origin_and_logout(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.panel = self.panel
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def request(method, path, body=None, headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            headers = dict(headers or {})
            if body is not None:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = conn.getresponse()
            status, response_headers, raw = (
                response.status,
                dict(response.getheaders()),
                response.read(),
            )
            conn.close()
            return status, response_headers, json.loads(raw)

        self.assertEqual(request("GET", "/api/state")[0], 401)
        status, headers, body = request("POST", "/api/login", {"password": "test-password-123"})
        self.assertEqual(status, 200)
        auth = {"Cookie": headers["Set-Cookie"].split(";")[0]}
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertEqual(request("GET", "/api/state", headers=auth)[0], 200)
        self.assertEqual(request("POST", "/api/service", {}, auth)[0], 403)
        auth["X-CSRF-Token"] = body["csrf"]
        self.assertEqual(
            request("POST", "/api/service", {}, {**auth, "Origin": "https://evil.example"})[0], 403
        )
        self.assertEqual(
            request("POST", "/api/service", {"action": "pause", "revision": self.revision()}, auth)[
                0
            ],
            200,
        )
        self.assertTrue(self.store.read()[0]["_web_service_paused"])
        self.assertEqual(request("POST", "/api/logout", {}, auth)[0], 200)
        self.assertEqual(request("GET", "/api/state", headers=auth)[0], 401)


class WorkerTests(unittest.TestCase):
    def test_real_child_process_redaction_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            config = copy.deepcopy(DEFAULT)
            config["devices"] = [dict(screen_id=SID, name="TV", offset=0)]
            store.write(config)
            script = "import time; print('Refreshed auth, lounge id token SECRET', flush=True); time.sleep(30)"
            worker = Worker(store, [sys.executable, "-u", "-c", script], folder, emit=False)
            try:
                worker.start()
                self.assertTrue(worker.status()["running"])
                deadline = time.time() + 4
                while worker.seq < 2 and time.time() < deadline:
                    time.sleep(0.02)
                self.assertNotIn("SECRET", json.dumps(list(worker.logs)))
                self.assertTrue(any("hidden" in x["message"] for x in worker.logs))
            finally:
                worker.stop()
            self.assertFalse(worker.status()["running"])
            config["devices"] = []
            store.write(config)
            worker.start()
            self.assertFalse(worker.status()["running"])

    def test_redaction(self):
        self.assertEqual(redact("Playing video with 0 segments"), "Playing video with 0 segments")
        self.assertNotIn(SID, redact("iSponsorBlockTV-" + SID + " - INFO - Playing"))
        for line in (
            "Authorization: secret",
            "cookie: secret",
            "lounge id secret",
            "apikey=secret",
        ):
            self.assertNotIn("secret", redact(line))


if __name__ == "__main__":
    unittest.main()
