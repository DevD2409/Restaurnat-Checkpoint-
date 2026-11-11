#!/usr/bin/env python3
"""
Cryptographically Secure Secrets Generator for SRMP Production Deployments
Generates 256-bit entropy keys for SECRET_KEY, QR_SECRET, and generates initial Platform Super Admin credentials.
"""

import os
import sys
import secrets
import string
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def generate_strong_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%^&*" for c in password)):
            return password

def generate_production_env():
    secret_key = secrets.token_hex(32)  # 256 bits
    qr_secret = secrets.token_hex(32)   # 256 bits
    webhook_secret = secrets.token_hex(24)
    superadmin_password = generate_strong_password(24)

    env_content = f"""# ==============================================================================
# SRMP Multi-Tenant SaaS - Production Environment Configuration
# Generated automatically by scripts/generate_production_secrets.py
# DO NOT COMMIT REAL PRODUCTION SECRETS TO VERSION CONTROL
# ==============================================================================

ENVIRONMENT=production
PROJECT_NAME="Smart Restaurant Management Platform"
VERSION="1.0.0"
API_V1_STR="/api/v1"
LOG_LEVEL=INFO

# Cryptographic Security
SECRET_KEY="{secret_key}"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
QR_SECRET="{qr_secret}"

# Managed Database (PostgreSQL)
# e.g. postgresql://postgres:<password>@<host>:5432/<dbname>?sslmode=require
DATABASE_URL="postgresql://postgres:REPLACE_WITH_MANAGED_DB_PASSWORD@host:5432/smart_restaurant_db?sslmode=require"

# Hosting Domains & CORS
# Production uses Firebase Hosting defaults unless PRODUCTION_DOMAIN overrides it
FRONTEND_URL="https://srmp-platform.web.app"
BACKEND_CORS_ORIGINS=["https://srmp-platform.web.app","https://srmp-platform.firebaseapp.com"]

# Platform Razorpay Merchant Gateway (Flow B: SaaS Subscriptions -> Owner's Verified Individual Bank)
PLATFORM_RAZORPAY_KEY_ID="rzp_live_REPLACE_WITH_PLATFORM_KEY"
PLATFORM_RAZORPAY_KEY_SECRET="REPLACE_WITH_PLATFORM_KEY_SECRET"
PLATFORM_RAZORPAY_WEBHOOK_SECRET="{webhook_secret}"
PLATFORM_SETTLEMENT_BANK_NAME=""
PLATFORM_SETTLEMENT_ACCOUNT=""
PLATFORM_SETTLEMENT_IFSC=""

# Individual Business Identity & GST Flags
BUSINESS_OPERATING_MODEL="INDIVIDUAL_UNREGISTERED"
OWNER_LEGAL_NAME=""
BRAND_TRADE_NAME="SRMP (Smart Restaurant Management Platform)"
BUSINESS_IDENTITY_STATUS="PENDING_OWNER_CONFIGURATION"
IS_GST_REGISTERED=false
IS_GST_RATE_CA_CONFIRMED=false
PRODUCTION_DOMAIN=""

# Restaurant Payments Safety: Flow A payments must NEVER fall back to platform merchant
DISABLE_RESTAURANT_PAYMENT_FALLBACK=true
LIVE_MODE_FLOW_A=false
LIVE_MODE_FLOW_B=false
SEED_DEMO_DATA=false
SUPERADMIN_INITIAL_PASSWORD="{superadmin_password}"

# Persistent Object Storage (Cloudflare R2 / AWS S3)
STORAGE_BACKEND="s3"
S3_BUCKET_NAME="srmp-production-uploads"
S3_ENDPOINT_URL="https://<account-id>.r2.cloudflarestorage.com"
S3_ACCESS_KEY_ID="REPLACE_WITH_R2_ACCESS_KEY_ID"
S3_SECRET_ACCESS_KEY="REPLACE_WITH_R2_SECRET_ACCESS_KEY"
S3_REGION="auto"
S3_PUBLIC_BASE_URL="https://pub-<hash>.r2.dev"

# Error Monitoring (Sentry)
# SENTRY_DSN="https://<key>@o<org>.ingest.sentry.io/<project>"

# ==============================================================================
# Initial Platform Super Admin Provisioning
# Username: superadmin (provision via SUPERADMIN_INITIAL_PASSWORD above and rotate on first login)
# ==============================================================================
"""

    out_file = BASE_DIR / "backend" / ".env.production.local"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"[OK] Generated local gitignored production secrets file: {out_file}")
    return {
        "secret_key_len": len(secret_key),
        "qr_secret_len": len(qr_secret),
        "superadmin_password_len": len(superadmin_password)
    }

if __name__ == "__main__":
    generate_production_env()
