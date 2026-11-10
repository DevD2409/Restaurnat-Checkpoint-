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

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "role": role
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
