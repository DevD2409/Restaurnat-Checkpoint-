from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.reservation import ReservationStatus

class ReservationCreate(BaseModel):
    restaurant_id: int = 1
    customer_name: str
    customer_email: Optional[EmailStr] = None
    customer_phone: str
    guest_count: int = 2
    reservation_date: str  # YYYY-MM-DD
    reservation_time: str  # e.g., "07:30 PM"
    special_requests: Optional[str] = None
    table_id: Optional[int] = None

class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus
    table_id: Optional[int] = None
    special_requests: Optional[str] = None

class ReservationResponse(BaseModel):
    id: int
    restaurant_id: int
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: str
    guest_count: int
    reservation_date: str
    reservation_time: str
    table_id: Optional[int] = None
    table_number: Optional[str] = None
    status: ReservationStatus
    special_requests: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

