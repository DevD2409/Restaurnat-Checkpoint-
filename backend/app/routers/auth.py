from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import func
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
from app.core.dependencies import (
    get_current_user,
    get_current_user_allow_password_change,
    require_roles,
    get_tenant_id,
)
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
    current_user: User = Depends(get_current_user_allow_password_change),
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
def read_current_user(current_user: User = Depends(get_current_user_allow_password_change)):
    return current_user

# Staff Management APIs (Scoped to Owner/Manager's Restaurant)
OWNER_ROLES = {UserRole.RESTAURANT_OWNER, UserRole.ADMIN}
MANAGER_ROLES = {UserRole.RESTAURANT_MANAGER, UserRole.MANAGER}
OPERATIONAL_STAFF_ROLES = {
    UserRole.WAITER,
    UserRole.KITCHEN,
    UserRole.CASHIER,
}
OWNER_ASSIGNABLE_ROLES = OWNER_ROLES | MANAGER_ROLES | OPERATIONAL_STAFF_ROLES

STAFF_MANAGERS = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER
]


def _validate_staff_role_assignment(caller: User, target_role: UserRole) -> None:
    """Enforce backend role hierarchy and block platform-role assignment via HTTP staff endpoints."""
    if target_role == UserRole.PLATFORM_SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PLATFORM_SUPER_ADMIN role cannot be assigned via HTTP staff endpoints",
        )

    if caller.role == UserRole.PLATFORM_SUPER_ADMIN or caller.role in OWNER_ROLES:
        allowed_roles = OWNER_ASSIGNABLE_ROLES
    elif caller.role in MANAGER_ROLES:
        allowed_roles = OPERATIONAL_STAFF_ROLES
    else:
        allowed_roles = set()

    if target_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Role '{caller.role.value}' cannot assign role '{target_role.value}'",
        )


def _ensure_target_staff_accessible(caller: User, staff: User, action: str) -> None:
    """Protect PLATFORM_SUPER_ADMIN accounts and enforce strict tenant isolation on target staff."""
    if staff.role == UserRole.PLATFORM_SUPER_ADMIN:
        past_tense = "modified" if action == "modify" else "deleted"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Platform Super Admin accounts cannot be {past_tense} via staff endpoints",
        )

    if caller.role != UserRole.PLATFORM_SUPER_ADMIN:
        if not caller.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not associated with any restaurant tenant",
            )
        if staff.restaurant_id is None or staff.restaurant_id != caller.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Cannot {action} staff from another restaurant",
            )


@router.get("/staff", response_model=List[UserResponse])
def list_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_MANAGERS))
):
    query = db.query(User)
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        if not current_user.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not associated with any restaurant tenant",
            )
        query = query.filter(
            User.restaurant_id == current_user.restaurant_id,
            User.role != UserRole.PLATFORM_SUPER_ADMIN,
        )
    return query.order_by(User.id.asc()).all()


@router.post("/staff", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    staff_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_MANAGERS))
):
    _validate_staff_role_assignment(current_user, staff_data.role)

    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
        if not staff_data.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="restaurant_id is required when creating tenant staff as platform super admin",
            )
        target_restaurant_id = staff_data.restaurant_id
    else:
        if not current_user.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is not associated with any restaurant tenant",
            )
        if staff_data.restaurant_id is not None and staff_data.restaurant_id != current_user.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot create staff for another restaurant",
            )
        target_restaurant_id = current_user.restaurant_id

    restaurant = db.query(Restaurant).filter(Restaurant.id == target_restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found")

    if len(staff_data.password.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    _enforce_production_credential_policy(password=staff_data.password, email=staff_data.email)
    existing = db.query(User).filter(
        (User.email == staff_data.email) | (User.username == staff_data.username)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )

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

    _ensure_target_staff_accessible(current_user, staff, action="modify")

    if current_user.role in MANAGER_ROLES and staff.role not in OPERATIONAL_STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Managers can only modify operational staff accounts",
        )

    if staff_update.role is not None:
        _validate_staff_role_assignment(current_user, staff_update.role)

    if staff_update.password is not None and len(staff_update.password.strip()) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )

    # Prevent duplicate email across accounts (409 Conflict)
    if staff_update.email is not None and staff_update.email.strip().lower() != staff.email.lower():
        existing_email = db.query(User).filter(
            func.lower(User.email) == staff_update.email.strip().lower(),
            User.id != staff.id,
        ).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists",
            )

    # Prevent self-deactivation or self-demotion of the last active owner/admin
    if staff.id == current_user.id and staff.role in [UserRole.RESTAURANT_OWNER, UserRole.ADMIN]:
        if staff_update.is_active is False:
            other_active_owners = db.query(User).filter(
                User.restaurant_id == staff.restaurant_id,
                User.role.in_([UserRole.RESTAURANT_OWNER, UserRole.ADMIN]),
                User.is_active == True,
                User.id != staff.id,
            ).count()
            if other_active_owners == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active owner or administrator account for this restaurant",
                )

        if staff_update.role is not None and staff_update.role not in [UserRole.RESTAURANT_OWNER, UserRole.ADMIN]:
            other_active_owners = db.query(User).filter(
                User.restaurant_id == staff.restaurant_id,
                User.role.in_([UserRole.RESTAURANT_OWNER, UserRole.ADMIN]),
                User.is_active == True,
                User.id != staff.id,
            ).count()
            if other_active_owners == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot demote the last active owner or administrator account for this restaurant",
                )

    if staff_update.email is not None or staff_update.password:
        _enforce_production_credential_policy(
            password=staff_update.password,
            email=staff_update.email,
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

    _ensure_target_staff_accessible(current_user, staff, action="delete")

    if staff.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")

    if staff.role in [UserRole.RESTAURANT_OWNER, UserRole.ADMIN]:
        other_active_owners = db.query(User).filter(
            User.restaurant_id == staff.restaurant_id,
            User.role.in_([UserRole.RESTAURANT_OWNER, UserRole.ADMIN]),
            User.is_active == True,
            User.id != staff.id,
        ).count()
        if other_active_owners == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the last active owner or administrator account for this restaurant",
            )
    
    db.delete(staff)
    db.commit()
    return {"message": "Staff member deleted successfully"}
