import hmac
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Union
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], role: str, restaurant_id: Optional[int] = None, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role,
        "restaurant_id": restaurant_id
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_table_qr_token(restaurant_id: int, table_id: int, table_number: str) -> str:
    """
    Creates a tamper-proof signed token containing restaurant_id and table_id
    Format: table_number.restaurant_id.table_id.timestamp.signature
    """
    ts = int(time.time())
    payload = f"{restaurant_id}:{table_id}:{table_number}:{ts}"
    signature = hmac.new(settings.QR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{restaurant_id}_{table_id}_{table_number}_{ts}_{signature}"

def verify_table_qr_token(token: str, max_age_days: Optional[int] = 180) -> Optional[dict]:
    """
    Verifies that the table token was genuinely generated and has not been tampered with or expired.
    """
    try:
        parts = token.split("_")
        if len(parts) != 5:
            return None
        restaurant_id, table_id, table_number, ts, signature = parts
        token_ts = int(ts)

        # Max age validation (replay and stale QR mitigation)
        if max_age_days is not None:
            max_age_seconds = max_age_days * 86400
            if time.time() - token_ts > max_age_seconds:
                return None

        payload = f"{restaurant_id}:{table_id}:{table_number}:{ts}"
        expected_sig = hmac.new(settings.QR_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
        if hmac.compare_digest(signature, expected_sig):
            return {
                "restaurant_id": int(restaurant_id),
                "table_id": int(table_id),
                "table_number": table_number,
                "timestamp": token_ts
            }
        return None
    except Exception:
        return None


BLOCKED_DEMO_PASSWORD_HASHES = frozenset({
    # SHA-256 digests of demo/fixture passwords blocked from production use
    "e34f92a20532a873cb3184398070b4b82a8fa29cf48572c203dc5f0fa6158231",
    "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
    "866485796cfa8d7c0cf7111640205b83076433547577511d81f8030ae99ecea5",
    "1a303e87599632e4a19d3603ca36a6762dea330dccb8017796d6a3b9f82154ac",
    "fa0990ab6f2ecfd562611cedad67152e8c1117f91c22d15094d1e242314243af",
    "b4c94003c562bb0d89535eca77f07284fe560fd48a7cc1ed99f0a56263d616ba",
    "ef382c75452f3577ff353a8c3e2cb5380a80d2543654c3851e62859903b08398",
})

DEMO_SEED_EMAILS = frozenset({
    "admin@royalsaffron.com",
    "manager@royalsaffron.com",
    "waiter@royalsaffron.com",
    "chef@royalsaffron.com",
    "cashier@royalsaffron.com",
    "superadmin@srmp-saas.com",
})


def is_blocked_demo_password(password: Optional[str]) -> bool:
    """Return True if password matches a known demo/fixture password digest."""
    if not password:
        return False
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return digest in BLOCKED_DEMO_PASSWORD_HASHES


def is_demo_seed_account(email: Optional[str]) -> bool:
    """Return True if email belongs to a seeded demo fixture account."""
    if not email:
        return False
    return email.strip().lower() in DEMO_SEED_EMAILS
