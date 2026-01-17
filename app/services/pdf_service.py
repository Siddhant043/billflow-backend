from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from io import BytesIO
from datetime import datetime
from typing import Optional

from app.models.invoice import Invoice
from app.models.user import User


class PDFService:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
        ))
        
        self.styles.add(ParagraphStyle(
            name='InvoiceNumber',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=colors.HexColor('#666666'),
            spaceAfter=20,
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='RightAlign',
            parent=self.styles['Normal'],
            alignment=TA_RIGHT,
        ))
    
    def generate_invoice_pdf(
        self,
        invoice: Invoice,
        user: User,
        output_path: Optional[str] = None
    ) -> BytesIO:
        """Generate PDF for an invoice."""
        # Create buffer or file
        if output_path:
            buffer = open(output_path, 'wb')
        else:
            buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Container for PDF elements
        elements = []
        
        # Add company header
        elements.append(Paragraph(
            user.company_name or user.full_name or "Your Company",
            self.styles['CustomTitle']
        ))
        
        if user.address:
            elements.append(Paragraph(user.address, self.styles['Normal']))
            elements.append(Spacer(1, 6))
        
        if user.email:
            elements.append(Paragraph(f"Email: {user.email}", self.styles['Normal']))
        
        if user.phone:
            elements.append(Paragraph(f"Phone: {user.phone}", self.styles['Normal']))
        
        elements.append(Spacer(1, 20))
        
        # Invoice number and dates
        invoice_info_data = [
            ['INVOICE', invoice.invoice_number],
            ['Issue Date:', invoice.issue_date.strftime('%B %d, %Y')],
            ['Due Date:', invoice.due_date.strftime('%B %d, %Y')],
            ['Status:', invoice.status.value.upper()]
        ]
        
        invoice_info_table = Table(invoice_info_data, colWidths=[2*inch, 3*inch])
        invoice_info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 16),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#666666')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(invoice_info_table)
        elements.append(Spacer(1, 30))
        
        # Bill To section
        elements.append(Paragraph("BILL TO", self.styles['SectionHeader']))
    
        if invoice.client:
            elements.append(Paragraph(invoice.client.name, self.styles['Normal']))
        
        if invoice.client.company:
            elements.append(Paragraph(invoice.client.company, self.styles['Normal']))
        
        if invoice.client.email:
            elements.append(Paragraph(invoice.client.email, self.styles['Normal']))
        
        if invoice.client.address:
            elements.append(Paragraph(invoice.client.address, self.styles['Normal']))
    
        elements.append(Spacer(1, 30))
    
        # Items table
        items_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]
    
        for item in invoice.items:
            items_data.append([
                item.description,
                f"{float(item.quantity):.2f}",
                f"${float(item.unit_price):.2f}",
                f"${float(item.total):.2f}"
            ])
    
        items_table = Table(
            items_data,
            colWidths=[3.5*inch, 1*inch, 1.25*inch, 1.25*inch]
        )
    
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#333333')),
        
            # Alignment
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        
            # Lines
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#1a1a1a')),
            ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        
            # Padding
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
    
        elements.append(items_table)
        elements.append(Spacer(1, 20))
    
        # Totals
        totals_data = [
            ['Subtotal:', f"${float(invoice.subtotal):.2f}"],
        ]
    
        if invoice.discount > 0:
            totals_data.append(['Discount:', f"-${float(invoice.discount):.2f}"])
    
        if invoice.tax_amount > 0:
            totals_data.append([
                f'Tax ({float(invoice.tax_rate):.1f}%):',
                f"${float(invoice.tax_amount):.2f}"
            ])
    
            totals_data.append(['TOTAL:', f"${float(invoice.total_amount):.2f}"])
    
            totals_table = Table(totals_data, colWidths=[5*inch, 2*inch])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -2), 10),
                ('FONTSIZE', (0, -1), (-1, -1), 14),
                ('TEXTCOLOR', (0, 0), (-1, -2), colors.HexColor('#666666')),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a1a1a')),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#1a1a1a')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -2), 6),
                ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
            ]))
    
            elements.append(totals_table)
    
            # Notes and terms
            if invoice.notes:
                elements.append(Spacer(1, 30))
                elements.append(Paragraph("NOTES", self.styles['SectionHeader']))
                elements.append(Paragraph(invoice.notes, self.styles['Normal']))
    
            if invoice.terms:
                elements.append(Spacer(1, 20))
                elements.append(Paragraph("TERMS & CONDITIONS", self.styles['SectionHeader']))
                elements.append(Paragraph(invoice.terms, self.styles['Normal']))
    
            # Footer
            elements.append(Spacer(1, 30))
            footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y')}"
            footer_style = ParagraphStyle(
                name='Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#999999'),
                alignment=TA_CENTER
            )
            elements.append(Paragraph(footer_text, footer_style))
    
            # Build PDF
            doc.build(elements)
    
            # Return buffer
            if not output_path:
                buffer.seek(0)
                return buffer
            else:
                buffer.close()
                return None