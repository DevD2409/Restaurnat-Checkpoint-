from pydantic import BaseModel
from typing import Optional

class RestaurantBase(BaseModel):
    name: str
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    tax_percentage: float = 5.0
    service_charge_percentage: float = 5.0
    currency: str = "INR"
    currency_symbol: str = "₹"
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    wifi_instructions: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    is_active: bool = True

class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    tax_percentage: Optional[float] = None
    service_charge_percentage: Optional[float] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    wifi_instructions: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    is_active: Optional[bool] = None

class RestaurantResponse(RestaurantBase):
    id: int

    class Config:
        from_attributes = True

