from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    company_name: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    logo_url: Optional[str] = None

class UserUpdatePassword(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: UUID
    is_active: bool
    logo_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True