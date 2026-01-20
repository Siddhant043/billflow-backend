import asyncio
import logging
from datetime import date, timedelta
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.rabbitmq import rabbitmq_client
from app.models.invoice import Invoice, InvoiceStatus
from app.services.invoice_service import InvoiceService

logger = logging.getLogger(__name__)


class PaymentWorker:
    def __init__(self):
        self.check_interval = 3600  # Check every hour
    
    async def check_overdue_invoices(self):
        """Check for overdue invoices and update status."""
        try:
            async with AsyncSessionLocal() as db:
                service = InvoiceService(db)
                await service.update_overdue_invoices()
                
            logger.info("Completed overdue invoices check")
            
        except Exception as e:
            logger.error(f"Error checking overdue invoices: {e}")
    
    async def send_upcoming_due_reminders(self):
        """Send reminders for invoices due in 3 days."""
        try:
            today = date.today()
            due_soon_date = today + timedelta(days=3)
            
            async with AsyncSessionLocal() as db:
                # Find invoices due in 3 days
                result = await db.execute(
                    select(Invoice).where(
                        and_(
                            Invoice.status == InvoiceStatus.SENT,
                            Invoice.due_date == due_soon_date
                        )
                    )
                )
                
                invoices = result.scalars().all()
                
                for invoice in invoices:
                    if invoice.client and invoice.client.email:
                        # Publish reminder event
                        await rabbitmq_client.publish(
                            "emails",
                            "email.payment_reminder",
                            {
                                "invoice_id": str(invoice.id),
                                "user_id": str(invoice.user_id),
                                "client_email": invoice.client.email,
                                "invoice_number": invoice.invoice_number,
                                "total_amount": float(invoice.total_amount),
                                "days_overdue": -3  # Negative means due soon
                            },
                            priority=7
                        )
                
                logger.info(f"Sent {len(invoices)} upcoming due reminders")
                
        except Exception as e:
            logger.error(f"Error sending due soon reminders: {e}")
    
    async def send_weekly_overdue_reminders(self):
        """Send weekly reminders for overdue invoices."""
        try:
            today = date.today()
            
            async with AsyncSessionLocal() as db:
                # Find overdue invoices
                result = await db.execute(
                    select(Invoice).where(
                        Invoice.status == InvoiceStatus.OVERDUE
                    )
                )
                
                invoices = result.scalars().all()
                
                for invoice in invoices:
                    days_overdue = (today - invoice.due_date).days
                    
                    # Send reminder weekly (every 7 days)
                    if days_overdue % 7 == 0 and invoice.client and invoice.client.email:
                        await rabbitmq_client.publish(
                            "emails",
                            "email.payment_reminder",
                            {
                                "invoice_id": str(invoice.id),
                                "user_id": str(invoice.user_id),
                                "client_email": invoice.client.email,
                                "invoice_number": invoice.invoice_number,
                                "total_amount": float(invoice.total_amount),
                                "days_overdue": days_overdue
                            },
                            priority=9
                        )
                
                logger.info(f"Processed {len(invoices)} overdue invoices for weekly reminders")
                
        except Exception as e:
            logger.error(f"Error sending weekly overdue reminders: {e}")
    
    async def start(self):
        """Start the payment worker."""
        logger.info("Starting payment worker...")
        
        # Connect to RabbitMQ
        await rabbitmq_client.connect()
        
        while True:
            try:
                # Run periodic tasks
                await self.check_overdue_invoices()
                await self.send_upcoming_due_reminders()
                await self.send_weekly_overdue_reminders()
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Payment worker error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error


async def main():
    """Main function to run the payment worker."""
    worker = PaymentWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())