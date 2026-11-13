from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import (
    authorize_staff_or_table_session_for_table,
    get_optional_current_user,
    get_optional_table_session,
)
from app.models.billing import Bill, BillSplit, Payment, BillStatus, SplitType
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.table import Table, TableSession, TableStatus
from app.models.user import User
from app.schemas.billing import (
    BillResponse, BillSplitCreate, BillSplitResponse
)

router = APIRouter(prefix="/billing", tags=["Billing & Receipts"])


def _authorize_bill_access(
    *,
    restaurant_id: int,
    table_id: Optional[int],
    order: Optional[Order],
    created_at: Optional[datetime],
    current_user: Optional[User],
    table_session: Optional[TableSession],
) -> str:
    if order is not None:
        if order.restaurant_id != restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant integrity violation: bill and order belong to different restaurants",
            )
        if order.table and order.table.restaurant_id != restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant integrity violation: table belongs to a different restaurant",
            )

    return authorize_staff_or_table_session_for_table(
        current_user,
        table_session,
        resource_restaurant_id=restaurant_id,
        resource_table_id=table_id if table_id is not None else (order.table_id if order else None),
        resource_session_id=order.session_id if order else None,
        resource_created_at=order.created_at if order else created_at,
    )


@router.get("/order/{order_id}", response_model=BillResponse)
def get_or_create_bill_for_order(
    order_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).options(
        joinedload(Bill.splits),
        joinedload(Bill.payments),
        joinedload(Bill.order).joinedload(Order.table)
    ).filter(Bill.order_id == order_id).first()

    if bill:
        _authorize_bill_access(
            restaurant_id=bill.restaurant_id,
            table_id=bill.table_id,
            order=bill.order,
            created_at=bill.created_at,
            current_user=current_user,
            table_session=table_session,
        )
    else:
        order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        _authorize_bill_access(
            restaurant_id=order.restaurant_id,
            table_id=order.table_id,
            order=order,
            created_at=order.created_at,
            current_user=current_user,
            table_session=table_session,
        )

        restaurant = db.query(Restaurant).filter(Restaurant.id == order.restaurant_id).first()
        tax_pct = restaurant.tax_percentage if restaurant else 5.0
        service_pct = restaurant.service_charge_percentage if restaurant else 5.0

        bill = Bill(
            bill_number=f"INV-{order.order_number[4:]}",
            restaurant_id=order.restaurant_id,
            order_id=order.id,
            table_id=order.table_id,
            subtotal=order.subtotal,
            tax_percentage=tax_pct,
            tax_amount=order.tax_amount,
            service_charge_percentage=service_pct,
            service_charge=order.service_charge,
            tip_amount=order.tip_amount,
            discount_amount=0.0,
            final_amount=order.total_amount,
            status=BillStatus.UNPAID
        )
        db.add(bill)
        db.commit()
        db.refresh(bill)

    if bill.order and bill.order.table:
        bill.table_number = bill.order.table.table_number
    return bill

@router.get("/{bill_id}", response_model=BillResponse)
def get_bill(
    bill_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).options(
        joinedload(Bill.splits),
        joinedload(Bill.payments),
        joinedload(Bill.order).joinedload(Order.table)
    ).filter(Bill.id == bill_id).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    _authorize_bill_access(
        restaurant_id=bill.restaurant_id,
        table_id=bill.table_id,
        order=bill.order,
        created_at=bill.created_at,
        current_user=current_user,
        table_session=table_session,
    )

    if bill.order and bill.order.table:
        bill.table_number = bill.order.table.table_number
    return bill

@router.post("/{bill_id}/splits", response_model=List[BillSplitResponse])
def configure_bill_splits(
    bill_id: int,
    splits_data: List[BillSplitCreate],
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db)
):
    bill = (
        db.query(Bill)
        .options(joinedload(Bill.order).joinedload(Order.table))
        .filter(Bill.id == bill_id)
        .first()
    )
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    _authorize_bill_access(
        restaurant_id=bill.restaurant_id,
        table_id=bill.table_id,
        order=bill.order,
        created_at=bill.created_at,
        current_user=current_user,
        table_session=table_session,
    )

    if bill.status == BillStatus.PAID:
        raise HTTPException(status_code=400, detail="Cannot modify splits for a bill that is already paid")
    if not splits_data or any(sp.amount <= 0 for sp in splits_data):
        raise HTTPException(status_code=400, detail="All bill split amounts must be greater than zero")

    # Remove existing unpaid splits
    db.query(BillSplit).filter(BillSplit.bill_id == bill_id, BillSplit.is_paid == False).delete()

    created_splits = []
    for sp in splits_data:
        split_obj = BillSplit(
            bill_id=bill_id,
            split_type=sp.split_type,
            person_name=sp.person_name,
            amount=round(sp.amount, 2),
            is_paid=False
        )
        db.add(split_obj)
        created_splits.append(split_obj)

    db.commit()
    for s in created_splits:
        db.refresh(s)
    return created_splits

@router.get("/{bill_id}/receipt")
def get_printable_receipt(
    bill_id: int,
    current_user: Optional[User] = Depends(get_optional_current_user),
    table_session: Optional[TableSession] = Depends(get_optional_table_session),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).options(
        joinedload(Bill.order).joinedload(Order.items),
        joinedload(Bill.order).joinedload(Order.table),
        joinedload(Bill.payments)
    ).filter(Bill.id == bill_id).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    order = bill.order
    _authorize_bill_access(
        restaurant_id=bill.restaurant_id,
        table_id=bill.table_id,
        order=order,
        created_at=bill.created_at,
        current_user=current_user,
        table_session=table_session,
    )

    restaurant = db.query(Restaurant).filter(Restaurant.id == bill.restaurant_id).first()
    gst_number = (
        restaurant.gst_number.strip()
        if restaurant and restaurant.gst_number and restaurant.gst_number.strip()
        else None
    )

    return {
        "restaurant_name": restaurant.name if restaurant else "",
        "restaurant_gst": gst_number,
        "bill_number": bill.bill_number,
        "date": bill.created_at.strftime("%d %b %Y %I:%M %p") if bill.created_at else "",
        "table_number": order.table.table_number if order and order.table else "N/A",
        "customer_name": order.customer_name if order else "Guest",
        "items": [
            {
                "name": item.item_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price
            }
            for item in (order.items if order else [])
        ],
        "subtotal": bill.subtotal,
        "tax_percentage": bill.tax_percentage,
        "tax_amount": bill.tax_amount,
        "service_charge_percentage": bill.service_charge_percentage,
        "service_charge": bill.service_charge,
        "tip_amount": bill.tip_amount,
        "final_amount": bill.final_amount,
        "status": bill.status.value,
        "payments": [
            {
                "id": p.id,
                "method": p.payment_method.value,
                "amount": p.amount,
                "transaction_id": p.transaction_id,
                "status": p.status.value
            }
            for p in bill.payments
        ]
    }

