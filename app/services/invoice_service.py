from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
import logging

from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.client import Client
from app.models.payment import Payment
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate, InvoiceItemCreate
from app.core.redis import redis_client
from app.core.rabbitmq import rabbitmq_client
from app.utils.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger(__name__)

class InvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_invoice(self, invoice: InvoiceCreate):
        """Generate unique invoice number."""
        # Get the count of user's invoices

        result = await self.db.execute(
            select(func.count(Invoice.id)).where(Invoice.user_id == user_id)
        )
        count = result.scalar() or 0
        
        # Format: INV-YYYYMM-XXXX
        today = date.today()
        invoice_number = f"INV-{today.year}{today.month:02d}-{count + 1:04d}"
        
        # Check if exists (rare collision)
        existing = await self.db.execute(
            select(Invoice).where(Invoice.invoice_number == invoice_number)
        )
        
        if existing.scalar_one_or_none():
            # Add random suffix if collision
            import random
            invoice_number = f"{invoice_number}-{random.randint(10, 99)}"
        
        return invoice_number
    
    def calculate_invoice_totals(
        self,
        items: List[InvoiceItemCreate],
        tax_rate: Decimal,
        discount: Decimal
    ) -> dict:
        """Calculate invoice totals."""
        subtotal = sum(item.quantity * item.unit_price for item in items)

        # Apply discount
        discounted_amount = subtotal - discount
        if discounted_amount < 0:
            discounted_amount = Decimal(0)
        
        # Calculate tax
        tax_amount = (discounted_amount * tax_rate) / 100
        
        # Total
        total_amount = discounted_amount + tax_amount
        
        return {
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount
        }

    async def create_invoice(
        self,
        invoice: InvoiceCreate,
        user_id:UUID
    ) -> Invoice:
        """Create a new invoice."""
        # Verify client belongs to user if provided
        if invoice_data.client_id:
            client_result = await self.db.execute(
                select(Client).where(
                    and_(
                        Client.id == invoice_data.client_id,
                        Client.user_id == user_id
                    )
                )
            )
            client = client_result.scalar_one_or_none()
            if not client:
                raise BadRequestException("Client not found or doesn't belong to user")
        
        # Generate invoice number
        invoice_number = await self.generate_invoice_number(user_id)
        
        # Calculate totals
        totals = self.calculate_invoice_totals(
            invoice_data.items,
            invoice_data.tax_rate,
            invoice_data.discount
        )

        # Create invoice
        invoice = Invoice(
            user_id=user_id,
            client_id=invoice_data.client_id,
            invoice_number=invoice_number,
            issue_date=invoice_data.issue_date,
            due_date=invoice_data.due_date,
            status=InvoiceStatus.DRAFT,
            tax_rate=invoice_data.tax_rate,
            discount=invoice_data.discount,
            notes=invoice_data.notes,
            subtotal=totals["subtotal"],
            tax_amount=totals["tax_amount"],
            total_amount=totals["total_amount"]
        )

        self.db.add(invoice)
        await self.db.flush()  # Get invoice ID

        # Create invoice items
        for item_data in invoice_data.items:
            item_total = item_data.quantity * item_data.unit_price
            item = InvoiceItem(
                invoice_id=invoice.id,
                description=item_data.description,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                total=item_total
            )
            self.db.add(item)
        
        await self.db.commit()
        await self.db.refresh(invoice)

        # Load relationships
        await self.db.refresh(invoice, ['items', 'client'])
        
        # Invalidate cache
        await redis_client.invalidate_pattern(f"invoices:{user_id}:*")
        
        # Publish event
        await rabbitmq_client.publish(
            "invoices",
            "invoice.created",
            {
                "invoice_id": str(invoice.id),
                "user_id": str(user_id),
                "invoice_number": invoice.invoice_number,
                "total_amount": float(invoice.total_amount)
            }
        )
        
        return invoice
    
    async def get_invoice(
        self,
        invoice_id: UUID,
        user_id: UUID
    ) -> Optional[Invoice]:
        """Get invoice by ID."""
        # Try cache
        cache_key = f"invoice:{invoice_id}"
        cached = await redis_client.get_json(cache_key)
        
        if cached and cached.get("user_id") == str(user_id):
            # Note: This is simplified. In production, you'd reconstruct the full object
            pass
        
        # Query database with relationships
        result = await self.db.execute(
            select(Invoice)
            .options(selectinload(Invoice.items), joinedload(Invoice.client))
            .where(
                and_(
                    Invoice.id == invoice_id,
                    Invoice.user_id == user_id
                )
            )
        )
        
        invoice = result.scalar_one_or_none()
        
        if invoice:
            # Cache for 30 minutes
            await redis_client.set_json(
                cache_key,
                {
                    "id": str(invoice.id),
                    "user_id": str(invoice.user_id),
                    "invoice_number": invoice.invoice_number,
                    "status": invoice.status.value,
                    "total_amount": float(invoice.total_amount)
                },
                expire=1800
            )
        
        return invoice

    async def list_invoices(
        self,
        user_id: UUID,
        status: Optional[InvoiceStatus] = None,
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Invoice], int]:
        """List invoices with filters."""
        # Build query
        query = select(Invoice).where(Invoice.user_id == user_id)
        
        # Apply filters
        if status:
            query = query.where(Invoice.status == status)
        
        if client_id:
            query = query.where(Invoice.client_id == client_id)
        
        if start_date:
            query = query.where(Invoice.issue_date >= start_date)
        
        if end_date:
            query = query.where(Invoice.issue_date <= end_date)
        
        if search:
            search_filter = f"%{search}%"
            query = query.where(
                or_(
                    Invoice.invoice_number.ilike(search_filter),
                    Invoice.notes.ilike(search_filter)
                )
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = (
            query
            .options(joinedload(Invoice.client))
            .order_by(Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        invoices = result.scalars().all()
        
        return invoices, total

    async def update_invoice(
        self,
        invoice_id: UUID,
        user_id: UUID,
        invoice_update: InvoiceUpdate
    ) -> Optional[Invoice]:
        """Update an invoice."""
        invoice = await self.get_invoice(invoice_id, user_id)
        
        if not invoice:
            return None
        
        # Don't allow updates to paid or cancelled invoices
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED]:
            raise BadRequestException(
                f"Cannot update invoice with status {invoice.status.value}"
            )
        
        update_data = invoice_update.model_dump(exclude_unset=True, exclude={'items'})
        
        # Update invoice fields
        for field, value in update_data.items():
            setattr(invoice, field, value)
        
        # Update items if provided
        if invoice_update.items is not None:
            # Delete existing items
            await self.db.execute(
                select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
            )
            for item in invoice.items:
                await self.db.delete(item)
            
            # Create new items
            new_items = []
            for item_data in invoice_update.items:
                item_total = item_data.quantity * item_data.unit_price
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=item_data.description,
                    quantity=item_data.quantity,
                    unit_price=item_data.unit_price,
                    total=item_total
                )
                new_items.append(item)
                self.db.add(item)
            
            # Recalculate totals
            totals = self.calculate_invoice_totals(
                invoice_update.items,
                invoice.tax_rate,
                invoice.discount
            )
            
            invoice.subtotal = totals["subtotal"]
            invoice.tax_amount = totals["tax_amount"]
            invoice.total_amount = totals["total_amount"]
        
        await self.db.commit()
        await self.db.refresh(invoice)
        await self.db.refresh(invoice, ['items', 'client'])
        
        # Invalidate cache
        await redis_client.delete(f"invoice:{invoice_id}")
        await redis_client.invalidate_pattern(f"invoices:{user_id}:*")
        
        # Publish event
        await rabbitmq_client.publish(
            "invoices",
            "invoice.updated",
            {
                "invoice_id": str(invoice.id),
                "user_id": str(user_id),
                "status": invoice.status.value
            }
        )
        
        return invoice

    async def delete_invoice(
        self,
        invoice_id: UUID,
        user_id: UUID
    ) -> bool:
        """Delete an invoice."""
        invoice = await self.get_invoice(invoice_id, user_id)
        
        if not invoice:
            return False
        
        # Don't allow deletion of paid invoices
        if invoice.status == InvoiceStatus.PAID:
            raise BadRequestException("Cannot delete paid invoices")
        
        await self.db.delete(invoice)
        await self.db.commit()
        
        # Invalidate cache
        await redis_client.delete(f"invoice:{invoice_id}")
        await redis_client.invalidate_pattern(f"invoices:{user_id}:*")
        
        return True

    async def send_invoice(
        self,
        invoice_id: UUID,
        user_id: UUID
    ) -> Invoice:
        """Mark invoice as sent and trigger email."""
        invoice = await self.get_invoice(invoice_id, user_id)
        
        if not invoice:
            raise NotFoundException("Invoice not found")
        
        if invoice.status != InvoiceStatus.DRAFT:
            raise BadRequestException("Can only send draft invoices")
        
        if not invoice.client or not invoice.client.email:
            raise BadRequestException("Invoice must have a client with email")
        
        # Update status
        invoice.status = InvoiceStatus.SENT
        invoice.sent_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        # Invalidate cache
        await redis_client.delete(f"invoice:{invoice_id}")
        
        # Publish email event
        await rabbitmq_client.publish(
            "emails",
            "email.invoice_sent",
            {
                "invoice_id": str(invoice.id),
                "user_id": str(user_id),
                "client_email": invoice.client.email,
                "client_name": invoice.client.name,
                "invoice_number": invoice.invoice_number,
                "total_amount": float(invoice.total_amount),
                "due_date": invoice.due_date.isoformat()
            },
            priority=8
        )
        
        return invoice

    async def mark_as_paid(
        self,
        invoice_id: UUID,
        user_id: UUID
    ) -> Invoice:
        """Mark invoice as paid."""
        invoice = await self.get_invoice(invoice_id, user_id)
        
        if not invoice:
            raise NotFoundException("Invoice not found")
        
        if invoice.status == InvoiceStatus.PAID:
            raise BadRequestException("Invoice is already paid")
        
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(invoice)
        
        # Invalidate cache
        await redis_client.delete(f"invoice:{invoice_id}")
        await redis_client.invalidate_pattern(f"invoices:{user_id}:*")
        
        # Publish event
        await rabbitmq_client.publish(
            "invoices",
            "invoice.paid",
            {
                "invoice_id": str(invoice.id),
                "user_id": str(user_id),
                "amount": float(invoice.total_amount)
            }
        )
        
        return invoice

    async def get_invoice_summary(self, user_id: UUID) -> dict:
        """Get invoice summary statistics."""
        # Try cache first
        cache_key = f"invoice_summary:{user_id}"
        cached = await redis_client.get_json(cache_key)
        
        if cached:
            return cached
        
        # Query statistics
        result = await self.db.execute(
            select(
                func.count(Invoice.id).label("total_invoices"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("total_revenue"),
                func.sum(
                    case((Invoice.status == InvoiceStatus.PAID, 1), else_=0)
                ).label("paid_invoices"),
                func.sum(
                    case((Invoice.status == InvoiceStatus.SENT, 1), else_=0)
                ).label("pending_invoices"),
                func.sum(
                    case((Invoice.status == InvoiceStatus.OVERDUE, 1), else_=0)
                ).label("overdue_invoices"),
                func.sum(
                    case((Invoice.status == InvoiceStatus.DRAFT, 1), else_=0)
                ).label("draft_invoices")
            ).where(Invoice.user_id == user_id)
        )
        
        stats = result.one()
        
        summary = {
            "total_invoices": stats.total_invoices or 0,
            "total_revenue": float(stats.total_revenue or 0),
            "paid_invoices": stats.paid_invoices or 0,
            "pending_invoices": stats.pending_invoices or 0,
            "overdue_invoices": stats.overdue_invoices or 0,
            "draft_invoices": stats.draft_invoices or 0
        }
        
        # Cache for 10 minutes
        await redis_client.set_json(cache_key, summary, expire=600)
        
        return summary

    async def update_overdue_invoices(self):
        """Update status of overdue invoices (run by background worker)."""
        today = date.today()
        
        result = await self.db.execute(
            select(Invoice).where(
                and_(
                    Invoice.status == InvoiceStatus.SENT,
                    Invoice.due_date < today
                )
            )
        )
        
        overdue_invoices = result.scalars().all()
        
        for invoice in overdue_invoices:
            invoice.status = InvoiceStatus.OVERDUE
            
            # Send reminder
            await rabbitmq_client.publish(
                "emails",
                "email.payment_reminder",
                {
                    "invoice_id": str(invoice.id),
                    "user_id": str(invoice.user_id),
                    "client_email": invoice.client.email if invoice.client else None,
                    "invoice_number": invoice.invoice_number,
                    "total_amount": float(invoice.total_amount),
                    "days_overdue": (today - invoice.due_date).days
                },
                priority=9
            )
        
        if overdue_invoices:
            await self.db.commit()
            logger.info(f"Updated {len(overdue_invoices)} invoices to overdue status")
        
