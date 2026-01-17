from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from datetime import date
import math

from app.core.database import get_db
from app.models.user import User
from app.models.invoice import InvoiceStatus
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceResponse,
    InvoiceWithClient,
    InvoiceListResponse,
    InvoiceSummary
)
from app.services.invoice_service import InvoiceService
from app.services.pdf_service import PDFService
from app.utils.dependencies import get_current_active_user

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    invoice_data: InvoiceCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new invoice."""
    service = InvoiceService(db)
    invoice = await service.create_invoice(current_user.id, invoice_data)
    return invoice


@router.get("/", response_model=InvoiceListResponse)
async def list_invoices(
    status: Optional[InvoiceStatus] = None,
    client_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = Query(None, max_length=255),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all invoices with pagination and filters."""
    service = InvoiceService(db)
    
    skip = (page - 1) * page_size
    
    invoices, total = await service.list_invoices(
        user_id=current_user.id,
        status=status,
        client_id=client_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        skip=skip,
        limit=page_size
    )
    
    # Add client info to response
    invoices_with_client = []
    for invoice in invoices:
        invoice_dict = {
            **invoice.__dict__,
            "client_name": invoice.client.name if invoice.client else None,
            "client_email": invoice.client.email if invoice.client else None,
            "client_company": invoice.client.company if invoice.client else None
        }
        invoices_with_client.append(invoice_dict)
    
    total_pages = math.ceil(total / page_size)
    
    return {
        "invoices": invoices_with_client,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/summary", response_model=InvoiceSummary)
async def get_invoice_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get invoice summary statistics."""
    service = InvoiceService(db)
    summary = await service.get_invoice_summary(current_user.id)
    return summary


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific invoice."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, current_user.id)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    invoice_update: InvoiceUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an invoice."""
    service = InvoiceService(db)
    invoice = await service.update_invoice(invoice_id, current_user.id, invoice_update)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an invoice."""
    service = InvoiceService(db)
    deleted = await service.delete_invoice(invoice_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return None


@router.post("/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send invoice to client via email."""
    service = InvoiceService(db)
    invoice = await service.send_invoice(invoice_id, current_user.id)
    return invoice


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceResponse)
async def mark_invoice_as_paid(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark invoice as paid."""
    service = InvoiceService(db)
    invoice = await service.mark_as_paid(invoice_id, current_user.id)
    return invoice


@router.get("/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Download invoice as PDF."""
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id, current_user.id)
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    # Generate PDF
    pdf_service = PDFService()
    pdf_buffer = pdf_service.generate_invoice_pdf(invoice, current_user)
    
    # Return as streaming response
    headers = {
        'Content-Disposition': f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    }
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers=headers
    )
