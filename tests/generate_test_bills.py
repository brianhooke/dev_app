#!/usr/bin/env python3
"""
Generate Test Bills for Playwright Tests

This script sends test emails with PDF attachments to test@mail.mason.build
to generate bills for E2E testing.

Usage:
    python tests/generate_test_bills.py

Requirements:
    - SMTP credentials configured
    - Access to send emails
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def create_test_pdf(invoice_number, supplier_name, net_amount, gst_amount):
    """Create a simple test invoice PDF"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, height - 100, "INVOICE")
    
    # Invoice details
    c.setFont("Helvetica", 12)
    y_position = height - 150
    
    c.drawString(100, y_position, f"Invoice Number: {invoice_number}")
    y_position -= 30
    c.drawString(100, y_position, f"Supplier: {supplier_name}")
    y_position -= 30
    c.drawString(100, y_position, f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    y_position -= 50
    
    # Line items
    c.drawString(100, y_position, "Description")
    c.drawString(400, y_position, "Amount")
    y_position -= 5
    c.line(100, y_position, 500, y_position)
    y_position -= 30
    
    c.drawString(100, y_position, "Services rendered")
    c.drawString(400, y_position, f"${net_amount:.2f}")
    y_position -= 50
    
    # Totals
    c.drawString(300, y_position, "Subtotal:")
    c.drawString(400, y_position, f"${net_amount:.2f}")
    y_position -= 20
    c.drawString(300, y_position, "GST (10%):")
    c.drawString(400, y_position, f"${gst_amount:.2f}")
    y_position -= 5
    c.line(300, y_position, 500, y_position)
    y_position -= 20
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, y_position, "Total:")
    c.drawString(400, y_position, f"${net_amount + gst_amount:.2f}")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def send_test_email(invoice_number, supplier_name, net_amount, gst_amount, 
                   from_email, smtp_server, smtp_port, smtp_user, smtp_password):
    """Send a test email with invoice PDF attachment"""
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = 'test@mail.mason.build'
    msg['Subject'] = f'Test Invoice {invoice_number} from {supplier_name}'
    
    # Email body
    body = f"""
    This is a test invoice for Playwright E2E testing.
    
    Invoice Number: {invoice_number}
    Supplier: {supplier_name}
    Net Amount: ${net_amount:.2f}
    GST Amount: ${gst_amount:.2f}
    Total: ${net_amount + gst_amount:.2f}
    
    Please process this invoice.
    """
    msg.attach(MIMEText(body, 'plain'))
    
    # Create and attach PDF
    pdf_data = create_test_pdf(invoice_number, supplier_name, net_amount, gst_amount)
    pdf_attachment = MIMEApplication(pdf_data, _subtype='pdf')
    pdf_attachment.add_header('Content-Disposition', 'attachment', 
                             filename=f'invoice_{invoice_number}.pdf')
    msg.attach(pdf_attachment)
    
    # Send email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"✓ Sent test invoice: {invoice_number} from {supplier_name}")
        return True
    except Exception as e:
        print(f"✗ Failed to send {invoice_number}: {e}")
        return False


def main():
    """Generate test bills for Playwright tests"""
    
    print("=" * 60)
    print("Generating Test Bills for Playwright E2E Tests")
    print("=" * 60)
    print()
    
    # SMTP Configuration - Update these with your credentials
    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    from_email = os.environ.get('FROM_EMAIL', smtp_user)
    
    if not smtp_user or not smtp_password:
        print("ERROR: SMTP credentials not configured!")
        print()
        print("Please set environment variables:")
        print("  export SMTP_SERVER='smtp.gmail.com'")
        print("  export SMTP_PORT='587'")
        print("  export SMTP_USER='your-email@gmail.com'")
        print("  export SMTP_PASSWORD='your-app-password'")
        print("  export FROM_EMAIL='your-email@gmail.com'")
        print()
        return
    
    # Test invoices to create
    test_invoices = [
        # Bills - Inbox (status -2): Unprocessed email bills
        {'invoice_number': 'TEST-INBOX-001', 'supplier': 'Test Supplier A', 'net': 100.00, 'gst': 10.00},
        {'invoice_number': 'TEST-INBOX-002', 'supplier': 'Test Supplier B', 'net': 250.00, 'gst': 25.00},
        {'invoice_number': 'TEST-INBOX-003', 'supplier': 'Test Supplier C', 'net': 500.00, 'gst': 50.00},
        
        # Bills - Direct (status 0): Ready to send to Xero
        {'invoice_number': 'TEST-DIRECT-001', 'supplier': 'Test Supplier D', 'net': 150.00, 'gst': 15.00},
        {'invoice_number': 'TEST-DIRECT-002', 'supplier': 'Test Supplier E', 'net': 300.00, 'gst': 30.00},
        {'invoice_number': 'TEST-DIRECT-003', 'supplier': 'Test Supplier F', 'net': 450.00, 'gst': 45.00},
    ]
    
    print(f"Sending {len(test_invoices)} test invoices to test@mail.mason.build...")
    print()
    
    success_count = 0
    for invoice in test_invoices:
        if send_test_email(
            invoice['invoice_number'],
            invoice['supplier'],
            invoice['net'],
            invoice['gst'],
            from_email,
            smtp_server,
            smtp_port,
            smtp_user,
            smtp_password
        ):
            success_count += 1
    
    print()
    print("=" * 60)
    print(f"Summary: {success_count}/{len(test_invoices)} emails sent successfully")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Wait a few minutes for emails to be processed")
    print("2. Check that bills appear in Bills - Inbox")
    print("3. Move some bills to Bills - Direct (status 0) if needed")
    print("4. Run Playwright tests: npm run test:ui")
    print()


if __name__ == '__main__':
    main()
