from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class BillStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"

class SplitType(str, enum.Enum):
    EQUAL = "EQUAL"
    BY_ITEM = "BY_ITEM"
    CUSTOM = "CUSTOM"

class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CARD = "CARD"
    UPI = "UPI"
    RAZORPAY = "RAZORPAY"

class PaymentRecordStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    bill_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., INV-20261109-001
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False, index=True)
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_percentage = Column(Float, default=5.0)
    tax_amount = Column(Float, default=0.0)
    service_charge_percentage = Column(Float, default=5.0)
    service_charge = Column(Float, default=0.0)
    tip_amount = Column(Float, default=0.0)
    discount_amount = Column(Float, default=0.0)
    final_amount = Column(Float, nullable=False, default=0.0)
    status = Column(SQLEnum(BillStatus), default=BillStatus.UNPAID, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("Order", back_populates="bill")
    splits = relationship("BillSplit", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="bill", cascade="all, delete-orphan")

class BillSplit(Base):
    __tablename__ = "bill_splits"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    split_type = Column(SQLEnum(SplitType), default=SplitType.EQUAL, nullable=False)
    person_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False)
    payment_method = Column(String(50), nullable=True)
    transaction_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bill = relationship("Bill", back_populates="splits")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod), default=PaymentMethod.RAZORPAY, nullable=False)
    transaction_id = Column(String(100), unique=True, index=True, nullable=True)
    razorpay_order_id = Column(String(100), nullable=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)
    status = Column(SQLEnum(PaymentRecordStatus), default=PaymentRecordStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bill = relationship("Bill", back_populates="payments")

