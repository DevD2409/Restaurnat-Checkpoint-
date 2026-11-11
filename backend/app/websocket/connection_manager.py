import json
import logging
from typing import Dict, List, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger("websocket")

class ConnectionManager:
    def __init__(self):
        # channel_name -> Set[WebSocket]
        self.rooms: Dict[str, Set[WebSocket]] = {
            "kitchen": set(),
            "staff": set(),
            "admin": set(),
            "general": set()
        }
        # "{restaurant_id}:{table_id}" -> Set[WebSocket]
        self.table_rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channel: str = "general",
        restaurant_id: Optional[int] = 1,
        table_id: Optional[int] = None
    ):
        await websocket.accept()
        r_id = restaurant_id or 1
        if table_id is not None:
            room_key = f"{r_id}:{table_id}"
            if room_key not in self.table_rooms:
                self.table_rooms[room_key] = set()
            self.table_rooms[room_key].add(websocket)
            logger.info(f"WebSocket connected to table {table_id} for tenant {r_id}")
        else:
            # Multi-tenant isolated room
            tenant_room = f"tenant_{r_id}_{channel}"
            if tenant_room not in self.rooms:
                self.rooms[tenant_room] = set()
            self.rooms[tenant_room].add(websocket)

            # Global room fallback for backward compatibility
            if channel in self.rooms:
                self.rooms[channel].add(websocket)
            logger.info(f"WebSocket connected to channel '{tenant_room}'")

    def disconnect(
        self,
        websocket: WebSocket,
        channel: str = "general",
        restaurant_id: Optional[int] = 1,
        table_id: Optional[int] = None
    ):
        r_id = restaurant_id or 1
        if table_id is not None:
            room_key = f"{r_id}:{table_id}"
            if room_key in self.table_rooms:
                self.table_rooms[room_key].discard(websocket)
                if not self.table_rooms[room_key]:
                    del self.table_rooms[room_key]
        else:
            tenant_room = f"tenant_{r_id}_{channel}"
            if tenant_room in self.rooms:
                self.rooms[tenant_room].discard(websocket)
            if channel in self.rooms:
                self.rooms[channel].discard(websocket)

    async def broadcast_to_channel(self, channel: str, message: dict, restaurant_id: Optional[int] = None):
        """Broadcasts event strictly to tenant subscribers while supporting global fallback."""
        payload = json.dumps(message)
        recipients = set()
        
        if restaurant_id is not None:
            tenant_room = f"tenant_{restaurant_id}_{channel}"
            if tenant_room in self.rooms:
                recipients.update(self.rooms[tenant_room])
        
        # If no specific tenant room or global broadcast
        if not recipients and channel in self.rooms:
            recipients.update(self.rooms[channel])

        stale_connections = []
        for ws in list(recipients):
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending message to ws: {e}")
                stale_connections.append(ws)

        for dead_ws in stale_connections:
            if restaurant_id is not None:
                tenant_room = f"tenant_{restaurant_id}_{channel}"
                if tenant_room in self.rooms:
                    self.rooms[tenant_room].discard(dead_ws)
            if channel in self.rooms:
                self.rooms[channel].discard(dead_ws)

    async def broadcast_to_table(self, table_id: int, message: dict, restaurant_id: Optional[int] = 1):
        r_id = restaurant_id or 1
        room_key = f"{r_id}:{table_id}"
        recipients = set()
        if room_key in self.table_rooms:
            recipients.update(self.table_rooms[room_key])

        # Backward compatibility fallback
        if not recipients and str(table_id) in self.table_rooms:
            recipients.update(self.table_rooms[str(table_id)])

        payload = json.dumps(message)
        stale = []
        for ws in list(recipients):
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending to table {table_id}: {e}")
                stale.append(ws)

        for dead_ws in stale:
            if room_key in self.table_rooms:
                self.table_rooms[room_key].discard(dead_ws)

    async def broadcast_event(self, event_type: str, data: dict, table_id: Optional[int] = None, restaurant_id: Optional[int] = 1):
        """High-level event dispatcher that fans out to kitchen, waiter, admin, and optionally table."""
        msg = {
            "type": event_type,
            "data": data
        }
        await self.broadcast_to_channel("kitchen", msg, restaurant_id=restaurant_id)
        await self.broadcast_to_channel("staff", msg, restaurant_id=restaurant_id)
        await self.broadcast_to_channel("admin", msg, restaurant_id=restaurant_id)
        if table_id:
            await self.broadcast_to_table(table_id, msg, restaurant_id=restaurant_id)

    async def broadcast_tenant_event(self, restaurant_id: int, event_type: str, data: dict, channel: str = "general", table_id: Optional[int] = None):
        """Broadcasts event scoped to a specific tenant and channel/table."""
        msg = {
            "type": event_type,
            "data": data
        }
        if channel in ("general", "all"):
            await self.broadcast_event(event_type, data, table_id=table_id, restaurant_id=restaurant_id)
        else:
            await self.broadcast_to_channel(channel, msg, restaurant_id=restaurant_id)
            if table_id:
                await self.broadcast_to_table(table_id, msg, restaurant_id=restaurant_id)

manager = ConnectionManager()
