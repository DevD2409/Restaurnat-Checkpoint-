import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

import app.main as app_main
from app.core.database import SessionLocal
from app.core.security import create_access_token, verify_table_qr_token, get_password_hash
from app.core.dependencies import require_feature_entitlement
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.models.table import Table, TableStatus
from app.models.subscription import SubscriptionPlan

client = TestClient(app_main.app)

# Register test routes guarded by require_feature_entitlement if not already attached
test_features_router = APIRouter(prefix="/api/v1/test-entitlements", tags=["Test Feature Entitlements"])

@test_features_router.get("/kds")
def get_kds_feature(tenant: Restaurant = Depends(require_feature_entitlement("kds_access"))):
    return {"status": "ok", "feature": "kds_access", "tenant_id": tenant.id}

@test_features_router.get("/branding")
def get_branding_feature(tenant: Restaurant = Depends(require_feature_entitlement("custom_branding"))):
    return {"status": "ok", "feature": "custom_branding", "tenant_id": tenant.id}

@test_features_router.get("/multi-branch")
def get_multi_branch_feature(tenant: Restaurant = Depends(require_feature_entitlement("multi_branch"))):
    return {"status": "ok", "feature": "multi_branch", "tenant_id": tenant.id}

app_main.app.include_router(test_features_router)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _make_token(user: User) -> str:
    return create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
    )


def test_public_onboarding_cannot_select_paid_plan():
    """Test 1: Public onboarding cannot select PRO/ENTERPRISE to obtain paid access."""
    uid = _uid()
    payload = {
        "restaurant_name": f"Trial Test Bistro {uid}",
        "slug": f"trial-bistro-{uid}",
        "owner_full_name": f"Owner {uid}",
        "owner_email": f"owner_{uid}@example.com",
        "owner_username": f"owner_{uid}",
        "owner_password": "SecurePassword#2026!",
        "subscription_plan": "ENTERPRISE",
        "table_count": 3
    }
    response = client.post("/api/v1/onboarding/register", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    restaurant_id = data["restaurant_id"]

    db = SessionLocal()
    try:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        assert restaurant is not None
        # Enforced finite trial, never arbitrary enterprise/pro plan
        assert restaurant.subscription_plan == "TRIAL"
        assert restaurant.subscription_status == "TRIAL"
    finally:
        db.close()


def test_new_restaurant_receives_finite_trial_with_expiration():
    """Test 2: New restaurants receive finite 14-day TRIAL entitlement with expiration."""
    uid = _uid()
    payload = {
        "restaurant_name": f"Finite Trial Cafe {uid}",
        "slug": f"finite-trial-{uid}",
        "owner_full_name": f"Owner {uid}",
        "owner_email": f"finite_owner_{uid}@example.com",
        "owner_username": f"finite_owner_{uid}",
        "owner_password": "SecurePassword#2026!",
        "table_count": 3
    }
    response = client.post("/api/v1/onboarding/register", json=payload)
    assert response.status_code == 201
    restaurant_id = response.json()["restaurant_id"]

    db = SessionLocal()
    try:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        assert restaurant.subscription_expires_at is not None

        exp = restaurant.subscription_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Expected approx 14 days in the future
        diff_days = (exp - now).total_seconds() / 86400
        assert 13 <= diff_days <= 15
        assert restaurant.evaluate_subscription_status() == "ACTIVE"
    finally:
        db.close()


def test_expired_trials_cannot_access_paid_features():
    """Test 3: Expired trials cannot access paid features (fail closed 403)."""
    uid = _uid()
    db = SessionLocal()
    try:
        # Create restaurant with expired trial
        past_date = datetime.now(timezone.utc) - timedelta(days=20)
        restaurant = Restaurant(
            name=f"Expired Cafe {uid}",
            slug=f"expired-cafe-{uid}",
            email=f"expired-{uid}@example.com",
            subscription_plan="TRIAL",
            subscription_status="TRIAL",
            subscription_expires_at=past_date,
            is_active=True
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        owner = User(
            restaurant_id=restaurant.id,
            email=f"exp-owner-{uid}@example.com",
            username=f"exp_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name=f"Owner {uid}",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        token = _make_token(owner)
    finally:
        db.close()

    response = client.get("/api/v1/test-entitlements/kds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
    assert "restricted" in response.json()["detail"].lower() or "expired" in response.json()["detail"].lower()


def test_unknown_subscription_plan_fails_closed():
    """Test 4: Unknown subscription plan fails closed on require_feature_entitlement (403)."""
    uid = _uid()
    db = SessionLocal()
    try:
        restaurant = Restaurant(
            name=f"Unknown Tier Cafe {uid}",
            slug=f"unknown-tier-{uid}",
            email=f"unknown-{uid}@example.com",
            subscription_plan="ULTRA_UNKNOWN_CUSTOM_TIER",
            subscription_status="ACTIVE",
            subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_active=True
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        owner = User(
            restaurant_id=restaurant.id,
            email=f"unknown-owner-{uid}@example.com",
            username=f"unk_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name=f"Owner {uid}",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        token = _make_token(owner)
    finally:
        db.close()

    response = client.get("/api/v1/test-entitlements/kds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
    assert "unknown" in response.json()["detail"].lower() or "not entitled" in response.json()["detail"].lower()


def test_missing_or_inactive_plan_record_fails_closed():
    """Test 5: Missing or inactive plan records do not grant paid entitlements (fail closed 403)."""
    uid = _uid()
    db = SessionLocal()
    try:
        # Create an inactive plan in the database
        inactive_plan = SubscriptionPlan(
            plan_code=f"INACTIVE_PLAN_{uid}",
            name="Inactive Special",
            price_paise=100000,
            is_active=False
        )
        db.add(inactive_plan)
        db.commit()

        restaurant = Restaurant(
            name=f"Inactive Plan Cafe {uid}",
            slug=f"inactive-plan-{uid}",
            email=f"inact-{uid}@example.com",
            subscription_plan=inactive_plan.plan_code,
            subscription_status="ACTIVE",
            subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_active=True
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        owner = User(
            restaurant_id=restaurant.id,
            email=f"inact-owner-{uid}@example.com",
            username=f"inact_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name=f"Owner {uid}",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        token = _make_token(owner)
    finally:
        db.close()

    response = client.get("/api/v1/test-entitlements/kds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
    assert "inactive" in response.json()["detail"].lower() or "unknown" in response.json()["detail"].lower()


def test_suspended_restaurant_fails_closed():
    """Test 6: Suspended restaurants cannot use restricted features (fail closed 403)."""
    uid = _uid()
    db = SessionLocal()
    try:
        restaurant = Restaurant(
            name=f"Suspended Cafe {uid}",
            slug=f"suspended-cafe-{uid}",
            email=f"susp-{uid}@example.com",
            subscription_plan="TRIAL",
            subscription_status="SUSPENDED",
            subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            is_active=True
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)

        owner = User(
            restaurant_id=restaurant.id,
            email=f"susp-owner-{uid}@example.com",
            username=f"susp_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name=f"Owner {uid}",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        token = _make_token(owner)
    finally:
        db.close()

    response = client.get("/api/v1/test-entitlements/kds", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403, response.text
    assert "suspended" in response.json()["detail"].lower()


def test_qr_tokens_use_actual_database_table_ids():
    """Test 7: QR tokens use actual database table IDs (tested when table ID sequence starts above 1)."""
    uid = _uid()
    db = SessionLocal()
    try:
        # Pre-seed a dummy restaurant and tables so new table IDs are >= 10
        dummy_rest = Restaurant(
            name=f"Pre-seed Rest {uid}",
            slug=f"preseed-rest-{uid}",
            is_active=True
        )
        db.add(dummy_rest)
        db.commit()
        db.refresh(dummy_rest)

        for i in range(15):
            t = Table(
                restaurant_id=dummy_rest.id,
                table_number=f"Pre{i}",
                is_active=True
            )
            db.add(t)
        db.commit()
    finally:
        db.close()

    # Now onboard a new restaurant
    payload = {
        "restaurant_name": f"QR ID Test Bistro {uid}",
        "slug": f"qr-id-bistro-{uid}",
        "owner_full_name": f"Owner {uid}",
        "owner_email": f"qrid_owner_{uid}@example.com",
        "owner_username": f"qrid_owner_{uid}",
        "owner_password": "SecurePassword#2026!",
        "table_count": 3
    }
    response = client.post("/api/v1/onboarding/register", json=payload)
    assert response.status_code == 201, response.text
    new_restaurant_id = response.json()["restaurant_id"]

    db = SessionLocal()
    try:
        tables = db.query(Table).filter(Table.restaurant_id == new_restaurant_id).order_by(Table.id.asc()).all()
        assert len(tables) == 3

        for idx, table in enumerate(tables, start=1):
            # Crucial verification: table.id is definitely > 3 because of pre-seeded tables
            assert table.id > 3
            # And loop index would have been idx (1, 2, or 3)
            assert table.id != idx

            # Verify the QR token payload matches actual table.id
            verified = verify_table_qr_token(table.qr_token)
            assert verified is not None
            assert verified["restaurant_id"] == new_restaurant_id
            assert verified["table_id"] == table.id
            assert verified["table_number"] == table.table_number
    finally:
        db.close()


def test_qr_validation_works_with_table_id_different_from_index():
    """Test 8: QR validation works when table IDs differ from loop indices."""
    uid = _uid()
    # Onboard restaurant
    payload = {
        "restaurant_name": f"QR Validate Rest {uid}",
        "slug": f"qr-val-rest-{uid}",
        "owner_full_name": f"Owner {uid}",
        "owner_email": f"qrval_owner_{uid}@example.com",
        "owner_username": f"qrval_owner_{uid}",
        "owner_password": "SecurePassword#2026!",
        "table_count": 2
    }
    response = client.post("/api/v1/onboarding/register", json=payload)
    assert response.status_code == 201
    rest_id = response.json()["restaurant_id"]

    db = SessionLocal()
    try:
        table = db.query(Table).filter(Table.restaurant_id == rest_id).first()
        assert table is not None
        qr_token = table.qr_token
        actual_table_id = table.id
    finally:
        db.close()

    # Call /api/v1/tables/validate-qr with this token
    val_resp = client.post("/api/v1/tables/validate-qr", json={"qr_token": qr_token})
    assert val_resp.status_code == 200, val_resp.text
    val_data = val_resp.json()
    assert val_data["table_id"] == actual_table_id
    assert val_data["restaurant_id"] == rest_id


def test_duplicate_staff_email_update_returns_409():
    """Test 9: Duplicate staff email update returns 409 Conflict."""
    uid = _uid()
    db = SessionLocal()
    try:
        rest = Restaurant(
            name=f"Staff Email Rest {uid}",
            slug=f"staff-email-rest-{uid}",
            is_active=True
        )
        db.add(rest)
        db.commit()
        db.refresh(rest)

        owner = User(
            restaurant_id=rest.id,
            email=f"owner_{uid}@example.com",
            username=f"owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Owner User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        staff1 = User(
            restaurant_id=rest.id,
            email=f"staff1_{uid}@example.com",
            username=f"staff1_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Staff One",
            role=UserRole.WAITER,
            is_active=True
        )
        staff2 = User(
            restaurant_id=rest.id,
            email=f"staff2_{uid}@example.com",
            username=f"staff2_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Staff Two",
            role=UserRole.WAITER,
            is_active=True
        )
        db.add_all([owner, staff1, staff2])
        db.commit()
        db.refresh(owner)
        db.refresh(staff1)
        db.refresh(staff2)

        owner_token = _make_token(owner)
        staff2_id = staff2.id
        staff1_email = staff1.email
    finally:
        db.close()

    # Try updating staff2's email to staff1's email
    resp = client.put(
        f"/api/v1/auth/staff/{staff2_id}",
        json={"email": staff1_email},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 409, resp.text
    assert "already exists" in resp.json()["detail"].lower()


def test_staff_passwords_shorter_than_8_chars_rejected():
    """Test 10: Staff passwords shorter than 8 characters are rejected."""
    uid = _uid()
    db = SessionLocal()
    try:
        rest = Restaurant(
            name=f"Password Policy Rest {uid}",
            slug=f"pwd-policy-rest-{uid}",
            is_active=True
        )
        db.add(rest)
        db.commit()
        db.refresh(rest)

        owner = User(
            restaurant_id=rest.id,
            email=f"pwd_owner_{uid}@example.com",
            username=f"pwd_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Owner User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        staff = User(
            restaurant_id=rest.id,
            email=f"pwd_staff_{uid}@example.com",
            username=f"pwd_staff_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Staff User",
            role=UserRole.WAITER,
            is_active=True
        )
        db.add_all([owner, staff])
        db.commit()
        db.refresh(owner)
        db.refresh(staff)

        owner_token = _make_token(owner)
        staff_id = staff.id
    finally:
        db.close()

    # 1. Onboarding short password
    resp_onboard = client.post("/api/v1/onboarding/register", json={
        "restaurant_name": f"Short Pwd Rest {uid}",
        "slug": f"short-pwd-{uid}",
        "owner_full_name": "Short Pwd",
        "owner_email": f"short_{uid}@example.com",
        "owner_username": f"short_{uid}",
        "owner_password": "short",
    })
    assert resp_onboard.status_code == 400
    assert "at least 8 characters" in resp_onboard.json()["detail"]

    # 2. Create staff short password
    resp_create = client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"new_short_{uid}@example.com",
            "username": f"new_short_{uid}",
            "password": "12345",
            "full_name": "Short Staff",
            "role": "WAITER",
        },
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp_create.status_code == 400
    assert "at least 8 characters" in resp_create.json()["detail"]

    # 3. Update staff short password
    resp_update = client.put(
        f"/api/v1/auth/staff/{staff_id}",
        json={"password": "shortpw"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp_update.status_code == 400
    assert "at least 8 characters" in resp_update.json()["detail"]


def test_unauthorized_managers_cannot_change_razorpay_or_is_active():
    """Test 11: Unauthorized managers cannot change Razorpay credentials or is_active (403)."""
    uid = _uid()
    db = SessionLocal()
    try:
        rest = Restaurant(
            name=f"Manager Restrict Rest {uid}",
            slug=f"mgr-restrict-rest-{uid}",
            is_active=True
        )
        db.add(rest)
        db.commit()
        db.refresh(rest)

        owner = User(
            restaurant_id=rest.id,
            email=f"mgr_owner_{uid}@example.com",
            username=f"mgr_owner_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Owner User",
            role=UserRole.RESTAURANT_OWNER,
            is_active=True
        )
        manager = User(
            restaurant_id=rest.id,
            email=f"mgr_user_{uid}@example.com",
            username=f"mgr_user_{uid}",
            hashed_password=get_password_hash("SecurePassword#2026!"),
            full_name="Manager User",
            role=UserRole.MANAGER,
            is_active=True
        )
        db.add_all([owner, manager])
        db.commit()
        db.refresh(owner)
        db.refresh(manager)

        owner_token = _make_token(owner)
        mgr_token = _make_token(manager)
        rest_id = rest.id
    finally:
        db.close()

    # Manager attempting to update razorpay_key_id via PUT /
    resp1 = client.put(
        "/api/v1/restaurants/",
        json={"razorpay_key_id": "rzp_tampered_key"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert resp1.status_code == 403, resp1.text
    assert "Access denied" in resp1.json()["detail"]

    # Manager attempting to update is_active via PUT /{id}
    resp2 = client.put(
        f"/api/v1/restaurants/{rest_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert resp2.status_code == 403, resp2.text
    assert "Access denied" in resp2.json()["detail"]

    # Manager attempting to update razorpay_key_secret via PUT /{id}
    resp3 = client.put(
        f"/api/v1/restaurants/{rest_id}",
        json={"razorpay_key_secret": "tampered_secret"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert resp3.status_code == 403, resp3.text
    assert "Access denied" in resp3.json()["detail"]

    # Manager updating normal operational field (tagline) should SUCCEED
    resp4 = client.put(
        "/api/v1/restaurants/",
        json={"tagline": "Updated by manager safely"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert resp4.status_code == 200, resp4.text
    assert resp4.json()["tagline"] == "Updated by manager safely"

    # Owner updating sensitive field SHOULD succeed
    resp5 = client.put(
        "/api/v1/restaurants/",
        json={"razorpay_key_id": "rzp_test_legit_key_123"},
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp5.status_code == 200, resp5.text
    assert resp5.json()["razorpay_key_id"] == "rzp_test_legit_key_123"


def test_legitimate_onboarding_ordering_owner_lifecycle():
    """Test 12: Legitimate onboarding, customer QR ordering, and owner management continue working."""
    uid = _uid()
    # 1. Onboard a new restaurant
    payload = {
        "restaurant_name": f"Grand Palace {uid}",
        "slug": f"grand-palace-{uid}",
        "owner_full_name": f"Grand Owner {uid}",
        "owner_email": f"grand_owner_{uid}@example.com",
        "owner_username": f"grand_owner_{uid}",
        "owner_password": "StrongOwnerPassword#2026!",
        "table_count": 3
    }
    onboard_res = client.post("/api/v1/onboarding/register", json=payload)
    assert onboard_res.status_code == 201, onboard_res.text
    onboard_data = onboard_res.json()
    token = onboard_data["access_token"]
    rest_id = onboard_data["restaurant_id"]

    # 2. Check profile
    me_res = client.get("/api/v1/restaurants/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["name"] == f"Grand Palace {uid}"
    assert me_res.json()["subscription_plan"] == "TRIAL"

    # 3. Verify trial entitlement allows kds_access, but forbids custom_branding (TRIAL restrictions)
    kds_res = client.get("/api/v1/test-entitlements/kds", headers={"Authorization": f"Bearer {token}"})
    assert kds_res.status_code == 200
    assert kds_res.json()["status"] == "ok"

    branding_res = client.get("/api/v1/test-entitlements/branding", headers={"Authorization": f"Bearer {token}"})
    assert branding_res.status_code == 403
    assert "not included in the trial plan" in branding_res.json()["detail"].lower()

    # 4. Create a manager
    mgr_res = client.post(
        "/api/v1/auth/staff",
        json={
            "email": f"mgr_{uid}@example.com",
            "username": f"mgr_{uid}",
            "password": "StrongManagerPassword#2026!",
            "full_name": "Grand Manager",
            "role": "MANAGER"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert mgr_res.status_code == 201, mgr_res.text

    # 5. Prevent self-deactivation or self-demotion of last active owner
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.username == f"grand_owner_{uid}").first()
        owner_id = owner.id
    finally:
        db.close()

    # Self-deactivation attempt
    deact_res = client.put(
        f"/api/v1/auth/staff/{owner_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert deact_res.status_code == 400
    assert "cannot deactivate the last active owner" in deact_res.json()["detail"].lower()

    # Self-demotion attempt
    demote_res = client.put(
        f"/api/v1/auth/staff/{owner_id}",
        json={"role": "WAITER"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert demote_res.status_code == 400
    assert "cannot demote the last active owner" in demote_res.json()["detail"].lower()

    # 6. Customer fetches menu by restaurant id
    menu_res = client.get(f"/api/v1/menu/categories?restaurant_id={rest_id}")
    assert menu_res.status_code == 200
    assert len(menu_res.json()) >= 1
    assert menu_res.json()[0]["name"] == "Chef's Specials"
