from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.table import TableStatus

class TableBase(BaseModel):
    table_number: str
    capacity: int = 4
    section: str = "Main Dining"
    status: TableStatus = TableStatus.AVAILABLE
    pos_x: int = 100
    pos_y: int = 100

class TableCreate(TableBase):
    restaurant_id: int = 1

class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    section: Optional[str] = None
    status: Optional[TableStatus] = None
    pos_x: Optional[int] = None
    pos_y: Optional[int] = None
    is_active: Optional[bool] = None

class TableResponse(TableBase):
    id: int
    restaurant_id: int
    qr_token: Optional[str] = None
    qr_code_url: Optional[str] = None
    current_session_id: Optional[int] = None
    is_active: bool
    active_order_id: Optional[int] = None
    active_bill_amount: Optional[float] = None
    session_start_time: Optional[datetime] = None

    class Config:
        from_attributes = True

class TableSessionCreate(BaseModel):
    customer_name: str = "Guest"
    customer_phone: Optional[str] = None
    guest_count: int = 2

class TableSessionResponse(BaseModel):
    id: int
    table_id: int
    customer_name: str
    customer_phone: Optional[str] = None
    guest_count: int
    session_token: str
    is_active: bool
    started_at: datetime
    table_number: Optional[str] = None

    class Config:
        from_attributes = True

class QRValidationRequest(BaseModel):
    qr_token: str

class QRValidationResponse(BaseModel):
    valid: bool
    table_id: Optional[int] = None
    table_number: Optional[str] = None
    restaurant_id: Optional[int] = None
    session_token: Optional[str] = None
    message: str

