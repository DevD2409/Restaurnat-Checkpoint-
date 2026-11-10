import json
import time
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles, get_active_tenant
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.subscription import (
    SubscriptionPlan, SubscriptionCoupon, SubscriptionInvoice,
    SubscriptionPayment, SubscriptionWebhookEvent
)
from app.schemas.subscription import (
    SubscriptionPlanResponse, CouponValidateRequest, CouponValidateResponse,
    SubscriptionCheckoutRequest, SubscriptionCheckoutResponse,
    SubscriptionVerifyRequest, SubscriptionInvoiceResponse, SubscriptionRefundRequest
)
from app.services.payment_service import PaymentService
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/subscriptions", tags=["Flow B: SRMP SaaS Subscription Payments"])

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Public catalog of available SRMP SaaS subscription tiers."""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    return plans

@router.post("/coupons/validate", response_model=CouponValidateResponse)
def validate_coupon(data: CouponValidateRequest, db: Session = Depends(get_db)):
    """Validates coupon code eligibility for a specific subscription plan."""
    code_clean = data.code.strip().upper()
    coupon = db.query(SubscriptionCoupon).filter(
        SubscriptionCoupon.code == code_clean,
        SubscriptionCoupon.is_active == True
    ).first()

    if not coupon:
        return CouponValidateResponse(
            is_valid=False,
            code=data.code,
            message="Invalid or expired promo code"
        )

    if coupon.valid_until and coupon.valid_until < datetime.now():
        return CouponValidateResponse(
            is_valid=False,
            code=data.code,
            message="This promo code has expired"
        )

    if coupon.times_used >= coupon.max_uses:
        return CouponValidateResponse(
            is_valid=False,
            code=data.code,
            message="Promo code usage limit has been reached"
        )

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == data.plan_code).first()
    discount_val = 0.0
    if plan:
        if coupon.discount_percentage > 0:
            discount_val = round(plan.price * (coupon.discount_percentage / 100.0), 2)
        elif coupon.discount_amount > 0:
            discount_val = min(plan.price, coupon.discount_amount)

    return CouponValidateResponse(
        is_valid=True,
        code=coupon.code,
        discount_percentage=coupon.discount_percentage,
        discount_amount=discount_val,
        message=f"Promo code applied successfully! Saved ₹{discount_val:.2f}"
    )

@router.post("/checkout", response_model=SubscriptionCheckoutResponse)
def create_subscription_checkout(
    data: SubscriptionCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN
    ]))
):
    """
    Creates an authoritative SaaS subscription invoice and Razorpay order
    strictly under the SRMP Platform's verified merchant gateway account.
    """
    target_rest_id = data.restaurant_id
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        target_rest_id = current_user.restaurant_id

    if not target_rest_id:
        raise HTTPException(status_code=400, detail="Restaurant ID must be specified")

    restaurant = db.query(Restaurant).filter(Restaurant.id == target_rest_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_code == data.plan_code,
        SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Subscription plan '{data.plan_code}' not found")

    # Authoritative calculation
    subtotal = plan.price
    if data.billing_cycle == "ANNUAL":
        subtotal = round(plan.price * 10.0, 2)  # 2 months free for annual billing

    discount_amount = 0.0
    coupon_id = None
    if data.coupon_code:
        coupon = db.query(SubscriptionCoupon).filter(
            SubscriptionCoupon.code == data.coupon_code.strip().upper(),
            SubscriptionCoupon.is_active == True
        ).first()
        if coupon and (not coupon.valid_until or coupon.valid_until >= datetime.now()) and coupon.times_used < coupon.max_uses:
            coupon_id = coupon.id
            if coupon.discount_percentage > 0:
                discount_amount = round(subtotal * (coupon.discount_percentage / 100.0), 2)
            elif coupon.discount_amount > 0:
                discount_amount = min(subtotal, coupon.discount_amount)

    taxable_amount = max(0.0, subtotal - discount_amount)
    tax_percentage = 18.0  # 18% GST for Cloud Software Services
    tax_amount = round(taxable_amount * (tax_percentage / 100.0), 2)
    final_amount = round(taxable_amount + tax_amount, 2)

    # Generate unique invoice number: SRMP-INV-YYYYMM-XXXX
    timestamp_str = datetime.now().strftime("%Y%m")
    inv_count = db.query(SubscriptionInvoice).count() + 1
    invoice_number = f"SRMP-INV-{timestamp_str}-{target_rest_id:02d}{inv_count:04d}"

    invoice = SubscriptionInvoice(
        invoice_number=invoice_number,
        restaurant_id=target_rest_id,
        plan_id=plan.id,
        billing_cycle=data.billing_cycle,
        subtotal=subtotal,
        discount_amount=discount_amount,
        coupon_id=coupon_id,
        tax_percentage=tax_percentage,
        tax_amount=tax_amount,
        final_amount=final_amount,
        currency="INR",
        status="UNPAID"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Create Gateway Order strictly on Platform Merchant Account
    order_data = PaymentService.create_subscription_order(invoice)

    return SubscriptionCheckoutResponse(
        razorpay_order_id=order_data["razorpay_order_id"],
        amount=order_data["amount"],
        amount_paise=order_data["amount_paise"],
        currency=order_data["currency"],
        key_id=order_data["key_id"],
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        subtotal=subtotal,
        discount_amount=discount_amount,
        tax_amount=tax_amount,
        final_amount=final_amount
    )

@router.post("/verify")
def verify_subscription_payment(
    data: SubscriptionVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Cryptographically verifies SaaS subscription payment signature against
    the Platform Key Secret. Updates ledger, activates restaurant subscription.
    """
    invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Subscription invoice not found")

    restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == invoice.plan_id).first()

    # Signature verification strictly against Platform Secret
    is_valid = PaymentService.verify_platform_payment_signature(
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid platform subscription payment signature"
        )

    # Idempotent deduplication
    existing_p = db.query(SubscriptionPayment).filter(
        SubscriptionPayment.razorpay_payment_id == data.razorpay_payment_id
    ).first()
    if existing_p:
        return {
            "success": True,
            "message": "Subscription payment already processed (idempotent)",
            "invoice_number": invoice.invoice_number,
            "subscription_status": restaurant.subscription_status
        }

    # Record platform payment in SaaS subscription ledger
    payment = SubscriptionPayment(
        invoice_id=invoice.id,
        restaurant_id=invoice.restaurant_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
        amount=invoice.final_amount,
        currency=invoice.currency,
        payment_method="RAZORPAY",
        status="SUCCESS"
    )
    db.add(payment)

    # Update invoice lifecycle
    now = datetime.now()
    duration_days = 365 if invoice.billing_cycle == "ANNUAL" else 30
    invoice.status = "PAID"
    invoice.paid_at = now
    invoice.billing_start_date = now
    invoice.billing_end_date = now + timedelta(days=duration_days)

    # Activate restaurant subscription
    restaurant.subscription_plan = plan.plan_code if plan else "PRO"
    restaurant.subscription_status = "ACTIVE"
    restaurant.subscription_expires_at = invoice.billing_end_date

    # Increment coupon counter if used
    if invoice.coupon_id:
        coupon = db.query(SubscriptionCoupon).filter(SubscriptionCoupon.id == invoice.coupon_id).first()
        if coupon:
            coupon.times_used += 1

    db.commit()

    return {
        "success": True,
        "message": f"Successfully activated {restaurant.name} on {restaurant.subscription_plan} plan",
        "invoice_number": invoice.invoice_number,
        "subscription_status": restaurant.subscription_status,
        "expires_at": restaurant.subscription_expires_at.isoformat() if restaurant.subscription_expires_at else None
    }

@router.post("/webhook")
async def platform_subscription_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Dedicated signed webhook endpoint for SaaS Platform Subscriptions.
    Processes renewal, failed charges, and cancellations with raw body HMAC SHA256 check.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature header")

    is_valid_sig = PaymentService.verify_platform_webhook_signature(raw_body, signature)
    if not is_valid_sig:
        raise HTTPException(status_code=400, detail="Invalid platform webhook signature")

    try:
        payload = json.loads(raw_body.decode())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("event_id") or payload.get("id") or request.headers.get("X-Razorpay-Event-Id")
    if not event_id:
        event_id = f"evt_saas_{int(time.time())}"

    # Idempotency check
    existing_evt = db.query(SubscriptionWebhookEvent).filter(SubscriptionWebhookEvent.event_id == event_id).first()
    if existing_evt:
        return {"status": "ok", "message": "Subscription event already processed (idempotent)", "event_id": event_id}

    event_type = payload.get("event", "unknown")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    notes = payment_entity.get("notes", {})
    invoice_id = int(notes.get("invoice_id", 0)) if notes.get("invoice_id") else None

    if event_type in ["payment.captured", "order.paid"] and invoice_id:
        invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == invoice_id).first()
        if invoice and invoice.status != "PAID":
            invoice.status = "PAID"
            invoice.paid_at = datetime.now()
            restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
            if restaurant:
                restaurant.subscription_status = "ACTIVE"
            db.commit()

    elif event_type == "payment.failed" and invoice_id:
        invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == invoice_id).first()
        if invoice:
            invoice.status = "VOID"
            db.commit()

    webhook_record = SubscriptionWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        invoice_id=invoice_id,
        status="PROCESSED",
        payload=json.dumps(payload)
    )
    db.add(webhook_record)
    db.commit()

    return {"status": "ok", "message": "Platform subscription webhook processed", "event_id": event_id}

@router.get("/invoices", response_model=List[SubscriptionInvoiceResponse])
def get_subscription_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN
    ]))
):
    """Retrieves subscription billing ledger and invoices."""
    query = db.query(SubscriptionInvoice)
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        query = query.filter(SubscriptionInvoice.restaurant_id == current_user.restaurant_id)

    invoices = query.order_by(SubscriptionInvoice.created_at.desc()).all()
    # Enrich plan name
    for inv in invoices:
        if inv.plan:
            inv.plan_name = inv.plan.name
    return invoices

@router.post("/refund")
def refund_subscription(
    data: SubscriptionRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Super Admin privileged endpoint to issue refunds for SaaS subscriptions."""
    payment = db.query(SubscriptionPayment).filter(SubscriptionPayment.id == data.payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Subscription payment not found")

    refund_res = PaymentService.refund_subscription_payment(
        payment=payment,
        amount=data.amount,
        reason=data.reason or "Subscription cancellation refund"
    )

    payment.status = "REFUNDED"
    payment.refund_id = refund_res["refund_id"]
    payment.refund_amount = refund_res["refund_amount"]
    payment.refunded_at = datetime.now()

    invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == payment.invoice_id).first()
    if invoice:
        invoice.status = "REFUNDED"

    restaurant = db.query(Restaurant).filter(Restaurant.id == payment.restaurant_id).first()
    if restaurant:
        restaurant.subscription_status = "SUSPENDED"

    db.commit()

    return {
        "success": True,
        "message": "Subscription payment refunded successfully",
        "refund_id": refund_res["refund_id"],
        "refund_amount": refund_res["refund_amount"]
    }

