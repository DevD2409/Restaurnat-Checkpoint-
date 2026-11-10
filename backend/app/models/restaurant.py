from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    tagline = Column(String(255), default="Finest Dining & Smart Culinary Experience")
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    gst_number = Column(String(50), default="27AABCU9603R1ZM")
    tax_percentage = Column(Float, default=5.0)  # GST 5%
    service_charge_percentage = Column(Float, default=5.0)  # 5%
    currency = Column(String(10), default="INR")
    currency_symbol = Column(String(5), default="₹")
    
    # Wi-Fi Guest Config
    wifi_ssid = Column(String(100), default="SmartDine-Guest-5G")
    wifi_password = Column(String(100), default="DeliciousFood2026")
    wifi_instructions = Column(Text, default="Connect to 'SmartDine-Guest-5G' and enjoy high-speed internet during your culinary journey.")
    
    opening_time = Column(String(20), default="10:00 AM")
    closing_time = Column(String(20), default="11:30 PM")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

