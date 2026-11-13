import json
import logging
from typing import Dict, List, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger("websocket")

class ConnectionManager:
    def __init__(self):
        # "tenant_{restaurant_id}_{channel}" -> Set[WebSocket]
        self.rooms: Dict[str, Set[WebSocket]] = {}
        # "{restaurant_id}:{table_id}" -> Set[WebSocket]
        self.table_rooms: Dict[str, Set[WebSocket]] = {}

    @staticmethod
    def _normalize_tenant_id(restaurant_id: Optional[int]) -> Optional[int]:
        if restaurant_id is None or isinstance(restaurant_id, bool):
            return None
        try:
            r_id = int(restaurant_id)
        except (TypeError, ValueError):
            return None
        return r_id if r_id > 0 else None

    async def connect(
        self,
        websocket: WebSocket,
        channel: str = "general",
        restaurant_id: Optional[int] = None,
        table_id: Optional[int] = None
    ):
        r_id = self._normalize_tenant_id(restaurant_id)
        if r_id is None:
            raise ValueError("Valid restaurant_id is required to connect to a WebSocket room")

        norm_channel = (channel or "general").strip().lower()
        await websocket.accept()
        if table_id is not None:
            room_key = f"{r_id}:{table_id}"
            if room_key not in self.table_rooms:
                self.table_rooms[room_key] = set()
            self.table_rooms[room_key].add(websocket)
            logger.info(f"WebSocket connected to table {table_id} for tenant {r_id}")
        else:
            tenant_room = f"tenant_{r_id}_{norm_channel}"
            if tenant_room not in self.rooms:
                self.rooms[tenant_room] = set()
            self.rooms[tenant_room].add(websocket)
            logger.info(f"WebSocket connected to channel '{tenant_room}'")

    def disconnect(
        self,
        websocket: WebSocket,
        channel: str = "general",
        restaurant_id: Optional[int] = None,
        table_id: Optional[int] = None
    ):
        r_id = self._normalize_tenant_id(restaurant_id)
        norm_channel = (channel or "general").strip().lower()
        if table_id is not None and r_id is not None:
            room_key = f"{r_id}:{table_id}"
            if room_key in self.table_rooms:
                self.table_rooms[room_key].discard(websocket)
                if not self.table_rooms[room_key]:
                    del self.table_rooms[room_key]
        elif r_id is not None:
            tenant_room = f"tenant_{r_id}_{norm_channel}"
            if tenant_room in self.rooms:
                self.rooms[tenant_room].discard(websocket)
                if not self.rooms[tenant_room]:
                    del self.rooms[tenant_room]

        # Defensive sweep so no socket reference lingers in any room
        for room_map in (self.rooms, self.table_rooms):
            empty_keys = []
            for key, sockets in room_map.items():
                sockets.discard(websocket)
                if not sockets:
                    empty_keys.append(key)
            for key in empty_keys:
                del room_map[key]

    async def broadcast_to_channel(self, channel: str, message: dict, restaurant_id: Optional[int] = None):
        """Broadcasts event strictly to tenant-isolated channel subscribers with zero global fallback."""
        r_id = self._normalize_tenant_id(restaurant_id)
        if r_id is None:
            logger.warning(f"Skipping channel '{channel}' broadcast without valid restaurant_id")
            return

        norm_channel = (channel or "general").strip().lower()
        tenant_room = f"tenant_{r_id}_{norm_channel}"
        recipients = self.rooms.get(tenant_room)
        if not recipients:
            return

        payload = json.dumps(message)
        stale_connections = []
        for ws in list(recipients):
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending message to ws in '{tenant_room}': {e}")
                stale_connections.append(ws)

        for dead_ws in stale_connections:
            if tenant_room in self.rooms:
                self.rooms[tenant_room].discard(dead_ws)
                if not self.rooms[tenant_room]:
                    del self.rooms[tenant_room]

    async def broadcast_to_table(self, table_id: int, message: dict, restaurant_id: Optional[int] = None):
        """Broadcasts event strictly to the tenant-scoped table room with zero global fallback."""
        r_id = self._normalize_tenant_id(restaurant_id)
        if r_id is None:
            logger.warning(f"Skipping table '{table_id}' broadcast without valid restaurant_id")
            return

        room_key = f"{r_id}:{table_id}"
        recipients = self.table_rooms.get(room_key)
        if not recipients:
            return

        payload = json.dumps(message)
        stale = []
        for ws in list(recipients):
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending to table {table_id} in tenant {r_id}: {e}")
                stale.append(ws)

        for dead_ws in stale:
            if room_key in self.table_rooms:
                self.table_rooms[room_key].discard(dead_ws)
                if not self.table_rooms[room_key]:
                    del self.table_rooms[room_key]

    async def broadcast_event(self, event_type: str, data: dict, table_id: Optional[int] = None, restaurant_id: Optional[int] = None):
        """High-level event dispatcher that fans out strictly within the target restaurant tenant."""
        r_id = self._normalize_tenant_id(restaurant_id)
        if r_id is None:
            logger.warning(f"Skipping event '{event_type}' broadcast without valid restaurant_id")
            return

        msg = {
            "type": event_type,
            "data": data
        }
        await self.broadcast_to_channel("kitchen", msg, restaurant_id=r_id)
        await self.broadcast_to_channel("staff", msg, restaurant_id=r_id)
        await self.broadcast_to_channel("admin", msg, restaurant_id=r_id)
        if table_id is not None:
            await self.broadcast_to_table(table_id, msg, restaurant_id=r_id)

    async def broadcast_tenant_event(self, restaurant_id: int, event_type: str, data: dict, channel: str = "general", table_id: Optional[int] = None):
        """Broadcasts event scoped strictly to a specific tenant and channel/table."""
        r_id = self._normalize_tenant_id(restaurant_id)
        if r_id is None:
            logger.warning(f"Skipping tenant event '{event_type}' without valid restaurant_id")
            return

        norm_channel = (channel or "general").strip().lower()
        msg = {
            "type": event_type,
            "data": data
        }
        if norm_channel in ("general", "all"):
            await self.broadcast_event(event_type, data, table_id=table_id, restaurant_id=r_id)
        else:
            await self.broadcast_to_channel(norm_channel, msg, restaurant_id=r_id)
            if table_id is not None:
                await self.broadcast_to_table(table_id, msg, restaurant_id=r_id)

manager = ConnectionManager()
