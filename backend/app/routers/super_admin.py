from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.order import Order
from app.models.billing import Payment, PaymentRecordStatus
from app.models.table import Table

router = APIRouter(prefix="/platform", tags=["Platform Super Admin Management"])

class TenantStatusUpdate(BaseModel):
    subscription_status: str  # ACTIVE, SUSPENDED, CANCELLED
    is_active: Optional[bool] = None

@router.get("/stats")
def get_platform_overview_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Global SaaS overview metrics for Platform Super Admin."""
    total_tenants = db.query(Restaurant).count()
    active_tenants = db.query(Restaurant).filter(
        Restaurant.is_active == True,
        Restaurant.subscription_status == "ACTIVE"
    ).count()

    total_orders = db.query(Order).count()

    total_rev_result = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.status == PaymentRecordStatus.SUCCESS
    ).scalar()
    total_platform_revenue = round(float(total_rev_result), 2)

    total_users = db.query(User).count()

    # Plan distribution
    plans = db.query(Restaurant.subscription_plan, func.count(Restaurant.id)).group_by(Restaurant.subscription_plan).all()
    plan_distribution = {plan: count for plan, count in plans}

    return {
        "total_tenants": total_tenants,
        "total_restaurants": total_tenants,
        "active_tenants": active_tenants,
        "total_platform_orders": total_orders,
        "total_platform_revenue": total_platform_revenue,
        "total_registered_users": total_users,
        "subscription_plans": plan_distribution,
        "subscription_breakdown": plan_distribution
    }

@router.get("/restaurants")
@router.get("/tenants")
def list_all_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Lists all restaurants and hotels onboarded on the SaaS platform."""
    restaurants = db.query(Restaurant).order_by(Restaurant.id.desc()).all()
    result = []
    for r in restaurants:
        owner = db.query(User).filter(User.id == r.owner_id).first() if r.owner_id else None
        order_count = db.query(Order).filter(Order.restaurant_id == r.id).count()
        table_count = db.query(Table).filter(Table.restaurant_id == r.id, Table.is_active == True).count()
        rev = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).join(Order, Payment.bill_id == Order.id, isouter=True).filter(
            Order.restaurant_id == r.id,
            Payment.status == PaymentRecordStatus.SUCCESS
        ).scalar()

        result.append({
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "email": r.email,
            "phone": r.phone,
            "subscription_plan": r.subscription_plan,
            "subscription_status": r.subscription_status,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "owner": {
                "name": owner.full_name if owner else "Platform Admin",
                "email": owner.email if owner else r.email,
                "username": owner.username if owner else "admin"
            },
            "metrics": {
                "tables": table_count,
                "orders": order_count,
                "revenue": round(float(rev), 2)
            }
        })
    return result

@router.patch("/tenants/{restaurant_id}/status")
def update_tenant_status(
    restaurant_id: int,
    data: TenantStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Enables, suspends, or cancels a tenant restaurant subscription."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found")

    restaurant.subscription_status = data.subscription_status
    if data.is_active is not None:
        restaurant.is_active = data.is_active
    elif data.subscription_status in ["SUSPENDED", "CANCELLED"]:
        restaurant.is_active = False
    elif data.subscription_status == "ACTIVE":
        restaurant.is_active = True

    db.commit()
    db.refresh(restaurant)
    return {
        "message": f"Tenant '{restaurant.name}' subscription status updated to {restaurant.subscription_status}",
        "restaurant_id": restaurant.id,
        "subscription_status": restaurant.subscription_status,
        "is_active": restaurant.is_active
    }

