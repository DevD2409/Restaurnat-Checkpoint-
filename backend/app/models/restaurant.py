from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(100), unique=True, index=True, nullable=False, default="royal-saffron")
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
    timezone = Column(String(50), default="Asia/Kolkata")
    
    # Branding & Visual Identity
    logo_url = Column(String(500), nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    primary_color = Column(String(30), default="#f97316")
    secondary_color = Column(String(30), default="#090a0f")
    
    # Facilities & Service Configuration
    facilities = Column(Text, default="High-Speed Wi-Fi, Valet Parking, Wheelchair Accessible, Air Conditioned, Live Music, Outdoor Seating")
    service_types = Column(String(255), default="DINE_IN,TAKEAWAY,ROOM_SERVICE,DELIVERY")
    
    # Wi-Fi Guest Config
    wifi_ssid = Column(String(100), default="SmartDine-Guest-5G")
    wifi_password = Column(String(100), default="DeliciousFood2026")
    wifi_instructions = Column(Text, default="Connect to guest Wi-Fi and enjoy high-speed internet during your culinary journey.")
    
    # Tenant-Specific Payment Gateway
    razorpay_key_id = Column(String(100), nullable=True)
    razorpay_key_secret_enc = Column(String(255), nullable=True)
    
    # SaaS Subscription Plan & Account Status
    subscription_plan = Column(String(50), default="PRO")  # FREE_TRIAL, STARTER, PRO, ENTERPRISE
    subscription_status = Column(String(50), default="ACTIVE")  # ACTIVE, TRIALING, SUSPENDED, CANCELLED
    owner_id = Column(Integer, nullable=True)
    
    opening_time = Column(String(20), default="10:00 AM")
    closing_time = Column(String(20), default="11:30 PM")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tables = relationship("Table", back_populates="restaurant", cascade="all, delete-orphan")
    menu_categories = relationship("MenuCategory", back_populates="restaurant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="restaurant", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="restaurant", cascade="all, delete-orphan")
