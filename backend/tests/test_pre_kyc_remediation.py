import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.core.config import settings
from app.models.restaurant import Restaurant
from app.models.billing import Bill
from app.models.subscription import SubscriptionInvoice
from app.services.payment_service import PaymentService
from app.services.gst_service import (
    validate_gstin,
    compute_subscription_tax_inclusive,
    get_financial_year,
    generate_statutory_invoice_number
)

client = TestClient(app)

# =============================================================================
# 1. GSTIN VALIDATION TESTS
# =============================================================================

def test_gstin_validation_valid_formats():
    # Valid Maharashtra (27)
    valid, cleaned, state = validate_gstin("27AABCU9603R1ZM")
    assert valid is True
    assert cleaned == "27AABCU9603R1ZM"
    assert state == "27"

    # Valid Karnataka (29) with lowercase and whitespace
    valid, cleaned, state = validate_gstin("  29aabcu9603r1zm  ")
    assert valid is True
    assert cleaned == "29AABCU9603R1ZM"
    assert state == "29"

    # Valid Delhi (07)
    valid, cleaned, state = validate_gstin("07AAAAA0000A1Z5")
    assert valid is True
    assert cleaned == "07AAAAA0000A1Z5"
    assert state == "07"

def test_gstin_validation_invalid_and_missing_formats():
    for raw in (None, "   ", "27AABCU9603R", "27AABCU9603R1Z@"):
        valid, cleaned, state = validate_gstin(raw)
        assert valid is False
        assert state is None

# =============================================================================
# 2. TAX-INCLUSIVE INTEGER-PAISE COMPUTATION (UNREGISTERED & GST MODES)
# =============================================================================

def test_tax_inclusive_unregistered_individual_business():
    """Default unregistered individual business does not collect GST and issues PAYMENT_RECEIPT."""
    res_m = compute_subscription_tax_inclusive(99900, "27AABCU9603R1ZM", is_gst_registered=False)
    assert res_m["is_gst_registered"] is False
    assert res_m["document_type"] == "PAYMENT_RECEIPT"
    assert res_m["tax_type"] == "UNREGISTERED_NO_GST"
    assert res_m["taxable_paise"] == 99900
    assert res_m["tax_paise"] == 0
    assert res_m["final_amount_paise"] == 99900

    res_y = compute_subscription_tax_inclusive(999900, None, is_gst_registered=False)
    assert res_y["is_gst_registered"] is False
    assert res_y["document_type"] == "PAYMENT_RECEIPT"
    assert res_y["tax_paise"] == 0
    assert res_y["final_amount_paise"] == 999900

def test_gst_computation_intra_state_same_state():
    """GST-registered & CA-confirmed: Supplier (27) and Recipient (27) -> Tax-inclusive CGST + SGST."""
    res = compute_subscription_tax_inclusive(
        99900,
        "27AABCU9603R1ZM",
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert res["is_gst_registered"] is True
    assert res["document_type"] == "TAX_INVOICE"
    assert res["tax_type"] == "INTRA_STATE"
    assert res["is_gstin_valid"] is True
    assert res["taxable_paise"] == 84661
    assert res["tax_paise"] == 15239
    assert res["cgst_paise"] + res["sgst_paise"] == 15239
    assert res["igst_paise"] == 0
    assert res["final_amount_paise"] == 99900
    assert res["taxable_paise"] + res["cgst_paise"] + res["sgst_paise"] == res["final_amount_paise"]

def test_gst_computation_inter_state_different_state():
    """GST-registered & CA-confirmed: Supplier (27) and Recipient (29) -> Tax-inclusive IGST 18%."""
    res = compute_subscription_tax_inclusive(
        99900,
        "29AABCU9603R1ZM",
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert res["tax_type"] == "INTER_STATE"
    assert res["is_gstin_valid"] is True
    assert res["taxable_paise"] == 84661
    assert res["igst_paise"] == 15239
    assert res["cgst_paise"] == 0
    assert res["sgst_paise"] == 0
    assert res["tax_paise"] == 15239
    assert res["final_amount_paise"] == 99900

def test_gst_computation_yearly_tax_inclusive_integer_paise():
    """Yearly plan ₹9,999 (999,900 paise) GST-inclusive math -> 847,373 + 152,527 == 999,900."""
    intra = compute_subscription_tax_inclusive(
        999900,
        "27AABCU9603R1ZM",
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert intra["taxable_paise"] == 847373
    assert intra["tax_paise"] == 152527
    assert intra["cgst_paise"] + intra["sgst_paise"] == 152527
    assert intra["final_amount_paise"] == 999900

    inter = compute_subscription_tax_inclusive(
        999900,
        "29AABCU9603R1ZM",
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert inter["taxable_paise"] == 847373
    assert inter["igst_paise"] == 152527
    assert inter["final_amount_paise"] == 999900

def test_gst_computation_safe_fallback_on_missing_or_invalid_gstin():
    """Missing or invalid recipient GSTIN defaults safely when GST is active without crashing."""
    res_none = compute_subscription_tax_inclusive(
        99900,
        None,
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert res_none["tax_type"] == "INTRA_STATE"
    assert res_none["is_gstin_valid"] is False
    assert res_none["tax_paise"] == 15239
    assert res_none["final_amount_paise"] == 99900

    res_invalid = compute_subscription_tax_inclusive(
        99900,
        "INVALID_GST",
        is_gst_registered=True,
        is_gst_rate_ca_confirmed=True,
        supplier_gstin="27AABCU9603R1ZP",
        supplier_state_code="27",
    )
    assert res_invalid["tax_type"] == "INTRA_STATE"
    assert res_invalid["is_gstin_valid"] is False
    assert res_invalid["tax_paise"] == 15239

# =============================================================================
# 3. STATUTORY DOCUMENT SERIAL GENERATION & RULE 46(b) COMPLIANCE
# =============================================================================

def test_statutory_invoice_number_length_and_structure():
    db = SessionLocal()
    try:
        dt = datetime(2026, 11, 10)
        fy = get_financial_year(dt)
        assert fy == "2627"

        # Default unregistered business issues Non-GST Payment Receipt R{FY}/{TID:03d}-{SEQ:05d}
        rec_num = generate_statutory_invoice_number(db, restaurant_id=1, dt=dt, is_gst_registered=False)
        assert len(rec_num) <= 16
        assert rec_num.startswith("R2627/001-")

        # Future GST-registered business issues CGST Rule 46(b) Tax Invoice I{FY}/{TID:03d}-{SEQ:05d}
        inv_num = generate_statutory_invoice_number(db, restaurant_id=1, dt=dt, is_gst_registered=True)
        assert len(inv_num) <= 16
        assert inv_num.startswith("I2627/001-")
        assert len(inv_num) == 15

        parts = inv_num.split("/")
        assert parts[0] == "I2627"
        tid_seq = parts[1].split("-")
        assert tid_seq[0] == "001"
        assert len(tid_seq[1]) == 5
    finally:
        db.close()

def test_statutory_invoice_financial_year_transition():
    assert get_financial_year(datetime(2026, 4, 1)) == "2627"
    assert get_financial_year(datetime(2027, 3, 31)) == "2627"
    assert get_financial_year(datetime(2027, 4, 1)) == "2728"
    assert get_financial_year(datetime(2026, 1, 15)) == "2526"

# =============================================================================
# 4. PAYMENT LIVE-KEY GUARD STANDARDIZED RESPONSES (HTTP 403)
# =============================================================================

def test_flow_a_live_key_guard_raises_403_forbidden():
    from fastapi import HTTPException

    mock_restaurant = Restaurant(
        id=999,
        name="Test Live Restaurant",
        razorpay_key_id="rzp_live_test_key_12345",
        razorpay_key_secret_enc="mock_secret",
        payment_gateway_mode="DIRECT_MERCHANT"
    )
    mock_bill = Bill(id=999, bill_number="TEST-BILL-999")

    assert settings.LIVE_MODE_FLOW_A is False

    with pytest.raises(HTTPException) as excinfo:
        PaymentService.create_restaurant_order(mock_restaurant, mock_bill, 500.0)

    assert excinfo.value.status_code == 403
    assert "Live payment gateway is disabled by platform policy" in excinfo.value.detail

def test_flow_b_live_key_guard_raises_403_forbidden(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_ID", "rzp_live_platform_test_key")
    monkeypatch.setattr(settings, "LIVE_MODE_FLOW_B", False)

    mock_invoice = SubscriptionInvoice(
        id=999,
        invoice_number="R2627/001-00001",
        restaurant_id=1,
        final_amount_paise=99900,
        currency="INR"
    )

    with pytest.raises(HTTPException) as excinfo:
        PaymentService.create_subscription_order(mock_invoice)

    assert excinfo.value.status_code == 403
    assert "Live payment gateway is disabled by platform policy" in excinfo.value.detail

# =============================================================================
# 5. COMPLIANCE & INDIVIDUAL BUSINESS IDENTITY ENDPOINT VERIFICATION
# =============================================================================

def test_compliance_entity_info_endpoint():
    res = client.get("/api/v1/subscriptions/compliance/info")
    assert res.status_code == 200
    data = res.json()

    assert data["business_operating_model"] == "INDIVIDUAL_UNREGISTERED"
    assert data["brand_trade_name"] == "SRMP (Smart Restaurant Management Platform)"
    assert data["is_gst_registered"] is False
    assert data["gstin"] is None
    assert data["sac_code"] is None
    assert data["is_sac_approved_by_ca"] is False
    assert data["refund_policy_status"] == "DRAFT_PENDING_OWNER_APPROVAL"
    assert data["is_refund_policy_approved"] is False
    assert "is_owner_legal_name_configured" in data
    assert "is_support_email_configured" in data
    assert "is_telephone_configured" in data
    assert "is_production_domain_configured" in data

    # Verify zero fabricated corporate disclosures leak into payload
    serialized = str(data)
    for forbidden in ("Cloud Hospitality", "U72900MH", "27AABCS1429", "ACC_SRMP_CORP", "Rajesh Sharma", "srmp-saas.com"):
        assert forbidden not in serialized
