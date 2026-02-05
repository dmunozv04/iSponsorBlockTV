"""WebSocket handler for real-time updates."""

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from .state import DeviceState, StateManager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        
        async with self._lock:
            disconnected = set()
            for connection in self.active_connections:
                try:
                    if connection.client_state == WebSocketState.CONNECTED:
                        await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected clients
            self.active_connections -= disconnected
    
    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")


# Global connection manager
manager = ConnectionManager()


def create_status_callback(connection_manager: ConnectionManager):
    """Create a callback for status updates that broadcasts via WebSocket."""
    async def callback(screen_id: str, state: DeviceState):
        await connection_manager.broadcast({
            "type": "device_status",
            "screen_id": screen_id,
            "data": state.to_dict(),
        })
    return callback


async def websocket_endpoint(websocket: WebSocket, state_manager: StateManager):
    """Handle WebSocket connections."""
    await manager.connect(websocket)
    
    # Send initial status
    await manager.send_personal(websocket, {
        "type": "initial_status",
        "data": state_manager.get_status(),
    })
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                
                if msg_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif msg_type == "get_status":
                    await manager.send_personal(websocket, {
                        "type": "status",
                        "data": state_manager.get_status(),
                    })
                else:
                    logger.warning(f"Unknown WebSocket message type: {msg_type}")
            
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
    
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
