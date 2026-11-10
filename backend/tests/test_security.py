import pytest
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, decode_access_token,
    generate_table_qr_token, verify_table_qr_token
)

def test_password_hashing():
    password = "SuperSecretPassword123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_flow():
    user_id = 42
    role = "ADMIN"
    token = create_access_token(subject=user_id, role=role)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["role"] == role

def test_qr_token_cryptographic_verification():
    restaurant_id = 1
    table_id = 5
    table_number = "T-05"

    token = generate_table_qr_token(restaurant_id, table_id, table_number)
    assert isinstance(token, str)

    # Valid token verification
    verified = verify_table_qr_token(token)
    assert verified is not None
    assert verified["restaurant_id"] == restaurant_id
    assert verified["table_id"] == table_id
    assert verified["table_number"] == table_number

    # Tampered token verification (must fail!)
    tampered_token = token[:-4] + "abcd"
    assert verify_table_qr_token(tampered_token) is None

    # Invalid format token
    assert verify_table_qr_token("invalid_random_string") is None

