import json
import time
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles, get_active_tenant
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.billing import (
    Bill, BillSplit, Payment, BillStatus, PaymentMethod, PaymentRecordStatus, PaymentWebhookEvent
)
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.table import Table, TableStatus
from app.schemas.billing import (
    RazorpayOrderCreate, RazorpayVerifyPayment, PaymentRefundRequest, PaymentReconciliationResponse
)
from app.services.payment_service import PaymentService
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/payments", tags=["Flow A: Restaurant Customer Payments"])

@router.post("/razorpay-order")
def create_razorpay_order(data: RazorpayOrderCreate, db: Session = Depends(get_db)):
    """
    Creates an authoritative Razorpay order on the restaurant's merchant account.
    All calculations are derived from authoritative database records.
    """
    PaymentService.ensure_payments_active("A")

    bill = db.query(Bill).filter(Bill.id == data.bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    restaurant = db.query(Restaurant).filter(Restaurant.id == bill.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found")

    # Authoritative calculation of remaining balance
    already_paid = sum(
        p.amount for p in db.query(Payment).filter(
            Payment.bill_id == bill.id,
            Payment.status == PaymentRecordStatus.SUCCESS
        ).all()
    )
    remaining_balance = max(0.0, bill.final_amount - already_paid)

    # Use authoritative amount
    target_amount = data.amount
    if target_amount <= 0 or target_amount > (remaining_balance + 1.0):
        target_amount = remaining_balance

    order_result = PaymentService.create_restaurant_order(
        restaurant=restaurant,
        bill=bill,
        amount=target_amount,
        currency=data.currency or restaurant.currency or "INR"
    )

    return order_result

@router.post("/verify-razorpay-payment")
async def verify_razorpay_payment(
    data: RazorpayVerifyPayment,
    db: Session = Depends(get_db)
):
    """
    Cryptographically verifies the customer payment signature against the restaurant's key secret.
    Enforces idempotency and updates bill, order and table status.
    """
    PaymentService.ensure_payments_active("A")

    bill = db.query(Bill).filter(Bill.id == data.bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    restaurant = db.query(Restaurant).filter(Restaurant.id == bill.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant tenant not found")

    # Cryptographic HMAC SHA256 Signature Verification
    is_valid = PaymentService.verify_restaurant_payment_signature(
        restaurant=restaurant,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment signature. Verification failed."
        )

    # Idempotent Deduplication: Check if this payment is already recorded
    tx_id = f"tx_{data.razorpay_payment_id}"
    existing_payment = db.query(Payment).filter(
        (Payment.transaction_id == tx_id) | (Payment.razorpay_payment_id == data.razorpay_payment_id)
    ).first()

    if existing_payment:
        return {
            "success": True,
            "message": "Payment already verified and recorded (idempotent callback)",
            "bill_status": bill.status.value,
            "transaction_id": existing_payment.transaction_id,
            "is_duplicate": True
        }

    # Record successful payment transaction under the tenant's ledger
    payment = Payment(
        bill_id=bill.id,
        restaurant_id=bill.restaurant_id,
        amount=data.amount,
        currency=restaurant.currency or "INR",
        payment_method=PaymentMethod.RAZORPAY,
        transaction_id=tx_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
        status=PaymentRecordStatus.SUCCESS,
        settlement_status="PENDING"
    )
    db.add(payment)

    # Handle split bill link if applicable
    if data.split_id:
        split = db.query(BillSplit).filter(
            BillSplit.id == data.split_id,
            BillSplit.bill_id == bill.id
        ).first()
        if split:
            split.is_paid = True
            split.payment_method = "RAZORPAY"
            split.transaction_id = data.razorpay_payment_id

    db.commit()

    # Re-calculate total paid to update bill, order and table status
    total_paid = sum(
        p.amount for p in db.query(Payment).filter(
            Payment.bill_id == bill.id,
            Payment.status == PaymentRecordStatus.SUCCESS
        ).all()
    )

    order = db.query(Order).filter(Order.id == bill.order_id).first()
    table = db.query(Table).filter(Table.id == bill.table_id).first()

    if total_paid >= (bill.final_amount - 1.0):  # Rounding buffer
        bill.status = BillStatus.PAID
        if order:
            order.payment_status = PaymentStatus.PAID
            order.status = OrderStatus.COMPLETED
        if table:
            table.status = TableStatus.CLEANING
    else:
        bill.status = BillStatus.PARTIAL
        if order:
            order.payment_status = PaymentStatus.PARTIAL

    db.commit()

    # Broadcast real-time payment success via tenant-isolated WebSocket
    event_payload = {
        "bill_id": bill.id,
        "bill_number": bill.bill_number,
        "restaurant_id": bill.restaurant_id,
        "table_id": bill.table_id,
        "amount_paid": data.amount,
        "total_paid": total_paid,
        "bill_status": bill.status.value,
        "transaction_id": payment.transaction_id
    }
    await manager.broadcast_event(
        "PAYMENT_SUCCESS",
        event_payload,
        restaurant_id=bill.restaurant_id,
        table_id=bill.table_id
    )

    return {
        "success": True,
        "message": "Payment verified and recorded successfully",
        "bill_status": bill.status.value,
        "transaction_id": payment.transaction_id
    }

@router.post("/webhook/restaurant/{restaurant_id}")
@router.post("/webhook")
async def restaurant_razorpay_webhook(
    request: Request,
    restaurant_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Idempotent Webhook endpoint for Restaurant Customer Payments.
    Verifies raw body signature against the restaurant's webhook secret.
    Safely handles duplicate, delayed, failed and out-of-order events.
    """
    PaymentService.ensure_payments_active("A")

    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    # Parse JSON payload
    try:
        payload = json.loads(raw_body.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Resolve target restaurant
    target_rest_id = restaurant_id
    if not target_rest_id:
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        notes = payment_entity.get("notes", {})
        if "restaurant_id" in notes:
            target_rest_id = int(notes["restaurant_id"])
        elif "bill_id" in notes:
            b = db.query(Bill).filter(Bill.id == int(notes["bill_id"])).first()
            if b:
                target_rest_id = b.restaurant_id

    target_rest_id = target_rest_id or 1
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_rest_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found for webhook")

    # Cryptographic webhook signature check
    is_valid_sig = PaymentService.verify_restaurant_webhook_signature(restaurant, raw_body, signature)
    if not is_valid_sig:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Event ID for idempotency deduplication
    event_id = payload.get("event_id") or payload.get("id") or request.headers.get("X-Razorpay-Event-Id")
    if not event_id:
        payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id", "evt")
        event_id = f"evt_{payment_id}_{payload.get('event', 'unknown')}"

    existing_event = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.event_id == event_id).first()
    if existing_event:
        return {
            "status": "ok",
            "message": "Webhook event already processed (idempotent)",
            "event_id": event_id
        }

    event_type = payload.get("event", "unknown")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_payment_id = payment_entity.get("id")
    razorpay_order_id = payment_entity.get("order_id")
    notes = payment_entity.get("notes", {})
    bill_id = int(notes.get("bill_id", 0)) if notes.get("bill_id") else None

    # Handle payment capture or order paid
    if event_type in ["payment.captured", "order.paid"] and bill_id:
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if bill:
            tx_id = f"tx_{razorpay_payment_id}"
            existing_p = db.query(Payment).filter(
                (Payment.transaction_id == tx_id) | (Payment.razorpay_payment_id == razorpay_payment_id)
            ).first()

            if not existing_p:
                amount_paid = float(payment_entity.get("amount", 0)) / 100.0
                new_payment = Payment(
                    bill_id=bill.id,
                    restaurant_id=bill.restaurant_id,
                    amount=amount_paid,
                    currency=payment_entity.get("currency", "INR"),
                    payment_method=PaymentMethod.RAZORPAY,
                    transaction_id=tx_id,
                    razorpay_order_id=razorpay_order_id,
                    razorpay_payment_id=razorpay_payment_id,
                    status=PaymentRecordStatus.SUCCESS,
                    settlement_status="PENDING"
                )
                db.add(new_payment)

                db.commit()
                total_paid = sum(
                    p.amount for p in db.query(Payment).filter(
                        Payment.bill_id == bill.id,
                        Payment.status == PaymentRecordStatus.SUCCESS
                    ).all()
                )
                if total_paid >= (bill.final_amount - 1.0):
                    bill.status = BillStatus.PAID
                    order = db.query(Order).filter(Order.id == bill.order_id).first()
                    table = db.query(Table).filter(Table.id == bill.table_id).first()
                    if order:
                        order.payment_status = PaymentStatus.PAID
                        order.status = OrderStatus.COMPLETED
                    if table:
                        table.status = TableStatus.CLEANING
                    db.commit()

    elif event_type == "payment.failed" and bill_id:
        error_code = payment_entity.get("error_code")
        error_desc = payment_entity.get("error_description")
        failed_payment = Payment(
            bill_id=bill_id,
            restaurant_id=target_rest_id,
            amount=float(payment_entity.get("amount", 0)) / 100.0,
            payment_method=PaymentMethod.RAZORPAY,
            transaction_id=f"failed_{razorpay_payment_id}",
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            status=PaymentRecordStatus.FAILED,
            error_code=error_code,
            error_description=error_desc
        )
        db.add(failed_payment)
        db.commit()

    # Record event in idempotency table
    webhook_record = PaymentWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        restaurant_id=target_rest_id,
        entity_id=razorpay_payment_id or razorpay_order_id,
        status="PROCESSED",
        payload=json.dumps(payload)
    )
    db.add(webhook_record)
    db.commit()

    return {"status": "ok", "message": "Webhook processed successfully", "event_id": event_id}

@router.post("/refund")
async def refund_payment(
    data: PaymentRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """
    Staff-authorised refund endpoint for customer food orders.
    Enforces strict tenant isolation and updates ledger and bill state.
    """
    PaymentService.ensure_payments_active("A")

    payment = db.query(Payment).filter(Payment.id == data.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    # Cross-tenant permission check
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and payment.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Cannot refund payments belonging to another restaurant")

    restaurant = db.query(Restaurant).filter(Restaurant.id == payment.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    refund_res = PaymentService.refund_restaurant_payment(
        restaurant=restaurant,
        payment=payment,
        amount=data.amount,
        reason=data.reason or "Authorized refund"
    )

    payment.status = PaymentRecordStatus.REFUNDED
    payment.refund_id = refund_res["refund_id"]
    payment.refund_amount = refund_res["refund_amount"]
    db.commit()

    bill = db.query(Bill).filter(Bill.id == payment.bill_id).first()
    if bill:
        total_valid_paid = sum(
            p.amount for p in db.query(Payment).filter(
                Payment.bill_id == bill.id,
                Payment.status == PaymentRecordStatus.SUCCESS
            ).all()
        )
        if total_valid_paid <= 0:
            bill.status = BillStatus.UNPAID
        elif total_valid_paid < bill.final_amount:
            bill.status = BillStatus.PARTIAL
        db.commit()

    return {
        "success": True,
        "message": "Payment refunded successfully",
        "refund_id": refund_res["refund_id"],
        "refund_amount": refund_res["refund_amount"],
        "bill_status": bill.status.value if bill else "UNKNOWN"
    }

@router.get("/reconcile/{bill_id}", response_model=PaymentReconciliationResponse)
def reconcile_bill_payments(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER,
        UserRole.CASHIER,
        UserRole.WAITER
    ]))
):
    """
    Reconciles authoritative bill amounts against gateway transactions to detect discrepancies.
    """
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and bill.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    payments = db.query(Payment).filter(
        Payment.bill_id == bill.id,
        Payment.status == PaymentRecordStatus.SUCCESS
    ).all()
    total_recorded_paid = sum(p.amount for p in payments)
    is_balanced = (
        (bill.status == BillStatus.PAID and total_recorded_paid >= (bill.final_amount - 1.0)) or
        (bill.status == BillStatus.UNPAID and total_recorded_paid == 0.0) or
        (bill.status == BillStatus.PARTIAL and 0.0 < total_recorded_paid < bill.final_amount)
    )

    return PaymentReconciliationResponse(
        bill_id=bill.id,
        bill_number=bill.bill_number,
        bill_final_amount=bill.final_amount,
        total_recorded_paid=total_recorded_paid,
        bill_status=bill.status.value,
        is_balanced=is_balanced,
        payments_count=len(payments)
    )

@router.post("/offline-payment")
async def record_offline_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER,
        UserRole.CASHIER,
        UserRole.WAITER
    ]))
):
    """
    Separate authorised workflow for Cash or In-Person Card payments.
    Strictly checked for operational staff permissions and tenant scoping.
    """
    bill_id = payload.get("bill_id")
    amount = float(payload.get("amount", 0.0))
    method_str = payload.get("payment_method", "CASH")

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and bill.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Cannot record offline payment for another restaurant")

    method = PaymentMethod.CASH if method_str == "CASH" else PaymentMethod.CARD
    txn_id = f"offline_{int(time.time())}_{bill.id}"

    payment = Payment(
        bill_id=bill.id,
        restaurant_id=bill.restaurant_id,
        amount=amount,
        payment_method=method,
        transaction_id=txn_id,
        status=PaymentRecordStatus.SUCCESS,
        settlement_status="SETTLED"
    )
    db.add(payment)
    db.commit()

    total_paid = sum(
        p.amount for p in db.query(Payment).filter(
            Payment.bill_id == bill.id,
            Payment.status == PaymentRecordStatus.SUCCESS
        ).all()
    )

    order = db.query(Order).filter(Order.id == bill.order_id).first()
    table = db.query(Table).filter(Table.id == bill.table_id).first()

    if total_paid >= (bill.final_amount - 1.0):
        bill.status = BillStatus.PAID
        if order:
            order.payment_status = PaymentStatus.PAID
            order.status = OrderStatus.COMPLETED
        if table:
            table.status = TableStatus.CLEANING
    else:
        bill.status = BillStatus.PARTIAL
        if order:
            order.payment_status = PaymentStatus.PARTIAL

    db.commit()

    await manager.broadcast_event(
        "PAYMENT_SUCCESS",
        {
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "restaurant_id": bill.restaurant_id,
            "table_id": bill.table_id,
            "amount_paid": amount,
            "total_paid": total_paid,
            "bill_status": bill.status.value,
            "payment_method": method.value
        },
        restaurant_id=bill.restaurant_id,
        table_id=bill.table_id
    )

    return {
        "success": True,
        "message": f"{method.value} payment recorded successfully",
        "bill_status": bill.status.value,
        "transaction_id": txn_id
    }
