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
    
    # Tenant-Specific Payment Gateway (Flow A)
    razorpay_key_id = Column(String(100), nullable=True)
    razorpay_key_secret_enc = Column(String(255), nullable=True)
    razorpay_webhook_secret_enc = Column(String(255), nullable=True)
    razorpay_account_id = Column(String(100), nullable=True)  # Razorpay Route linked account (e.g. acc_xxx)
    payment_gateway_mode = Column(String(50), default="DIRECT_MERCHANT")  # DIRECT_MERCHANT or RAZORPAY_ROUTE
    settlement_bank_account_verified = Column(Boolean, default=False)
    
    # SaaS Subscription Plan & Account Status (Flow B)
    subscription_plan = Column(String(50), default="MONTHLY")  # MONTHLY, YEARLY, TRIAL
    subscription_status = Column(String(50), default="ACTIVE")  # TRIAL, ACTIVE, PAST_DUE, EXPIRED, CANCELLED, SUSPENDED
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    grace_period_days = Column(Integer, default=7)
    owner_id = Column(Integer, nullable=True)
    
    # Customer Feedback & Google Reviews Configuration
    google_review_url = Column(String(500), nullable=True)
    allow_feedback_edits = Column(Boolean, default=False)
    
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

    @property
    def has_razorpay_secret(self) -> bool:
        return bool(self.razorpay_key_secret_enc)

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self.razorpay_webhook_secret_enc)

    def evaluate_subscription_status(self) -> str:
        """Evaluates live subscription status considering expiration date and grace period."""
        if self.subscription_status in ["CANCELLED", "SUSPENDED"]:
            return self.subscription_status
        if not self.subscription_expires_at:
            return self.subscription_status or "TRIAL"
        
        from datetime import datetime, timezone, timedelta
        # Normalize timezone if present
        now = datetime.now()
        exp = self.subscription_expires_at
        if hasattr(exp, 'tzinfo') and exp.tzinfo is not None:
            now = datetime.now(timezone.utc)
            
        if now <= exp:
            return "ACTIVE"
        
        grace_days = self.grace_period_days if self.grace_period_days is not None else 7
        grace_deadline = exp + timedelta(days=grace_days)
        if now <= grace_deadline:
            return "PAST_DUE"
        
        return "EXPIRED"
