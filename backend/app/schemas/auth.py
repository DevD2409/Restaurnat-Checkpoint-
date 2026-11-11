from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    username: str
    restaurant_id: Optional[int] = None
    restaurant_slug: Optional[str] = None
    must_change_password: bool = False

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    restaurant_id: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    role: UserRole = UserRole.WAITER
    phone_number: Optional[str] = None
    restaurant_id: Optional[int] = None
    shift: Optional[str] = "General Shift"

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    phone_number: Optional[str] = None
    shift: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    restaurant_id: Optional[int] = None
    email: str
    username: str
    full_name: str
    role: UserRole
    phone_number: Optional[str] = None
    shift: Optional[str] = None
    is_active: bool
    must_change_password: bool = False

    class Config:
        from_attributes = True

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
