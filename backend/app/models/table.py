from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class TableStatus(str, enum.Enum):
    AVAILABLE = "Available"
    OCCUPIED = "Occupied"
    RESERVED = "Reserved"
    CLEANING = "Cleaning"
    ORDER_PENDING = "Order Pending"
    BILL_REQUESTED = "Bill Requested"

class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True, nullable=False)
    table_number = Column(String(50), nullable=False, index=True)
    service_type = Column(String(50), default="TABLE")  # TABLE, ROOM, POOL_BAR, CABANA, BANQUET
    capacity = Column(Integer, default=4, nullable=False)
    section = Column(String(50), default="Main Dining")  # Terrace, Bar, VIP Lounge, Main Dining, Suite, Poolside
    status = Column(SQLEnum(TableStatus), default=TableStatus.AVAILABLE, nullable=False)
    qr_token = Column(String(255), unique=True, nullable=True)
    pos_x = Column(Integer, default=100)  # for interactive floor map positioning
    pos_y = Column(Integer, default=100)
    current_session_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("restaurant_id", "table_number", name="uq_restaurant_table_number"),
    )

    restaurant = relationship("Restaurant", back_populates="tables")
    sessions = relationship("TableSession", back_populates="table", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="table")
    service_requests = relationship("ServiceRequest", back_populates="table")

class TableSession(Base):
    __tablename__ = "table_sessions"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False, index=True)
    customer_name = Column(String(100), default="Guest")
    customer_phone = Column(String(30), nullable=True)
    guest_count = Column(Integer, default=2)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    table = relationship("Table", back_populates="sessions")
    orders = relationship("Order", back_populates="session")
