from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    token: str

class EmailVerificationRequest(BaseModel):
    user_id: str
    code: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
    success: bool = True 