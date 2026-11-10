from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models.billing import Bill, BillSplit, Payment, BillStatus, SplitType
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.table import Table, TableStatus
from app.schemas.billing import (
    BillResponse, BillSplitCreate, BillSplitResponse
)

router = APIRouter(prefix="/billing", tags=["Billing & Receipts"])

@router.get("/order/{order_id}", response_model=BillResponse)
def get_or_create_bill_for_order(order_id: int, db: Session = Depends(get_db)):
    bill = db.query(Bill).options(
        joinedload(Bill.splits),
        joinedload(Bill.payments),
        joinedload(Bill.order).joinedload(Order.table)
    ).filter(Bill.order_id == order_id).first()

    if not bill:
        order = db.query(Order).options(joinedload(Order.table)).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

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
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(Bill).options(
        joinedload(Bill.splits),
        joinedload(Bill.payments),
        joinedload(Bill.order).joinedload(Order.table)
    ).filter(Bill.id == bill_id).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if bill.order and bill.order.table:
        bill.table_number = bill.order.table.table_number
    return bill

@router.post("/{bill_id}/splits", response_model=List[BillSplitResponse])
def configure_bill_splits(
    bill_id: int,
    splits_data: List[BillSplitCreate],
    db: Session = Depends(get_db)
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

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
def get_printable_receipt(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(Bill).options(
        joinedload(Bill.order).joinedload(Order.items),
        joinedload(Bill.order).joinedload(Order.table),
        joinedload(Bill.payments)
    ).filter(Bill.id == bill_id).first()

    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    order = bill.order
    return {
        "restaurant_name": "The Royal Saffron - Smart Bistro & Lounge",
        "restaurant_gst": "07AABCR9603R1ZM",
        "bill_number": bill.bill_number,
        "date": bill.created_at.strftime("%d %b %Y %I:%M %p"),
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

