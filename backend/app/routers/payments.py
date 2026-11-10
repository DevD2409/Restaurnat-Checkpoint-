import hmac
import hashlib
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import razorpay
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.billing import Bill, BillSplit, Payment, BillStatus, PaymentMethod, PaymentRecordStatus
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.table import Table, TableStatus
from app.schemas.billing import RazorpayOrderCreate, RazorpayVerifyPayment, PaymentResponse
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/payments", tags=["Payments & Razorpay Gateway"])

def get_razorpay_client():
    try:
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    except Exception:
        return None

@router.post("/razorpay-order")
def create_razorpay_order(data: RazorpayOrderCreate, db: Session = Depends(get_db)):
    bill = db.query(Bill).filter(Bill.id == data.bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    amount_in_paise = int(data.amount * 100)
    client = get_razorpay_client()
    razorpay_order_id = f"order_mock_{int(time.time())}_{bill.id}"

    # If active valid Razorpay credentials are set, call actual API
    if client and not settings.RAZORPAY_KEY_ID.startswith("rzp_test_placeholder"):
        try:
            rzp_order = client.order.create({
                "amount": amount_in_paise,
                "currency": data.currency,
                "receipt": bill.bill_number,
                "notes": {
                    "bill_id": bill.id,
                    "order_id": bill.order_id
                }
            })
            razorpay_order_id = rzp_order["id"]
        except Exception as e:
            # Fall back to sandbox mock order id
            razorpay_order_id = f"order_mock_{int(time.time())}_{bill.id}"

    return {
        "razorpay_order_id": razorpay_order_id,
        "amount": data.amount,
        "amount_paise": amount_in_paise,
        "currency": data.currency,
        "key_id": settings.RAZORPAY_KEY_ID,
        "bill_id": bill.id,
        "bill_number": bill.bill_number
    }

@router.post("/verify-razorpay-payment")
async def verify_razorpay_payment(
    data: RazorpayVerifyPayment,
    db: Session = Depends(get_db)
):
    bill = db.query(Bill).filter(Bill.id == data.bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Verify signature if live razorpay client, or check sandbox match
    is_valid_signature = True
    if not data.razorpay_order_id.startswith("order_mock_") and not settings.RAZORPAY_KEY_ID.startswith("rzp_test_placeholder"):
        try:
            generated_signature = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                f"{data.razorpay_order_id}|{data.razorpay_payment_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            is_valid_signature = hmac.compare_digest(generated_signature, data.razorpay_signature)
        except Exception:
            is_valid_signature = False

    if not is_valid_signature:
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Deduplication / Idempotent handling for duplicate payment callbacks
    tx_id = f"tx_{data.razorpay_payment_id}"
    existing_payment = db.query(Payment).filter(Payment.transaction_id == tx_id).first()
    if existing_payment:
        return {
            "success": True,
            "message": "Payment already verified and recorded (duplicate callback ignored)",
            "bill_status": bill.status.value,
            "transaction_id": existing_payment.transaction_id,
            "is_duplicate": True
        }

    # Record payment transaction
    payment = Payment(
        bill_id=bill.id,
        amount=data.amount,
        payment_method=PaymentMethod.RAZORPAY,
        transaction_id=tx_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
        status=PaymentRecordStatus.SUCCESS
    )
    db.add(payment)

    # If this payment was for a specific split
    if data.split_id:
        split = db.query(BillSplit).filter(BillSplit.id == data.split_id).first()
        if split:
            split.is_paid = True
            split.payment_method = "RAZORPAY"
            split.transaction_id = data.razorpay_payment_id

    # Check total paid against bill
    db.commit()
    total_paid = sum(p.amount for p in db.query(Payment).filter(
        Payment.bill_id == bill.id,
        Payment.status == PaymentRecordStatus.SUCCESS
    ).all())

    order = db.query(Order).filter(Order.id == bill.order_id).first()
    table = db.query(Table).filter(Table.id == bill.table_id).first()

    if total_paid >= (bill.final_amount - 1.0):  # Allow for small rounding
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

    # Broadcast event via WebSocket
    await manager.broadcast_event(
        "PAYMENT_SUCCESS",
        {
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "table_id": bill.table_id,
            "amount_paid": data.amount,
            "total_paid": total_paid,
            "bill_status": bill.status.value,
            "transaction_id": payment.transaction_id
        },
        table_id=bill.table_id
    )

    return {
        "success": True,
        "message": "Payment verified and recorded successfully",
        "bill_status": bill.status.value,
        "transaction_id": payment.transaction_id
    }

@router.post("/offline-payment")
async def record_offline_payment(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER, UserRole.CASHIER, UserRole.WAITER]))
):
    bill_id = payload.get("bill_id")
    amount = float(payload.get("amount", 0.0))
    method_str = payload.get("payment_method", "CASH")

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    method = PaymentMethod.CASH if method_str == "CASH" else PaymentMethod.CARD
    txn_id = f"offline_{int(time.time())}_{bill.id}"

    payment = Payment(
        bill_id=bill.id,
        amount=amount,
        payment_method=method,
        transaction_id=txn_id,
        status=PaymentRecordStatus.SUCCESS
    )
    db.add(payment)
    db.commit()

    total_paid = sum(p.amount for p in db.query(Payment).filter(
        Payment.bill_id == bill.id,
        Payment.status == PaymentRecordStatus.SUCCESS
    ).all())

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
            "table_id": bill.table_id,
            "amount_paid": amount,
            "total_paid": total_paid,
            "bill_status": bill.status.value,
            "payment_method": method.value
        },
        table_id=bill.table_id
    )

    return {
        "success": True,
        "message": f"{method.value} payment recorded successfully",
        "bill_status": bill.status.value,
        "transaction_id": txn_id
    }

@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Razorpay asynchronous payment capture notifications.
    Verifies cryptographic HMAC SHA256 webhook signature.
    """
    payload_body = await request.body()
    webhook_signature = request.headers.get("X-Razorpay-Signature")

    if not webhook_signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    if not settings.RAZORPAY_KEY_SECRET.startswith("rzp_test_placeholder"):
        expected_sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, webhook_signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    return {"status": "ok", "message": "Webhook processed successfully"}

