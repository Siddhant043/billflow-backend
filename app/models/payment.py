from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Numeric as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class Payment(Base):
    __payments__ = "payments"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable="False")
    amount = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(Datetime, nullable=False)
    payment_method = Column(S)

    