from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base

class Client(Base):
    __tablename__="clients"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(225), nullable=False)
    email = Column(String(225), nullable=False)
    phone_number = Column(String(225), nullable=False)
    address = Column(String(225), nullable=False)
    company=Column(String(225), nullable=False)
    logo_url=Column(String(225))
    gst_number=Column(String(225), nullable=False)
    website=Column(String(225))
    notes=Column(String(225))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    #Relationships
    user = relationship("User", back_populates="clients")
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Client(id={self.id}, name={self.name})"
    