from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RestaurantBase(BaseModel):
    name: str
    slug: Optional[str] = "royal-saffron"
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    tax_percentage: float = 5.0
    service_charge_percentage: float = 5.0
    currency: str = "INR"
    currency_symbol: str = "₹"
    timezone: str = "Asia/Kolkata"
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str = "#f97316"
    secondary_color: str = "#090a0f"
    facilities: Optional[str] = "High-Speed Wi-Fi, Valet Parking, Wheelchair Accessible, Air Conditioned, Live Music"
    service_types: Optional[str] = "DINE_IN,TAKEAWAY,ROOM_SERVICE"
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    wifi_instructions: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    google_review_url: Optional[str] = None
    subscription_plan: str = "PRO"
    subscription_status: str = "ACTIVE"
    google_review_url: Optional[str] = None
    allow_feedback_edits: bool = False
    is_active: bool = True

class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    tax_percentage: Optional[float] = None
    service_charge_percentage: Optional[float] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None
    timezone: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    facilities: Optional[str] = None
    service_types: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    wifi_instructions: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    google_review_url: Optional[str] = None
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_key_secret_enc: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None
    razorpay_webhook_secret_enc: Optional[str] = None
    razorpay_account_id: Optional[str] = None
    payment_gateway_mode: Optional[str] = None
    google_review_url: Optional[str] = None
    allow_feedback_edits: Optional[bool] = None
    is_active: Optional[bool] = None

class RestaurantResponse(RestaurantBase):
    id: int
    razorpay_key_id: Optional[str] = None
    has_razorpay_secret: bool = False
    has_webhook_secret: bool = False
    razorpay_account_id: Optional[str] = None
    payment_gateway_mode: str = "DIRECT_MERCHANT"
    settlement_bank_account_verified: bool = False
    subscription_expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class RestaurantPublicProfile(BaseModel):
    id: int
    name: str
    slug: str
    tagline: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    currency: str
    currency_symbol: str
    tax_percentage: float
    service_charge_percentage: float
    timezone: str
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    facilities: Optional[str] = None
    service_types: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_instructions: Optional[str] = None
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    google_review_url: Optional[str] = None

    class Config:
        from_attributes = True
