from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import require_roles, oauth2_scheme
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/kitchen", tags=["Kitchen Display System (KDS)"])

@router.get("/active")
def get_kitchen_active_orders(
    restaurant_id: Optional[int] = Query(None),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """
    Returns live orders in kitchen pipeline strictly isolated to the authenticated restaurant tenant.
    Prevents cross-restaurant kitchen queue leakage.
    """
    target_id = restaurant_id
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            user = db.query(User).filter(User.id == int(payload["sub"])).first()
            if user:
                if user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id:
                    target_id = user.restaurant_id
    if target_id is None:
        target_id = 1

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
    db: Session = Depends(get_db)
):
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    item.status = status_str
    db.commit()
    db.refresh(item)
    return {"id": item.id, "status": item.status}

@router.post("/update-status")
async def kitchen_update_status(
    payload: dict,
    db: Session = Depends(get_db)
):
    order_id = payload.get("order_id")
    new_status_str = payload.get("status")
    chef_name = payload.get("chef_name", "Kitchen Chef")

    if not order_id or not new_status_str:
        raise HTTPException(status_code=400, detail="Missing order_id or status")

    try:
        new_status = OrderStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order status")

    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

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

