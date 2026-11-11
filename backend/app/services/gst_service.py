import re
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import settings

# Indian GSTIN regex: 2 digits (state) + 10 chars (PAN) + 1 entity num + 'Z' + 1 check digit
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


def validate_gstin(gstin: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates Indian GSTIN format and extracts the 2-digit state code.
    Returns (is_valid, cleaned_gstin, state_code).
    Handles None, empty, whitespace, and malformed strings safely without exceptions.
    """
    if not gstin or not isinstance(gstin, str):
        return False, None, None

    clean = gstin.strip().upper()
    if not clean:
        return False, None, None

    if GSTIN_REGEX.match(clean):
        state_code = clean[:2]
        return True, clean, state_code

    return False, clean, None


def is_platform_gst_active(
    is_gst_registered: Optional[bool] = None,
    is_gst_rate_ca_confirmed: Optional[bool] = None,
    supplier_gstin: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Determines whether GST collection & tax invoice generation are legally active.
    Requires:
      1. Explicit GST registration flag (IS_GST_REGISTERED = True)
      2. Valid 15-character supplier GSTIN (OWNER_GSTIN)
      3. Documented CA rate confirmation (IS_GST_RATE_CA_CONFIRMED = True)
    Returns (is_active, valid_supplier_gstin, supplier_state_code).
    """
    reg_flag = is_gst_registered if is_gst_registered is not None else getattr(settings, "IS_GST_REGISTERED", False)
    ca_flag = (
        is_gst_rate_ca_confirmed
        if is_gst_rate_ca_confirmed is not None
        else getattr(settings, "IS_GST_RATE_CA_CONFIRMED", False)
    )
    raw_supplier_gstin = supplier_gstin if supplier_gstin is not None else getattr(settings, "OWNER_GSTIN", None)
    valid_sup, clean_sup, sup_state = validate_gstin(raw_supplier_gstin)

    active = bool(reg_flag and ca_flag and valid_sup)
    if not sup_state:
        cfg_state = getattr(settings, "SUPPLIER_GST_STATE_CODE", None)
        sup_state = cfg_state.strip() if isinstance(cfg_state, str) and cfg_state.strip() else None

    return active, (clean_sup if valid_sup else None), sup_state


def compute_subscription_tax_inclusive(
    final_amount_paise: int,
    recipient_gstin: Optional[str] = None,
    is_gst_registered: Optional[bool] = None,
    is_gst_rate_ca_confirmed: Optional[bool] = None,
    supplier_gstin: Optional[str] = None,
    supplier_state_code: Optional[str] = None,
    gst_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Computes tax-inclusive subscription breakdown strictly in integer paise.

    Authoritative Pricing Rule:
    - Subscription prices (₹999 / 99,900 paise monthly, ₹9,999 / 999,900 paise yearly)
      are inclusive of all applicable taxes and compulsory charges.
    - GST is NEVER added on top of final_amount_paise.

    Paths:
    1. Unregistered / Individual Business (default or unconfirmed CA rate):
       - Does NOT collect GST (tax_paise = 0)
       - Issues non-GST PAYMENT_RECEIPT (never TAX_INVOICE)
       - taxable_paise == final_amount_paise
    2. Registered GST Entity with CA-confirmed 18% rate:
       - Extracts included GST using tax-inclusive integer math:
         taxable_paise = round(final_amount_paise / 1.18)
         tax_paise = final_amount_paise - taxable_paise
         Guarantees exact sum: taxable_paise + tax_paise == final_amount_paise
       - Monthly (99,900): taxable = 84,661, included GST = 15,239
       - Yearly (999,900): taxable = 847,373, included GST = 152,527
       - Splits Intra-State (CGST + SGST) vs Inter-State (IGST) based on GSTIN state codes.
    """
    final_paise = max(0, int(final_amount_paise))
    is_gst_active, valid_sup_gstin, detected_sup_state = is_platform_gst_active(
        is_gst_registered=is_gst_registered,
        is_gst_rate_ca_confirmed=is_gst_rate_ca_confirmed,
        supplier_gstin=supplier_gstin,
    )
    eff_supplier_state = (supplier_state_code.strip() if supplier_state_code else detected_sup_state)
    is_valid_rec, cleaned_rec_gstin, rec_state = validate_gstin(recipient_gstin)

    if not is_gst_active:
        return {
            "is_gst_registered": False,
            "is_gst_applicable": False,
            "is_tax_inclusive": True,
            "document_type": "PAYMENT_RECEIPT",
            "tax_type": "UNREGISTERED_NO_GST",
            "is_gstin_valid": is_valid_rec,
            "recipient_gstin": cleaned_rec_gstin if is_valid_rec else None,
            "recipient_state_code": rec_state,
            "supplier_gstin": None,
            "supplier_state_code": None,
            "taxable_paise": final_paise,
            "taxable_inr": round(final_paise / 100.0, 2),
            "cgst_rate": 0.0,
            "cgst_paise": 0,
            "cgst_inr": 0.0,
            "sgst_rate": 0.0,
            "sgst_paise": 0,
            "sgst_inr": 0.0,
            "igst_rate": 0.0,
            "igst_paise": 0,
            "igst_inr": 0.0,
            "tax_rate_total": 0.0,
            "tax_paise": 0,
            "tax_inr": 0.0,
            "final_amount_paise": final_paise,
            "final_amount_inr": round(final_paise / 100.0, 2),
        }

    rate = float(gst_rate if gst_rate is not None else getattr(settings, "GST_RATE_PERCENTAGE", 18.0))
    taxable_paise = int(round(final_paise / (1.0 + (rate / 100.0))))
    tax_paise = final_paise - taxable_paise

    if is_valid_rec and rec_state and eff_supplier_state and rec_state != eff_supplier_state:
        tax_type = "INTER_STATE"
        cgst_rate = 0.0
        sgst_rate = 0.0
        igst_rate = rate
        cgst_paise = 0
        sgst_paise = 0
        igst_paise = tax_paise
    else:
        tax_type = "INTRA_STATE"
        cgst_rate = rate / 2.0
        sgst_rate = rate / 2.0
        igst_rate = 0.0
        cgst_paise = tax_paise // 2
        sgst_paise = tax_paise - cgst_paise
        igst_paise = 0

    return {
        "is_gst_registered": True,
        "is_gst_applicable": True,
        "is_tax_inclusive": True,
        "document_type": "TAX_INVOICE",
        "tax_type": tax_type,
        "is_gstin_valid": is_valid_rec,
        "recipient_gstin": cleaned_rec_gstin if is_valid_rec else None,
        "recipient_state_code": rec_state,
        "supplier_gstin": valid_sup_gstin,
        "supplier_state_code": eff_supplier_state,
        "taxable_paise": taxable_paise,
        "taxable_inr": round(taxable_paise / 100.0, 2),
        "cgst_rate": cgst_rate,
        "cgst_paise": cgst_paise,
        "cgst_inr": round(cgst_paise / 100.0, 2),
        "sgst_rate": sgst_rate,
        "sgst_paise": sgst_paise,
        "sgst_inr": round(sgst_paise / 100.0, 2),
        "igst_rate": igst_rate,
        "igst_paise": igst_paise,
        "igst_inr": round(igst_paise / 100.0, 2),
        "tax_rate_total": rate,
        "tax_paise": tax_paise,
        "tax_inr": round(tax_paise / 100.0, 2),
        "final_amount_paise": final_paise,
        "final_amount_inr": round(final_paise / 100.0, 2),
    }


def get_financial_year(dt: Optional[datetime] = None) -> str:
    """
    Computes Indian Financial Year 4-digit code (e.g., Nov 2026 -> '2627').
    In India, FY runs from April 1 to March 31.
    """
    d = dt or datetime.now()
    if d.month >= 4:
        start_yy = d.year % 100
        end_yy = (d.year + 1) % 100
    else:
        start_yy = (d.year - 1) % 100
        end_yy = d.year % 100
    return f"{start_yy:02d}{end_yy:02d}"


def generate_statutory_invoice_number(
    db: Session,
    restaurant_id: int,
    dt: Optional[datetime] = None,
    is_gst_registered: Optional[bool] = None,
) -> str:
    """
    Generates a sequential document number <= 16 characters.
    - When GST-registered and CA-confirmed: I{FY}/{TID:03d}-{SEQ:05d} (Tax Invoice, Rule 46(b) <= 16 chars)
    - When unregistered individual business: R{FY}/{TID:03d}-{SEQ:05d} (Non-GST Payment Receipt)
    """
    from app.models.subscription import SubscriptionInvoice

    d = dt or datetime.now()
    fy = get_financial_year(d)

    if is_gst_registered is None:
        is_gst_active, _, _ = is_platform_gst_active()
    else:
        is_gst_active = bool(is_gst_registered)

    prefix_char = "I" if is_gst_active else "R"
    prefix = f"{prefix_char}{fy}/{restaurant_id:03d}-"

    existing_count = db.query(SubscriptionInvoice).filter(
        SubscriptionInvoice.restaurant_id == restaurant_id,
        SubscriptionInvoice.invoice_number.like(f"{prefix}%")
    ).count()

    seq = existing_count + 1
    candidate = f"{prefix}{seq:05d}"

    while db.query(SubscriptionInvoice).filter(SubscriptionInvoice.invoice_number == candidate).first():
        seq += 1
        candidate = f"{prefix}{seq:05d}"

    assert len(candidate) <= 16, f"Document number '{candidate}' exceeds statutory 16-character limit!"
    return candidate
