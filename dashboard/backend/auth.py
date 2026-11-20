"""Optional password sign-in and session management for the web dashboard."""

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import HTTPException

from iSponsorBlockTV.config_store import atomic_write_json

COOKIE_NAME = "isponsorblocktv_session"
SESSION_LIFETIME = 12 * 60 * 60
ATTEMPT_WINDOW = 15 * 60


def password_hash(password, salt):
    """Derive a hex-encoded scrypt hash for a password and hex salt."""
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt),
        n=32768,
        r=8,
        p=1,
        dklen=64,
        maxmem=64 * 1024 * 1024,
    ).hex()


def equal(left, right):
    """Compare two strings in constant time."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def validate_username(username):
    """Validate dashboard username length and character constraints."""
    if not isinstance(username, str) or not re.fullmatch(r"[^:\x00-\x1f\x7f]{1,128}", username):
        raise ValueError(
            "Choose a username of 1-128 characters without colons or control characters"
        )
    if not username.strip():
        raise ValueError("Username cannot be blank")


def validate_password(password):
    """Validate dashboard password length and character constraints."""
    if not isinstance(password, str) or not re.fullmatch(r"[^\x00-\x1f\x7f]{12,256}", password):
        raise ValueError("Choose a password of 12-256 characters without control characters")


class DashboardAuth:
    """Manage persisted dashboard credentials and active Starlette sessions."""

    def __init__(
        self, path, bootstrap_password=None, bootstrap_username="admin", now=time.monotonic
    ):
        self.path = Path(path)
        self.now = now
        self.active_sessions = deque(maxlen=20)
        self.attempts = {}
        self.lock = threading.RLock()
        try:
            self.saved = json.loads(self.path.read_text(encoding="utf-8"))
            self._validate_saved()
        except FileNotFoundError:
            self.saved = {"enabled": False, "username": "admin", "salt": "", "hash": ""}
            if bootstrap_password:
                validate_username(bootstrap_username)
                validate_password(bootstrap_password)
                salt = secrets.token_hex(16)
                self._save(
                    {
                        "enabled": True,
                        "username": bootstrap_username,
                        "salt": salt,
                        "hash": password_hash(bootstrap_password, salt),
                    }
                )
        except (ValueError, TypeError, KeyError) as error:
            raise RuntimeError(
                "Dashboard security settings are invalid; refusing to start"
            ) from error

    def _validate_saved(self):
        saved = self.saved
        if not isinstance(saved, dict) or set(saved) != {"enabled", "username", "salt", "hash"}:
            raise ValueError("Invalid security document")
        if type(saved["enabled"]) is not bool:
            raise ValueError("Invalid enabled flag")
        validate_username(saved["username"])
        if not isinstance(saved["salt"], str) or not isinstance(saved["hash"], str):
            raise TypeError("Invalid credential fields")
        has_credentials = bool(saved["salt"] or saved["hash"])
        if has_credentials and (
            not re.fullmatch(r"[0-9a-f]{32}", saved["salt"])
            or not re.fullmatch(r"[0-9a-f]{128}", saved["hash"])
        ):
            raise ValueError("Invalid password hash")
        if saved["enabled"] and not has_credentials:
            raise ValueError("Sign-in requires credentials")

    def _save(self, saved):
        atomic_write_json(self.path, saved, indent=2, prefix=".dashboard-auth-")
        self.saved = saved

    @property
    def enabled(self):
        """Return whether dashboard sign-in is currently enabled."""
        return self.saved["enabled"]

    def settings(self):
        """Return public security configuration without credential hashes."""
        return {
            "enabled": self.enabled,
            "username": self.saved["username"],
            "password_configured": bool(self.saved["hash"]),
        }

    def is_authenticated(self, request):
        """Return True if the request carries an active authenticated session."""
        sid = request.session.get("sid")
        with self.lock:
            return bool(self.enabled and sid and sid in self.active_sessions)

    def snapshot(self, request):
        """Return current authentication state for the dashboard client."""
        authenticated = self.is_authenticated(request)
        return {
            "enabled": self.enabled,
            "authenticated": authenticated,
            **({"username": self.saved["username"]} if authenticated else {}),
        }

    def _sign_in(self, request):
        sid = secrets.token_urlsafe(16)
        self.active_sessions.append(sid)
        request.session.clear()
        request.session["sid"] = sid
        return {"enabled": True, "authenticated": True, "username": self.saved["username"]}

    def _revoke(self, request):
        sid = request.session.get("sid")
        if sid in self.active_sessions:
            self.active_sessions.remove(sid)

    def _verify(self, username, password, ip):
        now = self.now()
        self.attempts = {key: value for key, value in self.attempts.items() if value[1] > now}
        count, deadline = self.attempts.get(ip, (0, now + ATTEMPT_WINDOW))
        if count >= 10 or (ip not in self.attempts and len(self.attempts) >= 1000):
            raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
        self.attempts[ip] = (count + 1, deadline)
        actual = password_hash(password, self.saved["salt"])
        valid = equal(username, self.saved["username"]) & equal(actual, self.saved["hash"])
        if not valid:
            raise HTTPException(401, "Incorrect username or password")
        self.attempts.pop(ip, None)

    def login(self, username, password, request):
        """Authenticate credentials and start a new session."""
        with self.lock:
            if not self.enabled:
                raise HTTPException(409, "Dashboard sign-in is not enabled")
            self._verify(username, password, request.client.host if request.client else "unknown")
            self._revoke(request)
            return self._sign_in(request)

    def logout(self, request):
        """Revoke the current session and clear the session cookie."""
        with self.lock:
            self._revoke(request)
            request.session.clear()
            return {"enabled": self.enabled, "authenticated": False}

    def update(self, values, request):
        """Update dashboard login settings and invalidate other active sessions."""
        with self.lock:
            username = values.username.strip()
            try:
                validate_username(username)
                if values.password:
                    validate_password(values.password)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            if self.enabled:
                try:
                    self._verify(
                        self.saved["username"],
                        values.current_password,
                        request.client.host if request.client else "unknown",
                    )
                except HTTPException as error:
                    if error.status_code == 401:
                        raise HTTPException(400, "Current password is incorrect") from error
                    raise
            saved = {**self.saved, "enabled": values.enabled, "username": username}
            if values.password:
                saved["salt"] = secrets.token_hex(16)
                saved["hash"] = password_hash(values.password, saved["salt"])
            if saved["enabled"] and not saved["hash"]:
                raise HTTPException(422, "Set a password before enabling sign-in")
            try:
                self._save(saved)
            except OSError as error:
                raise HTTPException(500, "Cannot save dashboard security settings") from error
            self.active_sessions.clear()
            session = self._sign_in(request) if self.enabled else self.logout(request)
            return {**self.settings(), "session": session}
