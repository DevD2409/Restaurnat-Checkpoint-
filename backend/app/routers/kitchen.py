from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/kitchen", tags=["Kitchen Display System (KDS)"])

@router.get("/active")
def get_kitchen_active_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.table)
    ).filter(
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
                    "name": item.item_name,
                    "quantity": item.quantity,
                    "customizations_json": item.customizations_json,
                    "special_instructions": item.special_instructions,
                    "status": item.status
                }
                for item in o.items
            ]
        }

        if o.status == OrderStatus.PLACED:
            new_orders.append(order_data)
        elif o.status in [OrderStatus.ACCEPTED, OrderStatus.PREPARING]:
            preparing.append(order_data)
        elif o.status == OrderStatus.READY:
            ready.append(order_data)
        elif o.status == OrderStatus.SERVED:
            completed.append(order_data)

    return {
        "new_orders": new_orders,
        "preparing": preparing,
        "ready": ready,
        "completed": completed,
        "total_active": len(new_orders) + len(preparing) + len(ready)
    }

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

    await manager.broadcast_event(
        "ORDER_STATUS_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "table_id": order.table_id,
            "table_number": order.table.table_number if order.table else "",
            "previous_status": old_status.value,
            "new_status": new_status.value,
            "notes": f"Kitchen update by {chef_name}"
        },
        table_id=order.table_id
    )

    return {"message": "Order status updated successfully", "status": new_status.value}

