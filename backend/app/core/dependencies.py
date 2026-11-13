from datetime import datetime
from typing import Optional, List
from fastapi import Depends, HTTPException, Header, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession

STAFF_ROLES: List[UserRole] = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER,
    UserRole.WAITER,
    UserRole.KITCHEN,
    UserRole.CASHIER,
]

MANAGEMENT_ROLES: List[UserRole] = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER,
]

KITCHEN_ROLES: List[UserRole] = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER,
    UserRole.KITCHEN,
]

BILLING_ROLES: List[UserRole] = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER,
    UserRole.WAITER,
    UserRole.CASHIER,
]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def _lookup_active_user_from_token(token: Optional[str], db: Session) -> Optional[User]:
    """Decode JWT and fetch an active User row, returning None on invalid/expired/inactive tokens."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.query(User).filter(User.id == uid, User.is_active == True).first()


def authenticate_websocket_user(token: Optional[str], db: Session) -> Optional[User]:
    """
    Authenticate an active user for WebSocket connections.
    Rejects invalid tokens, inactive accounts, and users pending mandatory password change.
    """
    user = _lookup_active_user_from_token(token, db)
    if not user or user.must_change_password:
        return None
    return user


def get_current_user_allow_password_change(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate an active user from JWT without enforcing must_change_password."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = db.query(User).filter(User.id == uid, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_current_user(
    current_user: User = Depends(get_current_user_allow_password_change),
) -> User:
    """Authenticate an active user and block access if a forced password change is pending."""
    if current_user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing protected resources",
        )
    return current_user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication for mixed public/staff endpoints.
    Anonymous callers receive None; callers presenting a token must be active and not pending password change.
    """
    if not token:
        return None
    return get_current_user(get_current_user_allow_password_change(token=token, db=db))

def require_roles(allowed_roles: List[UserRole]):
    """
    Role-based access check.
    PLATFORM_SUPER_ADMIN possesses global administrative override.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {[r.value for r in allowed_roles]} role(s)",
            )
        return current_user
    return role_checker

def resolve_explicit_tenant_id(
    current_user: User,
    requested_tenant_id: Optional[int] = None,
) -> int:
    """
    Authoritatively derive and validate active tenant_id for authenticated actions.
    - Non-superadmin users are locked to current_user.restaurant_id.
    - PLATFORM_SUPER_ADMIN without a bound restaurant_id must explicitly supply requested_tenant_id
      and never silently defaults to tenant 1.
    """
    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
        resolved = requested_tenant_id if requested_tenant_id is not None else current_user.restaurant_id
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit tenant selection (restaurant_id) is required for platform super admin tenant-scoped operations",
            )
        return resolved

    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not associated with any restaurant tenant",
        )

    # Reject cross-tenant access attempts
    if requested_tenant_id is not None and requested_tenant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access violation: You are not authorized to access another restaurant's data",
        )

    return current_user.restaurant_id


def resolve_optional_auth_tenant_id(
    current_user: Optional[User],
    requested_tenant_id: Optional[int] = None,
    *,
    default_public_tenant_id: Optional[int] = 1,
) -> Optional[int]:
    """
    Resolve target tenant_id for mixed public/authenticated endpoints:
    - Authenticated caller: strictly validated via resolve_explicit_tenant_id (rejects cross-tenant requests).
    - Anonymous caller: uses requested_tenant_id or default_public_tenant_id.
    """
    if current_user is not None:
        return resolve_explicit_tenant_id(current_user, requested_tenant_id)

    if requested_tenant_id is not None:
        return requested_tenant_id
    return default_public_tenant_id


def is_staff_user(user: Optional[User]) -> bool:
    """Return True when the authenticated user holds an internal restaurant or platform staff role."""
    return user is not None and user.role in STAFF_ROLES


def _normalize_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def verify_table_session_token(
    db: Session,
    raw_token: Optional[str],
    *,
    expected_table_id: Optional[int] = None,
) -> Optional[TableSession]:
    """Verify an active non-ended customer table session joined to an active table."""
    if not raw_token:
        return None
    token = raw_token.strip()
    if not token:
        return None
    query = (
        db.query(TableSession)
        .join(Table, TableSession.table_id == Table.id)
        .filter(
            TableSession.session_token == token,
            TableSession.is_active == True,
            TableSession.ended_at.is_(None),
            Table.is_active == True,
        )
    )
    if expected_table_id is not None:
        query = query.filter(TableSession.table_id == expected_table_id)
    return query.first()


def get_optional_table_session(
    x_table_session: Optional[str] = Header(None, alias="X-Table-Session"),
    session_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Optional[TableSession]:
    """
    Validate a customer table session supplied via X-Table-Session header or session_token query parameter.
    Returns None if no token was supplied; raises 401 if a supplied token is invalid, expired, or inactive.
    """
    raw_token = x_table_session if x_table_session is not None else session_token
    if raw_token is None:
        return None

    token = raw_token.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or empty table session token",
        )

    session = verify_table_session_token(db, token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired table session",
        )
    return session


def authorize_staff_or_table_session_for_table(
    current_user: Optional[User],
    table_session: Optional[TableSession],
    *,
    resource_restaurant_id: int,
    resource_table_id: Optional[int],
    resource_session_id: Optional[int] = None,
    resource_created_at: Optional[datetime] = None,
) -> str:
    """
    Enforce authorization for table-scoped customer resources (orders, bills, receipts):
    - Authenticated staff (non-CUSTOMER): validated against resource_restaurant_id via resolve_explicit_tenant_id.
    - Verified active TableSession: validated against matching table_id, restaurant_id, and session boundary.
    Returns 'staff' or 'table_session' when authorized; raises 401/403 otherwise.
    """
    if current_user is not None:
        if is_staff_user(current_user):
            resolve_explicit_tenant_id(current_user, resource_restaurant_id)
            return "staff"
        if table_session is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient role privileges",
            )

    if table_session is not None:
        session_table = table_session.table
        if not session_table or not session_table.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or inactive table for session",
            )
        if session_table.restaurant_id != resource_restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied for table session",
            )
        if resource_table_id is None or table_session.table_id != resource_table_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Table session does not grant access to another table's resource",
            )
        if resource_session_id is not None:
            if resource_session_id != table_session.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Resource belongs to a different table session",
                )
        elif resource_created_at is not None and table_session.started_at is not None:
            if _normalize_naive_utc(resource_created_at) < _normalize_naive_utc(table_session.started_at):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Table session cannot access historical resources created before session start",
                )
        return "table_session"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication or valid active table session required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_tenant_id(
    current_user: User = Depends(get_current_user),
    requested_tenant_id: Optional[int] = Query(None)
) -> int:
    """
    Authoritatively derives and validates active tenant_id for authenticated staff/admin actions.
    Guarantees cross-tenant isolation by never trusting client-supplied tenant IDs.
    """
    return resolve_explicit_tenant_id(current_user, requested_tenant_id)

def get_active_tenant(
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.id == tenant_id, Restaurant.is_active == True).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found or inactive")

    # Platform Super Admins can inspect tenants regardless of subscription status
    if current_user and current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
        return restaurant

    live_status = restaurant.evaluate_subscription_status()
    if live_status in ["EXPIRED", "SUSPENDED", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Restaurant subscription is {live_status}. Please renew your plan to restore operational access."
        )
    return restaurant

TRIAL_ENTITLEMENTS = {
    "max_tables": 10,
    "kds_access": True,
    "advanced_analytics": True,
    "custom_branding": False,
    "multi_branch": False,
}

def require_feature_entitlement(feature_key: str):
    """
    Verifies that the restaurant's active subscription tier includes access to a requested feature.
    Fails closed (HTTP 403) when plan record is missing, unknown, inactive, or subscription is
    expired, past due, suspended, or cancelled.
    Platform super-admins bypass this check.
    """
    def checker(
        tenant_id: int = Depends(get_tenant_id),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> Restaurant:
        restaurant = db.query(Restaurant).filter(Restaurant.id == tenant_id, Restaurant.is_active == True).first()
        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant tenant not found or inactive")

        # Platform Super Admins possess global administrative override
        if current_user and current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
            return restaurant

        live_status = restaurant.evaluate_subscription_status()
        if live_status in ["EXPIRED", "SUSPENDED", "CANCELLED", "PAST_DUE"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Subscription is {live_status}. Access to feature '{feature_key}' is restricted."
            )

        from app.models.subscription import SubscriptionPlan
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.plan_code == restaurant.subscription_plan,
            SubscriptionPlan.is_active == True
        ).first()

        if plan:
            entitlements = plan.get_entitlements()
            if not entitlements.get(feature_key, False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Feature '{feature_key}' is not included in the {restaurant.subscription_plan} plan. Please upgrade your subscription."
                )
            return restaurant

        # Fallback for explicit TRIAL plan
        if restaurant.subscription_plan == "TRIAL" and live_status in ["ACTIVE", "TRIAL"]:
            if not TRIAL_ENTITLEMENTS.get(feature_key, False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Feature '{feature_key}' is not included in the TRIAL plan. Please upgrade your subscription."
                )
            return restaurant

        # Fail closed for missing, unknown or inactive plans
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Subscription plan '{restaurant.subscription_plan}' is unknown, inactive, or not entitled to '{feature_key}'."
        )

    return checker
