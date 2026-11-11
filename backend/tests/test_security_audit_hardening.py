import pytest
import hmac
import hashlib
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, generate_table_qr_token, verify_table_qr_token
from app.core.rate_limiter import login_limiter
from app.models.billing import Bill
from app.core.database import SessionLocal

client = TestClient(app)

def test_login_rate_limiting_brute_force_protection():
    """Verify that multiple consecutive failed logins trigger HTTP 429 Too Many Requests."""
    fake_username = f"attacker_{int(time.time())}"
    
    # 5 failed attempts
    for i in range(5):
        resp = client.post("/api/v1/auth/login", json={
            "username": fake_username,
            "password": "wrong_password_attempt"
        })
        assert resp.status_code == 401

    # 6th attempt must be throttled with 429
    throttled_resp = client.post("/api/v1/auth/login", json={
        "username": fake_username,
        "password": "wrong_password_attempt"
    })
    assert throttled_resp.status_code == 429
    assert "Too many failed login attempts" in throttled_resp.json()["detail"]
    assert "Retry-After" in throttled_resp.headers

def test_offline_payment_access_control():
    """Verify that unauthenticated users cannot record offline payments."""
    db = SessionLocal()
    bill = db.query(Bill).first()
    bill_id = bill.id if bill else 1
    db.close()

    # 1. Unauthenticated request must return 401
    unauth_resp = client.post("/api/v1/payments/offline-payment", json={
        "bill_id": bill_id,
        "amount": 100.0,
        "payment_method": "CASH"
    })
    assert unauth_resp.status_code == 401

    # 2. Staff token (Admin/Waiter) succeeds
    login_resp = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    auth_resp = client.post("/api/v1/payments/offline-payment", json={
        "bill_id": bill_id,
        "amount": 10.0,
        "payment_method": "CASH"
    }, headers=headers)
    assert auth_resp.status_code in [200, 404]

def test_order_price_tampering_prevention():
    """Verify that if a client passes a fake 1.0 unit_price, backend overrides with DB price."""
    # Place an order for item 1 (Truffle Paneer Tikka, base price ₹380.0) with tampered unit_price = 1.0
    tampered_payload = {
        "restaurant_id": 1,
        "table_id": 1,
        "customer_name": "Tamper Test",
        "items": [
            {
                "menu_item_id": 1,
                "item_name": "Truffle Paneer Tikka",
                "unit_price": 1.0,  # Maliciously tampered price!
                "quantity": 1
            }
        ],
        "tip_amount": 0.0
    }

    resp = client.post("/api/v1/orders/", json=tampered_payload)
    assert resp.status_code == 201
    order = resp.json()

    # The order subtotal MUST be ₹380.0, not ₹1.0!
    assert order["subtotal"] >= 380.0
    assert order["items"][0]["unit_price"] >= 380.0

def test_webhook_signature_verification(monkeypatch):
    """Verify kill-switch blocks webhooks with 503 when disabled and signature check fails closed when enabled."""
    fake_payload = b'{"event": "payment.captured"}'

    # 1. With default EMERGENCY_DISABLE_PAYMENTS=True, webhooks return 503 safely
    disabled_resp = client.post(
        "/api/v1/payments/webhook",
        content=fake_payload,
        headers={"Content-Type": "application/json"},
    )
    assert disabled_resp.status_code == 503

    # 2. When payment flows are active, missing or forged X-Razorpay-Signature must fail with 400
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_A_ENABLED", True)

    resp = client.post(
        "/api/v1/payments/webhook",
        content=fake_payload,
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert "Missing X-Razorpay-Signature" in resp.json()["detail"]

    forged_resp = client.post(
        "/api/v1/payments/webhook",
        content=fake_payload,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "forged_signature"},
    )
    assert forged_resp.status_code == 400
    assert "Invalid webhook signature" in forged_resp.json()["detail"]

def test_qr_token_max_age_and_tampering():
    """Verify that forged and expired QR tokens fail verification."""
    # Valid token
    valid_token = generate_table_qr_token(1, 1, "T-01")
    assert verify_table_qr_token(valid_token) is not None

    # Tampered table number
    parts = valid_token.split("_")
    parts[2] = "T-99"
    tampered_token = "_".join(parts)
    assert verify_table_qr_token(tampered_token) is None

    # Expired token (simulate timestamp from 200 days ago)
    old_ts = int(time.time()) - (200 * 86400)
    payload = f"1:1:T-01:{old_ts}"
    sig = hmac.new(settings.QR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    expired_token = f"1_1_T-01_{old_ts}_{sig}"
    assert verify_table_qr_token(expired_token, max_age_days=180) is None


def test_production_blocks_demo_credentials_and_demo_seeding(monkeypatch):
    """Verify production rejects demo passwords/accounts, blocks seeding, and supports strong credentials."""
    from pydantic import ValidationError
    from app.core.config import Settings
    from app.utils.seed_data import seed_database, _resolve_seed_password

    # 1. Production config validator must reject SEED_DEMO_DATA=True
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SEED_DEMO_DATA=True,
            SECRET_KEY="a" * 64,
            DATABASE_URL="postgresql://user:pass@localhost:5432/srmp_prod",
            QR_SECRET="b" * 32,
        )

    # 2. _resolve_seed_password generates strong random secret when env vars are unset
    generated_pw, was_generated = _resolve_seed_password(("SRMP_UNSET_SEED_VAR_999",), "test_staff")
    assert was_generated is True
    assert len(generated_pw) >= 20

    # 3. Switch settings to production cleanly for runtime checks
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with pytest.raises(RuntimeError):
        seed_database()

    # Known demo/weak fixture passwords must be rejected in production login
    for demo_user, demo_pw in (
        ("superadmin", "superadmin123"),
        ("admin", "admin123"),
        (f"owner_{int(time.time())}", "Password@2026"),
    ):
        resp = client.post("/api/v1/auth/login", json={"username": demo_user, "password": demo_pw})
        assert resp.status_code == 403

    # Onboarding in production must reject weak demo passwords and reserved demo emails
    uid = int(time.time() * 1000) % 1000000
    weak_onboard = client.post("/api/v1/onboarding/register", json={
        "restaurant_name": f"Weak Prod Check {uid}",
        "owner_full_name": "Prod Checker",
        "owner_email": f"prodcheck_{uid}@example.com",
        "owner_username": f"prodweak_{uid}",
        "owner_password": "Password@2026",
    })
    assert weak_onboard.status_code == 400

    # Onboarding with a strong password in production succeeds and can log in
    strong_pw = "Str0ng!Prod#Key_9482"
    strong_username = f"prodstrong_{uid}"
    strong_onboard = client.post("/api/v1/onboarding/register", json={
        "restaurant_name": f"Strong Prod Bistro {uid}",
        "owner_full_name": "Strong Owner",
        "owner_email": f"strongowner_{uid}@example.com",
        "owner_username": strong_username,
        "owner_password": strong_pw,
    })
    assert strong_onboard.status_code == 201
    strong_login = client.post("/api/v1/auth/login", json={
        "username": strong_username,
        "password": strong_pw,
    })
    assert strong_login.status_code == 200
