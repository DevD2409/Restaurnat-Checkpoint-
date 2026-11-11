import json
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(50), unique=True, index=True, nullable=False)  # MONTHLY, YEARLY
    name = Column(String(100), nullable=False)
    billing_cycle = Column(String(20), default="MONTHLY")  # MONTHLY, YEARLY
    price_paise = Column(Integer, nullable=False)  # Stored in integer paise (e.g. 99900 = ₹999, 999900 = ₹9,999)
    currency = Column(String(10), default="INR")
    duration_days = Column(Integer, default=30)  # 30 for monthly, 365 for yearly
    features = Column(Text, nullable=True)  # Comma-separated or description
    entitlements_json = Column(Text, nullable=True)  # JSON dictionary of feature access
    max_tables = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoices = relationship("SubscriptionInvoice", back_populates="plan")

    @property
    def price_inr(self) -> float:
        return round(self.price_paise / 100.0, 2)

    def get_entitlements(self) -> dict:
        if not self.entitlements_json:
            return {
                "max_tables": self.max_tables,
                "kds_access": True,
                "advanced_analytics": True,
                "custom_branding": True,
                "multi_branch": False
            }
        try:
            return json.loads(self.entitlements_json)
        except Exception:
            return {"max_tables": self.max_tables}

class SubscriptionCoupon(Base):
    __tablename__ = "subscription_coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # Uppercase code e.g. LAUNCH_MONTHLY
    discount_paise = Column(Integer, default=0)  # Fixed discount in integer paise (e.g. 100000 = ₹1,000)
    discount_type = Column(String(20), default="FIXED_AMOUNT")  # FIXED_AMOUNT, PERCENTAGE
    discount_percentage = Column(Float, default=0.0)
    eligible_plan_codes = Column(String(255), default="*")  # Comma-separated plan codes or '*' for all
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)  # Expiry date
    max_uses_global = Column(Integer, default=500)  # Total allowed uses platform-wide
    max_uses_per_restaurant = Column(Integer, default=1)  # Max uses per individual restaurant
    times_used = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    redemptions = relationship("SubscriptionCouponRedemption", back_populates="coupon", cascade="all, delete-orphan")

    @property
    def discount_inr(self) -> float:
        return round(self.discount_paise / 100.0, 2)

class SubscriptionCouponRedemption(Base):
    __tablename__ = "subscription_coupon_redemptions"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("subscription_coupons.id"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("subscription_invoices.id"), nullable=True, index=True)
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now())

    coupon = relationship("SubscriptionCoupon", back_populates="redemptions")

class SubscriptionInvoice(Base):
    __tablename__ = "subscription_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)  # R2627/001-00001 or I2627/001-00001
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True)
    billing_cycle = Column(String(20), default="MONTHLY")
    
    # Financial values in integer paise (tax-inclusive final amounts)
    subtotal_paise = Column(Integer, nullable=False)
    discount_paise = Column(Integer, default=0)
    tax_percentage = Column(Float, default=0.0)  # 0.0 when unregistered; 18.0 when GST-registered & CA confirmed
    tax_paise = Column(Integer, default=0)
    final_amount_paise = Column(Integer, nullable=False)
    
    currency = Column(String(10), default="INR")
    status = Column(String(50), default="UNPAID", index=True)  # UNPAID, PAID, VOID, REFUNDED
    coupon_id = Column(Integer, ForeignKey("subscription_coupons.id"), nullable=True)
    
    billing_start_date = Column(DateTime(timezone=True), nullable=True)
    billing_end_date = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("SubscriptionPlan", back_populates="invoices")
    payments = relationship("SubscriptionPayment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def subtotal_inr(self) -> float:
        return round(self.subtotal_paise / 100.0, 2)

    @property
    def discount_inr(self) -> float:
        return round(self.discount_paise / 100.0, 2)

    @property
    def tax_inr(self) -> float:
        return round(self.tax_paise / 100.0, 2)

    @property
    def taxable_paise(self) -> int:
        return max(0, (self.final_amount_paise or 0) - (self.tax_paise or 0))

    @property
    def taxable_inr(self) -> float:
        return round(self.taxable_paise / 100.0, 2)

    @property
    def is_gst_registered(self) -> bool:
        return bool((self.tax_paise or 0) > 0)

    @property
    def document_type(self) -> str:
        return "TAX_INVOICE" if self.is_gst_registered else "PAYMENT_RECEIPT"

    @property
    def final_amount_inr(self) -> float:
        return round(self.final_amount_paise / 100.0, 2)

    @property
    def recipient_gstin(self) -> Optional[str]:
        if hasattr(self, '_recipient_gstin') and self._recipient_gstin is not None:
            return self._recipient_gstin
        try:
            from app.core.database import SessionLocal
            from app.models.restaurant import Restaurant
            db = SessionLocal()
            r = db.query(Restaurant).filter(Restaurant.id == self.restaurant_id).first()
            val = r.gst_number if r else None
            db.close()
            return val
        except Exception:
            return None

    @recipient_gstin.setter
    def recipient_gstin(self, val: Optional[str]):
        self._recipient_gstin = val

    @property
    def supplier_gstin(self) -> Optional[str]:
        if not self.is_gst_registered:
            return None
        from app.services.gst_service import is_platform_gst_active
        is_active, clean_sup, _ = is_platform_gst_active()
        return clean_sup if is_active else None

    @property
    def gst_breakdown(self) -> dict:
        from app.services.gst_service import compute_subscription_tax_inclusive
        # Respect the historical tax status stored on this invoice row
        is_gst_inv = bool((self.tax_paise or 0) > 0)
        return compute_subscription_tax_inclusive(
            final_amount_paise=self.final_amount_paise or 0,
            recipient_gstin=self.recipient_gstin,
            is_gst_registered=is_gst_inv,
            is_gst_rate_ca_confirmed=is_gst_inv,
        )

    @property
    def tax_type(self) -> str:
        return self.gst_breakdown.get("tax_type", "UNREGISTERED_NO_GST")

    @property
    def cgst_paise(self) -> int:
        return self.gst_breakdown.get("cgst_paise", 0)

    @property
    def sgst_paise(self) -> int:
        return self.gst_breakdown.get("sgst_paise", 0)

    @property
    def igst_paise(self) -> int:
        return self.gst_breakdown.get("igst_paise", 0)

    @property
    def cgst_inr(self) -> float:
        return self.gst_breakdown.get("cgst_inr", 0.0)

    @property
    def sgst_inr(self) -> float:
        return self.gst_breakdown.get("sgst_inr", 0.0)

    @property
    def igst_inr(self) -> float:
        return self.gst_breakdown.get("igst_inr", 0.0)

class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("subscription_invoices.id"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), unique=True, nullable=True, index=True)
    razorpay_signature = Column(String(255), nullable=True)
    
    # Financial values in integer paise
    amount_paise = Column(Integer, nullable=False)
    refund_amount_paise = Column(Integer, default=0)
    
    currency = Column(String(10), default="INR")
    payment_method = Column(String(50), default="RAZORPAY")
    status = Column(String(50), default="SUCCESS", index=True)  # PENDING, SUCCESS, FAILED, REFUNDED
    
    refund_id = Column(String(100), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("SubscriptionInvoice", back_populates="payments")

    @property
    def amount_inr(self) -> float:
        return round(self.amount_paise / 100.0, 2)

class SubscriptionWebhookEvent(Base):
    __tablename__ = "subscription_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    invoice_id = Column(Integer, nullable=True, index=True)
    restaurant_id = Column(Integer, nullable=True, index=True)
    status = Column(String(50), default="PROCESSED")  # PROCESSED, FAILED, IGNORED
    payload = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

class SubscriptionNotification(Base):
    __tablename__ = "subscription_notifications"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)  # RENEWAL_UPCOMING, RENEWAL_SUCCESS, PAST_DUE_WARNING, EXPIRED, PAYMENT_FAILED
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
