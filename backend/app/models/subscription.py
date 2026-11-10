from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(50), unique=True, index=True, nullable=False)  # STARTER, PRO, ENTERPRISE
    name = Column(String(100), nullable=False)
    billing_cycle = Column(String(20), default="MONTHLY")  # MONTHLY, ANNUAL
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    features = Column(Text, nullable=True)  # JSON or comma-separated feature list
    max_tables = Column(Integer, default=25)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoices = relationship("SubscriptionInvoice", back_populates="plan")

class SubscriptionCoupon(Base):
    __tablename__ = "subscription_coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    discount_percentage = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    max_uses = Column(Integer, default=100)
    times_used = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SubscriptionInvoice(Base):
    __tablename__ = "subscription_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., SRMP-INV-202611-0001
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False, index=True)
    billing_cycle = Column(String(20), default="MONTHLY")
    subtotal = Column(Float, nullable=False)
    discount_amount = Column(Float, default=0.0)
    coupon_id = Column(Integer, ForeignKey("subscription_coupons.id"), nullable=True)
    tax_percentage = Column(Float, default=18.0)  # 18% GST for SaaS platform services
    tax_amount = Column(Float, default=0.0)
    final_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    status = Column(String(50), default="UNPAID", index=True)  # UNPAID, PAID, VOID, REFUNDED
    
    billing_start_date = Column(DateTime(timezone=True), nullable=True)
    billing_end_date = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("SubscriptionPlan", back_populates="invoices")
    payments = relationship("SubscriptionPayment", back_populates="invoice", cascade="all, delete-orphan")

class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("subscription_invoices.id"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), unique=True, nullable=True, index=True)
    razorpay_signature = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    payment_method = Column(String(50), default="RAZORPAY")
    status = Column(String(50), default="SUCCESS", index=True)  # PENDING, SUCCESS, FAILED, REFUNDED
    
    refund_id = Column(String(100), nullable=True)
    refund_amount = Column(Float, default=0.0)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship("SubscriptionInvoice", back_populates="payments")

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

