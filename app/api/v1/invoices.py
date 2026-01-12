from fastapi import APIRouter, Body
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate

router = APIRouter()

@router.get("/invoices")
async def get_invoices():
    return {"message": "Get invoices"}

@router.post("/invoices")
async def create_invoice(invoice: InvoiceCreate = Body(...)):
    return {"message": "Invoice created"}

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int):
    return {"message": "Get invoice"}

@router.put("/invoices/{invoice_id}")
async def update_invoice(invoice_id: int, invoice: InvoiceUpdate = Body(...)):
    return {"message": "Update invoice"}

@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: int):
    return {"message": "Delete invoice"}
