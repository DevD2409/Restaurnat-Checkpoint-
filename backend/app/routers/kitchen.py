from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import (
    KITCHEN_ROLES,
    STAFF_ROLES,
    require_roles,
    resolve_explicit_tenant_id,
)
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/kitchen", tags=["Kitchen Display System (KDS)"])

@router.get("/active")
def get_kitchen_active_orders(
    restaurant_id: Optional[int] = Query(None),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    """
    Returns live orders in kitchen pipeline strictly isolated to the authenticated restaurant tenant.
    Prevents cross-restaurant kitchen queue leakage.
    """
    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)

    orders = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.table)
    ).filter(
        Order.restaurant_id == target_id,
        Order.status.in_([
            OrderStatus.PLACED,
            OrderStatus.ACCEPTED,
            OrderStatus.PREPARING,
            OrderStatus.READY,
            OrderStatus.SERVED
        ])
    ).order_by(Order.created_at.asc()).all()

    now = datetime.now(timezone.utc)
    new_orders = []
    preparing = []
    ready = []
    completed = []

    for o in orders:
        created_tz = o.created_at
        if created_tz.tzinfo is None:
            created_tz = created_tz.replace(tzinfo=timezone.utc)
        elapsed_minutes = int((now - created_tz).total_seconds() / 60)
        is_delayed = elapsed_minutes > o.estimated_prep_time

        order_data = {
            "id": o.id,
            "order_number": o.order_number,
            "restaurant_id": o.restaurant_id,
            "table_id": o.table_id,
            "table_number": o.table.table_number if o.table else "Unknown",
            "customer_name": o.customer_name,
            "status": o.status.value,
            "priority": o.priority.value,
            "special_instructions": o.special_instructions,
            "created_at": o.created_at.isoformat(),
            "elapsed_minutes": elapsed_minutes,
            "estimated_prep_time": o.estimated_prep_time,
            "is_delayed": is_delayed,
            "items": [
                {
                    "id": item.id,
                    "item_name": item.item_name,
                    "quantity": item.quantity,
                    "special_instructions": item.special_instructions,
                    "status": item.status,
                    "customizations_json": item.customizations_json
                }
                for item in o.items
            ]
        }

        if o.status in [OrderStatus.PLACED, OrderStatus.ACCEPTED]:
            new_orders.append(order_data)
        elif o.status == OrderStatus.PREPARING:
            preparing.append(order_data)
        elif o.status == OrderStatus.READY:
            ready.append(order_data)
        elif o.status == OrderStatus.SERVED:
            completed.append(order_data)

    return {
        "restaurant_id": target_id,
        "new_orders": new_orders,
        "preparing": preparing,
        "ready": ready,
        "completed": completed,
        "total_active": len(orders),
        "delayed_count": sum(1 for o in orders if int((now - (o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=timezone.utc))).total_seconds() / 60) > o.estimated_prep_time)
    }

@router.patch("/item/{item_id}/status")
async def update_kitchen_item_status(
    item_id: int,
    status_str: str = Query(..., description="QUEUED, COOKING, READY"),
    restaurant_id: Optional[int] = Query(None),
    current_user: User = Depends(require_roles(KITCHEN_ROLES)),
    db: Session = Depends(get_db)
):
    item = (
        db.query(OrderItem)
        .options(joinedload(OrderItem.order))
        .filter(OrderItem.id == item_id)
        .first()
    )
    if not item or not item.order:
        raise HTTPException(status_code=404, detail="Order item not found")

    if restaurant_id is not None and restaurant_id != item.order.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied: supplied restaurant_id does not match order item tenant",
        )
    resolve_explicit_tenant_id(current_user, item.order.restaurant_id)

    item.status = status_str
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": item.status}

@router.post("/update-status")
async def kitchen_update_status(
    payload: dict,
    current_user: User = Depends(require_roles(KITCHEN_ROLES)),
    db: Session = Depends(get_db)
):
    order_id = payload.get("order_id")
    new_status_str = payload.get("status")
    chef_name = payload.get("chef_name") or current_user.full_name or current_user.username
    requested_restaurant_id = payload.get("restaurant_id")

    if not order_id or not new_status_str:
        raise HTTPException(status_code=400, detail="Missing order_id or status")

    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid order_id")

    try:
        new_status = OrderStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order status")

    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id_int).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if requested_restaurant_id is not None:
        try:
            req_rid_int = int(requested_restaurant_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid restaurant_id")
        if req_rid_int != order.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied: supplied restaurant_id does not match order tenant",
            )

    resolve_explicit_tenant_id(current_user, order.restaurant_id)

    old_status = order.status
    order.status = new_status

    if new_status == OrderStatus.READY and order.actual_prep_time is None:
        created_tz = order.created_at
        if created_tz.tzinfo is None:
            created_tz = created_tz.replace(tzinfo=timezone.utc)
        elapsed = int((datetime.now(timezone.utc) - created_tz).total_seconds() / 60)
        order.actual_prep_time = max(1, elapsed)

    db.add(OrderStatusHistory(
        order_id=order.id,
        previous_status=old_status.value,
        new_status=new_status.value,
        changed_by=chef_name,
        notes=f"Status advanced to {new_status.value} by kitchen"
    ))

    db.commit()

    await manager.broadcast_tenant_event(
        order.restaurant_id,
        "ORDER_STATUS_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "restaurant_id": order.restaurant_id,
            "table_id": order.table_id,
            "table_number": order.table.table_number if order.table else "",
            "previous_status": old_status.value,
            "new_status": new_status.value,
            "notes": f"Kitchen update by {chef_name}"
        },
        channel="kitchen",
        table_id=order.table_id
    )

    return {"message": "Order status updated successfully", "status": new_status.value}

