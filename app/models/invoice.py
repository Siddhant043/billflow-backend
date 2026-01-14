from sqlalchemy import Column, String, DateTime, ForeignKey, Numeric, Date, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from enum import Enum
from app.core.database import Base

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class Invoice(Base):
    __tablename__="inovoices"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete= "CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete= "CASCADE"), nullable=False)
    invoice_number = Column(String(225), nullable=False)
    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(5,2), default=0)
    notes=Column(Text, nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="invoices")
    client = relationship("Client", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Invoice(id={self.id}, invoice_number={self.invoice_number})"

class InvoiceItem(Base):
    __tablename__="invoice_items"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("inovoices.id", ondelete= "CASCADE"), nullable=False)
    item_name= Column(String(225), nullable=False)
    quantity= Column(Numeric(10,2), nullable=False)
    unit_price= Column(Numeric(10,2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice = relationship("Invoice", back_populates="items")

    def __repr__(self):
        return f"InvoiceItem(id={self.id}, item_name={self.item_name})"
    