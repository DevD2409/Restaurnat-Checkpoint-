from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    is_blocked_demo_password,
    is_demo_seed_account,
)
from app.core.dependencies import get_current_user, require_roles, get_tenant_id
from app.core.rate_limiter import login_limiter
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.schemas.auth import Token, LoginRequest, UserCreate, UserUpdate, UserResponse, ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["Authentication & Staff"])


def _enforce_production_credential_policy(
    password: Optional[str] = None,
    email: Optional[str] = None,
) -> None:
    """Reject known demo passwords or reserved demo seed accounts in production."""
    if settings.ENVIRONMENT.lower() != "production":
        return
    if password and is_blocked_demo_password(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo passwords are prohibited in production."
        )
    if email and is_demo_seed_account(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Demo accounts are prohibited in production."
        )

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # 1. Enforce rate limiting and brute force protection
    login_limiter.check(request, login_data.username)

    is_prod = settings.ENVIRONMENT.lower() == "production"
    if is_prod and is_blocked_demo_password(login_data.password):
        login_limiter.record_failure(request, login_data.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo credentials are disabled in production"
        )

    # 2. Authenticate by username or email
    user = db.query(User).filter(
        (User.username == login_data.username) | (User.email == login_data.username)
    ).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        login_limiter.record_failure(request, login_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if is_prod and is_demo_seed_account(user.email):
        login_limiter.record_failure(request, login_data.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts are disabled in production"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    # 3. Reset rate limiter upon successful authentication
    login_limiter.record_success(request, login_data.username)

    restaurant_slug = None
    if user.restaurant_id:
        restaurant = db.query(Restaurant).filter(Restaurant.id == user.restaurant_id).first()
        if restaurant:
            restaurant_slug = restaurant.slug

    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
        "full_name": user.full_name,
        "username": user.username,
        "restaurant_id": user.restaurant_id,
        "restaurant_slug": restaurant_slug,
        "must_change_password": bool(user.must_change_password)
    }

@router.post("/change-password")
def change_password(
    pwd_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Enforces secure self-service password change, clearing the must_change_password flag."""
    if not verify_password(pwd_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    if len(pwd_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )
    if pwd_data.current_password == pwd_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    _enforce_production_credential_policy(password=pwd_data.new_password)

    current_user.hashed_password = get_password_hash(pwd_data.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password updated successfully"}

@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

# Staff Management APIs (Scoped to Owner/Manager's Restaurant)
STAFF_MANAGERS = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER
]

@router.get("/staff", response_model=List[UserResponse])
def list_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_MANAGERS))
):
    query = db.query(User)
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        query = query.filter(User.restaurant_id == current_user.restaurant_id)
    return query.order_by(User.id.asc()).all()

@router.post("/staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    staff_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_MANAGERS))
):
    _enforce_production_credential_policy(password=staff_data.password, email=staff_data.email)
    existing = db.query(User).filter(
        (User.email == staff_data.email) | (User.username == staff_data.username)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    
    # Enforce tenant context
    target_restaurant_id = current_user.restaurant_id
    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN and staff_data.restaurant_id:
        target_restaurant_id = staff_data.restaurant_id

    new_staff = User(
        restaurant_id=target_restaurant_id,
        email=staff_data.email,
        username=staff_data.username,
        hashed_password=get_password_hash(staff_data.password),
        full_name=staff_data.full_name,
        role=staff_data.role,
        phone_number=staff_data.phone_number,
        shift=staff_data.shift or "General Shift",
        is_active=True
    )
    db.add(new_staff)
    db.commit()
    db.refresh(new_staff)
    return new_staff

@router.put("/staff/{staff_id}", response_model=UserResponse)
def update_staff(
    staff_id: int,
    staff_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_MANAGERS))
):
    staff = db.query(User).filter(User.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Cross-tenant modification guard
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and staff.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot modify staff from another restaurant"
        )

    if staff_update.email is not None:
        staff.email = staff_update.email
    if staff_update.full_name is not None:
        staff.full_name = staff_update.full_name
    if staff_update.role is not None:
        staff.role = staff_update.role
    if staff_update.phone_number is not None:
        staff.phone_number = staff_update.phone_number
    if staff_update.shift is not None:
        staff.shift = staff_update.shift
    if staff_update.is_active is not None:
        staff.is_active = staff_update.is_active
    if staff_update.email is not None or staff_update.password:
        _enforce_production_credential_policy(
            password=staff_update.password,
            email=staff_update.email,
        )
    if staff_update.password:
        staff.hashed_password = get_password_hash(staff_update.password)

    db.commit()
    db.refresh(staff)
    return staff

@router.delete("/staff/{staff_id}")
def delete_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN, UserRole.RESTAURANT_OWNER, UserRole.ADMIN]))
):
    staff = db.query(User).filter(User.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Cross-tenant deletion guard
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and staff.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot delete staff from another restaurant"
        )

    if staff.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
    
    db.delete(staff)
    db.commit()
    return {"message": "Staff member deleted successfully"}
