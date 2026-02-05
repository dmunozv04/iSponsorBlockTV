"""FastAPI application for iSponsorBlockTV web interface."""

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from appdirs import user_data_dir

from ..helpers import Config
from ..constants import skip_categories as SKIP_CATEGORIES
from .auth import AuthManager, hash_password, verify_password, is_auth_configured
from .state import StateManager
from .websocket import manager as ws_manager, create_status_callback, websocket_endpoint

logger = logging.getLogger(__name__)

# Get data directory
DATA_DIR = os.getenv("iSPBTV_data_dir") or user_data_dir("iSponsorBlockTV", "dmunozv04")

# Global state
_config: Optional[Config] = None
_state_manager: Optional[StateManager] = None
_auth_manager: Optional[AuthManager] = None

security = HTTPBasic(auto_error=False)


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config(DATA_DIR)
    return _config


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager(get_config())
        # Register WebSocket callback
        _state_manager.add_status_callback(create_status_callback(ws_manager))
    return _state_manager


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager(get_config())
    return _auth_manager


def reload_config():
    """Reload config from disk."""
    global _config, _auth_manager
    _config = Config(DATA_DIR)
    _auth_manager = AuthManager(_config)
    return _config


async def verify_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> str:
    """Verify authentication - returns username or raises 401/403."""
    config = get_config()
    
    if not is_auth_configured(config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication not configured",
        )
    
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    username_correct = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        config.web_username.encode("utf-8"),
    )
    password_correct = verify_password(credentials.password, config.web_password_hash)
    
    if not (username_correct and password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting iSponsorBlockTV Web Interface")
    yield
    # Cleanup
    state_manager = get_state_manager()
    if state_manager.is_running:
        await state_manager.stop()
    logger.info("Shutting down iSponsorBlockTV Web Interface")


app = FastAPI(
    title="iSponsorBlockTV",
    description="Web interface for iSponsorBlockTV",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class AuthSetupRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class DeviceConfig(BaseModel):
    screen_id: str
    name: str = "YouTube on TV"
    offset: int = 0


class PairRequest(BaseModel):
    pairing_code: str


class ChannelWhitelist(BaseModel):
    id: str
    name: str


class ConfigUpdate(BaseModel):
    skip_categories: Optional[List[str]] = None
    skip_count_tracking: Optional[bool] = None
    mute_ads: Optional[bool] = None
    skip_ads: Optional[bool] = None
    minimum_skip_length: Optional[int] = None
    auto_play: Optional[bool] = None
    join_name: Optional[str] = None
    apikey: Optional[str] = None
    channel_whitelist: Optional[List[ChannelWhitelist]] = None
    use_proxy: Optional[bool] = None


# ============ Auth Endpoints ============

@app.get("/api/auth/status")
async def auth_status():
    """Check if authentication is configured."""
    config = get_config()
    return {"configured": is_auth_configured(config)}


@app.post("/api/auth/setup")
async def setup_auth(request: AuthSetupRequest):
    """Set up initial authentication credentials."""
    config = get_config()
    
    if is_auth_configured(config):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication already configured",
        )
    
    auth_manager = get_auth_manager()
    if auth_manager.setup(request.username, request.password):
        reload_config()
        return {"message": "Authentication configured successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Failed to configure authentication",
    )


@app.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    username: str = Depends(verify_auth),
):
    """Change the current password."""
    auth_manager = get_auth_manager()
    
    if auth_manager.change_password(request.old_password, request.new_password):
        reload_config()
        return {"message": "Password changed successfully"}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid old password",
    )


@app.get("/api/auth/verify")
async def verify_auth_endpoint(username: str = Depends(verify_auth)):
    """Verify current credentials."""
    return {"username": username, "authenticated": True}


# ============ Config Endpoints ============

@app.get("/api/config")
async def get_config_endpoint(username: str = Depends(verify_auth)):
    """Get current configuration."""
    config = get_config()
    return {
        "devices": [
            {"screen_id": d.screen_id if hasattr(d, "screen_id") else d.get("screen_id"),
             "name": d.name if hasattr(d, "name") else d.get("name", "Unknown"),
             "offset": int((d.offset if hasattr(d, "offset") else d.get("offset", 0)) * 1000)}
            for d in config.devices
        ],
        "skip_categories": config.skip_categories,
        "skip_count_tracking": config.skip_count_tracking,
        "mute_ads": config.mute_ads,
        "skip_ads": config.skip_ads,
        "minimum_skip_length": config.minimum_skip_length,
        "auto_play": config.auto_play,
        "join_name": config.join_name,
        "apikey": config.apikey,
        "channel_whitelist": config.channel_whitelist,
        "use_proxy": config.use_proxy,
    }


@app.put("/api/config")
async def update_config_endpoint(
    update: ConfigUpdate,
    username: str = Depends(verify_auth),
):
    """Update configuration."""
    config = get_config()
    
    if update.skip_categories is not None:
        # Validate categories
        valid_categories = [c[1] for c in SKIP_CATEGORIES]
        for cat in update.skip_categories:
            if cat not in valid_categories:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category: {cat}",
                )
        config.skip_categories = update.skip_categories
    
    if update.skip_count_tracking is not None:
        config.skip_count_tracking = update.skip_count_tracking
    
    if update.mute_ads is not None:
        config.mute_ads = update.mute_ads
    
    if update.skip_ads is not None:
        config.skip_ads = update.skip_ads
    
    if update.minimum_skip_length is not None:
        config.minimum_skip_length = update.minimum_skip_length
    
    if update.auto_play is not None:
        config.auto_play = update.auto_play
    
    if update.join_name is not None:
        config.join_name = update.join_name
    
    if update.apikey is not None:
        config.apikey = update.apikey
    
    if update.channel_whitelist is not None:
        config.channel_whitelist = [
            {"id": c.id, "name": c.name} for c in update.channel_whitelist
        ]
    
    if update.use_proxy is not None:
        config.use_proxy = update.use_proxy
    
    config.save()
    reload_config()
    
    return {"message": "Configuration updated"}


@app.get("/api/config/categories")
async def get_categories():
    """Get available skip categories."""
    return [
        {"value": cat[1], "label": cat[0]}
        for cat in SKIP_CATEGORIES
    ]


# ============ Device Endpoints ============

@app.get("/api/devices")
async def list_devices(username: str = Depends(verify_auth)):
    """List all configured devices."""
    config = get_config()
    state_manager = get_state_manager()
    status_dict = state_manager.get_status()
    
    devices = []
    for d in config.devices:
        screen_id = d.screen_id if hasattr(d, "screen_id") else d.get("screen_id")
        device_status = status_dict.get("devices", {}).get(screen_id, {})
        devices.append({
            "screen_id": screen_id,
            "name": d.name if hasattr(d, "name") else d.get("name", "Unknown"),
            "offset": int((d.offset if hasattr(d, "offset") else d.get("offset", 0)) * 1000),
            "status": device_status.get("status", "disconnected"),
            "current_video": device_status.get("current_video"),
            "current_video_title": device_status.get("current_video_title"),
        })
    
    return devices


@app.post("/api/devices")
async def add_device(
    device: DeviceConfig,
    username: str = Depends(verify_auth),
):
    """Add a new device."""
    config = get_config()
    
    # Check if device already exists
    for d in config.devices:
        existing_id = d.screen_id if hasattr(d, "screen_id") else d.get("screen_id")
        if existing_id == device.screen_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Device already exists",
            )
    
    state_manager = get_state_manager()
    await state_manager.add_device({
        "screen_id": device.screen_id,
        "name": device.name,
        "offset": device.offset,
    })
    reload_config()
    
    return {"message": "Device added", "device": device.model_dump()}


@app.delete("/api/devices/{screen_id}")
async def remove_device(
    screen_id: str,
    username: str = Depends(verify_auth),
):
    """Remove a device."""
    state_manager = get_state_manager()
    await state_manager.remove_device(screen_id)
    reload_config()
    
    return {"message": "Device removed"}


@app.put("/api/devices/{screen_id}")
async def update_device(
    screen_id: str,
    device: DeviceConfig,
    username: str = Depends(verify_auth),
):
    """Update a device's configuration."""
    config = get_config()
    
    found = False
    new_devices = []
    for d in config.devices:
        existing_id = d.screen_id if hasattr(d, "screen_id") else d.get("screen_id")
        if existing_id == screen_id:
            found = True
            new_devices.append({
                "screen_id": device.screen_id,
                "name": device.name,
                "offset": device.offset,
            })
        else:
            if hasattr(d, "screen_id"):
                new_devices.append({
                    "screen_id": d.screen_id,
                    "name": d.name,
                    "offset": int(d.offset * 1000),
                })
            else:
                new_devices.append(d)
    
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )
    
    config.devices = new_devices
    config.save()
    reload_config()
    
    return {"message": "Device updated"}


@app.get("/api/devices/discover")
async def discover_devices(username: str = Depends(verify_auth)):
    """Discover devices on the local network via DIAL/SSDP."""
    state_manager = get_state_manager()
    
    try:
        devices = await state_manager.discover_devices()
        return devices
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {str(e)}",
        )


@app.post("/api/devices/pair")
async def pair_device(
    request: PairRequest,
    username: str = Depends(verify_auth),
):
    """Pair with a device using a pairing code."""
    state_manager = get_state_manager()
    
    device = await state_manager.pair_device(request.pairing_code)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to pair device. Check the pairing code and try again.",
        )
    
    return device


# ============ Monitoring Endpoints ============

@app.get("/api/status")
async def get_status(username: str = Depends(verify_auth)):
    """Get current monitoring status."""
    state_manager = get_state_manager()
    return state_manager.get_status()


@app.post("/api/start")
async def start_monitoring(username: str = Depends(verify_auth)):
    """Start monitoring all devices."""
    state_manager = get_state_manager()
    
    if state_manager.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monitoring is already running",
        )
    
    try:
        await state_manager.start()
        return {"message": "Monitoring started"}
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start: {str(e)}",
        )


@app.post("/api/stop")
async def stop_monitoring(username: str = Depends(verify_auth)):
    """Stop monitoring all devices."""
    state_manager = get_state_manager()
    
    if not state_manager.is_running:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monitoring is not running",
        )
    
    await state_manager.stop()
    return {"message": "Monitoring stopped"}


@app.post("/api/restart")
async def restart_monitoring(username: str = Depends(verify_auth)):
    """Restart monitoring with updated config."""
    state_manager = get_state_manager()
    await state_manager.restart()
    return {"message": "Monitoring restarted"}


# ============ Channel Search ============

@app.get("/api/channels/search")
async def search_channels(
    q: str,
    username: str = Depends(verify_auth),
):
    """Search for YouTube channels."""
    config = get_config()
    
    if not config.apikey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube API key not configured",
        )
    
    state_manager = get_state_manager()
    
    # Ensure web session exists
    if not state_manager._web_session:
        import aiohttp
        state_manager._web_session = await state_manager._create_web_session()
    
    if not state_manager._api_helper:
        from ..api_helpers import ApiHelper
        state_manager._api_helper = ApiHelper(config, state_manager._web_session)
    
    try:
        results = await state_manager._api_helper.search_channels(
            q, config.apikey, state_manager._web_session
        )
        return [
            {"id": r[0], "name": r[1], "subscribers": r[2]}
            for r in results
        ]
    except Exception as e:
        logger.error(f"Channel search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


# ============ WebSocket ============

@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    state_manager = get_state_manager()
    await websocket_endpoint(websocket, state_manager)


# ============ Static Files (Frontend) ============

# Serve static files from the bundled frontend
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Don't serve index.html for API routes
        if full_path.startswith("api/") or full_path == "ws":
            raise HTTPException(status_code=404)
        
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend not built")
