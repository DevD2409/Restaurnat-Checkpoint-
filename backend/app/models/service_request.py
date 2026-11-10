from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class ServiceRequestType(str, enum.Enum):
    CALL_WAITER = "CALL_WAITER"
    WATER = "WATER"
    CUTLERY = "CUTLERY"
    ASSISTANCE = "ASSISTANCE"
    BILL = "BILL"

class ServiceRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"

class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False, index=True)
    request_type = Column(SQLEnum(ServiceRequestType), nullable=False)
    status = Column(SQLEnum(ServiceRequestStatus), default=ServiceRequestStatus.PENDING, nullable=False, index=True)
    customer_notes = Column(String(255), nullable=True)
    staff_notes = Column(String(255), nullable=True)
    assigned_staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    table = relationship("Table", back_populates="service_requests")
    assigned_staff = relationship("User", foreign_keys=[assigned_staff_id])

