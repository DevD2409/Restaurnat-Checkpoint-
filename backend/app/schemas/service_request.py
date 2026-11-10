from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.service_request import ServiceRequestType, ServiceRequestStatus

class ServiceRequestCreate(BaseModel):
    restaurant_id: int = 1
    table_id: int
    request_type: ServiceRequestType
    customer_notes: Optional[str] = None

class ServiceRequestStatusUpdate(BaseModel):
    status: ServiceRequestStatus
    staff_notes: Optional[str] = None
    assigned_staff_id: Optional[int] = None

class ServiceRequestResponse(BaseModel):
    id: int
    restaurant_id: int
    table_id: int
    table_number: Optional[str] = None
    request_type: ServiceRequestType
    status: ServiceRequestStatus
    customer_notes: Optional[str] = None
    staff_notes: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    assigned_staff_name: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

