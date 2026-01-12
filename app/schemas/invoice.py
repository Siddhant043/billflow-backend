from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class InvoiceBase(BaseModel):
    client_id: UUID
    invoice_number: str
    invoice_date: datetime
    issue_date: datetime
    due_date: datetime
    total_amount: float
    tax_amount: float
    discount_amount: float
    status: InvoiceStatus
    notes: Optional[str] = None
    items: list[InvoiceItemBase] = Field(default_factory=list)

class InvoiceCreate(InvoiceBase):
    status: InvoiceStatus = InvoiceStatus.DRAFT

class InvoiceUpdate(InvoiceBase):
    client_id: Optional[UUID] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    discount_amount: Optional[float] = None
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None
    items: Optional[list[InvoiceItemBase]] = None
    class Config:
        from_attributes = True

class InvoiceResponse(InvoiceBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class InvoiceWithStats(InvoiceResponse):
    total_invoices: int
    total_revenue: float
    outstanding_amount: float

class InvoiceItemBase(BaseModel):
    invoice_id: UUID
    item_name: str
    quantity: int
    unit_price: float

