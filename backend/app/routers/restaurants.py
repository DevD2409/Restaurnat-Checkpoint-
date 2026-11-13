from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_tenant_id,
    require_roles,
    resolve_explicit_tenant_id,
    resolve_optional_auth_tenant_id,
)
from app.core.encryption import encrypt_secret
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.schemas.restaurant import RestaurantResponse, RestaurantUpdate, RestaurantPublicProfile

router = APIRouter(prefix="/restaurants", tags=["Restaurant Profile & Settings"])

OWNER_ONLY_FIELDS = {
    "is_active",
    "razorpay_key_id",
    "razorpay_key_secret",
    "razorpay_webhook_secret",
    "razorpay_key_secret_enc",
    "razorpay_webhook_secret_enc",
    "razorpay_account_id",
    "payment_gateway_mode",
    "subscription_plan",
    "subscription_status",
    "subscription_expires_at",
}

@router.get("/by-slug/{slug}", response_model=RestaurantPublicProfile)
def get_restaurant_by_slug(slug: str, db: Session = Depends(get_db)):
    """Public endpoint for customer app to resolve tenant branding and configuration by slug."""
    restaurant = db.query(Restaurant).filter(Restaurant.slug == slug, Restaurant.is_active == True).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant

@router.get("/public-list", response_model=List[RestaurantPublicProfile])
def list_public_restaurants(db: Session = Depends(get_db)):
    """Public listing of all onboarded restaurants and hospitality outlets."""
    return db.query(Restaurant).filter(Restaurant.is_active == True).order_by(Restaurant.name.asc()).all()

@router.get("/me", response_model=RestaurantResponse)
def get_my_restaurant_profile(
    restaurant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER,
        UserRole.WAITER,
        UserRole.KITCHEN,
        UserRole.CASHIER
    ]))
):
    """Returns the authenticated user's own restaurant tenant profile (or explicit tenant for super-admin)."""
    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")
    return restaurant

@router.get("/", response_model=RestaurantResponse)
def get_restaurant_profile(
    restaurant_id: Optional[int] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns restaurant profile:
    - If authenticated staff/owner: resolves their authoritative restaurant.
    - If super admin: requires explicit restaurant_id query parameter.
    - If unauthenticated: returns the default active restaurant (for backward compatibility).
    """
    target_id = resolve_optional_auth_tenant_id(
        current_user,
        restaurant_id,
        default_public_tenant_id=None,
    )

    if target_id:
        restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    else:
        restaurant = db.query(Restaurant).first()

    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")
    return restaurant

@router.put("/", response_model=RestaurantResponse)
def update_restaurant_profile(
    update_data: RestaurantUpdate,
    restaurant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """
    Self-service portal endpoint: Owners and managers can update their own restaurant profile,
    branding, tax, service charges, facilities, Wi-Fi, and payment gateway keys.
    """
    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")

    update_dict = update_data.model_dump(exclude_unset=True)

    if current_user.role not in [UserRole.PLATFORM_SUPER_ADMIN, UserRole.RESTAURANT_OWNER, UserRole.ADMIN]:
        disallowed = update_dict.keys() & OWNER_ONLY_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Only restaurant owners and platform administrators can modify sensitive tenant fields ({', '.join(sorted(disallowed))}).",
            )
    
    # Slug uniqueness check if slug is updated
    if "slug" in update_dict and update_dict["slug"] != restaurant.slug:
        existing = db.query(Restaurant).filter(Restaurant.slug == update_dict["slug"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug is already taken by another restaurant")

    # Securely encrypt secret keys before storing
    if "razorpay_key_secret" in update_dict:
        val = update_dict.pop("razorpay_key_secret")
        if val and val.strip():
            restaurant.razorpay_key_secret_enc = encrypt_secret(val.strip())
    elif "razorpay_key_secret_enc" in update_dict:
        val = update_dict.pop("razorpay_key_secret_enc")
        if val and val.strip():
            restaurant.razorpay_key_secret_enc = encrypt_secret(val.strip())

    if "razorpay_webhook_secret" in update_dict:
        val = update_dict.pop("razorpay_webhook_secret")
        if val and val.strip():
            restaurant.razorpay_webhook_secret_enc = encrypt_secret(val.strip())
    elif "razorpay_webhook_secret_enc" in update_dict:
        val = update_dict.pop("razorpay_webhook_secret_enc")
        if val and val.strip():
            restaurant.razorpay_webhook_secret_enc = encrypt_secret(val.strip())

    for field, value in update_dict.items():
        setattr(restaurant, field, value)

    db.commit()
    db.refresh(restaurant)
    return restaurant

@router.put("/{restaurant_id}", response_model=RestaurantResponse)
def update_specific_restaurant(
    restaurant_id: int,
    update_data: RestaurantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """Updates a specific restaurant, validating that non-superadmins can only modify their own tenant."""
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and current_user.restaurant_id != restaurant_id:
        raise HTTPException(status_code=403, detail="You are not authorized to update another restaurant's profile.")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")

    update_dict = update_data.model_dump(exclude_unset=True)

    if current_user.role not in [UserRole.PLATFORM_SUPER_ADMIN, UserRole.RESTAURANT_OWNER, UserRole.ADMIN]:
        disallowed = update_dict.keys() & OWNER_ONLY_FIELDS
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Only restaurant owners and platform administrators can modify sensitive tenant fields ({', '.join(sorted(disallowed))}).",
            )

    if "slug" in update_dict and update_dict["slug"] != restaurant.slug:
        existing = db.query(Restaurant).filter(Restaurant.slug == update_dict["slug"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug is already taken by another restaurant")

    # Securely encrypt secret keys before storing
    if "razorpay_key_secret" in update_dict:
        val = update_dict.pop("razorpay_key_secret")
        if val and val.strip():
            restaurant.razorpay_key_secret_enc = encrypt_secret(val.strip())
    elif "razorpay_key_secret_enc" in update_dict:
        val = update_dict.pop("razorpay_key_secret_enc")
        if val and val.strip():
            restaurant.razorpay_key_secret_enc = encrypt_secret(val.strip())

    if "razorpay_webhook_secret" in update_dict:
        val = update_dict.pop("razorpay_webhook_secret")
        if val and val.strip():
            restaurant.razorpay_webhook_secret_enc = encrypt_secret(val.strip())
    elif "razorpay_webhook_secret_enc" in update_dict:
        val = update_dict.pop("razorpay_webhook_secret_enc")
        if val and val.strip():
            restaurant.razorpay_webhook_secret_enc = encrypt_secret(val.strip())

    for field, value in update_dict.items():
        setattr(restaurant, field, value)

    db.commit()
    db.refresh(restaurant)
    return restaurant

