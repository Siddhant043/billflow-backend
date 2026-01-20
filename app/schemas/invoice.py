from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
from decimal import Decimal

from app.models.invoice import InvoiceStatus

class InvoiceItemBase(BaseModel):
    description: Optional[str] = None
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0)

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemResponse(InvoiceItemBase):
    id: UUID
    total: Decimal

    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    client_id:UUID
    due_date: date
    issue_date: date
    tax_rate: Decimal = Field(ge=0)
    discount: Decimal = Field(ge=0)
    notes: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_dates(self):
        if self.due_date < self.issue_date:
            raise ValueError('Due date must be after issue date')
        return self

class InvoiceCreate(InvoiceBase):
    items: List[InvoiceItemCreate] = Field(..., min_length=1)
    status: InvoiceStatus = InvoiceStatus.DRAFT

class InvoiceUpdate(InvoiceBase):
    client_id: Optional[UUID] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[InvoiceStatus] = InvoiceStatus.DRAFT
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    discount: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None


class InvoiceResponse(InvoiceBase):
    id: UUID
    user_id: UUID
    invoice_number: str
    status: InvoiceStatus
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[InvoiceItemResponse] = []
    
    class Config:
        from_attributes = True


class InvoiceWithClient(InvoiceResponse):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_company: Optional[str] = None


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceWithClient]
    total: int
    page: int
    page_size: int
    total_pages: int


class InvoiceSummary(BaseModel):
    total_invoices: int
    total_revenue: Decimal
    paid_invoices: int
    pending_invoices: int
    overdue_invoices: int
    draft_invoices: int