import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.subscription import SubscriptionInvoice
from app.services.payment_service import PaymentService

client = TestClient(app)


@pytest.fixture
def role_tokens():
    db = SessionLocal()
    owner = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.RESTAURANT_OWNER])).first()
    superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
    assert owner is not None
    assert superadmin is not None

    owner_token = create_access_token(
        subject=str(owner.id),
        role=owner.role.value,
        restaurant_id=owner.restaurant_id,
    )
    superadmin_token = create_access_token(
        subject=str(superadmin.id),
        role=superadmin.role.value,
        restaurant_id=None,
    )
    rest_id = owner.restaurant_id
    db.close()
    return {
        "owner_token": owner_token,
        "superadmin_token": superadmin_token,
        "restaurant_id": rest_id,
    }


def test_individual_business_default_identity_and_zero_fabrication():
    """Verify compliance endpoint reports individual/unregistered model with zero fabricated corporate fields."""
    res = client.get("/api/v1/subscriptions/compliance/info")
    assert res.status_code == 200
    data = res.json()

    assert data["business_operating_model"] == "INDIVIDUAL_UNREGISTERED"
    assert data["owner_legal_name"] is None
    assert data["is_owner_legal_name_configured"] is False
    assert data["brand_trade_name"] == "SRMP (Smart Restaurant Management Platform)"
    assert data["business_identity_status"] == "PENDING_OWNER_CONFIGURATION"
    assert data["is_business_identity_verified"] is False
    assert data["is_gst_registered"] is False
    assert data["gstin"] is None
    assert data["sac_code"] is None
    assert data["is_bank_account_verified"] is False
    assert data["is_support_email_configured"] is False
    assert data["is_grievance_email_configured"] is False
    assert data["is_telephone_configured"] is False
    assert data["is_production_domain_configured"] is False

    body_text = str(data)
    for forbidden in (
        "Cloud Hospitality",
        "U72900MH",
        "27AABCS1429",
        "ACC_SRMP_CORP",
        "HDFC Bank Limited",
        "Tech Horizon",
        "Saki Vihar",
        "Rajesh Sharma",
        "srmp-saas.com",
        "4982-1000",
    ):
        assert forbidden not in body_text


def test_configurable_owner_identity_and_domain(monkeypatch):
    """Owner legal name, bank details, domain, and contacts are cleanly configurable when supplied."""
    monkeypatch.setattr(settings, "OWNER_LEGAL_NAME", "Ananya Deshmukh")
    monkeypatch.setattr(settings, "BUSINESS_IDENTITY_STATUS", "INDIVIDUAL_PAN_VERIFIED")
    monkeypatch.setattr(settings, "BUSINESS_PAN", "ABCDE1234F")
    monkeypatch.setattr(settings, "BUSINESS_ADDRESS", "Pune, Maharashtra")
    monkeypatch.setattr(settings, "PLATFORM_SETTLEMENT_BANK_NAME", "State Bank of India")
    monkeypatch.setattr(settings, "PLATFORM_SETTLEMENT_ACCOUNT", "SBI_INDIV_MASKED_4421")
    monkeypatch.setattr(settings, "PRODUCTION_DOMAIN", "https://app.example-srmp.in")
    monkeypatch.setattr(settings, "SUPPORT_EMAIL", "help@example-srmp.in")

    res = client.get("/api/v1/subscriptions/compliance/info")
    assert res.status_code == 200
    data = res.json()

    assert data["owner_legal_name"] == "Ananya Deshmukh"
    assert data["is_owner_legal_name_configured"] is True
    assert data["brand_trade_name"] == "SRMP (Smart Restaurant Management Platform)"
    assert data["business_identity_status"] == "INDIVIDUAL_PAN_VERIFIED"
    assert data["is_business_identity_verified"] is True
    assert data["pan"] == "ABCDE1234F"
    assert data["business_address"] == "Pune, Maharashtra"
    assert data["settlement_bank_name"] == "State Bank of India"
    assert data["settlement_account_ref"] == "SBI_INDIV_MASKED_4421"
    assert data["is_bank_account_verified"] is True
    assert data["production_domain"] == "https://app.example-srmp.in"
    assert data["is_production_domain_configured"] is True
    assert data["support_email"] == "help@example-srmp.in"
    assert data["is_support_email_configured"] is True


def test_unregistered_direct_tax_inclusive_preview_and_checkout(monkeypatch, role_tokens):
    """
    When unregistered, ₹999 monthly and ₹9,999 yearly charge exact prices
    with 0 GST, 0 convenience fee, and generate Non-GST PAYMENT_RECEIPT (R{FY}/...).
    """
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_B_ENABLED", True)
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_ID", "rzp_test_unit_platform_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", "unit_test_platform_secret_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", "unit_test_platform_webhook_secret")

    # Monthly Preview
    prev_m = client.post("/api/v1/subscriptions/checkout/preview", json={"plan_code": "MONTHLY"})
    assert prev_m.status_code == 200
    pm = prev_m.json()
    assert pm["subtotal_paise"] == 99900
    assert pm["taxable_paise"] == 99900
    assert pm["tax_paise"] == 0
    assert pm["tax_percentage"] == 0.0
    assert pm["convenience_fee_paise"] == 0
    assert pm["final_amount_paise"] == 99900
    assert pm["is_tax_inclusive"] is True
    assert pm["is_gst_registered"] is False
    assert pm["document_type"] == "PAYMENT_RECEIPT"
    assert pm["tax_type"] == "UNREGISTERED_NO_GST"

    # Yearly Preview
    prev_y = client.post("/api/v1/subscriptions/checkout/preview", json={"plan_code": "YEARLY"})
    assert prev_y.status_code == 200
    py = prev_y.json()
    assert py["subtotal_paise"] == 999900
    assert py["taxable_paise"] == 999900
    assert py["tax_paise"] == 0
    assert py["convenience_fee_paise"] == 0
    assert py["final_amount_paise"] == 999900
    assert py["document_type"] == "PAYMENT_RECEIPT"

    # Checkout Monthly
    chk_m = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY"},
        headers={"Authorization": f"Bearer {role_tokens['owner_token']}"},
    )
    assert chk_m.status_code == 200
    cm = chk_m.json()
    assert cm["final_amount_paise"] == 99900
    assert cm["amount_paise"] == 99900
    assert cm["tax_paise"] == 0
    assert cm["tax_percentage"] == 0.0
    assert cm["convenience_fee_paise"] == 0
    assert cm["is_gst_registered"] is False
    assert cm["document_type"] == "PAYMENT_RECEIPT"
    assert cm["invoice_number"].startswith("R")

    # Checkout Yearly
    chk_y = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "YEARLY"},
        headers={"Authorization": f"Bearer {role_tokens['owner_token']}"},
    )
    assert chk_y.status_code == 200
    cy = chk_y.json()
    assert cy["final_amount_paise"] == 999900
    assert cy["amount_paise"] == 999900
    assert cy["tax_paise"] == 0
    assert cy["document_type"] == "PAYMENT_RECEIPT"
    assert cy["invoice_number"].startswith("R")


def test_gst_registered_ca_confirmed_tax_inclusive_split(monkeypatch, role_tokens):
    """
    When GST-registered AND CA-confirmed (18%), GST is extracted inclusively:
    - Monthly ₹999 (99,900 paise) -> taxable 84,661 + GST 15,239 = 99,900
    - Yearly ₹9,999 (999,900 paise) -> taxable 847,373 + GST 152,527 = 999,900
    Issues TAX_INVOICE (I{FY}/...) and NEVER adds tax on top of ₹999 or ₹9,999.
    """
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_B_ENABLED", True)
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_ID", "rzp_test_unit_platform_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", "unit_test_platform_secret_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", "unit_test_platform_webhook_secret")
    monkeypatch.setattr(settings, "IS_GST_REGISTERED", True)
    monkeypatch.setattr(settings, "IS_GST_RATE_CA_CONFIRMED", True)
    monkeypatch.setattr(settings, "OWNER_GSTIN", "27AABCU9603R1ZP")
    monkeypatch.setattr(settings, "GST_RATE_PERCENTAGE", 18.0)

    # Monthly checkout
    chk_m = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "MONTHLY"},
        headers={"Authorization": f"Bearer {role_tokens['owner_token']}"},
    )
    assert chk_m.status_code == 200
    cm = chk_m.json()
    assert cm["is_gst_registered"] is True
    assert cm["document_type"] == "TAX_INVOICE"
    assert cm["invoice_number"].startswith("I")
    assert cm["taxable_paise"] == 84661
    assert cm["tax_paise"] == 15239
    assert cm["final_amount_paise"] == 99900
    assert cm["amount_paise"] == 99900
    assert cm["taxable_paise"] + cm["tax_paise"] == cm["final_amount_paise"]

    # Yearly checkout
    chk_y = client.post(
        "/api/v1/subscriptions/checkout",
        json={"plan_code": "YEARLY"},
        headers={"Authorization": f"Bearer {role_tokens['owner_token']}"},
    )
    assert chk_y.status_code == 200
    cy = chk_y.json()
    assert cy["is_gst_registered"] is True
    assert cy["document_type"] == "TAX_INVOICE"
    assert cy["invoice_number"].startswith("I")
    assert cy["taxable_paise"] == 847373
    assert cy["tax_paise"] == 152527
    assert cy["final_amount_paise"] == 999900
    assert cy["amount_paise"] == 999900
    assert cy["taxable_paise"] + cy["tax_paise"] == cy["final_amount_paise"]


def test_gst_registered_without_ca_confirmation_stays_non_gst(monkeypatch):
    """If IS_GST_REGISTERED=True without valid GSTIN & CA rate confirmation, GST is not collected."""
    monkeypatch.setattr(settings, "IS_GST_REGISTERED", True)
    monkeypatch.setattr(settings, "IS_GST_RATE_CA_CONFIRMED", False)
    monkeypatch.setattr(settings, "OWNER_GSTIN", "27AABCU9603R1ZP")

    prev = client.post("/api/v1/subscriptions/checkout/preview", json={"plan_code": "MONTHLY"})
    assert prev.status_code == 200
    data = prev.json()
    assert data["is_gst_registered"] is False
    assert data["tax_paise"] == 0
    assert data["document_type"] == "PAYMENT_RECEIPT"
    assert data["final_amount_paise"] == 99900


def test_retired_pricing_coupons_blocked_everywhere(monkeypatch, role_tokens):
    """MONTHLY999 and YEARLY9999 must be rejected across validation, preview, checkout, and superadmin APIs."""
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_B_ENABLED", True)
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_ID", "rzp_test_unit_platform_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", "unit_test_platform_secret_key")
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", "unit_test_platform_webhook_secret")

    for legacy_code, plan_code in (("MONTHLY999", "MONTHLY"), ("YEARLY9999", "YEARLY")):
        # 1. Validation endpoint
        val_res = client.post(
            "/api/v1/subscriptions/coupons/validate",
            json={"code": legacy_code, "plan_code": plan_code},
        )
        assert val_res.status_code == 200
        assert val_res.json()["is_valid"] is False
        assert "retired" in val_res.json()["message"].lower()

        # 2. Preview endpoint
        prev_res = client.post(
            "/api/v1/subscriptions/checkout/preview",
            json={"plan_code": plan_code, "coupon_code": legacy_code},
        )
        assert prev_res.status_code == 400

        # 3. Checkout endpoint
        chk_res = client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_code": plan_code, "coupon_code": legacy_code},
            headers={"Authorization": f"Bearer {role_tokens['owner_token']}"},
        )
        assert chk_res.status_code == 400

        # 4. Super Admin recreation attempt blocked
        create_res = client.post(
            "/api/v1/subscriptions/admin/coupons",
            json={
                "code": legacy_code,
                "discount_paise": 100000,
                "discount_type": "FIXED_AMOUNT",
                "eligible_plan_codes": plan_code,
            },
            headers={"Authorization": f"Bearer {role_tokens['superadmin_token']}"},
        )
        assert create_res.status_code == 400


def test_flow_b_settlement_and_safety_flags():
    """Confirm Flow A & Flow B fail-closed defaults and zero hardcoded platform payment credentials."""
    assert settings.LIVE_MODE_FLOW_A is False
    assert settings.LIVE_MODE_FLOW_B is False
    assert settings.FLOW_A_ENABLED is False
    assert settings.FLOW_B_ENABLED is False
    assert settings.DISABLE_RESTAURANT_PAYMENT_FALLBACK is True
    assert settings.EMERGENCY_DISABLE_PAYMENTS is True

    creds = PaymentService.get_platform_credentials()
    assert creds["is_configured"] is False
    assert creds["key_id"] is None
    assert creds["key_secret"] is None
    assert "ACC_SRMP_CORP" not in str(creds["settlement_account"])
    assert "HDFC" not in str(creds["settlement_account"])
