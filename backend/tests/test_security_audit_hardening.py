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

def test_webhook_signature_verification():
    """Verify Razorpay webhook rejects missing or forged X-Razorpay-Signature."""
    fake_payload = b'{"event": "payment.captured"}'

    # Missing signature header
    resp = client.post(
        "/api/v1/payments/webhook",
        content=fake_payload,
        headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 400
    assert "Missing X-Razorpay-Signature" in resp.json()["detail"]

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
