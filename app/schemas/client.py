from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class ClientBase(BaseModel):
    name: str
    email: EmailStr = Field(..., description="The email of the client")
    phone_number: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    gst_number: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    gst_number: Optional[str] = None

class ClientResponse(ClientBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClientWithStats(ClientResponse):
    total_invoices: int
    total_revenue: float
    outstanding_amount: float