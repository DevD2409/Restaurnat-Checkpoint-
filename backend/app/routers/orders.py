import json
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import (
    STAFF_ROLES,
    authorize_staff_or_table_session_for_table,
    get_optional_current_user,
    get_optional_table_session,
    is_staff_user,
    require_roles,
    resolve_explicit_tenant_id,
)
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus, OrderPriority, PaymentStatus
from app.models.table import Table, TableSession, TableStatus
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
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.id == order_data.table_id, Table.is_active == True).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    # Authoritative tenant derivation: Table's restaurant_id is the single source of truth
    target_restaurant_id = table.restaurant_id

    resolved_session_id: Optional[int] = None
    if table_session is not None:
        if table_session.table_id != table.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Table session does not match target table",
            )
        resolved_session_id = table_session.id

    if order_data.session_id is not None:
        supplied_session = (
            db.query(TableSession)
            .filter(
                TableSession.id == order_data.session_id,
                TableSession.table_id == table.id,
                TableSession.is_active == True,
            )
            .first()
        )
        if not supplied_session:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid, inactive, or cross-table session_id",
            )
        if resolved_session_id is not None and resolved_session_id != supplied_session.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Conflicting table session identifier",
            )
        resolved_session_id = supplied_session.id

    restaurant = db.query(Restaurant).filter(Restaurant.id == target_restaurant_id).first()
    tax_percent = restaurant.tax_percentage if restaurant else 5.0
    service_charge_percent = restaurant.service_charge_percentage if restaurant else 5.0

    # Calculate item totals strictly within the table's restaurant menu
    subtotal = 0.0
    order_items_to_create = []

    for item in order_data.items:
        db_item = db.query(MenuItem).filter(
            MenuItem.id == item.menu_item_id,
            MenuItem.restaurant_id == target_restaurant_id
        ).first()

        if not db_item:
            raise HTTPException(
                status_code=400,
                detail=f"Menu item id {item.menu_item_id} does not belong to this restaurant",
            )
        if not db_item.is_available:
            raise HTTPException(status_code=400, detail=f"Menu item '{db_item.name}' is currently unavailable")

        authoritative_base_price = db_item.price
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
        restaurant_id=target_restaurant_id,
        table_id=order_data.table_id,
        session_id=resolved_session_id,
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

    for oi in order_items_to_create:
        oi.order_id = new_order.id
        db.add(oi)

    history = OrderStatusHistory(
        order_id=new_order.id,
        previous_status=None,
        new_status="PLACED",
        changed_by=order_data.customer_name or "Customer",
        notes="Order placed by customer via digital menu."
    )
    db.add(history)

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

    table.status = TableStatus.ORDER_PENDING
    db.commit()
    db.refresh(new_order)

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
            "restaurant_id": target_restaurant_id,
            "created_at": new_order.created_at.isoformat()
        },
        restaurant_id=target_restaurant_id
    )

    return new_order

@router.get("/", response_model=List[OrderResponse])
def get_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status"),
    table_id: Optional[int] = None,
    restaurant_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db)
):
    query = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.status_history),
        joinedload(Order.table)
    )

    staff_access = is_staff_user(current_user)
    if staff_access:
        target_tenant_id = resolve_explicit_tenant_id(current_user, restaurant_id)
        query = query.filter(Order.restaurant_id == target_tenant_id)
        if table_id is not None:
            query = query.filter(Order.table_id == table_id)
    elif table_session is not None:
        session_table = table_session.table
        if restaurant_id is not None and restaurant_id != session_table.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant access denied for table session",
            )
        if table_id is not None and table_id != table_session.table_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Table session does not grant access to another table's orders",
            )
        query = query.filter(
            Order.restaurant_id == session_table.restaurant_id,
            Order.table_id == table_session.table_id,
            or_(Order.session_id == table_session.id, Order.session_id.is_(None)),
        )
    elif current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: insufficient role privileges",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication or valid active table session required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if status_filter:
        query = query.filter(Order.status == status_filter)

    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
    if not staff_access and table_session is not None and table_session.started_at is not None:
        started_naive = (
            table_session.started_at.replace(tzinfo=None)
            if table_session.started_at.tzinfo is not None
            else table_session.started_at
        )
        filtered = []
        for o in orders:
            if o.session_id == table_session.id:
                filtered.append(o)
            elif o.session_id is None and o.created_at is not None:
                created_naive = o.created_at.replace(tzinfo=None) if o.created_at.tzinfo is not None else o.created_at
                if created_naive >= started_naive:
                    filtered.append(o)
        orders = filtered

    for o in orders:
        if o.table:
            o.table_number = o.table.table_number
        if not staff_access:
            o.customer_phone = None
    return orders

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db),
):
    order = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.status_history),
        joinedload(Order.table)
    ).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    access_mode = authorize_staff_or_table_session_for_table(
        current_user,
        table_session,
        resource_restaurant_id=order.restaurant_id,
        resource_table_id=order.table_id,
        resource_session_id=order.session_id,
        resource_created_at=order.created_at,
    )

    if order.table:
        order.table_number = order.table.table_number
    if access_mode != "staff":
        order.customer_phone = None
    return order

@router.patch("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    current_user: User = Depends(require_roles(STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    resolve_explicit_tenant_id(current_user, order.restaurant_id)
    if order.table and order.table.restaurant_id != order.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Order table does not belong to the order restaurant tenant",
        )

    old_status = order.status
    new_status = status_update.status
    order.status = new_status

    history = OrderStatusHistory(
        order_id=order.id,
        previous_status=old_status.value if old_status else None,
        new_status=new_status.value,
        changed_by=status_update.changed_by or current_user.full_name or current_user.username,
        notes=status_update.notes
    )
    db.add(history)

    if order.table:
        if new_status in [OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.SERVED]:
            order.table.status = TableStatus.OCCUPIED

    db.commit()
    db.refresh(order)

    await manager.broadcast_event(
        "ORDER_STATUS_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "table_id": order.table_id,
            "table_number": order.table.table_number if order.table else "",
            "previous_status": old_status.value if old_status else None,
            "new_status": new_status.value,
            "restaurant_id": order.restaurant_id,
            "notes": status_update.notes
        },
        restaurant_id=order.restaurant_id
    )

    if order.table:
        order.table_number = order.table.table_number
    return order

@router.patch("/{order_id}/priority", response_model=OrderResponse)
async def update_order_priority(
    order_id: int,
    priority_update: OrderPriorityUpdate,
    current_user: User = Depends(require_roles(STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    resolve_explicit_tenant_id(current_user, order.restaurant_id)

    order.priority = priority_update.priority
    db.commit()
    db.refresh(order)

    await manager.broadcast_event(
        "ORDER_PRIORITY_CHANGED",
        {
            "order_id": order.id,
            "order_number": order.order_number,
            "priority": order.priority.value,
            "restaurant_id": order.restaurant_id
        },
        restaurant_id=order.restaurant_id
    )

    if order.table:
        order.table_number = order.table.table_number
    return order
