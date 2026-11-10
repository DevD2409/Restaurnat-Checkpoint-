from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles, get_tenant_id, oauth2_scheme
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.schemas.restaurant import RestaurantResponse, RestaurantUpdate, RestaurantPublicProfile

router = APIRouter(prefix="/restaurants", tags=["Restaurant Profile & Settings"])

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
    """Returns the authenticated user's own restaurant tenant profile."""
    target_id = current_user.restaurant_id or 1
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")
    return restaurant

@router.get("/", response_model=RestaurantResponse)
def get_restaurant_profile(
    restaurant_id: Optional[int] = Query(None),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Returns restaurant profile:
    - If authenticated staff/owner: resolves their authoritative restaurant.
    - If super admin: allows querying arbitrary restaurant_id.
    - If unauthenticated: returns the default active restaurant (for backward compatibility).
    """
    target_id = restaurant_id
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            user = db.query(User).filter(User.id == int(payload["sub"])).first()
            if user:
                if user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id:
                    target_id = user.restaurant_id

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
    target_id = current_user.restaurant_id if current_user.role != UserRole.PLATFORM_SUPER_ADMIN else 1
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant profile not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Slug uniqueness check if slug is updated
    if "slug" in update_dict and update_dict["slug"] != restaurant.slug:
        existing = db.query(Restaurant).filter(Restaurant.slug == update_dict["slug"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug is already taken by another restaurant")

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
    if "slug" in update_dict and update_dict["slug"] != restaurant.slug:
        existing = db.query(Restaurant).filter(Restaurant.slug == update_dict["slug"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slug is already taken by another restaurant")

    for field, value in update_dict.items():
        setattr(restaurant, field, value)

    db.commit()
    db.refresh(restaurant)
    return restaurant

