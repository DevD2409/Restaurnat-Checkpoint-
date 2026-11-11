from typing import Optional, List
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
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
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user

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

def get_tenant_id(
    current_user: User = Depends(get_current_user),
    requested_tenant_id: Optional[int] = Query(None)
) -> int:
    """
    Authoritatively derives and validates active tenant_id for authenticated staff/admin actions.
    Guarantees cross-tenant isolation by never trusting client-supplied tenant IDs.
    """
    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN:
        return requested_tenant_id or current_user.restaurant_id or 1
    
    if not current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not associated with any restaurant tenant"
        )
    
    # Reject cross-tenant access attempts
    if requested_tenant_id is not None and requested_tenant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access violation: You are not authorized to access another restaurant's data"
        )
    
    return current_user.restaurant_id

def get_active_tenant(
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db)
) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.id == tenant_id, Restaurant.is_active == True).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found or inactive")
    
    live_status = restaurant.evaluate_subscription_status()
    if live_status in ["EXPIRED", "SUSPENDED", "CANCELLED"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Restaurant subscription is {live_status}. Please renew your plan to restore operational access."
        )
    return restaurant

def require_feature_entitlement(feature_key: str):
    """Verifies that the restaurant's active subscription tier includes access to a requested feature."""
    def checker(tenant: Restaurant = Depends(get_active_tenant), db: Session = Depends(get_db)):
        from app.models.subscription import SubscriptionPlan
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == tenant.subscription_plan).first()
        if plan:
            entitlements = plan.get_entitlements()
            if not entitlements.get(feature_key, False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Feature '{feature_key}' is not included in the {tenant.subscription_plan} plan. Please upgrade your subscription."
                )
        return tenant
    return checker
