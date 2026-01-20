import asyncio
import json
import logging
from aio_pika import connect_robust, IncomingMessage
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import settings
from app.services.email_service import EmailService
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


class EmailWorker:
    def __init__(self):
        self.email_service = EmailService()
    
    async def process_invoice_sent(self, message_data: dict):
        """Process invoice sent event."""
        try:
            invoice_id = message_data.get("invoice_id")
            client_email = message_data.get("client_email")
            client_name = message_data.get("client_name")
            invoice_number = message_data.get("invoice_number")
            total_amount = message_data.get("total_amount")
            due_date = message_data.get("due_date")
            user_id = message_data.get("user_id")
            
            # Get user/company info
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.error(f"User not found: {user_id}")
                    return
                
                company_name = user.company_name or user.full_name or "Your Company"
            
            # Generate invoice URL (you'll need to configure this based on your frontend)
            invoice_url = f"{settings.FRONTEND_URL}/invoices/{invoice_id}"
            
            # Render email
            html_content = self.email_service.render_invoice_sent_email(
                client_name=client_name,
                invoice_number=invoice_number,
                total_amount=total_amount,
                due_date=due_date,
                company_name=company_name,
                invoice_url=invoice_url
            )
            
            # Send email
            subject = f"New Invoice {invoice_number} from {company_name}"
            
            await self.email_service.send_email(
                to_email=client_email,
                subject=subject,
                html_content=html_content
            )
            
            logger.info(f"Sent invoice email for {invoice_number} to {client_email}")
            
        except Exception as e:
            logger.error(f"Error processing invoice sent event: {e}")
            raise
    
    async def process_payment_reminder(self, message_data: dict):
        """Process payment reminder event."""
        try:
            invoice_id = message_data.get("invoice_id")
            client_email = message_data.get("client_email")
            invoice_number = message_data.get("invoice_number")
            total_amount = message_data.get("total_amount")
            days_overdue = message_data.get("days_overdue")
            user_id = message_data.get("user_id")
            
            if not client_email:
                logger.warning(f"No client email for invoice {invoice_number}")
                return
            
            # Get user/company info and client name
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User, Invoice)
                    .join(Invoice, Invoice.user_id == User.id)
                    .where(Invoice.id == invoice_id)
                )
                row = result.one_or_none()
                
                if not row:
                    logger.error(f"Invoice not found: {invoice_id}")
                    return
                
                user, invoice = row
                company_name = user.company_name or user.full_name or "Your Company"
                client_name = invoice.client.name if invoice.client else "Valued Customer"
            
            invoice_url = f"{settings.FRONTEND_URL}/invoices/{invoice_id}"
            
            # Render email
            html_content = self.email_service.render_payment_reminder_email(
                client_name=client_name,
                invoice_number=invoice_number,
                total_amount=total_amount,
                days_overdue=days_overdue,
                company_name=company_name,
                invoice_url=invoice_url
            )
            
            # Send email
            subject = f"Payment Reminder: Invoice {invoice_number} is {days_overdue} days overdue"
            
            await self.email_service.send_email(
                to_email=client_email,
                subject=subject,
                html_content=html_content
            )
            
            logger.info(f"Sent payment reminder for {invoice_number} to {client_email}")
            
        except Exception as e:
            logger.error(f"Error processing payment reminder event: {e}")
            raise
    
    async def process_payment_received(self, message_data: dict):
        """Process payment received event."""
        try:
            invoice_id = message_data.get("invoice_id")
            amount = message_data.get("amount")
            user_id = message_data.get("user_id")
            
            # Get invoice and user info
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(User, Invoice)
                    .join(Invoice, Invoice.user_id == User.id)
                    .where(Invoice.id == invoice_id)
                )
                row = result.one_or_none()
                
                if not row:
                    logger.error(f"Invoice not found: {invoice_id}")
                    return
                
                user, invoice = row
                
                if not invoice.client or not invoice.client.email:
                    logger.warning(f"No client email for invoice {invoice.invoice_number}")
                    return
                
                company_name = user.company_name or user.full_name or "Your Company"
                client_name = invoice.client.name
                client_email = invoice.client.email
            
            # Render email
            from datetime import datetime
            html_content = self.email_service.render_payment_received_email(
                client_name=client_name,
                invoice_number=invoice.invoice_number,
                amount_paid=amount,
                payment_date=datetime.now().strftime("%B %d, %Y"),
                company_name=company_name
            )
            
            # Send email
            subject = f"Payment Received for Invoice {invoice.invoice_number}"
            
            await self.email_service.send_email(
                to_email=client_email,
                subject=subject,
                html_content=html_content
            )
            
            logger.info(f"Sent payment confirmation for {invoice.invoice_number} to {client_email}")
            
        except Exception as e:
            logger.error(f"Error processing payment received event: {e}")
            raise
    
    async def callback(self, message: AbstractIncomingMessage):
        """Process incoming message."""
        async with message.process():
            try:
                data = json.loads(message.body.decode())
                routing_key = message.routing_key
                
                logger.info(f"Received message with routing key: {routing_key}")
                
                if routing_key == "email.invoice_sent":
                    await self.process_invoice_sent(data)
                elif routing_key == "email.payment_reminder":
                    await self.process_payment_reminder(data)
                elif routing_key == "email.payment_received":
                    await self.process_payment_received(data)
                else:
                    logger.warning(f"Unknown routing key: {routing_key}")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # Message will be requeued due to nack
                raise
    
    async def start(self):
        """Start the email worker."""
        logger.info("Starting email worker...")
        
        try:
            connection = await connect_robust(settings.RABBITMQ_URL)
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            
            # Declare exchange
            exchange = await channel.declare_exchange(
                "emails",
                "topic",
                durable=True
            )
            
            # Declare queue
            queue = await channel.declare_queue(
                "email_notifications",
                durable=True,
                arguments={"x-max-priority": 10}
            )
            
            # Bind queue to exchange
            await queue.bind(exchange, routing_key="email.*")
            
            # Start consuming
            logger.info("Email worker started and waiting for messages...")
            await queue.consume(self.callback)
            
            # Keep the worker running
            await asyncio.Future()
            
        except Exception as e:
            logger.error(f"Email worker error: {e}")
            raise


async def main():
    """Main function to run the email worker."""
    worker = EmailWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())