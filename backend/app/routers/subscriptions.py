import json
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.subscription import (
    SubscriptionPlan, SubscriptionCoupon, SubscriptionCouponRedemption,
    SubscriptionInvoice, SubscriptionPayment, SubscriptionWebhookEvent,
    SubscriptionNotification
)
from app.schemas.subscription import (
    SubscriptionPlanResponse, SubscriptionPlanCreate,
    SubscriptionCouponCreate, SubscriptionCouponResponse,
    CouponValidateRequest, CouponValidateResponse,
    SubscriptionCheckoutPreviewRequest, SubscriptionCheckoutPreviewResponse,
    SubscriptionCheckoutRequest, SubscriptionCheckoutResponse,
    SubscriptionVerifyRequest, SubscriptionInvoiceResponse,
    SubscriptionRefundRequest, SubscriptionNotificationResponse,
    RestaurantSubscriptionStatusResponse, PlatformSubscriptionAnalyticsResponse
)
from app.services.payment_service import PaymentService
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/subscriptions", tags=["Flow B: SRMP SaaS Subscription & Coupon Management"])

# Helper: Parse coupon plan eligibility
def is_plan_eligible_for_coupon(coupon: SubscriptionCoupon, plan_code: str) -> bool:
    if not coupon.eligible_plan_codes or coupon.eligible_plan_codes.strip() in ["*", "ALL"]:
        return True
    eligible_list = [p.strip().upper() for p in coupon.eligible_plan_codes.split(",")]
    return plan_code.strip().upper() in eligible_list

# Helper: Validate coupon core logic
def validate_coupon_logic(
    db: Session,
    coupon_code: str,
    plan_code: str,
    restaurant_id: Optional[int] = None
) -> Tuple[bool, Optional[SubscriptionCoupon], str]:
    from typing import Tuple
    clean_code = coupon_code.strip().upper()
    coupon = db.query(SubscriptionCoupon).filter(SubscriptionCoupon.code == clean_code).first()
    if not coupon:
        return False, None, f"Coupon code '{clean_code}' does not exist"

    if not coupon.is_active:
        return False, coupon, f"Coupon code '{clean_code}' is currently inactive"

    now = datetime.now()
    if coupon.start_date and now < coupon.start_date:
        return False, coupon, f"Coupon code '{clean_code}' is not active yet"

    if coupon.end_date and now > coupon.end_date:
        return False, coupon, f"Coupon code '{clean_code}' has expired"

    if not is_plan_eligible_for_coupon(coupon, plan_code):
        return False, coupon, f"Coupon '{clean_code}' is not eligible for the {plan_code} plan. Eligible plans: {coupon.eligible_plan_codes}"

    if coupon.max_uses_global and coupon.times_used >= coupon.max_uses_global:
        return False, coupon, f"Coupon '{clean_code}' global redemption limit has been reached"

    if restaurant_id and coupon.max_uses_per_restaurant:
        prior_uses = db.query(SubscriptionCouponRedemption).filter(
            SubscriptionCouponRedemption.coupon_id == coupon.id,
            SubscriptionCouponRedemption.restaurant_id == restaurant_id
        ).count()
        if prior_uses >= coupon.max_uses_per_restaurant:
            return False, coupon, f"Coupon '{clean_code}' has already been redeemed by this restaurant"

    return True, coupon, "Coupon is valid"

# =============================================================================
# PUBLIC & RESTAURANT OWNER SUBSCRIPTION APIS
# =============================================================================

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Public catalog of available subscription tiers with pricing and feature entitlements."""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.price_paise.asc()).all()
    results = []
    for p in plans:
        results.append(SubscriptionPlanResponse(
            id=p.id,
            plan_code=p.plan_code,
            name=p.name,
            billing_cycle=p.billing_cycle,
            price_paise=p.price_paise,
            price_inr=p.price_inr,
            duration_days=p.duration_days,
            features=p.features,
            entitlements=p.get_entitlements(),
            max_tables=p.max_tables,
            is_active=p.is_active
        ))
    return results

@router.post("/coupons/validate", response_model=CouponValidateResponse)
def validate_coupon_endpoint(data: CouponValidateRequest, db: Session = Depends(get_db)):
    """
    Validates a coupon code against plan eligibility, date validity,
    global usage limits, and per-restaurant usage limits.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_code == data.plan_code.strip().upper(),
        SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        return CouponValidateResponse(
            is_valid=False,
            code=data.code,
            message=f"Plan '{data.plan_code}' not found"
        )

    is_valid, coupon, message = validate_coupon_logic(db, data.code, plan.plan_code, data.restaurant_id)
    if not is_valid or not coupon:
        return CouponValidateResponse(
            is_valid=False,
            code=data.code,
            message=message
        )

    # Calculate discount strictly in integer paise
    if coupon.discount_type == "PERCENTAGE" and coupon.discount_percentage > 0:
        discount_paise = int(round(plan.price_paise * (coupon.discount_percentage / 100.0)))
    else:
        discount_paise = min(plan.price_paise, coupon.discount_paise)

    final_paise = max(0, plan.price_paise - discount_paise)

    return CouponValidateResponse(
        is_valid=True,
        code=coupon.code,
        discount_paise=discount_paise,
        discount_inr=round(discount_paise / 100.0, 2),
        discount_percentage=coupon.discount_percentage if coupon.discount_type == "PERCENTAGE" else 0.0,
        discount_amount=round(discount_paise / 100.0, 2),
        final_amount_paise=final_paise,
        final_amount_inr=round(final_paise / 100.0, 2),
        message=f"Coupon '{coupon.code}' applied successfully! Saved ₹{discount_paise / 100.0:.2f}"
    )

@router.post("/checkout/preview", response_model=SubscriptionCheckoutPreviewResponse)
def preview_subscription_checkout(
    data: SubscriptionCheckoutPreviewRequest,
    db: Session = Depends(get_db)
):
    """
    Pre-checkout inspection showing original amount, discount, tax (18%),
    final payable amount in integer paise, and billing period before payment creation.
    """
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.plan_code == data.plan_code.strip().upper(),
        SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    subtotal_paise = plan.price_paise
    discount_paise = 0
    coupon_applied = None

    if data.coupon_code:
        is_valid, coupon, msg = validate_coupon_logic(db, data.coupon_code, plan.plan_code, data.restaurant_id)
        if not is_valid:
            raise HTTPException(status_code=400, detail=msg)
        coupon_applied = coupon.code
        if coupon.discount_type == "PERCENTAGE" and coupon.discount_percentage > 0:
            discount_paise = int(round(subtotal_paise * (coupon.discount_percentage / 100.0)))
        else:
            discount_paise = min(subtotal_paise, coupon.discount_paise)

    taxable_paise = max(0, subtotal_paise - discount_paise)
    tax_paise = int(round(taxable_paise * 0.18))  # 18% GST in integer paise
    final_amount_paise = taxable_paise + tax_paise

    now = datetime.now()
    end_date = now + timedelta(days=plan.duration_days)

    return SubscriptionCheckoutPreviewResponse(
        plan_code=plan.plan_code,
        name=plan.name,
        billing_cycle=plan.billing_cycle,
        duration_days=plan.duration_days,
        subtotal_paise=subtotal_paise,
        subtotal_inr=round(subtotal_paise / 100.0, 2),
        discount_paise=discount_paise,
        discount_inr=round(discount_paise / 100.0, 2),
        tax_paise=tax_paise,
        tax_inr=round(tax_paise / 100.0, 2),
        final_amount_paise=final_amount_paise,
        final_amount_inr=round(final_amount_paise / 100.0, 2),
        coupon_code=coupon_applied,
        billing_start_date=now.strftime("%d %b %Y"),
        billing_end_date=end_date.strftime("%d %b %Y")
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
    strictly in integer paise under the Platform merchant account.
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
        SubscriptionPlan.plan_code == data.plan_code.strip().upper(),
        SubscriptionPlan.is_active == True
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Subscription plan '{data.plan_code}' not found")

    # Authoritative calculation strictly in integer paise
    subtotal_paise = plan.price_paise
    discount_paise = 0
    coupon_id = None

    if data.coupon_code:
        is_valid, coupon, msg = validate_coupon_logic(db, data.coupon_code, plan.plan_code, target_rest_id)
        if not is_valid:
            raise HTTPException(status_code=400, detail=msg)
        coupon_id = coupon.id
        if coupon.discount_type == "PERCENTAGE" and coupon.discount_percentage > 0:
            discount_paise = int(round(subtotal_paise * (coupon.discount_percentage / 100.0)))
        else:
            discount_paise = min(subtotal_paise, coupon.discount_paise)

    taxable_paise = max(0, subtotal_paise - discount_paise)
    tax_paise = int(round(taxable_paise * 0.18))  # 18% GST
    final_amount_paise = taxable_paise + tax_paise

    # Generate invoice identifier
    timestamp_str = datetime.now().strftime("%Y%m")
    inv_count = db.query(SubscriptionInvoice).count() + 1
    invoice_number = f"SRMP-INV-{timestamp_str}-{target_rest_id:02d}{inv_count:04d}"

    invoice = SubscriptionInvoice(
        invoice_number=invoice_number,
        restaurant_id=target_rest_id,
        plan_id=plan.id,
        billing_cycle=plan.billing_cycle,
        subtotal_paise=subtotal_paise,
        discount_paise=discount_paise,
        tax_percentage=18.0,
        tax_paise=tax_paise,
        final_amount_paise=final_amount_paise,
        currency="INR",
        status="UNPAID",
        coupon_id=coupon_id
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Create Gateway Order strictly on Platform Merchant Account
    order_data = PaymentService.create_subscription_order(invoice)

    return SubscriptionCheckoutResponse(
        razorpay_order_id=order_data["razorpay_order_id"],
        amount_paise=order_data["amount_paise"],
        final_amount_paise=invoice.final_amount_paise,
        final_amount_inr=invoice.final_amount_inr,
        currency=order_data["currency"],
        key_id=order_data["key_id"],
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        subtotal_paise=invoice.subtotal_paise,
        discount_paise=invoice.discount_paise,
        tax_paise=invoice.tax_paise,
        subtotal_inr=invoice.subtotal_inr,
        discount_inr=invoice.discount_inr,
        tax_inr=invoice.tax_inr,
        final_amount=invoice.final_amount_inr
    )

@router.post("/verify")
def verify_subscription_payment(
    data: SubscriptionVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Cryptographically verifies subscription payment signature against Platform Key Secret.
    Activates or renews the subscription, creates receipt, records coupon redemption,
    and dispatches a renewal notification.
    """
    invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == data.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Subscription invoice not found")

    restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == invoice.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")

    # Cryptographic signature verification
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

    # Idempotent deduplication check
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

    # Record payment transaction in integer paise
    payment = SubscriptionPayment(
        invoice_id=invoice.id,
        restaurant_id=invoice.restaurant_id,
        razorpay_order_id=data.razorpay_order_id,
        razorpay_payment_id=data.razorpay_payment_id,
        razorpay_signature=data.razorpay_signature,
        amount_paise=invoice.final_amount_paise,
        currency=invoice.currency,
        payment_method="RAZORPAY",
        status="SUCCESS"
    )
    db.add(payment)

    # Compute renewal and expiration: extend from existing expiry if currently active, else from now
    now = datetime.now()
    base_date = now
    if restaurant.subscription_expires_at and restaurant.subscription_expires_at > now:
        base_date = restaurant.subscription_expires_at

    duration_days = plan.duration_days or 30
    invoice.status = "PAID"
    invoice.paid_at = now
    invoice.billing_start_date = base_date
    invoice.billing_end_date = base_date + timedelta(days=duration_days)

    # Activate/Renew restaurant subscription
    restaurant.subscription_plan = plan.plan_code
    restaurant.subscription_status = "ACTIVE"
    restaurant.subscription_expires_at = invoice.billing_end_date

    # Record coupon redemption if a coupon was used
    if invoice.coupon_id:
        coupon = db.query(SubscriptionCoupon).filter(SubscriptionCoupon.id == invoice.coupon_id).first()
        if coupon:
            coupon.times_used += 1
            redemption = SubscriptionCouponRedemption(
                coupon_id=coupon.id,
                restaurant_id=restaurant.id,
                invoice_id=invoice.id
            )
            db.add(redemption)

    # Generate renewal notification
    expiry_fmt = invoice.billing_end_date.strftime("%d %b %Y")
    notif = SubscriptionNotification(
        restaurant_id=restaurant.id,
        notification_type="RENEWAL_SUCCESS",
        title="Subscription Successfully Activated!",
        message=f"Your subscription to the {plan.name} is now ACTIVE until {expiry_fmt}. Receipt #{invoice.invoice_number} generated."
    )
    db.add(notif)

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
    Idempotent processing of renewals, charge failures, and cancellations.
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

    # Idempotency deduplication check
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
            # Create payment failure notification
            fail_notif = SubscriptionNotification(
                restaurant_id=invoice.restaurant_id,
                notification_type="PAYMENT_FAILED",
                title="Subscription Payment Failed",
                message=f"Payment for invoice #{invoice.invoice_number} failed. Please update your payment method to avoid suspension."
            )
            db.add(fail_notif)
            db.commit()

    elif event_type == "subscription.cancelled" and invoice_id:
        invoice = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == invoice_id).first()
        if invoice:
            restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
            if restaurant:
                restaurant.subscription_status = "CANCELLED"
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

@router.get("/my-status", response_model=RestaurantSubscriptionStatusResponse)
def get_my_subscription_status(
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
    Returns current subscription status, live evaluation (considering expiry and grace period),
    days remaining, and feature entitlements.
    """
    target_rest_id = current_user.restaurant_id or 1
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_rest_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    live_status = restaurant.evaluate_subscription_status()
    now = datetime.now()

    days_remaining = 0
    is_in_grace_period = (live_status == "PAST_DUE")

    if restaurant.subscription_expires_at:
        delta = restaurant.subscription_expires_at - now
        days_remaining = max(0, delta.days)

    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == restaurant.subscription_plan).first()
    entitlements = plan.get_entitlements() if plan else {
        "max_tables": 30,
        "kds_access": True,
        "advanced_analytics": True,
        "custom_branding": True
    }

    return RestaurantSubscriptionStatusResponse(
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
        subscription_plan=restaurant.subscription_plan or "MONTHLY",
        subscription_status=live_status,
        subscription_expires_at=restaurant.subscription_expires_at,
        grace_period_days=restaurant.grace_period_days or 7,
        days_remaining=days_remaining,
        is_in_grace_period=is_in_grace_period,
        entitlements=entitlements
    )

@router.get("/invoices", response_model=List[SubscriptionInvoiceResponse])
def get_subscription_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN
    ]))
):
    """Retrieves tenant subscription billing ledger, invoices and payment receipts."""
    query = db.query(SubscriptionInvoice)
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        query = query.filter(SubscriptionInvoice.restaurant_id == current_user.restaurant_id)

    invoices = query.order_by(SubscriptionInvoice.created_at.desc()).all()
    results = []
    for inv in invoices:
        plan_name = inv.plan.name if inv.plan else None
        payments_data = []
        for p in inv.payments:
            payments_data.append({
                "id": p.id,
                "invoice_id": p.invoice_id,
                "razorpay_payment_id": p.razorpay_payment_id,
                "amount_paise": p.amount_paise,
                "amount_inr": p.amount_inr,
                "currency": p.currency,
                "payment_method": p.payment_method,
                "status": p.status,
                "created_at": p.created_at
            })
        results.append(SubscriptionInvoiceResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            restaurant_id=inv.restaurant_id,
            plan_id=inv.plan_id,
            plan_name=plan_name,
            billing_cycle=inv.billing_cycle,
            subtotal_paise=inv.subtotal_paise,
            subtotal_inr=inv.subtotal_inr,
            discount_paise=inv.discount_paise,
            discount_inr=inv.discount_inr,
            tax_paise=inv.tax_paise,
            tax_inr=inv.tax_inr,
            final_amount_paise=inv.final_amount_paise,
            final_amount_inr=inv.final_amount_inr,
            currency=inv.currency,
            status=inv.status,
            billing_start_date=inv.billing_start_date,
            billing_end_date=inv.billing_end_date,
            paid_at=inv.paid_at,
            created_at=inv.created_at,
            payments=payments_data
        ))
    return results

@router.get("/notifications", response_model=List[SubscriptionNotificationResponse])
def get_subscription_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """Returns renewal and expiration notifications for the restaurant tenant."""
    target_rest_id = current_user.restaurant_id or 1
    notifications = db.query(SubscriptionNotification).filter(
        SubscriptionNotification.restaurant_id == target_rest_id
    ).order_by(SubscriptionNotification.created_at.desc()).all()
    return notifications

# =============================================================================
# PLATFORM SUPER-ADMIN SUBSCRIPTION & COUPON MANAGEMENT APIS
# =============================================================================

@router.get("/admin/analytics", response_model=PlatformSubscriptionAnalyticsResponse)
def get_platform_subscription_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """
    Super-Admin SaaS Metrics: MRR, ARR, active tenants, churn, and coupon usage.
    """
    restaurants = db.query(Restaurant).all()
    active_tenants = 0
    trial_tenants = 0
    past_due_tenants = 0
    expired_tenants = 0
    churn_count = 0

    mrr_paise = 0

    for r in restaurants:
        status = r.evaluate_subscription_status()
        if status == "ACTIVE":
            active_tenants += 1
            # Add to MRR based on active plan
            if r.subscription_plan == "MONTHLY":
                mrr_paise += 199900
            elif r.subscription_plan == "YEARLY":
                mrr_paise += int(round(1199900 / 12.0))
        elif status == "TRIAL":
            trial_tenants += 1
        elif status == "PAST_DUE":
            past_due_tenants += 1
        elif status == "EXPIRED":
            expired_tenants += 1
            churn_count += 1
        elif status in ["CANCELLED", "SUSPENDED"]:
            churn_count += 1

    arr_paise = mrr_paise * 12

    # Coupon redemptions analytics
    total_coupons_redeemed = db.query(SubscriptionCouponRedemption).count()
    all_paid_invoices = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.status == "PAID").all()
    total_discount_disbursed_paise = sum(inv.discount_paise for inv in all_paid_invoices if inv.discount_paise)

    return PlatformSubscriptionAnalyticsResponse(
        mrr_paise=mrr_paise,
        mrr_inr=round(mrr_paise / 100.0, 2),
        arr_paise=arr_paise,
        arr_inr=round(arr_paise / 100.0, 2),
        active_tenants=active_tenants,
        trial_tenants=trial_tenants,
        past_due_tenants=past_due_tenants,
        expired_tenants=expired_tenants,
        churn_count=churn_count,
        total_subscribers=len(restaurants),
        total_coupons_redeemed=total_coupons_redeemed,
        total_discount_disbursed_inr=round(total_discount_disbursed_paise / 100.0, 2)
    )

@router.post("/admin/evaluate-expiries")
def evaluate_expiries_job(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """
    Automated evaluation job that assesses tenant expiry dates, applies grace periods,
    and issues renewal warnings and expiration notices.
    """
    restaurants = db.query(Restaurant).all()
    updated_count = 0
    now = datetime.now()

    for r in restaurants:
        old_status = r.subscription_status
        new_status = r.evaluate_subscription_status()
        if old_status != new_status:
            r.subscription_status = new_status
            updated_count += 1

            if new_status == "PAST_DUE":
                grace_days = r.grace_period_days or 7
                notif = SubscriptionNotification(
                    restaurant_id=r.id,
                    notification_type="PAST_DUE_WARNING",
                    title="Subscription Past Due (Grace Period Active)",
                    message=f"Your subscription expired on {r.subscription_expires_at.strftime('%d %b %Y')}. You are currently in a {grace_days}-day grace period. Please renew to avoid service interruption."
                )
                db.add(notif)
            elif new_status == "EXPIRED":
                notif = SubscriptionNotification(
                    restaurant_id=r.id,
                    notification_type="EXPIRED",
                    title="Subscription Has Expired",
                    message="Your grace period has ended and subscription has expired. Please renew your plan to restore full platform access."
                )
                db.add(notif)

    db.commit()
    return {"success": True, "evaluated_restaurants": len(restaurants), "status_transitions": updated_count}

@router.post("/admin/plans", response_model=SubscriptionPlanResponse)
def create_subscription_plan(
    data: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Allows Super Admin to create a new subscription tier with price in paise and entitlements."""
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == data.plan_code.upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Plan code '{data.plan_code}' already exists")

    plan = SubscriptionPlan(
        plan_code=data.plan_code.upper(),
        name=data.name,
        billing_cycle=data.billing_cycle.upper(),
        price_paise=data.price_paise,
        currency="INR",
        duration_days=data.duration_days,
        features=data.features,
        entitlements_json=json.dumps(data.entitlements) if data.entitlements else None,
        max_tables=data.max_tables,
        is_active=True
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return SubscriptionPlanResponse(
        id=plan.id,
        plan_code=plan.plan_code,
        name=plan.name,
        billing_cycle=plan.billing_cycle,
        price_paise=plan.price_paise,
        price_inr=plan.price_inr,
        duration_days=plan.duration_days,
        features=plan.features,
        entitlements=plan.get_entitlements(),
        max_tables=plan.max_tables,
        is_active=plan.is_active
    )

@router.patch("/admin/plans/{plan_id}")
def toggle_plan_status(
    plan_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Enables or disables a subscription tier."""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found")
    plan.is_active = is_active
    db.commit()
    return {"success": True, "plan_id": plan.id, "is_active": plan.is_active}

@router.get("/admin/coupons", response_model=List[SubscriptionCouponResponse])
def list_admin_coupons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """List all coupons with redemption statistics for Super Admin."""
    coupons = db.query(SubscriptionCoupon).order_by(SubscriptionCoupon.created_at.desc()).all()
    results = []
    for c in coupons:
        results.append(SubscriptionCouponResponse(
            id=c.id,
            code=c.code,
            discount_paise=c.discount_paise,
            discount_inr=c.discount_inr,
            discount_type=c.discount_type,
            discount_percentage=c.discount_percentage,
            eligible_plan_codes=c.eligible_plan_codes,
            start_date=c.start_date,
            end_date=c.end_date,
            max_uses_global=c.max_uses_global,
            max_uses_per_restaurant=c.max_uses_per_restaurant,
            times_used=c.times_used,
            is_active=c.is_active,
            created_at=c.created_at
        ))
    return results

@router.post("/admin/coupons", response_model=SubscriptionCouponResponse)
def create_subscription_coupon(
    data: SubscriptionCouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Allows Super Admin to create a new promo discount coupon."""
    clean_code = data.code.strip().upper()
    existing = db.query(SubscriptionCoupon).filter(SubscriptionCoupon.code == clean_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Coupon code '{clean_code}' already exists")

    coupon = SubscriptionCoupon(
        code=clean_code,
        discount_paise=data.discount_paise,
        discount_type=data.discount_type,
        discount_percentage=data.discount_percentage,
        eligible_plan_codes=data.eligible_plan_codes.upper(),
        start_date=data.start_date or datetime.now(),
        end_date=data.end_date,
        max_uses_global=data.max_uses_global,
        max_uses_per_restaurant=data.max_uses_per_restaurant,
        times_used=0,
        is_active=data.is_active
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    return SubscriptionCouponResponse(
        id=coupon.id,
        code=coupon.code,
        discount_paise=coupon.discount_paise,
        discount_inr=coupon.discount_inr,
        discount_type=coupon.discount_type,
        discount_percentage=coupon.discount_percentage,
        eligible_plan_codes=coupon.eligible_plan_codes,
        start_date=coupon.start_date,
        end_date=coupon.end_date,
        max_uses_global=coupon.max_uses_global,
        max_uses_per_restaurant=coupon.max_uses_per_restaurant,
        times_used=coupon.times_used,
        is_active=coupon.is_active,
        created_at=coupon.created_at
    )

@router.patch("/admin/coupons/{coupon_id}")
def toggle_coupon_status(
    coupon_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PLATFORM_SUPER_ADMIN]))
):
    """Enables or disables a promotional coupon code."""
    coupon = db.query(SubscriptionCoupon).filter(SubscriptionCoupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    coupon.is_active = is_active
    db.commit()
    return {"success": True, "coupon_id": coupon.id, "code": coupon.code, "is_active": coupon.is_active}

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
        amount=round(data.amount_paise / 100.0, 2) if data.amount_paise else None,
        reason=data.reason or "Subscription cancellation refund"
    )

    payment.status = "REFUNDED"
    payment.refund_id = refund_res["refund_id"]
    payment.refund_amount_paise = int(round(refund_res["refund_amount"] * 100))
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
        "refund_amount_inr": refund_res["refund_amount"]
    }
