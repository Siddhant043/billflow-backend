from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base

class Client(Base):
    __tablename__="clients"
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    name = Column(String(225), nullable=False)
    email = Column(String(225), nullable=False)
    phone_number = Column(String(225), nullable=False)
    address = Column(String(225), nullable=False)
    company=Column(String(225), nullable=False)
    gst_number=Column(String(225), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    #Relationships
    invoices = relationship("Invoice", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Client(id={self.id}, name={self.name})"
    