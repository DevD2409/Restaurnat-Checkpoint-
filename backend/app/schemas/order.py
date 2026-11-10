from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.order import OrderStatus, OrderPriority, PaymentStatus

class OrderItemCustomizationItem(BaseModel):
    group_name: str
    option_name: str
    additional_price: float = 0.0

class OrderItemCreate(BaseModel):
    menu_item_id: int
    item_name: str
    unit_price: float
    quantity: int = 1
    customizations: Optional[List[OrderItemCustomizationItem]] = []
    special_instructions: Optional[str] = None

class OrderCreate(BaseModel):
    restaurant_id: int = 1
    table_id: int
    session_id: Optional[int] = None
    customer_name: str = "Guest"
    customer_phone: Optional[str] = None
    items: List[OrderItemCreate]
    special_instructions: Optional[str] = None
    tip_amount: float = 0.0

class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    changed_by: Optional[str] = "Staff"
    notes: Optional[str] = None

class OrderPriorityUpdate(BaseModel):
    priority: OrderPriority

class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    menu_item_id: Optional[int] = None
    item_name: str
    unit_price: float
    quantity: int
    total_price: float
    customizations_json: Optional[str] = None
    special_instructions: Optional[str] = None
    status: str

    class Config:
        from_attributes = True

class OrderStatusHistoryResponse(BaseModel):
    id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_by: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    order_number: str
    restaurant_id: int
    table_id: int
    table_number: Optional[str] = None
    session_id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = None
    status: OrderStatus
    priority: OrderPriority
    subtotal: float
    tax_amount: float
    service_charge: float
    tip_amount: float
    total_amount: float
    payment_status: PaymentStatus
    special_instructions: Optional[str] = None
    estimated_prep_time: int
    actual_prep_time: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[OrderItemResponse] = []
    status_history: List[OrderStatusHistoryResponse] = []

    class Config:
        from_attributes = True

