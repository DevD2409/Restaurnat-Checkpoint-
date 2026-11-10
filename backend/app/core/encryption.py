import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from app.core.config import settings

def _get_fernet_key() -> bytes:
    """Derives a deterministic 32-byte URL-safe base64 key from SECRET_KEY for Fernet."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_secret(plain_text: Optional[str]) -> Optional[str]:
    """Encrypts a sensitive secret string at rest using authenticated Fernet AES."""
    if not plain_text or not plain_text.strip():
        return None
    fernet = Fernet(_get_fernet_key())
    encrypted_bytes = fernet.encrypt(plain_text.encode())
    return encrypted_bytes.decode()

def decrypt_secret(cipher_text: Optional[str]) -> Optional[str]:
    """Decrypts a Fernet encrypted secret. If already plain/unencrypted or error, returns safely."""
    if not cipher_text or not cipher_text.strip():
        return None
    try:
        fernet = Fernet(_get_fernet_key())
        decrypted_bytes = fernet.decrypt(cipher_text.encode())
        return decrypted_bytes.decode()
    except Exception:
        # Fallback for plain text keys or test mocks
        return cipher_text

