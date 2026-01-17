from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from app.models.payment import PaymentMethod


class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    invoice_id: UUID


class PaymentResponse(PaymentBase):
    id: UUID
    invoice_id: UUID
    payment_date: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class PaymentWithInvoice(PaymentResponse):
    invoice_number: str
    invoice_total: Decimal