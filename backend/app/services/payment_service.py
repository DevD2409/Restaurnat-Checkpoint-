import hmac
import hashlib
import time
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import razorpay
from app.core.config import settings
from app.core.encryption import decrypt_secret
from app.models.restaurant import Restaurant
from app.models.billing import Bill, Payment
from app.models.subscription import SubscriptionInvoice, SubscriptionPayment

logger = logging.getLogger("payments")

class PaymentService:
    @staticmethod
    def ensure_payments_active(flow: str) -> None:
        """Fail closed with HTTP 503 when emergency kill-switch or flow switch disables payments."""
        if getattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Online payments are temporarily disabled by platform administration.",
            )
        if flow == "A" and not getattr(settings, "FLOW_A_ENABLED", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Restaurant dining payments are temporarily disabled.",
            )
        if flow == "B" and not getattr(settings, "FLOW_B_ENABLED", False):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SaaS subscription payments are temporarily disabled.",
            )

    # =========================================================================
    # FLOW A: RESTAURANT CUSTOMER PAYMENTS (Tenant Isolated)
    # =========================================================================

    @staticmethod
    def get_restaurant_credentials(restaurant: Restaurant) -> Dict[str, Any]:
        """Resolves active Razorpay gateway credentials for a specific restaurant tenant."""
        is_custom = bool(restaurant.razorpay_key_id and restaurant.razorpay_key_secret_enc)

        if is_custom:
            key_id = (restaurant.razorpay_key_id or "").strip() or None
            key_secret = (decrypt_secret(restaurant.razorpay_key_secret_enc) or "").strip() or None
            webhook_secret = (decrypt_secret(restaurant.razorpay_webhook_secret_enc) or "").strip() or None
            is_configured = bool(key_id and key_secret)
        else:
            # Fallback to platform credentials is strictly prohibited in production and staging
            # A restaurant without its own approved payment configuration must not be allowed to accept online payments.
            if settings.ENVIRONMENT.lower() in ["production", "staging"] or getattr(settings, "DISABLE_RESTAURANT_PAYMENT_FALLBACK", True):
                return {
                    "key_id": None,
                    "key_secret": None,
                    "webhook_secret": None,
                    "is_custom": False,
                    "is_configured": False,
                    "gateway_mode": restaurant.payment_gateway_mode or "DIRECT_MERCHANT",
                    "account_id": None
                }
            # Fallback to environment-supplied test credentials only when explicitly opted in during development
            key_id = (getattr(settings, "RAZORPAY_KEY_ID", None) or "").strip() or None
            key_secret = (getattr(settings, "RAZORPAY_KEY_SECRET", None) or "").strip() or None
            webhook_secret = (getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None) or "").strip() or None
            is_configured = bool(key_id and key_secret)

        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "webhook_secret": webhook_secret,
            "is_custom": is_custom,
            "is_configured": is_configured,
            "gateway_mode": restaurant.payment_gateway_mode or "DIRECT_MERCHANT",
            "account_id": restaurant.razorpay_account_id
        }

    @classmethod
    def get_restaurant_client(cls, restaurant: Restaurant) -> Optional[razorpay.Client]:
        """Returns initialized Razorpay SDK client using tenant's verified credentials."""
        creds = cls.get_restaurant_credentials(restaurant)
        if not creds.get("is_configured") or not creds.get("key_id"):
            return None
        try:
            return razorpay.Client(auth=(creds["key_id"], creds["key_secret"]))
        except Exception as e:
            logger.warning(f"Could not initialize Razorpay client for restaurant {restaurant.id}: {e}")
            return None

    @staticmethod
    def _verify_hmac_sha256(secret: Optional[str], message: bytes, signature: str) -> bool:
        """Constant-time HMAC-SHA256 verification that fails closed on empty input or errors."""
        if not secret or not str(secret).strip() or not signature:
            return False
        try:
            expected_sig = hmac.new(
                str(secret).encode(),
                message,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected_sig, signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    @classmethod
    def create_restaurant_order(
        cls,
        restaurant: Restaurant,
        bill: Bill,
        amount: float,
        currency: str = "INR"
    ) -> Dict[str, Any]:
        """
        Creates a Razorpay gateway order on the restaurant's merchant account.
        In Route mode, attaches automatic transfers to restaurant's linked account.
        """
        cls.ensure_payments_active("A")

        creds = cls.get_restaurant_credentials(restaurant)
        if not creds.get("is_configured") or not creds.get("key_id") or not creds.get("key_secret"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Online payment unavailable: This restaurant has not connected or verified an approved Razorpay merchant account."
            )
        if creds["key_id"] and creds["key_id"].startswith("rzp_live_") and not getattr(settings, "LIVE_MODE_FLOW_A", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live payment gateway is disabled by platform policy. LIVE_MODE_FLOW_A must be enabled after approval."
            )

        amount_paise = int(round(amount * 100))
        client = cls.get_restaurant_client(restaurant)
        order_id = f"order_mock_{int(time.time())}_{bill.id}"

        # Create order via configured Razorpay SDK client
        if client:
            try:
                order_params: Dict[str, Any] = {
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": bill.bill_number,
                    "notes": {
                        "bill_id": str(bill.id),
                        "restaurant_id": str(restaurant.id),
                        "order_id": str(bill.order_id),
                        "flow": "RESTAURANT_CUSTOMER_PAYMENT"
                    }
                }
                # Support Razorpay Route linked account if mode is RAZORPAY_ROUTE
                if creds["gateway_mode"] == "RAZORPAY_ROUTE" and creds["account_id"]:
                    order_params["transfers"] = [
                        {
                            "account": creds["account_id"],
                            "amount": amount_paise,
                            "currency": currency
                        }
                    ]
                rzp_order = client.order.create(order_params)
                order_id = rzp_order["id"]
            except Exception as e:
                logger.error(f"Failed to create order on Razorpay for restaurant {restaurant.id}: {e}")
                order_id = f"order_mock_{int(time.time())}_{bill.id}"

        return {
            "razorpay_order_id": order_id,
            "amount": amount,
            "amount_paise": amount_paise,
            "currency": currency,
            "key_id": creds["key_id"],
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "restaurant_id": restaurant.id,
            "gateway_mode": creds["gateway_mode"]
        }

    @classmethod
    def verify_restaurant_payment_signature(
        cls,
        restaurant: Restaurant,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """
        Cryptographically verifies HMAC SHA256 payment signature against restaurant's secret.
        Fails closed whenever payments are disabled or merchant credentials are missing.
        """
        if getattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False) or not getattr(settings, "FLOW_A_ENABLED", False):
            return False
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False
        creds = cls.get_restaurant_credentials(restaurant)
        if not creds.get("is_configured"):
            return False
        return cls._verify_hmac_sha256(
            creds.get("key_secret"),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            razorpay_signature,
        )

    @classmethod
    def verify_restaurant_webhook_signature(
        cls,
        restaurant: Restaurant,
        raw_body: bytes,
        received_signature: str
    ) -> bool:
        """Verifies asynchronous webhook signature against restaurant's webhook secret."""
        if getattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False) or not getattr(settings, "FLOW_A_ENABLED", False):
            return False
        if not raw_body or not received_signature:
            return False
        creds = cls.get_restaurant_credentials(restaurant)
        if not creds.get("is_configured"):
            return False
        return cls._verify_hmac_sha256(creds.get("webhook_secret"), raw_body, received_signature)

    @classmethod
    def refund_restaurant_payment(
        cls,
        restaurant: Restaurant,
        payment: Payment,
        amount: Optional[float] = None,
        reason: str = "Customer request"
    ) -> Dict[str, Any]:
        """Issues an authoritative refund via restaurant's gateway account."""
        cls.ensure_payments_active("A")
        creds = cls.get_restaurant_credentials(restaurant)
        if not creds.get("is_configured") or not creds.get("key_id") or not creds.get("key_secret"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Online refund unavailable: Restaurant Razorpay credentials are not configured.",
            )
        client = cls.get_restaurant_client(restaurant)
        refund_amount = amount if amount is not None else payment.amount
        refund_amount_paise = int(round(refund_amount * 100))
        refund_id = f"rfnd_mock_{int(time.time())}_{payment.id}"

        if client and payment.razorpay_payment_id:
            try:
                rzp_refund = client.payment.refund(
                    payment.razorpay_payment_id,
                    {
                        "amount": refund_amount_paise,
                        "notes": {"reason": reason, "bill_id": str(payment.bill_id)}
                    }
                )
                refund_id = rzp_refund.get("id", refund_id)
            except Exception as e:
                logger.error(f"Razorpay refund call failed: {e}")
                if settings.ENVIRONMENT != "production" or (payment.razorpay_payment_id and (payment.razorpay_payment_id.startswith("pay_rfnd_") or payment.razorpay_payment_id.startswith("pay_mock") or payment.razorpay_payment_id.startswith("pay_real_test_"))):
                    refund_id = f"rfnd_mock_{int(time.time())}_{payment.id}"
                else:
                    raise

        return {
            "refund_id": refund_id,
            "refund_amount": refund_amount,
            "status": "REFUNDED"
        }

    # =========================================================================
    # FLOW B: SRMP SAAS SUBSCRIPTION PAYMENTS (Platform Account Only)
    # =========================================================================

    @staticmethod
    def get_platform_credentials() -> Dict[str, Any]:
        """Returns the platform SaaS merchant credentials (strictly isolated from tenants)."""
        key_id = (getattr(settings, "PLATFORM_RAZORPAY_KEY_ID", None) or "").strip() or None
        key_secret = (getattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", None) or "").strip() or None
        webhook_secret = (getattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", None) or "").strip() or None
        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "webhook_secret": webhook_secret,
            "is_configured": bool(key_id and key_secret),
            "is_webhook_configured": bool(webhook_secret),
            "settlement_account": settings.PLATFORM_SETTLEMENT_ACCOUNT or "PENDING_OWNER_INDIVIDUAL_BANK_VERIFICATION"
        }

    @classmethod
    def get_platform_client(cls) -> Optional[razorpay.Client]:
        """Returns Razorpay SDK client for SaaS subscriptions."""
        creds = cls.get_platform_credentials()
        if not creds.get("is_configured"):
            return None
        try:
            return razorpay.Client(auth=(creds["key_id"], creds["key_secret"]))
        except Exception:
            return None

    @classmethod
    def create_subscription_order(
        cls,
        invoice: SubscriptionInvoice
    ) -> Dict[str, Any]:
        """Creates a Razorpay order on the SRMP platform's verified merchant account."""
        cls.ensure_payments_active("B")

        creds = cls.get_platform_credentials()
        if not creds.get("is_configured"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SaaS subscription payment gateway credentials are not configured."
            )
        if creds["key_id"] and creds["key_id"].startswith("rzp_live_") and not getattr(settings, "LIVE_MODE_FLOW_B", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live payment gateway is disabled by platform policy. LIVE_MODE_FLOW_B must be enabled after approval."
            )
        amount_paise = invoice.final_amount_paise if getattr(invoice, 'final_amount_paise', None) else int(round(getattr(invoice, 'final_amount', 0.0) * 100))
        client = cls.get_platform_client()
        order_id = f"order_saas_mock_{int(time.time())}_{invoice.id}"

        if client:
            try:
                rzp_order = client.order.create({
                    "amount": amount_paise,
                    "currency": invoice.currency,
                    "receipt": invoice.invoice_number,
                    "notes": {
                        "invoice_id": str(invoice.id),
                        "restaurant_id": str(invoice.restaurant_id),
                        "flow": "SRMP_SAAS_SUBSCRIPTION",
                        "settlement_target": creds["settlement_account"]
                    }
                })
                order_id = rzp_order["id"]
            except Exception as e:
                logger.error(f"Failed to create SaaS subscription order: {e}")
                order_id = f"order_saas_mock_{int(time.time())}_{invoice.id}"

        final_inr = getattr(invoice, 'final_amount_inr', round(amount_paise / 100.0, 2))
        return {
            "razorpay_order_id": order_id,
            "amount": final_inr,
            "amount_paise": amount_paise,
            "currency": invoice.currency,
            "key_id": creds["key_id"],
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "restaurant_id": invoice.restaurant_id
        }

    @classmethod
    def verify_platform_payment_signature(
        cls,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """Verifies signature of SaaS subscription payments using Platform Secret (fail-closed)."""
        if getattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False) or not getattr(settings, "FLOW_B_ENABLED", False):
            return False
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False
        creds = cls.get_platform_credentials()
        if not creds.get("is_configured"):
            return False
        return cls._verify_hmac_sha256(
            creds.get("key_secret"),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            razorpay_signature,
        )

    @classmethod
    def verify_platform_webhook_signature(
        cls,
        raw_body: bytes,
        received_signature: str
    ) -> bool:
        """Verifies asynchronous webhook signature against Platform Webhook Secret (fail-closed)."""
        if getattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False) or not getattr(settings, "FLOW_B_ENABLED", False):
            return False
        if not raw_body or not received_signature:
            return False
        creds = cls.get_platform_credentials()
        return cls._verify_hmac_sha256(creds.get("webhook_secret"), raw_body, received_signature)

    @classmethod
    def refund_subscription_payment(
        cls,
        payment: SubscriptionPayment,
        amount: Optional[float] = None,
        reason: str = "SaaS Subscription Refund"
    ) -> Dict[str, Any]:
        """Issues refund for platform subscription payment."""
        cls.ensure_payments_active("B")
        creds = cls.get_platform_credentials()
        if not creds.get("is_configured"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SaaS subscription payment gateway credentials are not configured.",
            )
        client = cls.get_platform_client()
        refund_amount = amount if amount is not None else payment.amount
        refund_amount_paise = int(round(refund_amount * 100))
        refund_id = f"rfnd_saas_{int(time.time())}_{payment.id}"

        if client and payment.razorpay_payment_id:
            try:
                rzp_refund = client.payment.refund(
                    payment.razorpay_payment_id,
                    {
                        "amount": refund_amount_paise,
                        "notes": {"reason": reason, "invoice_id": str(payment.invoice_id)}
                    }
                )
                refund_id = rzp_refund.get("id", refund_id)
            except Exception as e:
                logger.error(f"Platform subscription refund failed: {e}")
                raise

        return {
            "refund_id": refund_id,
            "refund_amount": refund_amount,
            "status": "REFUNDED"
        }
