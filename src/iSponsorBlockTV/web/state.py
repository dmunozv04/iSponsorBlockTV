"""State management for the web interface."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import aiohttp

from ..helpers import Config, Device
from ..main import DeviceListener
from ..api_helpers import ApiHelper

logger = logging.getLogger(__name__)


class DeviceStatus(str, Enum):
    """Device connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class DeviceState:
    """Current state of a device."""
    screen_id: str
    name: str
    status: DeviceStatus = DeviceStatus.DISCONNECTED
    current_video: Optional[str] = None
    current_video_title: Optional[str] = None
    last_skip_time: Optional[datetime] = None
    last_skip_category: Optional[str] = None
    error_message: Optional[str] = None
    listener: Optional[DeviceListener] = field(default=None, repr=False)
    task: Optional[asyncio.Task] = field(default=None, repr=False)
    refresh_task: Optional[asyncio.Task] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "screen_id": self.screen_id,
            "name": self.name,
            "status": self.status.value,
            "current_video": self.current_video,
            "current_video_title": self.current_video_title,
            "last_skip_time": self.last_skip_time.isoformat() if self.last_skip_time else None,
            "last_skip_category": self.last_skip_category,
            "error_message": self.error_message,
        }


class StateManager:
    """Manages the state of all devices and the monitoring service."""
    
    def __init__(self, config: Config):
        self.config = config
        self._devices: Dict[str, DeviceState] = {}
        self._web_session: Optional[aiohttp.ClientSession] = None
        self._api_helper: Optional[ApiHelper] = None
        self._running = False
        self._status_callbacks: Set[Callable[[str, DeviceState], Any]] = set()
        self._lock = asyncio.Lock()
    
    @property
    def is_running(self) -> bool:
        """Check if monitoring is running."""
        return self._running
    
    @property
    def devices(self) -> Dict[str, DeviceState]:
        """Get all device states."""
        return self._devices.copy()
    
    def add_status_callback(self, callback: Callable[[str, DeviceState], Any]):
        """Add a callback for status changes."""
        self._status_callbacks.add(callback)
    
    def remove_status_callback(self, callback: Callable[[str, DeviceState], Any]):
        """Remove a status callback."""
        self._status_callbacks.discard(callback)
    
    async def _notify_status_change(self, screen_id: str, state: DeviceState):
        """Notify all callbacks of a status change."""
        for callback in self._status_callbacks:
            try:
                result = callback(screen_id, state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    async def _create_web_session(self) -> aiohttp.ClientSession:
        """Create an aiohttp session."""
        return aiohttp.ClientSession(trust_env=self.config.use_proxy)
    
    def _create_device_callback(self, screen_id: str):
        """Create a callback for device status updates."""
        def callback(event_type: str, data: dict):
            if screen_id not in self._devices:
                return
            
            state = self._devices[screen_id]
            
            if event_type == "connected":
                state.status = DeviceStatus.CONNECTED
                state.error_message = None
            elif event_type == "disconnected":
                state.status = DeviceStatus.DISCONNECTED
            elif event_type == "error":
                state.status = DeviceStatus.ERROR
                state.error_message = data.get("message", "Unknown error")
            elif event_type == "now_playing":
                state.current_video = data.get("video_id")
                state.current_video_title = data.get("title")
            elif event_type == "skipped":
                state.last_skip_time = datetime.now()
                state.last_skip_category = data.get("category")
            
            # Schedule notification
            asyncio.create_task(self._notify_status_change(screen_id, state))
        
        return callback
    
    async def start(self):
        """Start monitoring all configured devices."""
        async with self._lock:
            if self._running:
                logger.warning("Monitoring is already running")
                return
            
            logger.info("Starting device monitoring")
            self._running = True
            
            # Create web session
            self._web_session = await self._create_web_session()
            self._api_helper = ApiHelper(self.config, self._web_session)
            
            # Reload config to get fresh device list
            self.config = Config(self.config.data_dir)
            self.config.validate()
            
            # Start monitoring each device
            for device in self.config.devices:
                await self._start_device(device)
    
    async def _start_device(self, device: Device):
        """Start monitoring a single device."""
        screen_id = device.screen_id
        
        # Create device state
        state = DeviceState(
            screen_id=screen_id,
            name=getattr(device, "name", "Unknown Device"),
            status=DeviceStatus.CONNECTING,
        )
        self._devices[screen_id] = state
        
        # Create listener
        listener = DeviceListener(device, self._api_helper, self.config)
        state.listener = listener
        
        # Create and start task
        async def run_listener():
            try:
                await listener.loop()
            except asyncio.CancelledError:
                logger.info(f"Device {screen_id} monitoring cancelled")
            except Exception as e:
                logger.error(f"Error monitoring device {screen_id}: {e}")
                state.status = DeviceStatus.ERROR
                state.error_message = str(e)
                await self._notify_status_change(screen_id, state)
        
        state.task = asyncio.create_task(run_listener())
        
        # Start refresh auth task
        async def run_refresh():
            try:
                await listener.refresh_auth_loop()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in refresh auth loop for {screen_id}: {e}")
        
        state.refresh_task = asyncio.create_task(run_refresh())
        
        await self._notify_status_change(screen_id, state)
    
    async def stop(self):
        """Stop monitoring all devices."""
        async with self._lock:
            if not self._running:
                logger.warning("Monitoring is not running")
                return
            
            logger.info("Stopping device monitoring")
            
            # Cancel all device tasks
            for screen_id, state in self._devices.items():
                if state.task and not state.task.done():
                    state.task.cancel()
                if state.refresh_task and not state.refresh_task.done():
                    state.refresh_task.cancel()
                if state.listener:
                    await state.listener.cancel()
                state.status = DeviceStatus.DISCONNECTED
                await self._notify_status_change(screen_id, state)
            
            # Wait for all tasks to complete
            tasks = [s.task for s in self._devices.values() if s.task]
            tasks += [s.refresh_task for s in self._devices.values() if s.refresh_task]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Close web session
            if self._web_session:
                await self._web_session.close()
                self._web_session = None
            
            self._api_helper = None
            self._devices.clear()
            self._running = False
    
    async def restart(self):
        """Restart monitoring with updated config."""
        await self.stop()
        await self.start()
    
    async def add_device(self, device_config: dict) -> bool:
        """Add a new device and start monitoring if running."""
        # Add to config
        self.config.devices.append(device_config)
        self.config.save()
        
        if self._running:
            # Reload config and start the new device
            device = Device(device_config)
            await self._start_device(device)
        
        return True
    
    async def remove_device(self, screen_id: str) -> bool:
        """Remove a device and stop its monitoring."""
        # Stop monitoring if running
        if screen_id in self._devices:
            state = self._devices[screen_id]
            if state.task and not state.task.done():
                state.task.cancel()
            if state.refresh_task and not state.refresh_task.done():
                state.refresh_task.cancel()
            if state.listener:
                await state.listener.cancel()
            del self._devices[screen_id]
        
        # Remove from config
        self.config.devices = [
            d for d in self.config.devices
            if (d.screen_id if isinstance(d, Device) else d.get("screen_id")) != screen_id
        ]
        self.config.save()
        
        return True
    
    def get_status(self) -> dict:
        """Get overall status."""
        return {
            "running": self._running,
            "device_count": len(self._devices),
            "devices": {
                screen_id: state.to_dict()
                for screen_id, state in self._devices.items()
            },
        }
    
    async def discover_devices(self) -> List[dict]:
        """Discover devices on the network."""
        if not self._web_session:
            self._web_session = await self._create_web_session()
        
        if not self._api_helper:
            self._api_helper = ApiHelper(self.config, self._web_session)
        
        return await self._api_helper.discover_youtube_devices_dial()
    
    async def pair_device(self, pairing_code: str) -> Optional[dict]:
        """Pair with a device using a pairing code."""
        from .. import ytlounge
        
        if not self._web_session:
            self._web_session = await self._create_web_session()
        
        try:
            lounge_controller = ytlounge.YtLoungeApi()
            await lounge_controller.change_web_session(self._web_session)
            
            # Clean up pairing code
            clean_code = int(pairing_code.replace("-", "").replace(" ", ""))
            
            paired = await lounge_controller.pair(clean_code)
            if not paired:
                return None
            
            return {
                "screen_id": lounge_controller.auth.screen_id,
                "name": lounge_controller.screen_name,
                "offset": 0,
            }
        except Exception as e:
            logger.error(f"Failed to pair device: {e}")
            return None
