import os
import json
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_FILE = os.path.join(BASE_DIR, "smart_restaurant.db").replace("\\", "/")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Restaurant Management Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:5173"
    SEED_DEMO_DATA: Optional[bool] = None
    SUPERADMIN_INITIAL_PASSWORD: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "super-secret-key-change-in-production-smart-restaurant-2026-auth"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    QR_SECRET: str = "smart-restaurant-qr-secure-salt-2026"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_FILE}"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        if isinstance(v, str):
            # Compatibility with Railway / Heroku / Supabase default connection strings
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql://", 1)
        return v
    
    # Platform Razorpay Merchant Gateway (Flow B: SaaS Subscriptions)
    PLATFORM_RAZORPAY_KEY_ID: str = "rzp_test_platform_key_2026"
    PLATFORM_RAZORPAY_KEY_SECRET: str = "rzp_test_platform_secret_2026"
    PLATFORM_RAZORPAY_WEBHOOK_SECRET: str = "rzp_test_platform_webhook_secret_2026"
    PLATFORM_SETTLEMENT_ACCOUNT: Optional[str] = None  # Pending owner's verified individual bank account after Razorpay approval
    PLATFORM_SETTLEMENT_BANK_NAME: Optional[str] = None
    PLATFORM_SETTLEMENT_IFSC: Optional[str] = None

    # Default Restaurant Razorpay Gateway (Flow A: Restaurant Order Payments Fallback)
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_key"
    RAZORPAY_KEY_SECRET: str = "rzp_test_placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "rzp_test_restaurant_webhook_secret_2026"
    DISABLE_RESTAURANT_PAYMENT_FALLBACK: bool = False

    # Independent Payment Flow Activation & Emergency Circuit Breakers
    FLOW_A_ENABLED: bool = True
    FLOW_B_ENABLED: bool = True
    LIVE_MODE_FLOW_A: bool = False
    LIVE_MODE_FLOW_B: bool = False
    EMERGENCY_DISABLE_PAYMENTS: bool = False

    # Platform Business Identity Profile (Individual / Unregistered Business by Default)
    BUSINESS_OPERATING_MODEL: str = "INDIVIDUAL_UNREGISTERED"  # INDIVIDUAL_UNREGISTERED or REGISTERED_ENTITY
    OWNER_LEGAL_NAME: Optional[str] = None  # Owner's actual legal name (pending configuration until verified)
    BRAND_TRADE_NAME: str = "SRMP (Smart Restaurant Management Platform)"
    BUSINESS_IDENTITY_STATUS: str = "PENDING_OWNER_CONFIGURATION"  # PENDING_OWNER_CONFIGURATION, CONFIGURED_PENDING_VERIFICATION, VERIFIED
    BUSINESS_PAN: Optional[str] = None
    BUSINESS_ADDRESS: Optional[str] = None

    # Tax & GST Registration Profile (Strictly disabled until valid GSTIN + documented CA rate confirmation)
    IS_GST_REGISTERED: bool = False
    OWNER_GSTIN: Optional[str] = None
    SUPPLIER_GST_STATE_CODE: Optional[str] = None
    GST_RATE_PERCENTAGE: float = 18.0
    IS_GST_RATE_CA_CONFIRMED: bool = False
    SAC_CODE: Optional[str] = None
    SAC_DESCRIPTION: Optional[str] = None

    # Configurable Production Domain, Support & Grievance Channels (Zero Fabricated Defaults)
    PRODUCTION_DOMAIN: Optional[str] = None
    SUPPORT_EMAIL: Optional[str] = None
    GRIEVANCE_EMAIL: Optional[str] = None
    TELEPHONE_HELPLINE: Optional[str] = None
    GRIEVANCE_CONTACT_NAME: Optional[str] = None
    REFUND_POLICY_APPROVED: bool = False  # Strict gate: cannot be presented as final while owner approval is pending
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    return json.loads(v_trimmed)
                except Exception:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Persistent Object Storage (Cloudflare R2 / AWS S3 / MinIO)
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None  # e.g., https://<account_id>.r2.cloudflarestorage.com
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_REGION: str = "auto"
    S3_PUBLIC_BASE_URL: Optional[str] = None  # e.g., https://pub-<hash>.r2.dev or CDN domain

    # Error Monitoring
    SENTRY_DSN: Optional[str] = None

    # Transactional Email (Resend)
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: Optional[str] = None
    ENABLE_TRANSACTIONAL_EMAIL: bool = False

    @model_validator(mode="after")
    def validate_production_configuration(self):
        env_lower = self.ENVIRONMENT.lower()
        if env_lower == "production" and self.SEED_DEMO_DATA is True:
            raise ValueError("In production, SEED_DEMO_DATA must never be enabled!")
        if env_lower in ["production", "staging"]:
            self.DISABLE_RESTAURANT_PAYMENT_FALLBACK = True
            if "change-in-production" in self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError(f"In {env_lower}, SECRET_KEY must be configured as a cryptographically secure key of at least 32 characters!")
            if self.DATABASE_URL.startswith("sqlite"):
                raise ValueError(f"In {env_lower}, DATABASE_URL must be a PostgreSQL connection string, not SQLite!")
            if "secure-salt-2026" in self.QR_SECRET:
                raise ValueError(f"In {env_lower}, QR_SECRET must be configured with a unique secret!")
            if self.STORAGE_BACKEND == "s3":
                if not (self.S3_BUCKET_NAME and self.S3_ENDPOINT_URL and self.S3_ACCESS_KEY_ID and self.S3_SECRET_ACCESS_KEY):
                    raise ValueError(f"In {env_lower} with STORAGE_BACKEND='s3', all S3/R2 credentials (BUCKET, ENDPOINT, ACCESS_KEY, SECRET_KEY) must be provided!")
            if self.ENABLE_TRANSACTIONAL_EMAIL and (not self.RESEND_API_KEY or not self.RESEND_FROM_EMAIL):
                raise ValueError(f"In {env_lower}, when ENABLE_TRANSACTIONAL_EMAIL is True, RESEND_API_KEY and RESEND_FROM_EMAIL must be provided!")
        return self

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
