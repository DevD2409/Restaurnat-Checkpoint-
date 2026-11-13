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
from app.core.dependencies import resolve_optional_auth_tenant_id
from app.core.security import create_access_token, generate_table_qr_token, get_password_hash
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession, TableStatus
from app.models.user import User, UserRole
from app.websocket.connection_manager import ConnectionManager, manager

client = TestClient(app_main.app)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_token(user: User) -> str:
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
    )


def _seed_ws_tenant(db, tag: str):
    restaurant = Restaurant(
        name=f"WS Bistro {tag}",
        slug=f"ws-bistro-{tag}",
        email=f"ws-{tag}@example.com",
        subscription_plan="PRO",
        subscription_status="ACTIVE",
        is_active=True,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    owner = User(
        restaurant_id=restaurant.id,
        email=f"ws-owner-{tag}@example.com",
        username=f"ws_owner_{tag}",
        hashed_password=get_password_hash("WsOwner#2026!"),
        full_name=f"WS Owner {tag}",
        role=UserRole.RESTAURANT_OWNER,
        is_active=True,
        must_change_password=False,
    )
    chef = User(
        restaurant_id=restaurant.id,
        email=f"ws-chef-{tag}@example.com",
        username=f"ws_chef_{tag}",
        hashed_password=get_password_hash("WsChef#2026!"),
        full_name=f"WS Chef {tag}",
        role=UserRole.KITCHEN,
        is_active=True,
        must_change_password=False,
    )
    waiter = User(
        restaurant_id=restaurant.id,
        email=f"ws-waiter-{tag}@example.com",
        username=f"ws_waiter_{tag}",
        hashed_password=get_password_hash("WsWaiter#2026!"),
        full_name=f"WS Waiter {tag}",
        role=UserRole.WAITER,
        is_active=True,
        must_change_password=False,
    )
    customer = User(
        restaurant_id=restaurant.id,
        email=f"ws-cust-{tag}@example.com",
        username=f"ws_cust_{tag}",
        hashed_password=get_password_hash("WsCust#2026!"),
        full_name=f"WS Customer {tag}",
        role=UserRole.CUSTOMER,
        is_active=True,
        must_change_password=False,
    )
    db.add_all([owner, chef, waiter, customer])
    db.commit()
    for u in (owner, chef, waiter, customer):
        db.refresh(u)

    table = Table(
        restaurant_id=restaurant.id,
        table_number=f"T-{tag[:4]}-1",
        capacity=4,
        section="Main",
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
        "customer": customer,
        "table": table,
    }


def test_connection_manager_no_global_fallback_and_full_disconnect_cleanup():
    """Tenant broadcasts never spill into global rooms or other tenants, even when target tenant has zero subscribers."""
    local_mgr = ConnectionManager()

    class _FakeWS:
        def __init__(self, label: str):
            self.label = label
            self.accepted = False
            self.messages = []

        async def accept(self):
            self.accepted = True

        async def send_text(self, payload: str):
            self.messages.append(json.loads(payload))

    async def scenario():
        ws_a = _FakeWS("tenant_a_kitchen")
        ws_b_table = _FakeWS("tenant_b_table")

        await local_mgr.connect(ws_a, channel="kitchen", restaurant_id=101)
        await local_mgr.connect(ws_b_table, restaurant_id=202, table_id=55)

        # No global un-tenanted 'kitchen', 'staff', 'admin', or 'general' room entries exist
        assert "kitchen" not in local_mgr.rooms
        assert "staff" not in local_mgr.rooms
        assert "admin" not in local_mgr.rooms
        assert "general" not in local_mgr.rooms
        assert "tenant_101_kitchen" in local_mgr.rooms
        assert "202:55" in local_mgr.table_rooms

        # Broadcast for Tenant B (with 0 kitchen subscribers) must NOT fall back and reach Tenant A
        await local_mgr.broadcast_event(
            "ORDER_PLACED",
            {"order_id": 999, "restaurant_id": 202},
            table_id=55,
            restaurant_id=202,
        )
        assert ws_a.messages == []
        assert len(ws_b_table.messages) == 1
        assert ws_b_table.messages[0]["data"]["order_id"] == 999

        # Broadcast for Tenant A reaches Tenant A only even though Tenant B has 0 kitchen subscribers
        await local_mgr.broadcast_tenant_event(
            101,
            "ORDER_STATUS_CHANGED",
            {"order_id": 111, "restaurant_id": 101},
            channel="kitchen",
        )
        assert len(ws_a.messages) == 1
        assert ws_a.messages[0]["data"]["order_id"] == 111
        assert len(ws_b_table.messages) == 1

        # Missing/None restaurant_id must never broadcast to tenant 1 or any global room
        await local_mgr.broadcast_to_channel("kitchen", {"type": "LEAK"}, restaurant_id=None)
        await local_mgr.broadcast_event("LEAK", {"x": 1}, restaurant_id=None)
        await local_mgr.broadcast_to_table(55, {"type": "LEAK"}, restaurant_id=None)
        assert len(ws_a.messages) == 1
        assert len(ws_b_table.messages) == 1

        # Disconnect cleanly removes socket references and empty rooms
        local_mgr.disconnect(ws_a, channel="kitchen", restaurant_id=101)
        local_mgr.disconnect(ws_b_table, restaurant_id=202, table_id=55)
        assert local_mgr.rooms == {}
        assert local_mgr.table_rooms == {}

        # Connecting without restaurant_id raises ValueError rather than defaulting to tenant 1
        with pytest.raises(ValueError):
            await local_mgr.connect(_FakeWS("bad"), channel="kitchen", restaurant_id=None)

    asyncio.run(scenario())


def test_live_tenant_isolation_between_tenant_a_and_tenant_b():
    """Live WebSocket connection on Tenant B never receives Tenant A's broadcasts; Tenant A still receives its own when Tenant B is disconnected."""
    db = SessionLocal()
    try:
        t_a = _seed_ws_tenant(db, f"ta{_uid()}")
        t_b = _seed_ws_tenant(db, f"tb{_uid()}")
        rest_a_id = t_a["restaurant"].id
        rest_b_id = t_b["restaurant"].id
        table_a_id = t_a["table"].id
        token_a = _make_token(t_a["chef"])
        token_b = _make_token(t_b["chef"])
    finally:
        db.close()

    # Connect Tenant B to its own kitchen room and Tenant A to its own kitchen room
    with client.websocket_connect(f"/ws/tenant/{rest_b_id}/kitchen?token={token_b}") as ws_b:
        with client.websocket_connect(f"/ws/tenant/{rest_a_id}/kitchen?token={token_a}") as ws_a:
            # Confirm global 'kitchen' room stays absent/empty
            assert "kitchen" not in manager.rooms

            # Post service request on Tenant A table -> broadcasts event strictly to Tenant A
            resp = client.post(
                "/api/v1/service-requests/",
                json={
                    "restaurant_id": rest_a_id,
                    "table_id": table_a_id,
                    "request_type": "WATER",
                    "customer_notes": "Tenant A isolation check",
                },
            )
            assert resp.status_code == 201
            msg_a = json.loads(ws_a.receive_text())
            assert msg_a["type"] == "SERVICE_REQUEST_CREATED"
            assert msg_a["data"]["restaurant_id"] == rest_a_id

            # Tenant B ping/pong works and received ONLY PONG (zero leaked events from Tenant A)
            ws_b.send_text("PING")
            pong_b = json.loads(ws_b.receive_text())
            assert pong_b == {
                "type": "PONG",
                "tenant_id": rest_b_id,
                "channel": "kitchen",
            }

    # Now Tenant B has zero connected subscribers; Tenant A still receives broadcasts normally
    with client.websocket_connect(f"/ws/kitchen?token={token_a}") as ws_a_only:
        resp2 = client.post(
            "/api/v1/service-requests/",
            json={
                "restaurant_id": rest_a_id,
                "table_id": table_a_id,
                "request_type": "CUTLERY",
                "customer_notes": "Tenant A works with Tenant B disconnected",
            },
        )
        assert resp2.status_code == 201
        msg_a2 = json.loads(ws_a_only.receive_text())
        assert msg_a2["data"]["restaurant_id"] == rest_a_id


def test_unauthorized_global_privileged_ws_rejected_across_environment_casings(monkeypatch):
    """Unauthorized global /ws/admin, /ws/kitchen, and /ws/staff connections fail closed (1008) in every ENVIRONMENT casing."""
    for env_value in ("development", "Development", "DEVELOPMENT", "staging", "Staging", "production", "Production"):
        monkeypatch.setattr(settings, "ENVIRONMENT", env_value)
        for path in (
            "/ws/admin",
            "/ws/ADMIN",
            "/ws/kitchen",
            "/ws/Kitchen",
            "/ws/staff",
            "/ws/Staff",
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(path) as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008, f"Expected 1008 for {path} under ENVIRONMENT={env_value}"


def test_platform_super_admin_cannot_silently_connect_to_tenant_one():
    """PLATFORM_SUPER_ADMIN with restaurant_id=None must provide explicit ?restaurant_id=... on /ws/{channel}."""
    db = SessionLocal()
    try:
        t_b = _seed_ws_tenant(db, f"sa{_uid()}")
        sa = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        assert sa is not None
        assert sa.restaurant_id is None
        sa_token = _make_token(sa)

        # Without explicit restaurant_id, super-admin must NOT silently bind to tenant 1
        for channel in ("admin", "kitchen", "staff"):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(f"/ws/{channel}?token={sa_token}") as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008

        # With explicit restaurant_id, connection succeeds for that target tenant
        with client.websocket_connect(f"/ws/admin?token={sa_token}&restaurant_id={t_b['restaurant'].id}") as ws:
            ws.send_text("PING")
            reply = json.loads(ws.receive_text())
            assert reply == {
                "type": "PONG",
                "tenant_id": t_b["restaurant"].id,
                "channel": "admin",
            }
    finally:
        db.close()


def test_table_ws_tenant_ownership_missing_table_and_db_failure(monkeypatch):
    """Table WebSockets enforce database ownership, reject missing tables, and never fall back to tenant 1 on DB failures."""
    db = SessionLocal()
    try:
        t_a = _seed_ws_tenant(db, f"tba{_uid()}")
        t_b = _seed_ws_tenant(db, f"tbb{_uid()}")
        owner_a_token = _make_token(t_a["owner"])
        owner_b_token = _make_token(t_b["owner"])

        # Customer sessions for each table
        sess_a = client.post("/api/v1/tables/validate-qr", json={"qr_token": t_a["table"].qr_token}).json()["session_token"]
        sess_b = client.post("/api/v1/tables/validate-qr", json={"qr_token": t_b["table"].qr_token}).json()["session_token"]

        # 1. Tenant A URL requesting Tenant B's table must reject BEFORE room join (both staff and customer session)
        for query_suffix in (f"token={owner_a_token}", f"token={owner_b_token}", f"session_token={sess_b}", f"session_token={sess_a}"):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(
                    f"/ws/tenant/{t_a['restaurant'].id}/table/{t_b['table'].id}?{query_suffix}"
                ) as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008
        assert f"{t_a['restaurant'].id}:{t_b['table'].id}" not in manager.table_rooms

        # 2. Missing table ID must be rejected cleanly (never resolved to tenant 1)
        for missing_path in (
            f"/ws/table/999999?token={owner_a_token}",
            f"/ws/tenant/{t_a['restaurant'].id}/table/999999?token={owner_a_token}",
            f"/ws/table/999999?session_token={sess_a}",
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(missing_path) as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008
        assert "1:999999" not in manager.table_rooms

        # 3. Database lookup failure must reject cleanly (never fall back to tenant 1)
        def _broken_session_local():
            raise RuntimeError("Simulated DB connection failure")

        monkeypatch.setattr(app_main, "SessionLocal", _broken_session_local)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{t_b['table'].id}?session_token={sess_b}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008
    finally:
        db.close()


def test_customer_table_session_ws_valid_and_invalid_rejected():
    """Valid active TableSession works on table WebSockets; invalid, ended, cross-table, and anonymous requests are rejected."""
    db = SessionLocal()
    try:
        t_a = _seed_ws_tenant(db, f"csa{_uid()}")
        t_b = _seed_ws_tenant(db, f"csb{_uid()}")

        val_a = client.post("/api/v1/tables/validate-qr", json={"qr_token": t_a["table"].qr_token})
        assert val_a.status_code == 200
        sess_a = val_a.json()["session_token"]

        val_b = client.post("/api/v1/tables/validate-qr", json={"qr_token": t_b["table"].qr_token})
        assert val_b.status_code == 200
        sess_b = val_b.json()["session_token"]

        # Valid customer session via query param on both /ws/table/{id} and /ws/tenant/{tid}/table/{id}
        with client.websocket_connect(f"/ws/table/{t_a['table'].id}?session_token={sess_a}") as ws1:
            ws1.send_text("PING")
            assert json.loads(ws1.receive_text()) == {
                "type": "PONG",
                "tenant_id": t_a["restaurant"].id,
                "table_id": t_a["table"].id,
            }

        with client.websocket_connect(
            f"/ws/tenant/{t_a['restaurant'].id}/table/{t_a['table'].id}",
            headers={"X-Table-Session": sess_a},
        ) as ws2:
            ws2.send_text("PING")
            assert json.loads(ws2.receive_text())["tenant_id"] == t_a["restaurant"].id

        # Public non-privileged customer channel still works when explicit active restaurant_id is provided
        with client.websocket_connect(f"/ws/menu?restaurant_id={t_a['restaurant'].id}") as ws_pub:
            ws_pub.send_text("PING")
            assert json.loads(ws_pub.receive_text()) == {
                "type": "PONG",
                "tenant_id": t_a["restaurant"].id,
                "channel": "menu",
            }

        # Anonymous without credentials, invalid token, or cross-table token rejected (1008)
        for bad_path in (
            f"/ws/table/{t_a['table'].id}",
            f"/ws/tenant/{t_a['restaurant'].id}/table/{t_a['table'].id}",
            f"/ws/table/{t_a['table'].id}?session_token=sess_bogus_123",
            f"/ws/table/{t_a['table'].id}?session_token=",
            f"/ws/table/{t_a['table'].id}?session_token={sess_b}",
            f"/ws/table/{t_a['table'].id}?token={_make_token(t_a['customer'])}",
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(bad_path) as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008, f"Expected 1008 for {bad_path}"

        # Ending the customer session invalidates further table WS connections
        end_resp = client.post(
            f"/api/v1/tables/{t_a['table'].id}/session/end",
            headers={"Authorization": f"Bearer {_make_token(t_a['owner'])}"},
        )
        assert end_resp.status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/ws/table/{t_a['table'].id}?session_token={sess_a}") as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008

        # Also test a session marked ended_at even if is_active wasn't toggled cleanly
        manual_expired = TableSession(
            table_id=t_b["table"].id,
            session_token=f"sess_exp_{_uid()}",
            is_active=True,
            ended_at=datetime.now(timezone.utc),
        )
        db.add(manual_expired)
        db.commit()
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/ws/table/{t_b['table'].id}?session_token={manual_expired.session_token}"
            ) as ws:
                ws.send_text("PING")
        assert exc_info.value.code == 1008
    finally:
        db.close()


def test_optional_tenant_resolution_and_unknown_slug_404():
    """Authenticated users cannot override tenant via optional-auth routes; unknown slugs return 404 (never tenant 1)."""
    db = SessionLocal()
    try:
        t_a = _seed_ws_tenant(db, f"optA{_uid()}")
        t_b = _seed_ws_tenant(db, f"optB{_uid()}")
        sa = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()

        # Direct unit check of resolve_optional_auth_tenant_id
        with pytest.raises(Exception) as exc:
            resolve_optional_auth_tenant_id(t_a["owner"], requested_tenant_id=t_b["restaurant"].id)
        assert getattr(exc.value, "status_code", None) == 403

        with pytest.raises(Exception) as exc_customer:
            resolve_optional_auth_tenant_id(t_a["customer"], requested_tenant_id=t_b["restaurant"].id)
        assert getattr(exc_customer.value, "status_code", None) == 403

        assert resolve_optional_auth_tenant_id(sa, requested_tenant_id=t_b["restaurant"].id) == t_b["restaurant"].id

        # HTTP check via optional-auth route GET /api/v1/restaurants/
        owner_headers = {"Authorization": f"Bearer {_make_token(t_a['owner'])}"}
        assert client.get(f"/api/v1/restaurants/?restaurant_id={t_b['restaurant'].id}", headers=owner_headers).status_code == 403

        sa_headers = {"Authorization": f"Bearer {_make_token(sa)}"}
        sa_ok = client.get(f"/api/v1/restaurants/?restaurant_id={t_b['restaurant'].id}", headers=sa_headers)
        assert sa_ok.status_code == 200
        assert sa_ok.json()["id"] == t_b["restaurant"].id

        # Unknown restaurant slugs must return 404 rather than defaulting to tenant 1
        unknown_slug = f"missing-slug-{_uid()}"
        assert client.get(f"/api/v1/restaurants/by-slug/{unknown_slug}").status_code == 404
        assert client.get(f"/api/v1/menu/categories?slug={unknown_slug}").status_code == 404
        assert client.get(f"/api/v1/menu/items?slug={unknown_slug}").status_code == 404
        assert client.get(f"/api/v1/tables/?slug={unknown_slug}").status_code == 404
        fb_res = client.post(
            "/api/v1/feedback/submit",
            json={"restaurant_slug": unknown_slug, "overall_rating": 5, "comment": "Probe"},
        )
        assert fb_res.status_code == 404
    finally:
        db.close()
