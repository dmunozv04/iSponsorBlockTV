import pytest
from fastapi.testclient import TestClient

from dashboard.backend.main import create_app
from iSponsorBlockTV.api_helpers import ApiHelper


def sign_in(client, password="test-password-123"):
    result = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert result.status_code == 200
    return result


@pytest.fixture
def dashboard(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>dashboard</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("private", encoding="utf-8")
    app = create_app(tmp_path / "data" / "config.json", static, password="test-password-123")
    with TestClient(app) as client:
        yield client, tmp_path


def test_authentication_and_health(dashboard):
    client, _ = dashboard
    assert client.get("/health").json() == {"status": "ok"}
    # The app shell is public so it can render the login page; configuration is protected.
    for path in ("/", "/assets/app.js"):
        assert client.get(path).status_code == 200
    response = client.get("/api/config")
    assert response.status_code == 401
    assert "www-authenticate" not in response.headers
    assert client.get("/api/config", auth=("admin", "test-password-123")).status_code == 401
    sign_in(client)
    assert client.get("/api/config").status_code == 200


def test_save_validates_creates_directory_and_preserves_previous_config(dashboard):
    client, root = dashboard
    sign_in(client)
    response = client.post("/api/config", json={"join_name": "Living room"})
    assert response.status_code == 200
    assert response.json()["config"]["join_name"] == "Living room"
    before = (root / "data" / "config.json").read_bytes()
    assert client.post("/api/config", json={"devices": "broken"}).status_code == 422
    assert (root / "data" / "config.json").read_bytes() == before
    assert client.get("/api/config").headers["cache-control"] == "no-store"


def test_dashboard_options_can_be_saved_with_manual_channel_entry(dashboard):
    client, _ = dashboard
    assert client.get("/api/config/options").status_code == 401
    sign_in(client)
    response = client.get("/api/config/options")
    assert response.status_code == 200
    options = response.json()
    categories = [entry["value"] for entry in options["skip_categories"]]
    assert {"exclusive_access", "preview", "filler", "hook"} <= set(categories)
    saved = client.post(
        "/api/config",
        json={
            "skip_categories": categories,
            "sponsorblock_api_url": "https://sponsor.example/api",
            "apikey": "manual-entry-test-key",
            "channel_whitelist": [{"id": "UCmanual-channel", "name": "Manual channel"}],
        },
    )
    assert saved.status_code == 200
    reloaded = client.get("/api/config").json()
    assert reloaded == saved.json()["config"]
    assert reloaded["skip_categories"] == categories
    assert reloaded["sponsorblock_api_url"] == "https://sponsor.example/api/"
    assert reloaded["channel_whitelist"] == [{"id": "UCmanual-channel", "name": "Manual channel"}]


def test_invalid_stored_config_does_not_leak_contents(dashboard):
    client, root = dashboard
    sign_in(client)
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "config.json").write_text('{"apikey": "private",', encoding="utf-8")
    response = client.get("/api/config")
    assert response.status_code == 409
    assert "private" not in response.text


def test_read_only_config_still_allows_loading_and_json_validation(dashboard, monkeypatch):
    import dashboard.backend.main as module

    client, root = dashboard
    sign_in(client)
    assert client.post("/api/config", json={"join_name": "Original"}).status_code == 200
    before = (root / "data" / "config.json").read_bytes()

    def read_only(*_):
        raise PermissionError("Read-only configuration mount")

    monkeypatch.setattr(module, "write_config", read_only)
    assert client.get("/api/config").json()["join_name"] == "Original"
    response = client.post("/api/config/validate", json={"join_name": "Exported draft"})
    assert response.status_code == 200
    assert response.json()["join_name"] == "Exported draft"
    assert client.post("/api/config", json=response.json()).status_code == 500
    assert (root / "data" / "config.json").read_bytes() == before


def test_cross_origin_writes_are_rejected(dashboard):
    client, _ = dashboard
    sign_in(client)
    assert (
        client.post("/api/config", json={}, headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert (
        client.post("/api/config", json={}, headers={"Origin": "http://testserver"}).status_code
        == 200
    )


def test_static_traversal_and_unknown_api_routes_are_rejected(dashboard):
    client, _ = dashboard
    sign_in(client)
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    for path in ("/%2e%2e/secret.txt", "/assets/%2e%2e/%2e%2e/secret.txt", "/api/missing"):
        assert client.get(path).status_code == 404
    assert "private" not in client.get("/%2e%2e/secret.txt").text


def test_pairing_uses_current_upstream_helper_and_preserves_leading_zero(dashboard, monkeypatch):
    client, _ = dashboard
    sign_in(client)
    calls = []

    async def pair(self, code):
        calls.append(code)
        return {"screen_id": "current-screen-id", "name": "TV", "lounge_token": "not-returned"}

    monkeypatch.setattr(ApiHelper, "pair_with_code", pair)
    response = client.post("/api/pair", json={"code": "012-345-678-901", "offset": -200.5})
    assert response.status_code == 200
    assert calls == ["012345678901"]
    assert response.json() == {"screen_id": "current-screen-id", "name": "TV", "offset": -200.5}
    assert client.post("/api/pair", json={"code": "invalid"}).status_code == 422


def test_search_uses_complete_current_configuration(dashboard, monkeypatch):
    client, _ = dashboard
    sign_in(client)
    assert client.get("/api/channels/search?query=test").status_code == 400
    client.post("/api/config", json={"apikey": "test-key"})
    calls = []

    async def search(self, query):
        calls.append((self.apikey, self.sponsorblock_api_url, query))
        return [("UC123", "Channel", "1,000")]

    monkeypatch.setattr(ApiHelper, "search_channels", search)
    response = client.get("/api/channels/search?query=test")
    assert response.json() == [{"id": "UC123", "name": "Channel", "subscribers": "1,000"}]
    assert calls[0][0] == "test-key"


def test_fresh_installation_starts_without_authentication(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD_FILE", raising=False)
    with TestClient(create_app(tmp_path / "config.json", tmp_path)) as client:
        assert client.get("/api/auth/session").json() == {"enabled": False, "authenticated": False}
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/security").json()["password_configured"] is False


def test_password_file_bootstraps_form_sign_in_once(tmp_path):
    password_file = tmp_path / "password"
    password_file.write_text("file-password-123\n", encoding="utf-8")
    with TestClient(
        create_app(tmp_path / "config.json", tmp_path, password_file=password_file)
    ) as client:
        assert client.get("/api/config").status_code == 401
        sign_in(client, "file-password-123")
        assert client.get("/api/config").status_code == 200


@pytest.mark.parametrize(
    "origin",
    ["null", "http://testserver.evil.test", "http://testserver/path", "https://evil.test"],
)
def test_cross_origin_rejects_foreign_and_opaque_origins(dashboard, origin):
    client, _ = dashboard
    sign_in(client)
    assert client.post("/api/config", json={}, headers={"Origin": origin}).status_code == 403


def test_reverse_proxy_https_origin_allowed_and_http_downgrade_rejected(tmp_path, dashboard):
    client, _ = dashboard
    sign_in(client)
    assert (
        client.post("/api/config", json={}, headers={"Origin": "https://testserver"}).status_code
        == 200
    )
    with TestClient(
        create_app(tmp_path / "https" / "config.json", tmp_path, password="test-password-123"),
        base_url="https://testserver",
    ) as https_client:
        sign_in(https_client)
        assert (
            https_client.post(
                "/api/config", json={}, headers={"Origin": "http://testserver"}
            ).status_code
            == 403
        )


def test_import_validation_normalizes_without_saving(dashboard):
    client, root = dashboard
    sign_in(client)
    response = client.post("/api/config/validate", json={"join_name": "Imported"})
    assert response.status_code == 200
    assert response.json()["devices"] == []
    assert response.json()["join_name"] == "Imported"
    assert not (root / "data" / "config.json").exists()
    assert client.post("/api/config/validate", json={"devices": "invalid"}).status_code == 422
    assert not (root / "data" / "config.json").exists()


def test_import_validation_requires_authentication(dashboard):
    client, _ = dashboard
    assert client.post("/api/config/validate", json={}).status_code == 401


def test_logout_revokes_cookie_replay(dashboard):
    client, _ = dashboard
    sign_in(client)
    token = client.cookies.get("isponsorblocktv_session")
    response = client.post("/api/auth/logout", json={})
    assert response.status_code == 200
    assert response.json() == {"enabled": True, "authenticated": False}
    assert "expires=thu, 01 jan 1970 00:00:00 gmt" in response.headers["set-cookie"].lower()
    client.cookies.set("isponsorblocktv_session", token)
    assert client.get("/api/config").status_code == 401
    assert client.post("/api/config", json={}).status_code == 401


def test_session_cookie_and_cross_site_protection(dashboard):
    client, _ = dashboard
    response = sign_in(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "max-age=43200" in cookie
    assert client.get("/api/config").status_code == 200
    assert (
        client.post("/api/config", json={}, headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )


def test_security_change_requires_current_password_and_keeps_session_on_mistake(dashboard):
    client, _ = dashboard
    sign_in(client)
    for current in ("", "incorrect-password"):
        response = client.put(
            "/api/security",
            json={"enabled": False, "username": "admin", "current_password": current},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Current password is incorrect"
        assert client.get("/api/config").status_code == 200
    assert client.get("/api/security").json()["enabled"]


def test_disable_and_reenable_sign_in_with_existing_credentials(dashboard):
    client, _ = dashboard
    sign_in(client)
    response = client.put(
        "/api/security",
        json={"enabled": False, "username": "admin", "current_password": "test-password-123"},
    )
    assert response.status_code == 200
    assert not response.json()["session"]["authenticated"]
    assert client.get("/api/config").status_code == 200
    client.cookies.clear()
    response = client.put("/api/security", json={"enabled": True, "username": "admin"})
    assert response.status_code == 200
    assert response.json()["session"]["authenticated"]
    assert client.post("/api/config", json={}).status_code == 200


def test_password_change_revokes_other_sessions_and_rotates_current_session(dashboard):
    client, _ = dashboard
    sign_in(client)
    before = client.cookies.get("isponsorblocktv_session")
    other = TestClient(client.app)
    try:
        sign_in(other)
        response = client.put(
            "/api/security",
            json={
                "enabled": True,
                "username": "owner",
                "password": "new-password-123",
                "current_password": "test-password-123",
            },
        )
        assert response.status_code == 200
        assert client.cookies.get("isponsorblocktv_session") != before
        assert other.get("/api/config").status_code == 401
        assert client.get("/api/config").status_code == 200
        other.cookies.clear()
        assert (
            other.post(
                "/api/auth/login", json={"username": "admin", "password": "test-password-123"}
            ).status_code
            == 401
        )
        assert (
            other.post(
                "/api/auth/login", json={"username": "owner", "password": "new-password-123"}
            ).status_code
            == 200
        )
    finally:
        other.close()


def test_fresh_installation_enables_auth_without_exposing_password(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD_FILE", raising=False)
    path = tmp_path / "config.json"
    with TestClient(create_app(path, tmp_path)) as client:
        assert (
            client.put("/api/security", json={"enabled": True, "username": "owner"}).status_code
            == 422
        )
        assert (
            client.put(
                "/api/security", json={"enabled": True, "username": "owner", "password": "short"}
            ).status_code
            == 422
        )
        response = client.put(
            "/api/security",
            json={"enabled": True, "username": "owner", "password": "fresh-password-123"},
        )
        assert response.status_code == 200
        assert response.json()["session"]["authenticated"]
        assert "fresh-password-123" not in response.text
        settings = client.get("/api/security").json()
        assert set(settings) == {"enabled", "username", "password_configured"}
        assert "fresh-password-123" not in (tmp_path / "dashboard-auth.json").read_text()
        assert not path.exists()
    # Credentials survive a restart; old cookies do not.
    old_token = client.cookies.get("isponsorblocktv_session")
    with TestClient(create_app(path, tmp_path)) as restarted:
        restarted.cookies.set("isponsorblocktv_session", old_token)
        assert restarted.get("/api/config").status_code == 401
        response = restarted.post(
            "/api/auth/login", json={"username": "owner", "password": "fresh-password-123"}
        )
        assert response.status_code == 200


def test_bootstrap_does_not_reenable_explicitly_disabled_login(tmp_path):
    path = tmp_path / "config.json"
    with TestClient(create_app(path, tmp_path, password="test-password-123")) as client:
        sign_in(client)
        assert (
            client.put(
                "/api/security",
                json={
                    "enabled": False,
                    "username": "admin",
                    "current_password": "test-password-123",
                },
            ).status_code
            == 200
        )
    with TestClient(create_app(path, tmp_path, password="test-password-123")) as restarted:
        assert restarted.get("/api/auth/session").json()["enabled"] is False
        assert restarted.get("/api/config").status_code == 200


@pytest.mark.parametrize("enabled", [True, False])
def test_saved_auth_does_not_require_bootstrap_password_file(tmp_path, enabled):
    path = tmp_path / "config.json"
    secret = tmp_path / "bootstrap-password"
    secret.write_text("test-password-123", encoding="utf-8")
    with TestClient(create_app(path, tmp_path, password_file=secret)) as client:
        sign_in(client)
        if not enabled:
            assert (
                client.put(
                    "/api/security",
                    json={
                        "enabled": False,
                        "username": "admin",
                        "current_password": "test-password-123",
                    },
                ).status_code
                == 200
            )
    secret.unlink()
    with TestClient(create_app(path, tmp_path, password_file=secret)) as restarted:
        assert restarted.get("/api/auth/session").json()["enabled"] is enabled
        if enabled:
            sign_in(restarted)
        assert restarted.get("/api/config").status_code == 200


def test_invalid_cookies_do_not_authenticate(dashboard):
    client, _ = dashboard
    sign_in(client)
    client.cookies.clear()
    client.cookies.set("isponsorblocktv_session", "invalid")
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/auth/session").json()["authenticated"] is False


def test_login_is_rate_limited_and_attempt_window_expires(dashboard, monkeypatch):
    import dashboard.backend.auth as module

    client, _ = dashboard
    auth = client.app.state.auth
    original_hash = module.password_hash
    monkeypatch.setattr(module, "password_hash", lambda *_: "0" * 128)
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login", json={"username": "admin", "password": "incorrect"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "incorrect"}
        ).status_code
        == 429
    )
    now = auth.now()
    auth.now = lambda: now + module.ATTEMPT_WINDOW + 1
    monkeypatch.setattr(module, "password_hash", original_hash)
    sign_in(client)
    assert client.get("/api/config").status_code == 200


def test_login_rejects_cross_origin_and_non_json_requests(dashboard):
    client, _ = dashboard
    payload = {"username": "admin", "password": "test-password-123"}
    assert (
        client.post(
            "/api/auth/login", json=payload, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.post("/api/auth/login", data=payload).status_code == 415


def test_https_requests_authenticate_with_session_cookie(tmp_path):
    with TestClient(
        create_app(tmp_path / "config.json", tmp_path, password="test-password-123"),
        base_url="https://testserver",
    ) as client:
        sign_in(client)
        assert client.get("/api/config").status_code == 200


def test_invalid_security_file_fails_closed(tmp_path):
    (tmp_path / "dashboard-auth.json").write_text('{"enabled":false,"salt":null}', encoding="utf-8")
    with (
        pytest.raises(RuntimeError, match="security settings are invalid"),
        TestClient(create_app(tmp_path / "config.json", tmp_path)),
    ):
        pass
