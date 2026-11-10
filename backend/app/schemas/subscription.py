from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SubscriptionPlanResponse(BaseModel):
    id: int
    plan_code: str
    name: str
    billing_cycle: str
    price: float
    currency: str
    features: Optional[str] = None
    max_tables: int
    is_active: bool

    class Config:
        from_attributes = True

class CouponValidateRequest(BaseModel):
    code: str
    plan_code: str

class CouponValidateResponse(BaseModel):
    is_valid: bool
    code: str
    discount_percentage: float = 0.0
    discount_amount: float = 0.0
    message: str

class SubscriptionCheckoutRequest(BaseModel):
    restaurant_id: Optional[int] = None
    plan_code: str
    billing_cycle: str = "MONTHLY"
    coupon_code: Optional[str] = None

class SubscriptionCheckoutResponse(BaseModel):
    razorpay_order_id: str
    amount: float
    amount_paise: int
    currency: str
    key_id: str
    invoice_id: int
    invoice_number: str
    subtotal: float
    discount_amount: float
    tax_amount: float
    final_amount: float

class SubscriptionVerifyRequest(BaseModel):
    invoice_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class SubscriptionPaymentResponse(BaseModel):
    id: int
    invoice_id: int
    razorpay_payment_id: Optional[str]
    amount: float
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
    subtotal: float
    discount_amount: float
    tax_amount: float
    final_amount: float
    currency: str
    status: str
    billing_start_date: Optional[datetime] = None
    billing_end_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    payments: List[SubscriptionPaymentResponse] = []

    class Config:
        from_attributes = True

class SubscriptionRefundRequest(BaseModel):
    payment_id: int
    amount: Optional[float] = None
    reason: Optional[str] = "Customer SaaS subscription cancellation"

