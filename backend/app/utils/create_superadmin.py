"""
Production Super-Admin Bootstrap CLI Utility.

Safely provisions the initial platform super-administrator in staging and production
environments where demo seeding is strictly prohibited.

Security guarantees:
1. Production-safe password hashing (bcrypt / passlib via get_password_hash).
2. Zero hardcoded credentials; inputs sourced from secure environment variables or interactive prompt.
3. Zero password logging to stdout, stderr, or loggers.
4. Existing super-admin protection (refuses to run if PLATFORM_SUPER_ADMIN already exists).
5. Explicit restaurant_id=None (platform-level scoping).
6. Exact UserRole.PLATFORM_SUPER_ADMIN role assignment.
7. must_change_password=True enforced so credentials must be rotated on first login.
8. Rejection of demo credentials, fixture accounts, and weak passwords (minimum 12 characters).
9. Explicit database target display and confirmation required before database write.
"""

import os
import sys
import getpass
import argparse
import re
from typing import Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.security import (
    get_password_hash,
    is_demo_seed_account,
    is_blocked_demo_password,
)
from app.models.user import User, UserRole


def mask_database_url(raw_url: str) -> str:
    """Mask credentials in database URL for safe operator display."""
    if not raw_url:
        return "UNSPECIFIED"
    try:
        parsed = urlparse(raw_url)
        if parsed.password:
            netloc = f"{parsed.username or ''}:********@{parsed.hostname or ''}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
        return raw_url
    except Exception:
        return "MASKED_DATABASE_URL"


def validate_email_format(email: str) -> bool:
    """Validate standard email structure."""
    if not email:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def create_initial_superadmin(
    email: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    full_name: str = "Platform Super Administrator",
    phone_number: str = "+91 99999 00000",
    confirm_override: bool = False,
) -> bool:
    """
    Safely creates the initial PLATFORM_SUPER_ADMIN account.
    Returns True if successfully created, False otherwise.
    """
    masked_db = mask_database_url(str(settings.DATABASE_URL))
    print(f"\n=======================================================")
    print(f" SRMP Platform Super-Admin Bootstrap Utility")
    print(f" Target Environment: {settings.ENVIRONMENT}")
    print(f" Target Database:    {masked_db}")
    print(f"=======================================================\n")

    # 1. Existing super-admin protection
    db = SessionLocal()
    try:
        existing_sa = db.query(User).filter(User.role == UserRole.PLATFORM_SUPER_ADMIN).first()
        if existing_sa:
            print(f"[BLOCKED] A platform super-administrator already exists (ID: {existing_sa.id}).")
            print("To preserve audit integrity, additional super-admins cannot be bootstrapped via CLI.")
            return False

        # 2. Resolve Email
        resolved_email = email or os.getenv("SUPERADMIN_EMAIL", "").strip()
        if not resolved_email and sys.stdin.isatty():
            resolved_email = input("Enter Super-Admin Email: ").strip()

        if not resolved_email or not validate_email_format(resolved_email):
            print("[ERROR] Valid super-admin email is required.")
            return False

        if is_demo_seed_account(resolved_email):
            print(f"[BLOCKED] '{resolved_email}' is a known demo/seed account email.")
            print("Production bootstrap requires an authentic operational email address.")
            return False

        # Check for existing user with this email
        if db.query(User).filter(User.email == resolved_email.lower()).first():
            print(f"[ERROR] A user with email '{resolved_email}' already exists.")
            return False

        # 3. Resolve Username
        resolved_username = username or os.getenv("SUPERADMIN_USERNAME", "").strip() or "superadmin"
        if db.query(User).filter(User.username == resolved_username).first():
            print(f"[ERROR] A user with username '{resolved_username}' already exists.")
            return False

        # 4. Resolve Password
        resolved_password = password or os.getenv("SUPERADMIN_INITIAL_PASSWORD", "").strip()
        if not resolved_password and sys.stdin.isatty():
            resolved_password = getpass.getpass("Enter Super-Admin Initial Password (min 12 chars): ")
            confirm_pwd = getpass.getpass("Confirm Super-Admin Initial Password: ")
            if resolved_password != confirm_pwd:
                print("[ERROR] Passwords do not match.")
                return False

        if not resolved_password:
            print("[ERROR] Super-admin password is required.")
            return False

        if len(resolved_password) < 12:
            print("[ERROR] Super-admin password must be at least 12 characters long.")
            return False

        if is_blocked_demo_password(resolved_password):
            print("[BLOCKED] Provided password matches a known demo fixture password.")
            print("Choose a strong, unique production passphrase.")
            return False

        # 5. Explicit Database Target Confirmation
        if not confirm_override:
            if sys.stdin.isatty():
                confirmation = input(
                    f"\nAre you sure you want to write PLATFORM_SUPER_ADMIN to {masked_db}?\nType 'CONFIRM' to proceed: "
                ).strip()
                if confirmation != "CONFIRM":
                    print("[ABORTED] Operation cancelled by operator.")
                    return False
            else:
                print("[ERROR] Explicit confirmation required in non-interactive mode (pass --yes or set confirm_override=True).")
                return False

        # 6. Safe Creation
        superadmin = User(
            restaurant_id=None,
            email=resolved_email.lower().strip(),
            username=resolved_username.strip(),
            hashed_password=get_password_hash(resolved_password),
            full_name=full_name.strip(),
            role=UserRole.PLATFORM_SUPER_ADMIN,
            phone_number=phone_number.strip(),
            is_active=True,
            must_change_password=True,
        )

        db.add(superadmin)
        db.commit()
        db.refresh(superadmin)

        print(f"\n[SUCCESS] Platform Super-Administrator successfully bootstrapped.")
        print(f"  User ID:              {superadmin.id}")
        print(f"  Email:                {superadmin.email}")
        print(f"  Username:             {superadmin.username}")
        print(f"  Role:                 {superadmin.role.value}")
        print(f"  Restaurant ID:        {superadmin.restaurant_id} (Platform Scoped)")
        print(f"  Must Change Password: {superadmin.must_change_password} (Rotation Enforced)")
        print(f"NOTE: Operator must rotate password upon first login at /api/v1/auth/change-password.\n")
        return True

    except Exception as e:
        db.rollback()
        print(f"[FATAL ERROR] Failed to create super-admin: {e}")
        return False
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="SRMP Platform Super-Admin Bootstrap CLI")
    parser.add_argument("--email", help="Super-admin email address", default=None)
    parser.add_argument("--username", help="Super-admin username", default=None)
    parser.add_argument("--full-name", help="Full name", default="Platform Super Administrator")
    parser.add_argument("--phone", help="Contact phone number", default="+91 99999 00000")
    parser.add_argument("--yes", "-y", help="Confirm database write non-interactively", action="store_true")
    args = parser.parse_args()

    success = create_initial_superadmin(
        email=args.email,
        username=args.username,
        full_name=args.full_name,
        phone_number=args.phone,
        confirm_override=args.yes,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
