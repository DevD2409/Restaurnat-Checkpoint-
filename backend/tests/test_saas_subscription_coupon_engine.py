import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.subscription import (
    SubscriptionPlan, SubscriptionCoupon, SubscriptionCouponRedemption,
    SubscriptionInvoice, SubscriptionPayment, SubscriptionNotification
)
from app.core.security import create_access_token

client = TestClient(app)

@pytest.fixture
def auth_tokens():
    db = SessionLocal()
    owner = db.query(User).filter(User.username == "owner_spice").first()
    if not owner:
        owner = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.RESTAURANT_OWNER])).first()

    superadmin = db.query(User).filter(User.username == "superadmin").first()

    owner_token = create_access_token(
        subject=str(owner.id),
        role=owner.role.value,
        restaurant_id=owner.restaurant_id
    )
    superadmin_token = create_access_token(
        subject=str(superadmin.id),
        role=superadmin.role.value,
        restaurant_id=None
    )
    db.close()
    return {
        "owner": owner_token,
        "superadmin": superadmin_token
    }

# 1. Test Integer Paise Plans: Monthly ₹1,999 (199900 paise) & Yearly ₹11,999 (1199900 paise)
def test_subscription_plans_integer_paise():
    res = client.get("/api/v1/subscriptions/plans")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) >= 2

    monthly = next(p for p in plans if p["plan_code"] == "MONTHLY")
    yearly = next(p for p in plans if p["plan_code"] == "YEARLY")

    # Verify integer paise
    assert isinstance(monthly["price_paise"], int)
    assert monthly["price_paise"] == 199900
    assert monthly["price_inr"] == 1999.0
    assert monthly["duration_days"] == 30

    assert isinstance(yearly["price_paise"], int)
    assert yearly["price_paise"] == 1199900
    assert yearly["price_inr"] == 11999.0
    assert yearly["duration_days"] == 365

    # Check entitlements
    assert "kds_access" in monthly["entitlements"]
    assert yearly["entitlements"]["multi_branch"] is True

# 2. Test Coupon Validation: Monthly coupon reduces ₹1,999 to ₹999 & Yearly reduces ₹11,999 to ₹9,999
def test_coupon_validation_monthly_and_yearly_discounts():
    # Monthly: ₹1,999 - ₹1,000 = ₹999
    res_m = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "MONTHLY999",
        "plan_code": "MONTHLY"
    })
    assert res_m.status_code == 200
    data_m = res_m.json()
    assert data_m["is_valid"] is True
    assert data_m["discount_paise"] == 100000  # ₹1,000 off
    assert data_m["final_amount_paise"] == 99900  # ₹999 payable
    assert data_m["final_amount_inr"] == 999.0

    # Yearly: ₹11,999 - ₹2,000 = ₹9,999
    res_y = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "YEARLY9999",
        "plan_code": "YEARLY"
    })
    assert res_y.status_code == 200
    data_y = res_y.json()
    assert data_y["is_valid"] is True
    assert data_y["discount_paise"] == 200000  # ₹2,000 off
    assert data_y["final_amount_paise"] == 999900  # ₹9,999 payable
    assert data_y["final_amount_inr"] == 9999.0

# 3. Test Coupon Plan Mismatch Rejection
def test_coupon_plan_mismatch_rejection():
    # Attempting to use Yearly coupon on Monthly plan
    res = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "YEARLY9999",
        "plan_code": "MONTHLY"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert "not eligible for the MONTHLY plan" in data["message"]

    # Attempting to use Monthly coupon on Yearly plan
    res2 = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "MONTHLY999",
        "plan_code": "YEARLY"
    })
    assert res2.status_code == 200
    assert res2.json()["is_valid"] is False

# 4. Test Expired and Inactive Coupon Rejection
def test_coupon_expiry_and_inactive_rejection(auth_tokens):
    db = SessionLocal()
    # Clean up any existing test coupons from previous test runs
    db.query(SubscriptionCoupon).filter(SubscriptionCoupon.code.in_(["EXPIRED100", "DISABLED50"])).delete(synchronize_session=False)
    db.commit()
    # Create expired coupon
    expired_coupon = SubscriptionCoupon(
        code="EXPIRED100",
        discount_paise=50000,
        discount_type="FIXED_AMOUNT",
        eligible_plan_codes="*",
        start_date=datetime.now() - timedelta(days=10),
        end_date=datetime.now() - timedelta(days=1),
        max_uses_global=100,
        max_uses_per_restaurant=1,
        is_active=True
    )
    # Create inactive coupon
    inactive_coupon = SubscriptionCoupon(
        code="DISABLED50",
        discount_paise=50000,
        discount_type="FIXED_AMOUNT",
        eligible_plan_codes="*",
        is_active=False
    )
    db.add(expired_coupon)
    db.add(inactive_coupon)
    db.commit()
    db.close()

    # Test expired coupon
    res_exp = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "EXPIRED100",
        "plan_code": "MONTHLY"
    })
    assert res_exp.status_code == 200
    assert res_exp.json()["is_valid"] is False
    assert "expired" in res_exp.json()["message"]

    # Test inactive coupon
    res_inact = client.post("/api/v1/subscriptions/coupons/validate", json={
        "code": "DISABLED50",
        "plan_code": "MONTHLY"
    })
    assert res_inact.status_code == 200
    assert res_inact.json()["is_valid"] is False
    assert "inactive" in res_inact.json()["message"]

# 5. Test Pre-Checkout Preview with 18% GST and Billing Dates
def test_checkout_preview_inspection():
    res = client.post("/api/v1/subscriptions/checkout/preview", json={
        "plan_code": "MONTHLY",
        "coupon_code": "MONTHLY999"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["subtotal_paise"] == 199900
    assert data["discount_paise"] == 100000
    # Taxable: 99900 paise. 18% GST = 17982 paise (₹179.82). Final = 99900 + 17982 = 117882 paise (₹1,178.82)
    assert data["tax_paise"] == 17982
    assert data["final_amount_paise"] == 117882
    assert data["final_amount_inr"] == 1178.82
    assert "billing_start_date" in data
    assert "billing_end_date" in data

# 6. Test Per-Restaurant Coupon Limit and Misuse Prevention
def test_per_restaurant_coupon_limit_enforcement(auth_tokens):
    db = SessionLocal()
    # Ensure fresh coupon with max_uses_per_restaurant = 1
    code = f"ONEOFF_{int(time.time())}"
    coupon = SubscriptionCoupon(
        code=code,
        discount_paise=50000,
        discount_type="FIXED_AMOUNT",
        eligible_plan_codes="MONTHLY",
        max_uses_global=100,
        max_uses_per_restaurant=1,
        is_active=True
    )
    db.add(coupon)
    db.commit()
    db.close()

    # 1. First checkout with coupon succeeds
    checkout_res = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY", "coupon_code": code},
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    assert checkout_res.status_code == 200
    inv_id = checkout_res.json()["invoice_id"]
    order_id = checkout_res.json()["razorpay_order_id"]
    pay_id = f"pay_test_{int(time.time())}"

    # Verify payment
    sig = hmac.new(
        settings.PLATFORM_RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{pay_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    verify_res = client.post("/api/v1/subscriptions/verify", json={
        "invoice_id": inv_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": pay_id,
        "razorpay_signature": sig
    })
    assert verify_res.status_code == 200

    # 2. Second checkout attempt with the same coupon for this restaurant MUST fail
    checkout_res2 = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY", "coupon_code": code},
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    assert checkout_res2.status_code == 400
    assert "already been redeemed by this restaurant" in checkout_res2.json()["detail"]

# 7. Test Subscription Renewal Extends Existing Expiration
def test_subscription_renewal_extends_expiration(auth_tokens):
    db = SessionLocal()
    rest = db.query(Restaurant).filter(Restaurant.id == 2).first()
    future_date = datetime.now() + timedelta(days=20)
    rest.subscription_expires_at = future_date
    rest.subscription_status = "ACTIVE"
    db.commit()
    db.close()

    # Checkout and verify another monthly subscription
    checkout_res = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY"},
        headers={"Authorization": f"Bearer {auth_tokens['owner']}"}
    )
    assert checkout_res.status_code == 200
    inv_id = checkout_res.json()["invoice_id"]
    order_id = checkout_res.json()["razorpay_order_id"]
    pay_id = f"pay_renew_{int(time.time())}"

    sig = hmac.new(
        settings.PLATFORM_RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{pay_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    verify_res = client.post("/api/v1/subscriptions/verify", json={
        "invoice_id": inv_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": pay_id,
        "razorpay_signature": sig
    })
    assert verify_res.status_code == 200

    # Verify that expiration was extended from future_date + 30 days (~50 days from now)
    db = SessionLocal()
    updated_rest = db.query(Restaurant).filter(Restaurant.id == 2).first()
    expected_min = future_date + timedelta(days=29)
    assert updated_rest.subscription_expires_at >= expected_min
    db.close()

# 8. Test Grace Period and Expiry Evaluation Logic
def test_grace_period_and_expiry_evaluation():
    db = SessionLocal()
    rest = db.query(Restaurant).filter(Restaurant.id == 1).first()
    rest.grace_period_days = 7

    # Case A: Expired 2 days ago -> Within 7 days grace period -> PAST_DUE
    rest.subscription_expires_at = datetime.now() - timedelta(days=2)
    rest.subscription_status = "ACTIVE"
    assert rest.evaluate_subscription_status() == "PAST_DUE"

    # Case B: Expired 10 days ago -> Beyond 7 days grace period -> EXPIRED
    rest.subscription_expires_at = datetime.now() - timedelta(days=10)
    assert rest.evaluate_subscription_status() == "EXPIRED"

    # Case C: Valid until next week -> ACTIVE
    rest.subscription_expires_at = datetime.now() + timedelta(days=7)
    assert rest.evaluate_subscription_status() == "ACTIVE"
    db.close()

# 9. Test Super Admin Subscription Analytics & MRR Calculation
def test_superadmin_subscription_analytics(auth_tokens):
    res = client.get(
        "/api/v1/subscriptions/admin/analytics",
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "mrr_paise" in data
    assert "mrr_inr" in data
    assert "arr_inr" in data
    assert "active_tenants" in data
    assert "total_coupons_redeemed" in data
    assert data["arr_inr"] == data["mrr_inr"] * 12

# 10. Test Super Admin Plan and Coupon Management
def test_superadmin_plan_and_coupon_management(auth_tokens):
    # 1. Super Admin creates a new tier
    new_plan_code = f"VIP_{int(time.time())}"
    res_p = client.post(
        "/api/v1/subscriptions/admin/plans",
        json={
            "plan_code": new_plan_code,
            "name": "VIP Platinum Plan",
            "billing_cycle": "MONTHLY",
            "price_paise": 799900,
            "duration_days": 30,
            "max_tables": 100
        },
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res_p.status_code == 200
    plan_id = res_p.json()["id"]

    # Toggle plan status
    res_toggle = client.patch(
        f"/api/v1/subscriptions/admin/plans/{plan_id}?is_active=false",
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_active"] is False

    # 2. Super Admin creates a new coupon
    new_coupon_code = f"DISC_{int(time.time())}"
    res_c = client.post(
        "/api/v1/subscriptions/admin/coupons",
        json={
            "code": new_coupon_code,
            "discount_paise": 50000,
            "discount_type": "FIXED_AMOUNT",
            "eligible_plan_codes": "MONTHLY",
            "max_uses_global": 200,
            "max_uses_per_restaurant": 1
        },
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res_c.status_code == 200
    coupon_id = res_c.json()["id"]

    # Toggle coupon status
    res_toggle_c = client.patch(
        f"/api/v1/subscriptions/admin/coupons/{coupon_id}?is_active=false",
        headers={"Authorization": f"Bearer {auth_tokens['superadmin']}"}
    )
    assert res_toggle_c.status_code == 200
    assert res_toggle_c.json()["is_active"] is False
