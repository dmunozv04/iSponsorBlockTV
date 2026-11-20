"""FastAPI backend serving the optional iSponsorBlockTV web dashboard."""

import math
import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
)
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from dashboard.backend.auth import COOKIE_NAME, SESSION_LIFETIME, DashboardAuth
from iSponsorBlockTV.api_helpers import ApiHelper
from iSponsorBlockTV.config_store import (
    DEFAULT_CONFIG,
    normalize_config,
    read_config,
    write_config,
)
from iSponsorBlockTV.constants import skip_categories


class PairRequest(BaseModel):
    """Payload for pairing a YouTube for TV screen via TV code."""

    model_config = ConfigDict(extra="forbid")
    code: StrictStr = Field(min_length=1, max_length=64)
    name: StrictStr = Field(default="", max_length=4096)
    offset: StrictInt | StrictFloat = 0

    @field_validator("offset")
    @classmethod
    def _finite_offset(cls, value):
        if not math.isfinite(value):
            raise ValueError("offset must be a finite number")
        return value


class LoginRequest(BaseModel):
    """Payload for authenticating into the dashboard."""

    model_config = ConfigDict(extra="forbid")
    username: StrictStr = Field(min_length=1, max_length=128)
    password: StrictStr = Field(min_length=1, max_length=256)


class SecurityRequest(BaseModel):
    """Payload for updating dashboard sign-in settings."""

    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    username: StrictStr = Field(min_length=1, max_length=128)
    password: StrictStr = Field(default="", max_length=256)
    current_password: StrictStr = Field(default="", max_length=256)


def create_app(config_path=None, static_dir=None, password=None, password_file=None):
    """Create and configure the FastAPI application instance."""
    config_path = Path(config_path or os.environ.get("CONFIG_PATH", "/app/data/config.json"))
    static_dir = Path(static_dir or os.environ.get("STATIC_DIR", "/app/static")).resolve()

    @asynccontextmanager
    async def lifespan(lifespan_app):
        auth_path = config_path.with_name("dashboard-auth.json")
        secret = None
        if not auth_path.exists():
            configured_file = password_file or os.environ.get("DASHBOARD_PASSWORD_FILE")
            secret = password if password is not None else os.environ.get("DASHBOARD_PASSWORD")
            if configured_file:
                secret = Path(configured_file).read_text(encoding="utf-8").rstrip("\r\n")
        lifespan_app.state.auth = DashboardAuth(
            auth_path,
            secret,
            os.environ.get("DASHBOARD_USERNAME", "admin"),
        )
        yield

    application = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @application.middleware("http")
    async def authenticate(request: Request, call_next):
        """Enforce same-origin writes, optional authentication, and security headers."""
        path = request.url.path
        mutation = request.method not in ("GET", "HEAD", "OPTIONS")
        if path.startswith("/api/"):
            if mutation:
                origin = request.headers.get("origin")
                if origin:
                    parsed_origin = urlsplit(origin)
                    host = request.headers.get("host", "")
                    allowed_scheme = parsed_origin.scheme == request.url.scheme or (
                        parsed_origin.scheme == "https" and request.url.scheme == "http"
                    )
                    if not (allowed_scheme and origin == f"{parsed_origin.scheme}://{host}"):
                        return JSONResponse(
                            {"detail": "Cross-origin writes are not permitted"}, status_code=403
                        )
                if request.headers.get("sec-fetch-site") == "cross-site":
                    return JSONResponse(
                        {"detail": "Cross-origin writes are not permitted"}, status_code=403
                    )
                if (
                    request.headers.get("content-type", "").split(";")[0].lower()
                    != "application/json"
                ):
                    return JSONResponse({"detail": "Send a JSON request"}, status_code=415)
            public = path in ("/api/auth/session", "/api/auth/login")
            auth = request.app.state.auth
            if auth.enabled and not public:
                authenticated = await run_in_threadpool(auth.is_authenticated, request)
                if not authenticated:
                    return JSONResponse({"detail": "Sign in to continue"}, status_code=401)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    application.add_middleware(
        SessionMiddleware,
        secret_key=secrets.token_urlsafe(32),
        session_cookie=COOKIE_NAME,
        max_age=SESSION_LIFETIME,
        same_site="strict",
        https_only=False,
    )

    @application.get("/api/auth/session")
    def session(request: Request):
        """Return the current session authentication state."""
        return request.app.state.auth.snapshot(request)

    @application.post("/api/auth/login")
    def login(data: LoginRequest, request: Request):
        """Sign in with dashboard credentials."""
        return request.app.state.auth.login(data.username, data.password, request)

    @application.post("/api/auth/logout")
    def logout(request: Request):
        """Sign out and revoke the active session."""
        return request.app.state.auth.logout(request)

    @application.get("/api/security")
    def security(request: Request):
        """Return dashboard login configuration."""
        return request.app.state.auth.settings()

    @application.put("/api/security")
    def update_security(data: SecurityRequest, request: Request):
        """Update dashboard login configuration."""
        return request.app.state.auth.update(data, request)

    @application.get("/health")
    def health():
        """Return container liveness status."""
        return {"status": "ok"}

    def load_config():
        try:
            return read_config(config_path)
        except (ValueError, TypeError):
            raise HTTPException(409, "Stored configuration is invalid; restore a valid config.json")
        except OSError:
            raise HTTPException(500, "Cannot read the configuration directory")

    @application.get("/api/config")
    def get_config():
        """Read and return the current configuration."""
        return load_config()

    @application.get("/api/config/options")
    def config_options():
        """Return available SponsorBlock skip categories and default API URL."""
        return {
            "skip_categories": [
                {"value": value, "label": label} for label, value in skip_categories
            ],
            "sponsorblock_api_url": DEFAULT_CONFIG["sponsorblock_api_url"],
        }

    @application.post("/api/config")
    def update_config(config: dict):
        """Validate and persist an updated configuration."""
        try:
            saved = write_config(config_path, config)
            return {"status": "success", "config": saved}
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error))
        except OSError:
            raise HTTPException(500, "Cannot write the configuration directory")

    @application.post("/api/config/validate")
    def validate_config(config: dict):
        """Validate and normalize a configuration draft without saving."""
        try:
            return normalize_config(config)
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error))

    @application.post("/api/pair")
    async def pair_device(data: PairRequest):
        """Pair a YouTube for TV screen using a 12-digit TV code."""
        code = data.code.replace("-", "").replace(" ", "")
        if not re.fullmatch(r"[0-9]{12}", code):
            raise HTTPException(
                422, "Enter the 12-digit code from YouTube Settings > Link with TV code"
            )
        config = SimpleNamespace(**load_config())
        try:
            async with aiohttp.ClientSession(
                trust_env=config.use_proxy, timeout=aiohttp.ClientTimeout(total=20)
            ) as client_session:
                paired = await ApiHelper(config, client_session).pair_with_code(code)
            if not paired:
                raise HTTPException(
                    400, "Pairing code is invalid or expired. Request a new TV code."
                )
            return {
                "name": data.name or paired["name"] or "YouTube on TV",
                "screen_id": paired["screen_id"],
                "offset": data.offset,
            }
        except (aiohttp.ClientError, TimeoutError):
            raise HTTPException(502, "YouTube could not be reached. Try again shortly.")

    @application.get("/api/channels/search")
    async def search_channels(query: str = ""):
        """Search YouTube channels using the saved YouTube Data API key."""
        if not query.strip():
            return []
        if len(query) > 200:
            raise HTTPException(422, "Search must be at most 200 characters")
        config = SimpleNamespace(**load_config())
        if not config.apikey:
            raise HTTPException(400, "Save a YouTube API key before searching for channels")
        try:
            async with aiohttp.ClientSession(
                trust_env=config.use_proxy, timeout=aiohttp.ClientTimeout(total=20)
            ) as client_session:
                results = await ApiHelper(config, client_session).search_channels(query)
            return [
                {"id": result[0], "name": result[1], "subscribers": result[2]} for result in results
            ]
        except ValueError:
            raise HTTPException(
                400, "YouTube rejected the search. Check the saved API key and quota."
            )
        except (aiohttp.ClientError, TimeoutError, KeyError, IndexError):
            raise HTTPException(502, "Channel search is unavailable. Try again shortly.")

    if (static_dir / "assets").is_dir():
        application.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @application.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve static frontend assets or fall back to the React app shell."""
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404)
        target = (static_dir / full_path).resolve()
        if not target.is_relative_to(static_dir):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if "." in Path(full_path).name:
            raise HTTPException(404)
        index = static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(503, "Dashboard assets are unavailable")
        return FileResponse(index)

    return application


app = create_app()
