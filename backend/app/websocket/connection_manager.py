import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("websocket")

class ConnectionManager:
    def __init__(self):
        # channel_name -> Set[WebSocket]
        self.rooms: Dict[str, Set[WebSocket]] = {
            "kitchen": set(),
            "staff": set(),
            "admin": set(),
        }
        # table_id -> Set[WebSocket]
        self.table_rooms: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "general", table_id: int = None):
        await websocket.accept()
        if table_id is not None:
            if table_id not in self.table_rooms:
                self.table_rooms[table_id] = set()
            self.table_rooms[table_id].add(websocket)
            logger.info(f"WebSocket connected to table_{table_id}")
        else:
            if channel not in self.rooms:
                self.rooms[channel] = set()
            self.rooms[channel].add(websocket)
            logger.info(f"WebSocket connected to channel '{channel}'")

    def disconnect(self, websocket: WebSocket, channel: str = "general", table_id: int = None):
        if table_id is not None and table_id in self.table_rooms:
            self.table_rooms[table_id].discard(websocket)
            if not self.table_rooms[table_id]:
                del self.table_rooms[table_id]
        elif channel in self.rooms:
            self.rooms[channel].discard(websocket)

    async def broadcast_to_channel(self, channel: str, message: dict):
        if channel in self.rooms:
            payload = json.dumps(message)
            stale_connections = []
            for ws in list(self.rooms[channel]):
                try:
                    await ws.send_text(payload)
                except Exception as e:
                    logger.warning(f"Error sending message to ws in channel {channel}: {e}")
                    stale_connections.append(ws)
            for dead_ws in stale_connections:
                self.rooms[channel].discard(dead_ws)

    async def broadcast_to_table(self, table_id: int, message: dict):
        if table_id in self.table_rooms:
            payload = json.dumps(message)
            stale_connections = []
            for ws in list(self.table_rooms[table_id]):
                try:
                    await ws.send_text(payload)
                except Exception as e:
                    logger.warning(f"Error sending message to table_{table_id}: {e}")
                    stale_connections.append(ws)
            for dead_ws in stale_connections:
                self.table_rooms[table_id].discard(dead_ws)

    async def broadcast_event(self, event_type: str, data: dict, table_id: int = None):
        """
        Universal event dispatcher:
        - Sends to kitchen channel if relevant to orders
        - Sends to staff channel if relevant to orders or service requests
        - Sends to admin channel for operational KPIs
        - Sends to table_id if table-specific
        """
        message = {
            "type": event_type,
            "data": data
        }
        
        # Broadcast to specific table if provided
        if table_id:
            await self.broadcast_to_table(table_id, message)
        
        # Order updates go to kitchen, staff, and admin
        if event_type.startswith("ORDER_"):
            await self.broadcast_to_channel("kitchen", message)
            await self.broadcast_to_channel("staff", message)
            await self.broadcast_to_channel("admin", message)
            
        # Service requests go to staff and admin
        elif event_type.startswith("REQUEST_") or event_type.startswith("SERVICE_"):
            await self.broadcast_to_channel("staff", message)
            await self.broadcast_to_channel("admin", message)
            
        # Table status updates go to staff and admin
        elif event_type.startswith("TABLE_"):
            await self.broadcast_to_channel("staff", message)
            await self.broadcast_to_channel("admin", message)

        # Payment updates go to admin, staff, and table
        elif event_type.startswith("PAYMENT_"):
            await self.broadcast_to_channel("admin", message)
            await self.broadcast_to_channel("staff", message)

manager = ConnectionManager()

