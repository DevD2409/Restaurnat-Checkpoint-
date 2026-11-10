import json
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.models.user import User, UserRole
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus, OrderPriority, PaymentStatus
from app.models.table import Table, TableStatus
from app.models.restaurant import Restaurant
from app.models.menu import MenuItem
from app.models.billing import Bill, BillStatus
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate, OrderPriorityUpdate
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/orders", tags=["Orders & Real-Time Tracking"])

def generate_order_number(db: Session) -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = db.query(Order).filter(Order.order_number.like(f"ORD-{today_str}-%")).count() + 1
    salt = uuid.uuid4().hex[:4].upper()
    return f"ORD-{today_str}-{count:03d}-{salt}"

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.id == order_data.table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    restaurant = db.query(Restaurant).filter(Restaurant.id == order_data.restaurant_id).first()
    tax_percent = restaurant.tax_percentage if restaurant else 5.0
    service_charge_percent = restaurant.service_charge_percentage if restaurant else 5.0

    # Calculate item totals
    subtotal = 0.0
    order_items_to_create = []

    for item in order_data.items:
        # Verify menu item in DB to prevent price tampering and ordering unavailable items
        db_item = db.query(MenuItem).filter(MenuItem.id == item.menu_item_id).first()
        if not db_item:
            raise HTTPException(status_code=400, detail=f"Menu item id {item.menu_item_id} not found")
        if not db_item.is_available:
            raise HTTPException(status_code=400, detail=f"Menu item '{db_item.name}' is currently unavailable")

        # Database authoritative base price overrides any tampered client value
        authoritative_base_price = db_item.price

        # Sum add-on additional prices
        addon_total = sum(c.additional_price for c in (item.customizations or []))
        unit_effective_price = authoritative_base_price + addon_total
        item_total = unit_effective_price * item.quantity
        subtotal += item_total

        customizations_json = None
        if item.customizations:
            customizations_json = json.dumps([c.model_dump() for c in item.customizations])

        order_items_to_create.append(
            OrderItem(
                menu_item_id=item.menu_item_id,
                item_name=db_item.name,
                unit_price=unit_effective_price,
                quantity=item.quantity,
                total_price=item_total,
                customizations_json=customizations_json,
                special_instructions=item.special_instructions,
                status="QUEUED"
            )
        )

    tax_amount = round(subtotal * (tax_percent / 100.0), 2)
    service_charge = round(subtotal * (service_charge_percent / 100.0), 2)
    total_amount = round(subtotal + tax_amount + service_charge + order_data.tip_amount, 2)

    order_num = generate_order_number(db)
    new_order = Order(
        order_number=order_num,
        restaurant_id=order_data.restaurant_id,
        table_id=order_data.table_id,
        session_id=order_data.session_id,
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        status=OrderStatus.PLACED,
        priority=OrderPriority.NORMAL,
        subtotal=round(subtotal, 2),
        tax_amount=tax_amount,
        service_charge=service_charge,
        tip_amount=order_data.tip_amount,
        total_amount=total_amount,
        payment_status=PaymentStatus.UNPAID,
        special_instructions=order_data.special_instructions,
        estimated_prep_time=20
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Attach order items
    for oi in order_items_to_create:
        oi.order_id = new_order.id
        db.add(oi)

    # Initial status history
    history = OrderStatusHistory(
        order_id=new_order.id,
        previous_status=None,
        new_status="PLACED",
        changed_by=order_data.customer_name or "Customer",
        notes="Order placed by customer via digital menu."
    )
    db.add(history)

    # Auto create initial bill record
    bill = Bill(
        bill_number=f"INV-{new_order.order_number[4:]}",
        restaurant_id=new_order.restaurant_id,
        order_id=new_order.id,
        table_id=new_order.table_id,
        subtotal=new_order.subtotal,
        tax_percentage=tax_percent,
        tax_amount=new_order.tax_amount,
        service_charge_percentage=service_charge_percent,
        service_charge=new_order.service_charge,
        tip_amount=new_order.tip_amount,
        discount_amount=0.0,
        final_amount=new_order.total_amount,
        status=BillStatus.UNPAID
    )
    db.add(bill)

    # Update table status
    table.status = TableStatus.ORDER_PENDING
    db.commit()
    db.refresh(new_order)

    # Broadcast event via WebSocket
    await manager.broadcast_event(
        "ORDER_PLACED",
        {
            "order_id": new_order.id,
            "order_number": new_order.order_number,
            "table_id": new_order.table_id,
            "table_number": table.table_number,
            "items_count": len(order_data.items),
            "total_amount": new_order.total_amount,
            "customer_name": new_order.customer_name,
            "status": new_order.status.value,
            "created_at": new_order.created_at.isoformat()
        },
        table_id=new_order.table_id
    )

    return new_order

@router.get("/", response_model=List[OrderResponse])
def get_orders(
    status: Optional[OrderStatus] = None,
    table_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.status_history),
        joinedload(Order.table)
    )

    if status:
        query = query.filter(Order.status == status)
    if table_id:
        query = query.filter(Order.table_id == table_id)

    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    # Populate table_number
    for o in orders:
        if o.table:
            o.table_number = o.table.table_number
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.status_history),
        joinedload(Order.table)
    ).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.table:
        order.table_number = order.table.table_number
    return order

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: Session = Depends(get_db)
):
    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    new_status = status_update.status
    order.status = new_status

    # Record history
    history = OrderStatusHistory(
        order_id=order.id,
        previous_status=old_status.value if old_status else None,
        new_status=new_status.value,
        changed_by=status_update.changed_by or "Staff",
        notes=status_update.notes
    )
    db.add(history)

    # Sync table status based on order progression
    if order.table:
        if new_status == OrderStatus.PREPARING:
            order.table.status = TableStatus.OCCUPIED
        elif new_status == OrderStatus.READY:
            order.table.status = TableStatus.OCCUPIED
        elif new_status == OrderStatus.SERVED:
            order.table.status = TableStatus.OCCUPIED
        elif new_status == OrderStatus.COMPLETED:
            pass  # Table freed when session ends or bill paid

    db.commit()
    db.refresh(order)

    # Broadcast status change across rooms
    await manager.broadcast_event(
        "ORDER_STATUS_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "table_id": order.table_id,
            "table_number": order.table.table_number if order.table else "",
            "previous_status": old_status.value if old_status else None,
            "new_status": new_status.value,
            "notes": status_update.notes
        },
        table_id=order.table_id
    )

    if order.table:
        order.table_number = order.table.table_number
    return order

@router.patch("/{order_id}/priority", response_model=OrderResponse)
async def update_order_priority(
    order_id: int,
    priority_update: OrderPriorityUpdate,
    db: Session = Depends(get_db)
):
    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.priority = priority_update.priority
    db.commit()
    db.refresh(order)

    await manager.broadcast_event(
        "ORDER_PRIORITY_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "priority": order.priority.value
        },
        table_id=order.table_id
    )

    if order.table:
        order.table_number = order.table.table_number
    return order

