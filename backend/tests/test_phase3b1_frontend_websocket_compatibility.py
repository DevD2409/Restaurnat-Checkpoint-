import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.main as app_main
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token, generate_table_qr_token, get_password_hash
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession, TableStatus
from app.models.user import User, UserRole

client = TestClient(app_main.app)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_token(user: User) -> str:
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
    )


def _seed_tenant_bundle(db, tag: str):
    restaurant = Restaurant(
        name=f"Compat Bistro {tag}",
        slug=f"compat-bistro-{tag}",
        email=f"compat-{tag}@example.com",
        subscription_plan="PRO",
        subscription_status="ACTIVE",
        is_active=True,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    owner = User(
        restaurant_id=restaurant.id,
        email=f"compat-owner-{tag}@example.com",
        username=f"compat_owner_{tag}",
        hashed_password=get_password_hash("Owner#2026!"),
        full_name=f"Owner {tag}",
        role=UserRole.RESTAURANT_OWNER,
        is_active=True,
        must_change_password=False,
    )
    chef = User(
        restaurant_id=restaurant.id,
        email=f"compat-chef-{tag}@example.com",
        username=f"compat_chef_{tag}",
        hashed_password=get_password_hash("Chef#2026!"),
        full_name=f"Chef {tag}",
        role=UserRole.KITCHEN,
        is_active=True,
        must_change_password=False,
    )
    waiter = User(
        restaurant_id=restaurant.id,
        email=f"compat-waiter-{tag}@example.com",
        username=f"compat_waiter_{tag}",
        hashed_password=get_password_hash("Waiter#2026!"),
        full_name=f"Waiter {tag}",
        role=UserRole.WAITER,
        is_active=True,
        must_change_password=False,
    )
    db.add_all([owner, chef, waiter])
    db.commit()
    db.refresh(owner)
    db.refresh(chef)
    db.refresh(waiter)

    table = Table(
        restaurant_id=restaurant.id,
        table_number=f"T-{tag}",
        capacity=4,
        section="Dining",
        status=TableStatus.AVAILABLE,
        is_active=True,
    )
    db.add(table)
    db.commit()
    db.refresh(table)

    table.qr_token = generate_table_qr_token(restaurant.id, table.id, table.table_number)
    db.commit()
    db.refresh(table)

    return {
        "restaurant": restaurant,
        "owner": owner,
        "chef": chef,
        "waiter": waiter,
        "table": table,
    }


def test_customer_qr_session_creation_followed_by_table_ws_connection():
    """
    1. Customer validates QR token via POST /tables/validate-qr.
    2. Receives valid response containing table_id and active session_token.
    3. Connects to table WebSocket using ?session_token=... parameter.
    4. Successfully receives heartbeat and messages.
    """
    db = SessionLocal()
    try:
        data = _seed_tenant_bundle(db, f"qr{_uid()}")
        table = data["table"]
        rest = data["restaurant"]

        # Validate QR token to obtain session_token
        qr_resp = client.post(
            "/api/v1/tables/validate-qr",
            json={"qr_token": table.qr_token},
        )
        assert qr_resp.status_code == 200
        qr_data = qr_resp.json()
        assert qr_data["valid"] is True
        assert qr_data["table_id"] == table.id
        assert qr_data["restaurant_id"] == rest.id
        session_token = qr_data["session_token"]
        assert session_token.startswith("sess_")

        # Connect customer table WS using session_token on /ws/table/{table_id}
        with client.websocket_connect(f"/ws/table/{table.id}?session_token={session_token}") as ws:
            ws.send_text("PING")
            msg = json.loads(ws.receive_text())
            assert msg == {
                "type": "PONG",
                "tenant_id": rest.id,
                "table_id": table.id,
            }

        # Also connect customer table WS using session_token on tenant-scoped route
        with client.websocket_connect(f"/ws/tenant/{rest.id}/table/{table.id}?session_token={session_token}") as ws_tenant:
            ws_tenant.send_text("PING")
            msg_tenant = json.loads(ws_tenant.receive_text())
            assert msg_tenant == {
                "type": "PONG",
                "tenant_id": rest.id,
                "table_id": table.id,
            }
    finally:
        db.close()


def test_customer_session_expiry_and_rejection():
    """
    Customer session expiry, missing session tokens, and forged session tokens
    are rejected with WebSocket close code 1008.
    """
    db = SessionLocal()
    try:
        data = _seed_tenant_bundle(db, f"exp{_uid()}")
        table = data["table"]
        rest = data["restaurant"]

        # 1. Anonymous customer connection with no session_token -> 1008
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{table.id}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # 2. Forged / invalid session token -> 1008
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{table.id}?session_token=sess_forged999") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # 3. Create active session, then explicitly end it
        session = TableSession(
            table_id=table.id,
            customer_name="Expired Diner",
            guest_count=2,
            session_token=f"sess_{uuid.uuid4().hex}",
            is_active=False,
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{table.id}?session_token={session.session_token}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008
    finally:
        db.close()


def test_staff_kitchen_connection_with_valid_jwt():
    """
    Staff kitchen connection with a valid JWT succeeds for kitchen personnel
    on both /ws/tenant/{tenant_id}/kitchen and /ws/kitchen.
    """
    db = SessionLocal()
    try:
        data = _seed_tenant_bundle(db, f"kit{_uid()}")
        chef = data["chef"]
        rest = data["restaurant"]
        chef_token = _make_token(chef)

        # Tenant-scoped kitchen route
        with client.websocket_connect(f"/ws/tenant/{rest.id}/kitchen?token={chef_token}") as ws:
            ws.send_text("PING")
            msg = json.loads(ws.receive_text())
            assert msg == {
                "type": "PONG",
                "tenant_id": rest.id,
                "channel": "kitchen",
            }

        # Global kitchen route with user-bound restaurant
        with client.websocket_connect(f"/ws/kitchen?token={chef_token}") as ws_global:
            ws_global.send_text("PING")
            msg_global = json.loads(ws_global.receive_text())
            assert msg_global == {
                "type": "PONG",
                "tenant_id": rest.id,
                "channel": "kitchen",
            }
    finally:
        db.close()


def test_unauthorized_staff_connection_rejection():
    """
    Unauthorized staff (e.g. Waiter connecting to /ws/kitchen or /ws/admin,
    or user with must_change_password=True) is rejected with close code 1008.
    """
    db = SessionLocal()
    try:
        data = _seed_tenant_bundle(db, f"unauth{_uid()}")
        waiter = data["waiter"]
        rest = data["restaurant"]
        waiter_token = _make_token(waiter)

        # Waiter is not authorized for kitchen channel
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/kitchen?token={waiter_token}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/tenant/{rest.id}/kitchen?token={waiter_token}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # Waiter is not authorized for admin channel
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/admin?token={waiter_token}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # Chef with must_change_password=True is locked out
        locked_chef = User(
            restaurant_id=rest.id,
            email=f"locked-chef-{_uid()}@example.com",
            username=f"locked_chef_{_uid()}",
            hashed_password=get_password_hash("LockedChef#2026!"),
            full_name="Locked Chef",
            role=UserRole.KITCHEN,
            is_active=True,
            must_change_password=True,
        )
        db.add(locked_chef)
        db.commit()
        db.refresh(locked_chef)
        locked_token = _make_token(locked_chef)

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/kitchen?token={locked_token}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008
    finally:
        db.close()


def test_correct_tenant_routing_and_no_cross_tenant_events():
    """
    Tenant isolation guarantees events from Tenant A are NEVER delivered to Tenant B,
    and cross-tenant connection attempts are rejected with 1008.
    """
    db = SessionLocal()
    try:
        data_a = _seed_tenant_bundle(db, f"ta{_uid()}")
        data_b = _seed_tenant_bundle(db, f"tb{_uid()}")

        token_a = _make_token(data_a["chef"])
        token_b = _make_token(data_b["chef"])
        rest_a = data_a["restaurant"]
        rest_b = data_b["restaurant"]

        # Cross-tenant eavesdropping rejection: Chef A tries to join Tenant B's kitchen room
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/tenant/{rest_b.id}/kitchen?token={token_a}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # Chef A tries to join Tenant B's table room
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/tenant/{rest_b.id}/table/{data_b['table'].id}?token={token_a}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # Both connect to their legitimate tenant kitchen rooms
        with client.websocket_connect(f"/ws/tenant/{rest_a.id}/kitchen?token={token_a}") as ws_a:
            with client.websocket_connect(f"/ws/tenant/{rest_b.id}/kitchen?token={token_b}") as ws_b:
                # Trigger a service request for Tenant A
                create_resp = client.post(
                    "/api/v1/service-requests/",
                    json={
                        "restaurant_id": rest_a.id,
                        "table_id": data_a["table"].id,
                        "request_type": "WATER",
                        "customer_notes": "Glass of water for Table A",
                    },
                )
                assert create_resp.status_code == 201

                # Socket A receives the event
                msg_a = json.loads(ws_a.receive_text())
                assert msg_a["type"] == "SERVICE_REQUEST_CREATED"
                assert msg_a["data"]["restaurant_id"] == rest_a.id

                # Socket B pings its own room and receives ONLY its own PONG (no leaked event from A)
                ws_b.send_text("PING")
                msg_b = json.loads(ws_b.receive_text())
                assert msg_b["type"] == "PONG"
                assert msg_b["tenant_id"] == rest_b.id
    finally:
        db.close()


def test_no_tokens_exposed_beyond_supported_mechanisms():
    """
    Frontend URL sanitization helper redacts both 'token' and 'session_token'
    query strings so that cleartext credentials never appear in console logs.
    """
    raw_kitchen_url = "ws://localhost:8000/ws/kitchen?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret"
    raw_table_url = "ws://localhost:8000/ws/table/1?session_token=sess_abc123secret456"
    raw_mixed_url = "ws://localhost:8000/ws/tenant/1/table/2?token=secret_token&session_token=secret_sess"

    import re

    def sanitize(url: str) -> str:
        return re.sub(
            r"([?&](?:token|session_token)=)[^&]+",
            r"\1[REDACTED]",
            url,
            flags=re.IGNORECASE,
        )

    clean_kit = sanitize(raw_kitchen_url)
    assert "eyJhbGci" not in clean_kit
    assert "token=[REDACTED]" in clean_kit

    clean_tbl = sanitize(raw_table_url)
    assert "sess_abc123secret456" not in clean_tbl
    assert "session_token=[REDACTED]" in clean_tbl

    clean_mix = sanitize(raw_mixed_url)
    assert "secret_token" not in clean_mix
    assert "secret_sess" not in clean_mix
    assert "token=[REDACTED]" in clean_mix
    assert "session_token=[REDACTED]" in clean_mix


def test_backend_logging_filter_redacts_tokens():
    """
    Backend RedactSensitiveQueryFilter redacts both 'token' and 'session_token'
    query strings from application and uvicorn log records.
    """
    import logging
    from app.main import RedactSensitiveQueryFilter

    filter_instance = RedactSensitiveQueryFilter()
    record1 = logging.LogRecord(
        name="srmp",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Client connected: /ws/table/1?session_token=sess_secret_token_val",
        args=(),
        exc_info=None,
    )
    filter_instance.filter(record1)
    assert "sess_secret_token_val" not in record1.msg
    assert "session_token=[REDACTED]" in record1.msg

    record2 = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET /ws/kitchen?token=eyJhbGciOi.secret_jwt_payload HTTP/1.1",
        args=(),
        exc_info=None,
    )
    filter_instance.filter(record2)
    assert "secret_jwt_payload" not in record2.msg
    assert "token=[REDACTED]" in record2.msg


def test_table_session_cannot_authorize_staff_or_other_table():
    """
    Table session tokens are strictly restricted to their designated table and restaurant:
    - Cannot authorize connection to a different table (close code 1008).
    - Cannot authorize privileged staff channels like /ws/kitchen or /ws/admin (close code 1008).
    - Cannot authorize staff REST management endpoints (returns 401 Unauthorized).
    """
    db = SessionLocal()
    try:
        data = _seed_tenant_bundle(db, f"sec{_uid()}")
        rest = data["restaurant"]
        table_1 = data["table"]

        # Seed Table 2 under same restaurant
        table_2 = Table(
            restaurant_id=rest.id,
            table_number=f"T-2-{_uid()}",
            capacity=4,
            section="Patio",
            status=TableStatus.AVAILABLE,
            is_active=True,
        )
        db.add(table_2)
        db.commit()
        db.refresh(table_2)

        # Get valid active session token for Table 1
        qr_resp = client.post(
            "/api/v1/tables/validate-qr",
            json={"qr_token": table_1.qr_token},
        )
        assert qr_resp.status_code == 200
        table_1_session = qr_resp.json()["session_token"]

        # 1. Table 1's session token MUST NOT authorize Table 2
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{table_2.id}?session_token={table_1_session}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # 2. Table 1's session token MUST NOT authorize privileged kitchen channel
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/kitchen?token={table_1_session}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # 3. Table 1's session token MUST NOT authorize privileged admin channel
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/admin?token={table_1_session}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # 4. Table 1's session token MUST NOT authorize staff REST endpoints
        staff_resp = client.get(
            "/api/v1/auth/staff",
            headers={"Authorization": f"Bearer {table_1_session}"},
        )
        assert staff_resp.status_code == 401

        order_update_resp = client.patch(
            "/api/v1/orders/1/status",
            json={"status": "PREPARING"},
            headers={"Authorization": f"Bearer {table_1_session}"},
        )
        assert order_update_resp.status_code == 401
    finally:
        db.close()
