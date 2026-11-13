import json
import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.security import create_access_token, get_password_hash, verify_password
from app.main import app
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole

client = TestClient(app)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_tenant_and_users(db, tag: str):
    """Create an isolated tenant with owner, manager, and waiter accounts for testing."""
    restaurant = Restaurant(
        name=f"Sec Test Bistro {tag}",
        slug=f"sec-test-{tag}",
        email=f"bistro-{tag}@example.com",
        subscription_plan="PRO",
        subscription_status="ACTIVE",
        is_active=True,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    owner = User(
        restaurant_id=restaurant.id,
        email=f"owner-{tag}@example.com",
        username=f"owner_{tag}",
        hashed_password=get_password_hash("StrongOwner#2026!"),
        full_name="Tenant Owner",
        role=UserRole.RESTAURANT_OWNER,
        is_active=True,
        must_change_password=False,
    )
    manager = User(
        restaurant_id=restaurant.id,
        email=f"manager-{tag}@example.com",
        username=f"manager_{tag}",
        hashed_password=get_password_hash("StrongManager#2026!"),
        full_name="Tenant Manager",
        role=UserRole.RESTAURANT_MANAGER,
        is_active=True,
        must_change_password=False,
    )
    legacy_manager = User(
        restaurant_id=restaurant.id,
        email=f"legacymgr-{tag}@example.com",
        username=f"legacymgr_{tag}",
        hashed_password=get_password_hash("StrongManager#2026!"),
        full_name="Legacy Manager",
        role=UserRole.MANAGER,
        is_active=True,
        must_change_password=False,
    )
    waiter = User(
        restaurant_id=restaurant.id,
        email=f"waiter-{tag}@example.com",
        username=f"waiter_{tag}",
        hashed_password=get_password_hash("StrongWaiter#2026!"),
        full_name="Tenant Waiter",
        role=UserRole.WAITER,
        is_active=True,
        must_change_password=False,
    )
    db.add_all([owner, manager, legacy_manager, waiter])
    db.commit()
    for user in (owner, manager, legacy_manager, waiter):
        db.refresh(user)
    restaurant.owner_id = owner.id
    db.commit()
    return restaurant, owner, manager, legacy_manager, waiter


def _auth_header(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_cannot_create_platform_super_admin_via_staff_endpoint():
    """Owner, managers, and even super-admin must not create PLATFORM_SUPER_ADMIN via POST /auth/staff."""
    tag = _uid()
    db = SessionLocal()
    try:
        restaurant, owner, manager, legacy_manager, _ = _create_tenant_and_users(db, tag)
        superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        assert superadmin is not None

        for label, actor, extra in (
            ("owner", owner, {}),
            ("restaurant_manager", manager, {}),
            ("legacy_manager", legacy_manager, {}),
            ("superadmin", superadmin, {"restaurant_id": restaurant.id}),
        ):
            target_username = f"escalate_{label}_{tag}"
            payload = {
                "email": f"{target_username}@example.com",
                "username": target_username,
                "password": "StrongEscalate#2026!",
                "full_name": "Escalated Admin",
                "role": "PLATFORM_SUPER_ADMIN",
                **extra,
            }
            resp = client.post("/api/v1/auth/staff", json=payload, headers=_auth_header(actor))
            assert resp.status_code == 403, f"Expected 403 for {label}, got {resp.status_code}: {resp.text}"
            db_user = db.query(User).filter(User.username == target_username).first()
            assert db_user is None
    finally:
        db.close()


def test_cannot_promote_self_or_staff_to_platform_super_admin():
    """Owners, managers, and staff endpoints cannot promote any user to PLATFORM_SUPER_ADMIN."""
    tag = _uid()
    db = SessionLocal()
    try:
        _, owner, manager, legacy_manager, waiter = _create_tenant_and_users(db, tag)
        superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        assert superadmin is not None

        # Manager attempts self-promotion to PLATFORM_SUPER_ADMIN, RESTAURANT_OWNER, and ADMIN
        for attempted_role in ("PLATFORM_SUPER_ADMIN", "RESTAURANT_OWNER", "ADMIN"):
            resp_self = client.put(
                f"/api/v1/auth/staff/{manager.id}",
                json={"role": attempted_role},
                headers=_auth_header(manager),
            )
            assert resp_self.status_code == 403
            db.refresh(manager)
            assert manager.role == UserRole.RESTAURANT_MANAGER

            resp_legacy = client.put(
                f"/api/v1/auth/staff/{legacy_manager.id}",
                json={"role": attempted_role},
                headers=_auth_header(legacy_manager),
            )
            assert resp_legacy.status_code == 403
            db.refresh(legacy_manager)
            assert legacy_manager.role == UserRole.MANAGER

        # Owner and SuperAdmin cannot promote waiter to PLATFORM_SUPER_ADMIN via PUT /auth/staff/{id}
        for actor in (owner, superadmin):
            resp_promote = client.put(
                f"/api/v1/auth/staff/{waiter.id}",
                json={"role": "PLATFORM_SUPER_ADMIN"},
                headers=_auth_header(actor),
            )
            assert resp_promote.status_code == 403
            db.refresh(waiter)
            assert waiter.role == UserRole.WAITER
    finally:
        db.close()


def test_tenant_users_cannot_view_modify_deactivate_or_delete_platform_super_admin():
    """Tenant owners/managers must never view in tenant list, modify, deactivate, or delete PLATFORM_SUPER_ADMIN."""
    tag = _uid()
    db = SessionLocal()
    try:
        _, owner, manager, _, _ = _create_tenant_and_users(db, tag)
        superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        assert superadmin is not None
        original_email = superadmin.email
        original_name = superadmin.full_name
        original_hash = superadmin.hashed_password
        original_active = superadmin.is_active

        # 1. Tenant staff listing must not expose PLATFORM_SUPER_ADMIN
        list_resp = client.get("/api/v1/auth/staff", headers=_auth_header(owner))
        assert list_resp.status_code == 200
        assert all(item["role"] != "PLATFORM_SUPER_ADMIN" for item in list_resp.json())

        # 2. Owners and managers cannot modify or deactivate superadmin
        for actor in (owner, manager):
            mod_resp = client.put(
                f"/api/v1/auth/staff/{superadmin.id}",
                json={"full_name": "Hacked SuperAdmin", "email": f"hacked-{tag}@example.com"},
                headers=_auth_header(actor),
            )
            assert mod_resp.status_code == 403

            deact_resp = client.put(
                f"/api/v1/auth/staff/{superadmin.id}",
                json={"is_active": False},
                headers=_auth_header(actor),
            )
            assert deact_resp.status_code == 403

            del_resp = client.delete(
                f"/api/v1/auth/staff/{superadmin.id}",
                headers=_auth_header(actor),
            )
            assert del_resp.status_code == 403

        db.expire_all()
        sa_after = db.query(User).filter(User.id == superadmin.id).first()
        assert sa_after is not None
        assert sa_after.email == original_email
        assert sa_after.full_name == original_name
        assert sa_after.hashed_password == original_hash
        assert sa_after.is_active == original_active
        assert sa_after.role == UserRole.PLATFORM_SUPER_ADMIN
    finally:
        db.close()


def test_manager_cannot_assign_privileged_tenant_roles_or_modify_owners():
    """Ordinary managers can manage operational staff only; privileged tenant roles remain restricted."""
    tag = _uid()
    db = SessionLocal()
    try:
        _, owner, manager, _, waiter = _create_tenant_and_users(db, tag)

        # Manager cannot create privileged tenant roles or CUSTOMER
        for forbidden_role in ("RESTAURANT_OWNER", "ADMIN", "RESTAURANT_MANAGER", "MANAGER", "CUSTOMER"):
            uname = f"mgr_try_{forbidden_role.lower()}_{tag}"
            resp = client.post(
                "/api/v1/auth/staff",
                json={
                    "email": f"{uname}@example.com",
                    "username": uname,
                    "password": "StrongStaff#2026!",
                    "full_name": "Forbidden Role Test",
                    "role": forbidden_role,
                },
                headers=_auth_header(manager),
            )
            assert resp.status_code == 403, f"Manager unexpectedly allowed role {forbidden_role}"
            assert db.query(User).filter(User.username == uname).first() is None

            # Manager also cannot promote waiter to privileged roles
            promo_resp = client.put(
                f"/api/v1/auth/staff/{waiter.id}",
                json={"role": forbidden_role},
                headers=_auth_header(manager),
            )
            assert promo_resp.status_code == 403
            db.refresh(waiter)
            assert waiter.role == UserRole.WAITER

        # Manager cannot modify or deactivate an existing owner
        mod_owner = client.put(
            f"/api/v1/auth/staff/{owner.id}",
            json={"is_active": False, "full_name": "Disabled By Manager"},
            headers=_auth_header(manager),
        )
        assert mod_owner.status_code == 403
        db.refresh(owner)
        assert owner.is_active is True
        assert owner.full_name == "Tenant Owner"
    finally:
        db.close()


def test_cross_tenant_staff_and_privileged_role_isolation():
    """Tenant A owner cannot assign roles in Tenant B or inspect/modify/delete Tenant B staff."""
    tag_a = _uid()
    tag_b = _uid()
    db = SessionLocal()
    try:
        _, owner_a, _, _, _ = _create_tenant_and_users(db, tag_a)
        rest_b, owner_b, manager_b, _, waiter_b = _create_tenant_and_users(db, tag_b)

        # 1. Tenant A owner cannot create a privileged role (or any staff) targeting Tenant B
        cross_uname = f"cross_owner_{tag_a}"
        cross_create = client.post(
            "/api/v1/auth/staff",
            json={
                "email": f"{cross_uname}@example.com",
                "username": cross_uname,
                "password": "StrongCross#2026!",
                "full_name": "Cross Tenant Owner",
                "role": "RESTAURANT_OWNER",
                "restaurant_id": rest_b.id,
            },
            headers=_auth_header(owner_a),
        )
        assert cross_create.status_code == 403
        assert db.query(User).filter(User.username == cross_uname).first() is None

        # 2. Tenant A owner cannot modify or delete Tenant B staff/owner
        for target in (owner_b, manager_b, waiter_b):
            upd = client.put(
                f"/api/v1/auth/staff/{target.id}",
                json={"full_name": "Tampered", "is_active": False},
                headers=_auth_header(owner_a),
            )
            assert upd.status_code == 403

            dele = client.delete(
                f"/api/v1/auth/staff/{target.id}",
                headers=_auth_header(owner_a),
            )
            assert dele.status_code == 403

        # 3. Tenant A list does not leak Tenant B staff
        list_a = client.get("/api/v1/auth/staff", headers=_auth_header(owner_a))
        assert list_a.status_code == 200
        a_ids = {item["id"] for item in list_a.json()}
        assert owner_b.id not in a_ids
        assert waiter_b.id not in a_ids
    finally:
        db.close()


def test_legitimate_staff_management_still_works():
    """Owner and manager can legitimately create, update, and manage permitted staff within their tenant."""
    tag = _uid()
    db = SessionLocal()
    try:
        rest, owner, manager, _, _ = _create_tenant_and_users(db, tag)

        # Owner creates a manager and a chef
        mgr_username = f"new_mgr_{tag}"
        create_mgr = client.post(
            "/api/v1/auth/staff",
            json={
                "email": f"{mgr_username}@example.com",
                "username": mgr_username,
                "password": "ValidMgrPass#2026!",
                "full_name": "New Floor Manager",
                "role": "RESTAURANT_MANAGER",
                "restaurant_id": rest.id,
            },
            headers=_auth_header(owner),
        )
        assert create_mgr.status_code == 201
        created_mgr = create_mgr.json()
        assert created_mgr["role"] == "RESTAURANT_MANAGER"
        assert created_mgr["restaurant_id"] == rest.id

        # Manager creates an operational waiter and promotes them to cashier
        waiter_username = f"new_waiter_{tag}"
        create_waiter = client.post(
            "/api/v1/auth/staff",
            json={
                "email": f"{waiter_username}@example.com",
                "username": waiter_username,
                "password": "ValidWaiterPass#2026!",
                "full_name": "Operational Waiter",
                "role": "WAITER",
            },
            headers=_auth_header(manager),
        )
        assert create_waiter.status_code == 201
        waiter_id = create_waiter.json()["id"]

        upd_waiter = client.put(
            f"/api/v1/auth/staff/{waiter_id}",
            json={"role": "CASHIER", "shift": "Night Shift"},
            headers=_auth_header(manager),
        )
        assert upd_waiter.status_code == 200
        assert upd_waiter.json()["role"] == "CASHIER"
        assert upd_waiter.json()["shift"] == "Night Shift"

        # Owner deletes operational staff member cleanly
        del_waiter = client.delete(f"/api/v1/auth/staff/{waiter_id}", headers=_auth_header(owner))
        assert del_waiter.status_code == 200
        assert db.query(User).filter(User.id == waiter_id).first() is None
    finally:
        db.close()


def test_onboarding_cannot_grant_platform_super_admin_role():
    """Public onboarding must always create RESTAURANT_OWNER even if a privileged role is injected."""
    tag = _uid()
    username = f"onboard_{tag}"
    resp = client.post(
        "/api/v1/onboarding/register",
        json={
            "restaurant_name": f"Onboard Guard {tag}",
            "owner_full_name": "Normal Founder",
            "owner_email": f"{username}@example.com",
            "owner_username": username,
            "owner_password": "StrongOnboard#2026!",
            "role": "PLATFORM_SUPER_ADMIN",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        assert user is not None
        assert user.role == UserRole.RESTAURANT_OWNER
        assert user.restaurant_id == resp.json()["restaurant_id"]
    finally:
        db.close()

    # Platform super-admin endpoints must reject this onboarded owner
    stats_resp = client.get("/api/v1/platform/stats", headers={"Authorization": f"Bearer {token}"})
    assert stats_resp.status_code == 403


def test_must_change_password_enforcement_flow():
    """Users with must_change_password=True are restricted to /auth/me and /auth/change-password until rotated."""
    tag = _uid()
    initial_pw = "TempBootstrap#2026!"
    new_pw = "RotatedStrong#2026!"
    db = SessionLocal()
    try:
        rest, _, _, _, _ = _create_tenant_and_users(db, tag)
        forced_user = User(
            restaurant_id=rest.id,
            email=f"forced-{tag}@example.com",
            username=f"forced_{tag}",
            hashed_password=get_password_hash(initial_pw),
            full_name="Forced Change User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True,
            must_change_password=True,
        )
        db.add(forced_user)
        db.commit()
        db.refresh(forced_user)

        # 1. Login succeeds and flags must_change_password=True
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": forced_user.username, "password": initial_pw},
        )
        assert login_resp.status_code == 200
        login_body = login_resp.json()
        assert login_body["must_change_password"] is True
        headers = {"Authorization": f"Bearer {login_body['access_token']}"}

        # 2. /auth/me remains permitted so the client can read user/password-change status
        me_resp = client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["must_change_password"] is True

        # 3. Normal protected endpoints are blocked with 403 until password is changed
        assert client.get("/api/v1/auth/staff", headers=headers).status_code == 403
        assert client.get("/api/v1/restaurants/me", headers=headers).status_code == 403

        # 4. Wrong current password must fail without clearing must_change_password
        bad_change = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongPassword123!", "new_password": new_pw},
            headers=headers,
        )
        assert bad_change.status_code == 400
        db.refresh(forced_user)
        assert forced_user.must_change_password is True

        # 5. Valid password change succeeds, clears flag, and restores protected API access
        good_change = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": initial_pw, "new_password": new_pw},
            headers=headers,
        )
        assert good_change.status_code == 200

        db.expire_all()
        refreshed = db.query(User).filter(User.id == forced_user.id).first()
        assert refreshed.must_change_password is False
        assert verify_password(new_pw, refreshed.hashed_password) is True

        # 6. Protected endpoints work immediately after password rotation
        assert client.get("/api/v1/auth/staff", headers=headers).status_code == 200
        assert client.get("/api/v1/restaurants/me", headers=headers).status_code == 200

        # 7. Subsequent login reports must_change_password=False
        relogin = client.post(
            "/api/v1/auth/login",
            json={"username": forced_user.username, "password": new_pw},
        )
        assert relogin.status_code == 200
        assert relogin.json()["must_change_password"] is False
    finally:
        db.close()


def test_must_change_password_blocks_optional_auth_endpoints_until_rotated():
    """Users with must_change_password=True cannot bypass rotation via optional-auth endpoints."""
    tag = _uid()
    initial_pw = "TempOptAuth#2026!"
    new_pw = "RotatedOptAuth#2026!"
    db = SessionLocal()
    try:
        rest, _, _, _, _ = _create_tenant_and_users(db, tag)
        forced_user = User(
            restaurant_id=rest.id,
            email=f"forced-opt-{tag}@example.com",
            username=f"forced_opt_{tag}",
            hashed_password=get_password_hash(initial_pw),
            full_name="Forced Optional Auth User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True,
            must_change_password=True,
        )
        db.add(forced_user)
        db.commit()
        db.refresh(forced_user)

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": forced_user.username, "password": initial_pw},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        optional_auth_paths = [
            "/api/v1/analytics/overview",
            "/api/v1/kitchen/active",
            "/api/v1/tables/",
            "/api/v1/orders/",
            "/api/v1/reservations/",
            "/api/v1/restaurants/",
            "/api/v1/service-requests/",
        ]
        for path in optional_auth_paths:
            blocked = client.get(path, headers=headers)
            assert blocked.status_code == 403, f"Expected 403 on {path}, got {blocked.status_code}"

        # Rotate password
        rotate_resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": initial_pw, "new_password": new_pw},
            headers=headers,
        )
        assert rotate_resp.status_code == 200

        # Normal authenticated access is restored immediately across all optional-auth endpoints
        for path in optional_auth_paths:
            restored = client.get(path, headers=headers)
            assert restored.status_code == 200, f"Expected 200 on {path} after rotation, got {restored.status_code}"
    finally:
        db.close()


def test_must_change_password_blocks_protected_websockets_until_rotated():
    """Users pending password rotation must be rejected (close 1008) on protected WebSocket channels."""
    tag = _uid()
    initial_pw = "TempWsAuth#2026!"
    new_pw = "RotatedWsAuth#2026!"
    db = SessionLocal()
    try:
        rest, _, _, _, _ = _create_tenant_and_users(db, tag)
        forced_user = User(
            restaurant_id=rest.id,
            email=f"forced-ws-{tag}@example.com",
            username=f"forced_ws_{tag}",
            hashed_password=get_password_hash(initial_pw),
            full_name="Forced WS User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True,
            must_change_password=True,
        )
        db.add(forced_user)
        db.commit()
        db.refresh(forced_user)

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": forced_user.username, "password": initial_pw},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        for ws_path in (
            f"/ws/tenant/{rest.id}/admin?token={token}",
            f"/ws/tenant/{rest.id}/kitchen?token={token}",
            f"/ws/tenant/{rest.id}/staff?token={token}",
            f"/ws/kitchen?token={token}",
        ):
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(ws_path) as ws:
                    ws.send_text("PING")
            assert exc_info.value.code == 1008

        # Rotate password
        rotate_resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": initial_pw, "new_password": new_pw},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert rotate_resp.status_code == 200

        # WebSocket connection succeeds immediately after password rotation
        with client.websocket_connect(f"/ws/tenant/{rest.id}/admin?token={token}") as ws:
            ws.send_text("PING")
            reply = json.loads(ws.receive_text())
            assert reply["type"] == "PONG"
            assert reply["tenant_id"] == rest.id
            assert reply["channel"] == "admin"
    finally:
        db.close()


def test_platform_super_admin_requires_explicit_tenant_selection_and_preserves_platform_ops():
    """PLATFORM_SUPER_ADMIN must not silently fall back to tenant 1; platform-wide ops continue working."""
    tag = _uid()
    db = SessionLocal()
    try:
        rest_b, _, _, _, _ = _create_tenant_and_users(db, tag)
        superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        assert superadmin is not None
        assert superadmin.restaurant_id is None
        sa_headers = _auth_header(superadmin)

        # 1. Tenant-scoped operations without explicit restaurant_id must fail closed (400), never touch tenant 1
        for method, path in (
            ("GET", "/api/v1/restaurants/me"),
            ("GET", "/api/v1/restaurants/"),
            ("GET", "/api/v1/subscriptions/my-status"),
            ("GET", "/api/v1/subscriptions/notifications"),
            ("GET", "/api/v1/feedback/analytics"),
            ("GET", "/api/v1/analytics/overview"),
            ("GET", "/api/v1/kitchen/active"),
            ("GET", "/api/v1/tables/"),
            ("GET", "/api/v1/reservations/"),
            ("GET", "/api/v1/service-requests/"),
        ):
            resp = client.request(method, path, headers=sa_headers)
            assert resp.status_code == 400, f"Expected 400 on {method} {path}, got {resp.status_code}"

        put_no_tenant = client.put(
            "/api/v1/restaurants/",
            json={"tagline": "Should Not Mutate Tenant 1"},
            headers=sa_headers,
        )
        assert put_no_tenant.status_code == 400

        table_no_tenant = client.post(
            "/api/v1/tables/",
            json={"table_number": f"T-SA-{tag}", "capacity": 4},
            headers=sa_headers,
        )
        assert table_no_tenant.status_code == 400

        cat_no_tenant = client.post(
            "/api/v1/menu/categories",
            json={"name": f"SA Cat {tag}"},
            headers=sa_headers,
        )
        assert cat_no_tenant.status_code == 400

        # 2. Explicit tenant selection succeeds on the targeted tenant (rest_b, not tenant 1)
        explicit_me = client.get(f"/api/v1/restaurants/me?restaurant_id={rest_b.id}", headers=sa_headers)
        assert explicit_me.status_code == 200
        assert explicit_me.json()["id"] == rest_b.id

        explicit_analytics = client.get(
            f"/api/v1/analytics/overview?restaurant_id={rest_b.id}",
            headers=sa_headers,
        )
        assert explicit_analytics.status_code == 200

        explicit_sub_status = client.get(
            f"/api/v1/subscriptions/my-status?restaurant_id={rest_b.id}",
            headers=sa_headers,
        )
        assert explicit_sub_status.status_code == 200
        assert explicit_sub_status.json()["restaurant_id"] == rest_b.id

        # 3. Legitimate platform-wide operations remain unaffected
        assert client.get("/api/v1/platform/stats", headers=sa_headers).status_code == 200
        assert client.get("/api/v1/platform/restaurants", headers=sa_headers).status_code == 200
        assert client.get("/api/v1/platform/tenants", headers=sa_headers).status_code == 200
        assert client.get("/api/v1/subscriptions/admin/analytics", headers=sa_headers).status_code == 200
        assert client.get("/api/v1/subscriptions/invoices", headers=sa_headers).status_code == 200
    finally:
        db.close()
