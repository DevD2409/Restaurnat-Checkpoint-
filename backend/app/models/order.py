from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class OrderStatus(str, enum.Enum):
    PLACED = "PLACED"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    SERVED = "SERVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class OrderPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"

class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    REFUNDED = "REFUNDED"

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., ORD-20261109-001
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("table_sessions.id"), nullable=True, index=True)
    customer_name = Column(String(100), default="Guest")
    customer_phone = Column(String(30), nullable=True)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PLACED, nullable=False, index=True)
    priority = Column(SQLEnum(OrderPriority), default=OrderPriority.NORMAL, nullable=False)
    subtotal = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    service_charge = Column(Float, default=0.0)
    tip_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    special_instructions = Column(Text, nullable=True)
    estimated_prep_time = Column(Integer, default=20)  # in minutes
    actual_prep_time = Column(Integer, nullable=True)  # in minutes
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    table = relationship("Table", back_populates="orders")
    session = relationship("TableSession", back_populates="orders")
    restaurant = relationship("Restaurant", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    bill = relationship("Bill", back_populates="order", uselist=False)
    feedback = relationship("Feedback", back_populates="order", uselist=False)

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True)
    item_name = Column(String(200), nullable=False)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    total_price = Column(Float, nullable=False)
    customizations_json = Column(Text, nullable=True)  # JSON string of selected add-on options
    special_instructions = Column(String(255), nullable=True)
    status = Column(String(50), default="QUEUED")  # QUEUED, COOKING, READY

    order = relationship("Order", back_populates="items")

class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(String(100), default="System")
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="status_history")

