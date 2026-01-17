from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from app.models.payment import Payment
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.payment import PaymentCreate
from app.core.rabbitmq import rabbitmq_client
from app.utils.exceptions import NotFoundException, BadRequestException


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_payment(
        self,
        user_id: UUID,
        payment_data: PaymentCreate
    ) -> Payment:
        """Record a payment for an invoice."""
        # Get invoice and verify ownership
        result = await self.db.execute(
            select(Invoice).where(
                and_(
                    Invoice.id == payment_data.invoice_id,
                    Invoice.user_id == user_id
                )
            )
        )
        
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            raise NotFoundException("Invoice not found")
        
        if invoice.status == InvoiceStatus.CANCELLED:
            raise BadRequestException("Cannot add payment to cancelled invoice")
        
        # Calculate total paid
        existing_payments_result = await self.db.execute(
            select(Payment).where(Payment.invoice_id == payment_data.invoice_id)
        )
        existing_payments = existing_payments_result.scalars().all()
        
        total_paid = sum(p.amount for p in existing_payments) + payment_data.amount
        
        if total_paid > invoice.total_amount:
            raise BadRequestException(
                f"Payment amount exceeds invoice total. "
                f"Remaining: {invoice.total_amount - sum(p.amount for p in existing_payments)}"
            )
        
        # Create payment
        payment = Payment(
            invoice_id=payment_data.invoice_id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            transaction_id=payment_data.transaction_id,
            notes=payment_data.notes
        )
        
        self.db.add(payment)
        
        # Update invoice status if fully paid
        if total_paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
            from datetime import datetime
            invoice.paid_at = datetime.utcnow()
            
            # Publish payment completed event
            await rabbitmq_client.publish(
                "payments",
                "payment.completed",
                {
                    "invoice_id": str(invoice.id),
                    "user_id": str(user_id),
                    "amount": float(payment_data.amount),
                    "total_amount": float(invoice.total_amount)
                }
            )
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        return payment
    
    async def get_invoice_payments(
        self,
        invoice_id: UUID,
        user_id: UUID
    ) -> List[Payment]:
        """Get all payments for an invoice."""
        # Verify invoice ownership
        invoice_result = await self.db.execute(
            select(Invoice).where(
                and_(
                    Invoice.id == invoice_id,
                    Invoice.user_id == user_id
                )
            )
        )
        
        if not invoice_result.scalar_one_or_none():
            raise NotFoundException("Invoice not found")
        
        # Get payments
        result = await self.db.execute(
            select(Payment)
            .where(Payment.invoice_id == invoice_id)
            .order_by(Payment.payment_date.desc())
        )
        
        return result.scalars().all()
    
    async def delete_payment(
        self,
        payment_id: UUID,
        user_id: UUID
    ) -> bool:
        """Delete a payment."""
        # Get payment with invoice
        result = await self.db.execute(
            select(Payment)
            .join(Invoice)
            .where(
                and_(
                    Payment.id == payment_id,
                    Invoice.user_id == user_id
                )
            )
        )
        
        payment = result.scalar_one_or_none()
        
        if not payment:
            return False
        
        # Get invoice
        invoice_result = await self.db.execute(
            select(Invoice).where(Invoice.id == payment.invoice_id)
        )
        invoice = invoice_result.scalar_one()
        
        # Update invoice status if it was paid
        if invoice.status == InvoiceStatus.PAID:
            # Check remaining payments
            other_payments_result = await self.db.execute(
                select(Payment).where(
                    and_(
                        Payment.invoice_id == payment.invoice_id,
                        Payment.id != payment_id
                    )
                )
            )
            other_payments = other_payments_result.scalars().all()
            total_remaining = sum(p.amount for p in other_payments)
            
            if total_remaining < invoice.total_amount:
                invoice.status = InvoiceStatus.SENT
                invoice.paid_at = None
        
        await self.db.delete(payment)
        await self.db.commit()
        
        return True