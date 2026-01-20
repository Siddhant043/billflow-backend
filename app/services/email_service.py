import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Template
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAILS_FROM_EMAIL
        self.from_name = settings.EMAILS_FROM_NAME
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send an email."""
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            
            # Add text version if provided
            if text_content:
                text_part = MIMEText(text_content, "plain")
                message.attach(text_part)
            
            # Add HTML version
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                start_tls=True,
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    def render_invoice_sent_email(
        self,
        client_name: str,
        invoice_number: str,
        total_amount: float,
        due_date: str,
        company_name: str,
        invoice_url: str
    ) -> str:
        """Render invoice sent email template."""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #4F46E5;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background-color: #f9fafb;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }
        .invoice-details {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #4F46E5;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .detail-row:last-child {
            border-bottom: none;
            font-weight: bold;
            font-size: 1.2em;
            color: #4F46E5;
        }
        .button {
            display: inline-block;
            background-color: #4F46E5;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
            font-weight: bold;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>New Invoice from {{ company_name }}</h1>
    </div>
    <div class="content">
        <p>Hello {{ client_name }},</p>
        
        <p>You have received a new invoice from <strong>{{ company_name }}</strong>.</p>
        
        <div class="invoice-details">
            <div class="detail-row">
                <span>Invoice Number:</span>
                <span><strong>{{ invoice_number }}</strong></span>
            </div>
            <div class="detail-row">
                <span>Due Date:</span>
                <span>{{ due_date }}</span>
            </div>
            <div class="detail-row">
                <span>Amount Due:</span>
                <span>${{ "%.2f"|format(total_amount) }}</span>
            </div>
        </div>
        
        <center>
            <a href="{{ invoice_url }}" class="button">View Invoice</a>
        </center>
        
        <p>Please review the invoice and arrange payment by the due date.</p>
        
        <p>If you have any questions about this invoice, please don't hesitate to contact us.</p>
        
        <p>Best regards,<br>
        {{ company_name }}</p>
    </div>
    <div class="footer">
        <p>This is an automated email. Please do not reply directly to this message.</p>
    </div>
</body>
</html>
        """)
        
        return template.render(
            client_name=client_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            due_date=due_date,
            company_name=company_name,
            invoice_url=invoice_url
        )
    
    def render_payment_reminder_email(
        self,
        client_name: str,
        invoice_number: str,
        total_amount: float,
        days_overdue: int,
        company_name: str,
        invoice_url: str
    ) -> str:
        """Render payment reminder email template."""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #DC2626;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background-color: #f9fafb;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }
        .alert-box {
            background-color: #FEE2E2;
            border-left: 4px solid #DC2626;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .invoice-details {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .detail-row:last-child {
            border-bottom: none;
        }
        .button {
            display: inline-block;
            background-color: #DC2626;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
            font-weight: bold;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Payment Reminder</h1>
    </div>
    <div class="content">
        <p>Hello {{ client_name }},</p>
        
        <div class="alert-box">
            <p style="margin: 0; font-weight: bold;">
                ⚠️ This invoice is {{ days_overdue }} day(s) overdue
            </p>
        </div>
        
        <p>This is a friendly reminder that payment for the following invoice is overdue:</p>
        
        <div class="invoice-details">
            <div class="detail-row">
                <span>Invoice Number:</span>
                <span><strong>{{ invoice_number }}</strong></span>
            </div>
            <div class="detail-row">
                <span>Days Overdue:</span>
                <span style="color: #DC2626; font-weight: bold;">{{ days_overdue }} days</span>
            </div>
            <div class="detail-row">
                <span>Amount Due:</span>
                <span style="font-weight: bold; font-size: 1.2em;">${{ "%.2f"|format(total_amount) }}</span>
            </div>
        </div>
        
        <center>
            <a href="{{ invoice_url }}" class="button">Pay Now</a>
        </center>
        
        <p>Please arrange payment as soon as possible. If you have already made this payment, please disregard this reminder.</p>
        
        <p>If you have any questions or concerns regarding this invoice, please contact us immediately.</p>
        
        <p>Best regards,<br>
        {{ company_name }}</p>
    </div>
    <div class="footer">
        <p>This is an automated email. Please do not reply directly to this message.</p>
    </div>
</body>
</html>
        """)
        
        return template.render(
            client_name=client_name,
            invoice_number=invoice_number,
            total_amount=total_amount,
            days_overdue=days_overdue,
            company_name=company_name,
            invoice_url=invoice_url
        )
    
    def render_payment_received_email(
        self,
        client_name: str,
        invoice_number: str,
        amount_paid: float,
        payment_date: str,
        company_name: str
    ) -> str:
        """Render payment received confirmation email."""
        template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #10B981;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .content {
            background-color: #f9fafb;
            padding: 30px;
            border-radius: 0 0 8px 8px;
        }
        .success-box {
            background-color: #D1FAE5;
            border-left: 4px solid #10B981;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }
        .payment-details {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .detail-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .detail-row:last-child {
            border-bottom: none;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>✓ Payment Received</h1>
    </div>
    <div class="content">
        <p>Hello {{ client_name }},</p>
        
        <div class="success-box">
            <h2 style="color: #10B981; margin: 0;">Thank you for your payment!</h2>
        </div>
        
        <p>We have received your payment for invoice <strong>{{ invoice_number }}</strong>.</p>
        
        <div class="payment-details">
            <div class="detail-row">
                <span>Invoice Number:</span>
                <span><strong>{{ invoice_number }}</strong></span>
            </div>
            <div class="detail-row">
                <span>Payment Date:</span>
                <span>{{ payment_date }}</span>
            </div>
            <div class="detail-row">
                <span>Amount Paid:</span>
                <span style="color: #10B981; font-weight: bold; font-size: 1.2em;">${{ "%.2f"|format(amount_paid) }}</span>
            </div>
        </div>
        
        <p>This invoice has been marked as paid in our system. You will receive a receipt shortly.</p>
        
        <p>We appreciate your business and look forward to working with you again.</p>
        
        <p>Best regards,<br>
        {{ company_name }}</p>
    </div>
    <div class="footer">
        <p>This is an automated email. Please do not reply directly to this message.</p>
    </div>
</body>
</html>
        """)
        
        return template.render(
            client_name=client_name,
            invoice_number=invoice_number,
            amount_paid=amount_paid,
            payment_date=payment_date,
            company_name=company_name
        )