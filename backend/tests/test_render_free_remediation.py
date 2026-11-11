import hashlib
import hmac
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.database import SessionLocal
from app.core.encryption import encrypt_secret
from app.core.security import create_access_token
from app.main import app
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.services.payment_service import PaymentService

client = TestClient(app)


def test_settings_have_no_hardcoded_payment_secrets_and_fail_closed_defaults():
    """Verify Settings(_env_file=None) contains zero fallback Razorpay secrets and fails closed."""
    clean = Settings(_env_file=None)

    assert clean.PLATFORM_RAZORPAY_KEY_ID is None
    assert clean.PLATFORM_RAZORPAY_KEY_SECRET is None
    assert clean.PLATFORM_RAZORPAY_WEBHOOK_SECRET is None
    assert clean.RAZORPAY_KEY_ID is None
    assert clean.RAZORPAY_KEY_SECRET is None
    assert clean.RAZORPAY_WEBHOOK_SECRET is None

    assert clean.DISABLE_RESTAURANT_PAYMENT_FALLBACK is True
    assert clean.FLOW_A_ENABLED is False
    assert clean.FLOW_B_ENABLED is False
    assert clean.LIVE_MODE_FLOW_A is False
    assert clean.LIVE_MODE_FLOW_B is False
    assert clean.EMERGENCY_DISABLE_PAYMENTS is True
    assert clean.STORAGE_BACKEND == "local"


def test_production_config_supports_free_tier_local_storage_and_rejects_placeholder_secrets():
    """Production accepts Render Free local storage + disabled payments, and rejects insecure payment secrets."""
    prod_free = Settings(
        _env_file=None,
        ENVIRONMENT="production",
        SEED_DEMO_DATA=False,
        SECRET_KEY="x" * 48,
        QR_SECRET="y" * 48,
        DATABASE_URL="postgresql://user:pass@localhost:5432/srmp_prod",
        STORAGE_BACKEND="local",
        EMERGENCY_DISABLE_PAYMENTS=True,
        FLOW_A_ENABLED=False,
        FLOW_B_ENABLED=False,
        LIVE_MODE_FLOW_A=False,
        LIVE_MODE_FLOW_B=False,
        DISABLE_RESTAURANT_PAYMENT_FALLBACK=True,
    )
    assert prod_free.STORAGE_BACKEND == "local"
    assert prod_free.EMERGENCY_DISABLE_PAYMENTS is True

    # Placeholder/legacy payment secrets must be rejected in production
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SEED_DEMO_DATA=False,
            SECRET_KEY="x" * 48,
            QR_SECRET="y" * 48,
            DATABASE_URL="postgresql://user:pass@localhost:5432/srmp_prod",
            STORAGE_BACKEND="local",
            PLATFORM_RAZORPAY_KEY_SECRET="legacy_placeholder_secret",
        )

    # Enabling Flow B in production with missing platform credentials must be rejected
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SEED_DEMO_DATA=False,
            SECRET_KEY="x" * 48,
            QR_SECRET="y" * 48,
            DATABASE_URL="postgresql://user:pass@localhost:5432/srmp_prod",
            STORAGE_BACKEND="local",
            EMERGENCY_DISABLE_PAYMENTS=False,
            FLOW_B_ENABLED=True,
        )


def test_verification_fails_closed_when_credentials_missing(monkeypatch):
    """Missing credentials must never allow payment or webhook verification to pass."""
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_A_ENABLED", True)
    monkeypatch.setattr(settings, "FLOW_B_ENABLED", True)
    monkeypatch.setattr(settings, "DISABLE_RESTAURANT_PAYMENT_FALLBACK", False)

    # Platform missing secrets -> fail closed
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_ID", None)
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_KEY_SECRET", None)
    monkeypatch.setattr(settings, "PLATFORM_RAZORPAY_WEBHOOK_SECRET", None)

    assert PaymentService.verify_platform_payment_signature("order_1", "pay_1", "sig") is False
    assert PaymentService.verify_platform_webhook_signature(b'{"event":"order.paid"}', "sig") is False

    # Restaurant missing secrets & fallback missing -> fail closed
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", None)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", None)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "global_secret_must_not_leak")

    unconfigured_rest = Restaurant(id=998, name="Unconfigured Bistro")
    assert PaymentService.verify_restaurant_payment_signature(unconfigured_rest, "order_1", "pay_1", "sig") is False
    assert PaymentService.verify_restaurant_webhook_signature(unconfigured_rest, b"{}", "sig") is False

    # Custom restaurant without webhook_secret_enc must NOT fall back to settings.RAZORPAY_WEBHOOK_SECRET
    custom_no_webhook = Restaurant(
        id=997,
        name="Custom No Webhook Bistro",
        razorpay_key_id="rzp_test_custom",
        razorpay_key_secret_enc=encrypt_secret("unit_secret_only"),
        razorpay_webhook_secret_enc=None,
    )
    leaked_sig = hmac.new(b"global_secret_must_not_leak", b"{}", hashlib.sha256).hexdigest()
    assert PaymentService.verify_restaurant_webhook_signature(custom_no_webhook, b"{}", leaked_sig) is False


def test_fabricated_sandbox_signature_tokens_are_rejected(monkeypatch):
    """Legacy sandbox magic tokens must never bypass cryptographic HMAC verification."""
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_A_ENABLED", True)

    rest = Restaurant(
        id=996,
        name="Cryptographic Bistro",
        razorpay_key_id="rzp_test_crypto",
        razorpay_key_secret_enc=encrypt_secret("real_hmac_key_only"),
    )
    for magic_sig in ("mock_signature_valid_sandbox", "valid_signature_sandbox", "signature_valid"):
        assert (
            PaymentService.verify_restaurant_payment_signature(
                rest, "order_mock_12345", "pay_12345", magic_sig
            )
            is False
        )
        resp = client.post(
            "/api/v1/payments/verify-razorpay-payment",
            json={
                "bill_id": 1,
                "razorpay_order_id": "order_mock_12345",
                "razorpay_payment_id": "pay_12345",
                "razorpay_signature": magic_sig,
                "amount": 100.0,
            },
        )
        assert resp.status_code in (400, 404)


def test_emergency_disable_payments_blocks_all_online_payment_endpoints(monkeypatch):
    """EMERGENCY_DISABLE_PAYMENTS=True must return 503 on initiation, verify, webhook, and refunds."""
    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", True)

    db = SessionLocal()
    owner = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.RESTAURANT_OWNER])).first()
    superadmin = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
    assert owner is not None and superadmin is not None
    owner_token = create_access_token(str(owner.id), owner.role.value, owner.restaurant_id)
    superadmin_token = create_access_token(str(superadmin.id), superadmin.role.value, None)
    db.close()

    # Flow A online endpoints -> 503
    assert client.post("/api/v1/payments/razorpay-order", json={"bill_id": 1, "amount": 100.0}).status_code == 503
    assert (
        client.post(
            "/api/v1/payments/verify-razorpay-payment",
            json={
                "bill_id": 1,
                "razorpay_order_id": "order_x",
                "razorpay_payment_id": "pay_x",
                "razorpay_signature": "sig_x",
                "amount": 100.0,
            },
        ).status_code
        == 503
    )
    assert client.post("/api/v1/payments/webhook", content=b"{}", headers={"X-Razorpay-Signature": "x"}).status_code == 503
    assert client.post("/api/v1/payments/webhook/restaurant/1", content=b"{}", headers={"X-Razorpay-Signature": "x"}).status_code == 503
    assert (
        client.post(
            "/api/v1/payments/refund",
            json={"payment_id": 1, "amount": 10.0, "reason": "test"},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        ).status_code
        == 503
    )

    # Flow B online endpoints -> 503
    assert (
        client.post(
            "/api/v1/subscriptions/checkout",
            json={"plan_code": "MONTHLY"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).status_code
        == 503
    )
    assert (
        client.post(
            "/api/v1/subscriptions/verify",
            json={
                "invoice_id": 1,
                "razorpay_order_id": "order_x",
                "razorpay_payment_id": "pay_x",
                "razorpay_signature": "sig_x",
            },
        ).status_code
        == 503
    )
    assert client.post("/api/v1/subscriptions/webhook", content=b"{}", headers={"X-Razorpay-Signature": "x"}).status_code == 503
    assert (
        client.post(
            "/api/v1/subscriptions/refund",
            json={"payment_id": 1, "reason": "test"},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        ).status_code
        == 503
    )


def test_alembic_upgrade_head_on_isolated_temp_database(tmp_path: Path):
    """Verify Alembic migrations run cleanly to head without touching backend/smart_restaurant.db."""
    backend_dir = Path(__file__).resolve().parents[1]
    scratch_db = tmp_path / "alembic_migration_check.db"
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{scratch_db.as_posix()}")

    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(scratch_db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()

    assert version == "bd1e5a3970b2"
    for expected in (
        "restaurants",
        "users",
        "bills",
        "payments",
        "subscription_plans",
        "subscription_invoices",
        "subscription_payments",
    ):
        assert expected in tables
