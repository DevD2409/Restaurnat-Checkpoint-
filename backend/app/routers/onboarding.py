import re
from typing import Optional
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_password_hash, create_access_token, generate_table_qr_token
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.models.table import Table, TableStatus
from app.models.menu import MenuCategory, MenuItem

router = APIRouter(prefix="/onboarding", tags=["Tenant Onboarding & Registration"])

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

class OnboardingRegisterRequest(BaseModel):
    # Restaurant Details
    restaurant_name: str
    slug: Optional[str] = None
    tagline: Optional[str] = "Exceptional Dining & Hospitality"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    table_count: Optional[int] = 5
    currency: str = "INR"
    currency_symbol: str = "₹"
    tax_percentage: float = 5.0
    service_charge_percentage: float = 5.0
    timezone: str = "Asia/Kolkata"
    primary_color: str = "#f97316"
    subscription_plan: str = "PRO"

    # Owner Account Details
    owner_full_name: str
    owner_email: EmailStr
    owner_username: str
    owner_password: str
    owner_phone: Optional[str] = None

class OnboardingResponse(BaseModel):
    message: str
    restaurant_id: int
    restaurant_name: str
    restaurant_slug: str
    owner_username: str
    table_count: int = 5
    access_token: str
    token_type: str = "bearer"
    public_url: str

@router.get("/check-slug/{slug}")
def check_slug_availability(slug: str, db: Session = Depends(get_db)):
    clean_slug = slugify(slug)
    existing = db.query(Restaurant).filter(Restaurant.slug == clean_slug).first()
    return {
        "slug": clean_slug,
        "is_available": existing is None,
        "available": existing is None
    }

@router.get("/check-slug")
def check_slug_query(slug: str, db: Session = Depends(get_db)):
    clean_slug = slugify(slug)
    existing = db.query(Restaurant).filter(Restaurant.slug == clean_slug).first()
    return {
        "slug": clean_slug,
        "is_available": existing is None,
        "available": existing is None
    }

@router.post("/register", response_model=OnboardingResponse, status_code=status.HTTP_201_CREATED)
def onboard_restaurant(data: OnboardingRegisterRequest, db: Session = Depends(get_db)):
    # 1. Generate & validate clean slug
    slug = slugify(data.slug if data.slug else data.restaurant_name)
    if not slug:
        slug = f"restaurant-{int(time.time())}"

    existing_restaurant = db.query(Restaurant).filter(Restaurant.slug == slug).first()
    if existing_restaurant:
        raise HTTPException(status_code=400, detail=f"Restaurant slug '{slug}' is already registered. Please choose another.")

    # 2. Check owner username / email
    existing_user = db.query(User).filter(
        (User.username == data.owner_username) | (User.email == data.owner_email)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Owner username or email is already registered.")

    # 3. Create Tenant Restaurant
    restaurant = Restaurant(
        name=data.restaurant_name,
        slug=slug,
        tagline=data.tagline,
        address=data.address,
        phone=data.phone,
        email=data.email,
        gst_number=data.gst_number or "27AAACB2233M1Z5",
        currency=data.currency,
        currency_symbol=data.currency_symbol,
        tax_percentage=data.tax_percentage,
        service_charge_percentage=data.service_charge_percentage,
        timezone=data.timezone,
        primary_color=data.primary_color,
        subscription_plan=data.subscription_plan,
        subscription_status="ACTIVE",
        is_active=True
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    # 4. Create Owner Account
    owner = User(
        restaurant_id=restaurant.id,
        email=data.owner_email,
        username=data.owner_username,
        hashed_password=get_password_hash(data.owner_password),
        full_name=data.owner_full_name,
        role=UserRole.RESTAURANT_OWNER,
        phone_number=data.owner_phone,
        shift="All Shifts",
        is_active=True
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)

    restaurant.owner_id = owner.id

    # 5. Bootstrap Initial Sample Tables with Signed QR Codes
    table_count = data.table_count or 5
    for i in range(1, table_count + 1):
        t_num = f"T{i}"
        qr_token = generate_table_qr_token(restaurant.id, i, t_num)
        table = Table(
            restaurant_id=restaurant.id,
            table_number=t_num,
            capacity=4,
            section="Main Dining",
            status=TableStatus.AVAILABLE,
            qr_token=qr_token,
            is_active=True
        )
        db.add(table)

    # 6. Bootstrap Initial Starter Menu Category & Sample Item
    category = MenuCategory(
        restaurant_id=restaurant.id,
        name="Chef's Specials",
        description="Signature delicacies crafted for our guests",
        icon="Flame",
        display_order=1,
        is_active=True
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    item = MenuItem(
        restaurant_id=restaurant.id,
        category_id=category.id,
        name="Signature House Platter",
        description="Assortment of freshly grilled artisanal specialties served with house dip",
        price=450.0,
        is_veg=True,
        is_bestseller=True,
        is_available=True,
        preparation_time=15
    )
    db.add(item)
    db.commit()

    # 7. Generate Owner Access Token
    access_token = create_access_token(
        subject=owner.id,
        role=owner.role.value,
        restaurant_id=restaurant.id
    )

    return {
        "message": "Restaurant successfully onboarded and activated!",
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_username": owner.username,
        "table_count": table_count,
        "access_token": access_token,
        "token_type": "bearer",
        "public_url": f"/{restaurant.slug}/menu"
    }

