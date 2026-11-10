import hmac
import hashlib
import json
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.billing import Bill, Payment, BillStatus, PaymentRecordStatus
from app.models.subscription import SubscriptionPlan, SubscriptionCoupon, SubscriptionInvoice, SubscriptionPayment
from app.core.security import create_access_token

client = TestClient(app)

@pytest.fixture
def auth_tokens():
    db = SessionLocal()
    # Find or mock staff/owner tokens
    owner = db.query(User).filter(User.username == "owner_spice").first()
    if not owner:
        owner = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.RESTAURANT_OWNER])).first()

    waiter = db.query(User).filter(User.role == UserRole.WAITER).first()
    superadmin = db.query(User).filter(User.username == "superadmin").first()

    owner_token = create_access_token(
        subject=str(owner.id),
        role=owner.role.value,
        restaurant_id=owner.restaurant_id
    )
    waiter_token = create_access_token(
        subject=str(waiter.id),
        role=waiter.role.value,
        restaurant_id=waiter.restaurant_id
    )
    superadmin_token = create_access_token(
        subject=str(superadmin.id),
        role=superadmin.role.value,
        restaurant_id=None
    )

    db.close()
    return {
        "owner": owner_token,
        "waiter": waiter_token,
        "superadmin": superadmin_token
    }

# =============================================================================
# FLOW A: RESTAURANT CUSTOMER PAYMENTS TESTS
# =============================================================================

def test_flow_a_authoritative_calculation_and_order_creation():
    db = SessionLocal()
    # Create test order & bill
    table = db.query(Table).filter(Table.restaurant_id == 1).first()
    order = Order(
        order_number=f"ORD-TEST-PAY-{int(time.time())}",
        restaurant_id=1,
        table_id=table.id,
        subtotal=1000.0,
        tax_amount=50.0,
        service_charge=50.0,
        total_amount=1100.0,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.UNPAID
    )
    db.add(order)
    db.commit()

    bill = Bill(
        bill_number=f"INV-TEST-PAY-{int(time.time())}",
        restaurant_id=1,
        order_id=order.id,
        table_id=table.id,
        subtotal=1000.0,
        tax_percentage=5.0,
        tax_amount=50.0,
        service_charge_percentage=5.0,
        service_charge=50.0,
        final_amount=1100.0,
        status=BillStatus.UNPAID
    )
    db.add(bill)
    db.commit()
    bill_id = bill.id
    db.close()

    # Request Razorpay Order Creation
    res = client.post("/api/v1/payments/razorpay-order", json={
        "bill_id": bill_id,
        "amount": 1100.0,
        "currency": "INR"
    })
    assert res.status_code == 200
    data = res.json()
    assert "razorpay_order_id" in data
    assert data["amount"] == 1100.0
    assert data["amount_paise"] == 110000
    assert data["bill_id"] == bill_id
    assert data["restaurant_id"] == 1

def test_flow_a_payment_signature_verification_success_and_tampered():
    db = SessionLocal()
    table = db.query(Table).filter(Table.restaurant_id == 1).first()
    order = Order(
        order_number=f"ORD-SIG-{int(time.time())}",
        restaurant_id=1,
        table_id=table.id,
        subtotal=500.0,
        tax_amount=25.0,
        service_charge=25.0,
        total_amount=550.0,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.UNPAID
    )
    db.add(order)
    db.commit()

    bill = Bill(
        bill_number=f"INV-SIG-{int(time.time())}",
        restaurant_id=1,
        order_id=order.id,
        table_id=table.id,
        subtotal=500.0,
        tax_percentage=5.0,
        tax_amount=25.0,
        service_charge_percentage=5.0,
        service_charge=25.0,
        final_amount=550.0,
        status=BillStatus.UNPAID
    )
    db.add(bill)
    db.commit()
    bill_id = bill.id
    db.close()

    order_id = f"order_real_test_{int(time.time())}"
    payment_id = f"pay_real_test_{int(time.time())}"
    # Generate cryptographic HMAC SHA256 signature using the active test restaurant key secret
    valid_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    # 1. Tampered signature should be rejected with 400 Bad Request
    tampered_sig = valid_signature[:-4] + "dead"
    res_tampered = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": tampered_sig,
        "amount": 550.0
    })
    assert res_tampered.status_code == 400
    assert "Invalid payment signature" in res_tampered.json()["detail"]

    # 2. Valid cryptographic signature should succeed and update state
    res_valid = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_signature,
        "amount": 550.0
    })
    assert res_valid.status_code == 200
    res_json = res_valid.json()
    assert res_json["success"] is True
    assert res_json["bill_status"] == "PAID"

    # Verify authoritative database update
    db = SessionLocal()
    updated_bill = db.query(Bill).filter(Bill.id == bill_id).first()
    assert updated_bill.status == BillStatus.PAID
    updated_order = db.query(Order).filter(Order.id == updated_bill.order_id).first()
    assert updated_order.payment_status == PaymentStatus.PAID
    assert updated_order.status == OrderStatus.COMPLETED
    db.close()

def test_flow_a_duplicate_payment_callback_idempotency():
    db = SessionLocal()
    table = db.query(Table).filter(Table.restaurant_id == 1).first()
    order = Order(
        order_number=f"ORD-DUP-{int(time.time())}",
        restaurant_id=1,
        table_id=table.id,
        subtotal=200.0,
        tax_amount=10.0,
        service_charge=10.0,
        total_amount=220.0,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.UNPAID
    )
    db.add(order)
    db.commit()

    bill = Bill(
        bill_number=f"INV-DUP-{int(time.time())}",
        restaurant_id=1,
        order_id=order.id,
        table_id=table.id,
        subtotal=200.0,
        tax_percentage=5.0,
        tax_amount=10.0,
        service_charge_percentage=5.0,
        service_charge=10.0,
        final_amount=220.0,
        status=BillStatus.UNPAID
    )
    db.add(bill)
    db.commit()
    bill_id = bill.id
    db.close()

    order_id = f"order_dup_{int(time.time())}"
    payment_id = f"pay_dup_{int(time.time())}"
    signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    # Initial verification
    res1 = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature,
        "amount": 220.0
    })
    assert res1.status_code == 200

    # Duplicate verification call
    res2 = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature,
        "amount": 220.0
    })
    assert res2.status_code == 200
    assert res2.json().get("is_duplicate") is True

    # Assert exactly 1 payment record exists in database
    db = SessionLocal()
    pay_count = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).count()
    assert pay_count == 1
    db.close()

def test_flow_a_raw_body_webhook_signature_and_idempotency():
    db = SessionLocal()
    table = db.query(Table).filter(Table.restaurant_id == 1).first()
    order = Order(
        order_number=f"ORD-WB-{int(time.time())}",
        restaurant_id=1,
        table_id=table.id,
        subtotal=400.0,
        tax_amount=20.0,
        service_charge=20.0,
        total_amount=440.0,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.UNPAID
    )
    db.add(order)
    db.commit()

    bill = Bill(
        bill_number=f"INV-WB-{int(time.time())}",
        restaurant_id=1,
        order_id=order.id,
        table_id=table.id,
        subtotal=400.0,
        tax_percentage=5.0,
        tax_amount=20.0,
        service_charge_percentage=5.0,
        service_charge=20.0,
        final_amount=440.0,
        status=BillStatus.UNPAID
    )
    db.add(bill)
    db.commit()
    bill_id = bill.id
    db.close()

    event_id = f"evt_test_{int(time.time())}"
    pay_id = f"pay_wb_{int(time.time())}"
    webhook_payload = {
        "event_id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": pay_id,
                    "order_id": f"order_wb_{int(time.time())}",
                    "amount": 44000,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "bill_id": str(bill_id),
                        "restaurant_id": "1"
                    }
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode()

    # Generate HMAC SHA256 using restaurant webhook secret
    valid_sig = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    # 1. Invalid signature test
    res_bad = client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": "invalid_sig_xyz"}
    )
    assert res_bad.status_code == 400

    # 2. Valid webhook processing
    res_ok = client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "ok"

    # 3. Duplicate webhook should be acknowledged idempotently without double recording
    res_dup = client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
    )
    assert res_dup.status_code == 200
    assert "already processed" in res_dup.json()["message"]

def test_flow_a_refund_and_cross_tenant_isolation(auth_tokens):
    db = SessionLocal()
    # Create payment on restaurant 1
    bill = db.query(Bill).filter(Bill.restaurant_id == 1, Bill.status == BillStatus.PAID).first()
    payment = Payment(
        bill_id=bill.id,
        restaurant_id=1,
        amount=100.0,
        currency="INR",
        payment_method="RAZORPAY",
        transaction_id=f"tx_refund_test_{int(time.time())}",
        razorpay_payment_id=f"pay_rfnd_{int(time.time())}",
        status=PaymentRecordStatus.SUCCESS
    )
    db.add(payment)
    db.commit()
    payment_id = payment.id
    db.close()

    # Owner of Spice Bistro (restaurant 2) tries to refund restaurant 1 payment -> 403 Forbidden
    res_cross = client.post(
        "/api/v1/payments/refund",
        json={"payment_id": payment_id, "amount": 100.0, "reason": "Unauthorized test"},
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    # owner_spice has restaurant_id = 2, payment is restaurant_id = 1
    assert res_cross.status_code == 403
    assert "Cannot refund payments belonging to another restaurant" in res_cross.json()["detail"]

    # Superadmin refunds payment -> 200 OK
    res_admin = client.post(
        "/api/v1/payments/refund",
        json={"payment_id": payment_id, "amount": 100.0, "reason": "Guest satisfaction"},
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["success"] is True

def test_flow_a_offline_payment_authorization_and_isolation(auth_tokens):
    db = SessionLocal()
    table = db.query(Table).filter(Table.restaurant_id == 1).first()
    order = Order(
        order_number=f"ORD-CASH-{int(time.time())}",
        restaurant_id=1,
        table_id=table.id,
        subtotal=150.0,
        tax_amount=7.5,
        service_charge=7.5,
        total_amount=165.0,
        status=OrderStatus.PLACED,
        payment_status=PaymentStatus.UNPAID
    )
    db.add(order)
    db.commit()

    bill = Bill(
        bill_number=f"INV-CASH-{int(time.time())}",
        restaurant_id=1,
        order_id=order.id,
        table_id=table.id,
        subtotal=150.0,
        tax_percentage=5.0,
        tax_amount=7.5,
        service_charge_percentage=5.0,
        service_charge=7.5,
        final_amount=165.0,
        status=BillStatus.UNPAID
    )
    db.add(bill)
    db.commit()
    bill_id = bill.id
    db.close()

    # Authorized waiter records cash payment
    res = client.post(
        "/api/v1/payments/offline-payment",
        json={"bill_id": bill_id, "amount": 165.0, "payment_method": "CASH"},
        headers={"Authorization": f"Bearer {auth_tokens['waiter']}"}
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["bill_status"] == "PAID"

    # Reconcile endpoint check
    res_rec = client.get(
        f"/api/v1/payments/reconcile/{bill_id}",
        headers={"Authorization": f"Bearer {auth_tokens['waiter']}"}
    )
    assert res_rec.status_code == 200
    assert res_rec.json()["is_balanced"] is True

# =============================================================================
# FLOW B: SRMP SAAS SUBSCRIPTION PAYMENTS TESTS
# =============================================================================

def test_flow_b_subscription_catalog_and_coupon_discount():
    # 1. Fetch available plans
    res_plans = client.get("/api/v1/subscriptions/plans")
    assert res_plans.status_code == 200
    plans = res_plans.json()
    assert len(plans) >= 2
    plan_codes = [p["plan_code"] for p in plans]
    assert "MONTHLY" in plan_codes
    assert "YEARLY" in plan_codes

    # 2. Validate coupon LAUNCH50
    res_coupon = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "LAUNCH50",
        "plan_code": "MONTHLY"
    })
    assert res_coupon.status_code == 200
    coupon_data = res_coupon.json()
    assert coupon_data["is_valid"] is True
    assert coupon_data["discount_percentage"] == 50.0
    assert coupon_data["discount_paise"] > 0

    # 3. Test invalid coupon
    res_invalid = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "NON_EXISTENT_CODE",
        "plan_code": "MONTHLY"
    })
    assert res_invalid.status_code == 200
    assert res_invalid.json()["is_valid"] is False

def test_flow_b_subscription_checkout_platform_merchant(auth_tokens):
    # Restaurant owner checks out MONTHLY plan with LAUNCH50 coupon
    res = client.post(
        "/api/v1/subscriptions/checkout",
        json={
            "plan_code": "MONTHLY",
            "billing_cycle": "MONTHLY",
            "coupon_code": "LAUNCH50"
        },
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "razorpay_order_id" in data
    assert data["key_id"] == settings.PLATFORM_RAZORPAY_KEY_ID
    assert data["subtotal_paise"] == 199900
    assert data["discount_paise"] == 99950
    # Tax 18% on (199900 - 99950 = 99950) = 17991 paise
    assert data["tax_paise"] == 17991
    assert data["final_amount_paise"] == 117941

def test_flow_b_subscription_payment_verification_and_tenant_activation(auth_tokens):
    # 1. Create checkout invoice
    checkout_res = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY", "billing_cycle": "MONTHLY"},
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    invoice_id = checkout_res.json()["invoice_id"]
    order_id = checkout_res.json()["razorpay_order_id"]
    payment_id = f"pay_saas_{int(time.time())}"

    # Generate signature with platform key secret
    valid_sig = hmac.new(
        settings.PLATFORM_RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    # 2. Tampered signature should fail
    res_tampered = client.post("/api/v1/subscriptions/verify", json={
        "invoice_id": invoice_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_sig + "fake"
    })
    assert res_tampered.status_code == 400

    # 3. Valid signature should activate subscription
    res_valid = client.post("/api/v1/subscriptions/verify", json={
        "invoice_id": invoice_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": valid_sig
    })
    assert res_valid.status_code == 200
    assert res_valid.json()["success"] is True
    assert res_valid.json()["subscription_status"] == "ACTIVE"

    # 4. Invoices ledger check
    inv_res = client.get("/api/v1/subscriptions/invoices", headers={"Authorization": f"Bearer {auth_tokens['owner']}"})
    assert inv_res.status_code == 200
    assert any(inv["id"] == invoice_id and inv["status"] == "PAID" for inv in inv_res.json())

def test_flow_b_platform_webhook_signature_and_idempotency():
    db = SessionLocal()
    # Create an unpaid invoice
    inv = SubscriptionInvoice(
        invoice_number=f"SRMP-INV-TEST-{int(time.time())}",
        restaurant_id=1,
        plan_id=1,
        billing_cycle="MONTHLY",
        subtotal_paise=199900,
        discount_paise=0,
        tax_paise=35982,
        final_amount_paise=235882,
        status="UNPAID"
    )
    db.add(inv)
    db.commit()
    inv_id = inv.id
    db.close()

    event_id = f"evt_platform_saas_{int(time.time())}"
    webhook_payload = {
        "event_id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_saas_webhook_{int(time.time())}",
                    "amount": 235882,
                    "status": "captured",
                    "notes": {
                        "invoice_id": str(inv_id),
                        "flow": "SRMP_SAAS_SUBSCRIPTION"
                    }
                }
            }
        }
    }
    raw_body = json.dumps(webhook_payload).encode()
    valid_sig = hmac.new(
        settings.PLATFORM_RAZORPAY_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    # Post platform webhook
    res = client.post(
        "/api/v1/subscriptions/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Verify invoice status updated to PAID in DB
    db = SessionLocal()
    updated_inv = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == inv_id).first()
    assert updated_inv.status == "PAID"
    db.close()

    # Re-post same event -> should be acknowledged idempotently
    res_dup = client.post(
        "/api/v1/subscriptions/webhook",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Razorpay-Signature": valid_sig}
    )
    assert res_dup.status_code == 200
    assert "already processed" in res_dup.json()["message"]
