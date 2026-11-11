from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SubscriptionPlanResponse(BaseModel):
    id: int
    plan_code: str
    name: str
    billing_cycle: str
    price_paise: int
    price_inr: float
    duration_days: int
    features: Optional[str] = None
    entitlements: Optional[Dict[str, Any]] = None
    max_tables: int
    is_active: bool

    class Config:
        from_attributes = True

class SubscriptionPlanCreate(BaseModel):
    plan_code: str
    name: str
    billing_cycle: str = "MONTHLY"
    price_paise: int
    duration_days: int = 30
    features: Optional[str] = None
    entitlements: Optional[Dict[str, Any]] = None
    max_tables: int = 30

class SubscriptionCouponCreate(BaseModel):
    code: str
    discount_paise: int = 0
    discount_type: str = "FIXED_AMOUNT"
    discount_percentage: float = 0.0
    eligible_plan_codes: str = "*"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_uses_global: int = 500
    max_uses_per_restaurant: int = 1
    is_active: bool = True

class SubscriptionCouponResponse(BaseModel):
    id: int
    code: str
    discount_paise: int
    discount_inr: float
    discount_type: str
    discount_percentage: float
    eligible_plan_codes: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_uses_global: int
    max_uses_per_restaurant: int
    times_used: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CouponValidateRequest(BaseModel):
    code: str
    plan_code: str
    restaurant_id: Optional[int] = None

class CouponValidateResponse(BaseModel):
    is_valid: bool
    code: str
    discount_paise: int = 0
    discount_inr: float = 0.0
    discount_percentage: float = 0.0
    discount_amount: float = 0.0
    final_amount_paise: int = 0
    final_amount_inr: float = 0.0
    message: str

class SubscriptionCheckoutPreviewRequest(BaseModel):
    restaurant_id: Optional[int] = None
    plan_code: str
    coupon_code: Optional[str] = None

class SubscriptionCheckoutPreviewResponse(BaseModel):
    plan_code: str
    name: str
    billing_cycle: str
    duration_days: int
    subtotal_paise: int
    subtotal_inr: float
    discount_paise: int
    discount_inr: float
    taxable_paise: int = 0
    taxable_inr: float = 0.0
    tax_percentage: float = 0.0
    tax_paise: int
    tax_inr: float
    final_amount_paise: int
    final_amount_inr: float
    convenience_fee_paise: int = 0
    is_tax_inclusive: bool = True
    is_gst_registered: bool = False
    document_type: str = "PAYMENT_RECEIPT"
    coupon_code: Optional[str] = None
    billing_start_date: str
    billing_end_date: str
    tax_type: Optional[str] = "UNREGISTERED_NO_GST"
    cgst_paise: Optional[int] = 0
    sgst_paise: Optional[int] = 0
    igst_paise: Optional[int] = 0
    cgst_inr: Optional[float] = 0.0
    sgst_inr: Optional[float] = 0.0
    igst_inr: Optional[float] = 0.0
    recipient_gstin: Optional[str] = None
    is_gstin_valid: Optional[bool] = False

class SubscriptionCheckoutRequest(BaseModel):
    restaurant_id: Optional[int] = None
    plan_code: str
    coupon_code: Optional[str] = None

class SubscriptionCheckoutResponse(BaseModel):
    razorpay_order_id: str
    amount_paise: int
    final_amount_paise: int = 0
    final_amount_inr: float
    currency: str
    key_id: str
    invoice_id: int
    invoice_number: str
    subtotal_paise: int = 0
    discount_paise: int = 0
    taxable_paise: int = 0
    taxable_inr: float = 0.0
    tax_percentage: float = 0.0
    tax_paise: int = 0
    subtotal_inr: float
    discount_inr: float
    tax_inr: float
    final_amount: float  # Compatibility helper
    convenience_fee_paise: int = 0
    is_tax_inclusive: bool = True
    is_gst_registered: bool = False
    document_type: str = "PAYMENT_RECEIPT"
    tax_type: Optional[str] = "UNREGISTERED_NO_GST"
    cgst_paise: Optional[int] = 0
    sgst_paise: Optional[int] = 0
    igst_paise: Optional[int] = 0
    cgst_inr: Optional[float] = 0.0
    sgst_inr: Optional[float] = 0.0
    igst_inr: Optional[float] = 0.0
    recipient_gstin: Optional[str] = None

class SubscriptionVerifyRequest(BaseModel):
    invoice_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class SubscriptionPaymentResponse(BaseModel):
    id: int
    invoice_id: int
    razorpay_payment_id: Optional[str]
    amount_paise: int
    amount_inr: float
    currency: str
    payment_method: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SubscriptionInvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    restaurant_id: int
    plan_id: int
    plan_name: Optional[str] = None
    billing_cycle: str
    subtotal_paise: int
    subtotal_inr: float
    discount_paise: int
    discount_inr: float
    taxable_paise: int = 0
    taxable_inr: float = 0.0
    tax_percentage: float = 0.0
    tax_paise: int
    tax_inr: float
    final_amount_paise: int
    final_amount_inr: float
    currency: str
    status: str
    is_tax_inclusive: bool = True
    is_gst_registered: bool = False
    document_type: str = "PAYMENT_RECEIPT"
    billing_start_date: Optional[datetime] = None
    billing_end_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    tax_type: Optional[str] = "UNREGISTERED_NO_GST"
    cgst_paise: Optional[int] = 0
    sgst_paise: Optional[int] = 0
    igst_paise: Optional[int] = 0
    cgst_inr: Optional[float] = 0.0
    sgst_inr: Optional[float] = 0.0
    igst_inr: Optional[float] = 0.0
    recipient_gstin: Optional[str] = None
    supplier_gstin: Optional[str] = None
    payments: List[SubscriptionPaymentResponse] = []

    class Config:
        from_attributes = True

class SubscriptionRefundRequest(BaseModel):
    payment_id: int
    amount_paise: Optional[int] = None
    reason: Optional[str] = "Customer SaaS subscription cancellation"

class SubscriptionNotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ComplianceEntityInfoResponse(BaseModel):
    business_operating_model: str = "INDIVIDUAL_UNREGISTERED"
    owner_legal_name: Optional[str] = None
    is_owner_legal_name_configured: bool = False
    brand_trade_name: str = "SRMP (Smart Restaurant Management Platform)"
    business_identity_status: str = "PENDING_OWNER_CONFIGURATION"
    is_business_identity_verified: bool = False
    pan: Optional[str] = None
    is_pan_configured: bool = False
    business_address: Optional[str] = None
    is_address_configured: bool = False
    is_gst_registered: bool = False
    gstin: Optional[str] = None
    is_gstin_verified: bool = False
    is_gst_rate_ca_confirmed: bool = False
    gst_rate_percentage: float = 0.0
    supplier_state_code: Optional[str] = None
    sac_code: Optional[str] = None
    sac_description: Optional[str] = None
    is_sac_approved_by_ca: bool = False
    settlement_account_ref: Optional[str] = None
    settlement_bank_name: Optional[str] = None
    is_bank_account_verified: bool = False
    production_domain: Optional[str] = None
    is_production_domain_configured: bool = False
    support_email: Optional[str] = None
    is_support_email_configured: bool = False
    grievance_email: Optional[str] = None
    is_grievance_email_configured: bool = False
    telephone_helpline: Optional[str] = None
    is_telephone_configured: bool = False
    grievance_contact_name: Optional[str] = None
    is_grievance_contact_configured: bool = False
    refund_policy_status: str
    is_refund_policy_approved: bool = False

class RestaurantSubscriptionStatusResponse(BaseModel):
    restaurant_id: int
    restaurant_name: str
    subscription_plan: str
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None
    grace_period_days: int = 7
    days_remaining: int
    is_in_grace_period: bool
    entitlements: Dict[str, Any]

class PlatformSubscriptionAnalyticsResponse(BaseModel):
    mrr_paise: int
    mrr_inr: float
    arr_paise: int
    arr_inr: float
    active_tenants: int
    trial_tenants: int
    past_due_tenants: int
    expired_tenants: int
    churn_count: int
    total_subscribers: int
    total_coupons_redeemed: int
    total_discount_disbursed_inr: float
