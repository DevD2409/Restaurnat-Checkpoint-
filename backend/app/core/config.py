import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_FILE = os.path.join(BASE_DIR, "smart_restaurant.db").replace("\\", "/")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Smart Restaurant Management Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = "super-secret-key-change-in-production-smart-restaurant-2026-auth"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    QR_SECRET: str = "smart-restaurant-qr-secure-salt-2026"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_FILE}"
    
    # Platform Razorpay Merchant Gateway (Flow B: SaaS Subscriptions)
    PLATFORM_RAZORPAY_KEY_ID: str = "rzp_test_platform_key_2026"
    PLATFORM_RAZORPAY_KEY_SECRET: str = "rzp_test_platform_secret_2026"
    PLATFORM_RAZORPAY_WEBHOOK_SECRET: str = "rzp_test_platform_webhook_secret_2026"
    PLATFORM_SETTLEMENT_ACCOUNT: str = "ACC_SRMP_CORP_HDFC_00192"

    # Default Restaurant Razorpay Gateway (Flow A: Restaurant Order Payments Fallback)
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder_key"
    RAZORPAY_KEY_SECRET: str = "rzp_test_placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "rzp_test_restaurant_webhook_secret_2026"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
