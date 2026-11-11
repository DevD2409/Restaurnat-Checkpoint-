from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.billing import BillStatus, SplitType, PaymentMethod, PaymentRecordStatus

class BillSplitCreate(BaseModel):
    split_type: SplitType = SplitType.EQUAL
    person_name: str
    amount: float

class BillSplitResponse(BaseModel):
    id: int
    bill_id: int
    split_type: SplitType
    person_name: str
    amount: float
    is_paid: bool
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    bill_id: int
    amount: float
    payment_method: PaymentMethod = PaymentMethod.RAZORPAY
    transaction_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    split_id: Optional[int] = None

class RazorpayOrderCreate(BaseModel):
    bill_id: int
    amount: float
    currency: str = "INR"

class RazorpayVerifyPayment(BaseModel):
    bill_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    amount: float
    split_id: Optional[int] = None

class PaymentResponse(BaseModel):
    id: int
    bill_id: int
    amount: float
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    status: PaymentRecordStatus
    created_at: datetime

    class Config:
        from_attributes = True

class BillResponse(BaseModel):
    id: int
    bill_number: str
    restaurant_id: int
    order_id: int
    table_id: int
    table_number: Optional[str] = None
    subtotal: float
    tax_percentage: float
    tax_amount: float
    service_charge_percentage: float
    service_charge: float
    tip_amount: float
    discount_amount: float
    final_amount: float
    status: BillStatus
    created_at: datetime
    splits: List[BillSplitResponse] = []
    payments: List[PaymentResponse] = []

class PaymentRefundRequest(BaseModel):
    payment_id: int
    amount: Optional[float] = None
    reason: Optional[str] = "Customer refund request"

class PaymentReconciliationResponse(BaseModel):
    bill_id: int
    bill_number: str
    bill_final_amount: float
    total_recorded_paid: float
    bill_status: str
    is_balanced: bool
    payments_count: int


    class Config:
        from_attributes = True

