"""
Development script to create sample emails with invoices
Simulates emails received via SES → Lambda → Django flow
Creates local PDF files for development (no S3 required)
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.local')
django.setup()

from django.utils import timezone
from django.conf import settings
from core.models import ReceivedEmail, EmailAttachment, Bills
from datetime import timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def create_dummy_pdf(filepath, title, content_lines):
    """Create a simple PDF file for development"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, title)
    
    # Content
    c.setFont("Helvetica", 12)
    y = height - 100
    for line in content_lines:
        c.drawString(50, y, line)
        y -= 20
    
    c.save()
    return os.path.getsize(filepath)

print("📧 Creating sample emails for development...")

# Create media directory for dev emails if it doesn't exist
dev_emails_dir = os.path.join(settings.MEDIA_ROOT, 'dev_emails')
os.makedirs(dev_emails_dir, exist_ok=True)
print(f"  Using local storage: {dev_emails_dir}")

# Sample email data
emails_data = [
    {
        'from': 'accounts@acmesupplies.com.au',
        'subject': 'Invoice #INV-2024-001',
        'body_text': """Dear Accounts Team,

Please find attached our invoice for recent supplies delivered to your site.

Invoice Details:
- Invoice Number: INV-2024-001
- Amount: $1,250.00 (inc GST)
- Due Date: 30 days from invoice date

Please process at your earliest convenience.

Best regards,
Sarah Johnson
Accounts Receivable
Acme Supplies Pty Ltd
Phone: (02) 9876 5432
""",
        'attachments': [
            {'filename': 'INV-2024-001.pdf', 'size': 45678},
            {'filename': 'Delivery_Docket.pdf', 'size': 23456}
        ]
    },
    {
        'from': 'billing@builderswarehouse.com.au',
        'subject': 'Tax Invoice - Order #45892',
        'body_text': """Dear Sir/Madam,

Thank you for your recent order. Please find attached:
1. Tax Invoice
2. Itemised Statement

Order Number: 45892
Invoice Total: $3,450.00 (inc GST)
Payment Terms: 14 days

If you have any queries, please don't hesitate to contact our accounts department.

Kind regards,
Michael Chen
Builders Warehouse
accounts@builderswarehouse.com.au
""",
        'attachments': [
            {'filename': 'Tax_Invoice_45892.pdf', 'size': 67890},
            {'filename': 'Statement_45892.pdf', 'size': 34567}
        ]
    },
    {
        'from': 'invoices@electricalsupplies.net.au',
        'subject': 'Monthly Account - November 2024',
        'body_text': """Good afternoon,

Please find attached our monthly account statement and tax invoice for November 2024.

Account Summary:
- Previous Balance: $0.00
- New Charges: $2,180.00
- Total Due: $2,180.00

Payment is due within 30 days. We accept direct deposit or credit card.

Please remit payment to:
BSB: 062-000
Account: 1234 5678

Thank you for your continued business.

Regards,
Amanda Wilson
Credit Control Manager
Electrical Supplies Co.
Ph: 1300 555 789
""",
        'attachments': [
            {'filename': 'Monthly_Statement_Nov2024.pdf', 'size': 56789},
            {'filename': 'Tax_Invoice_Nov2024.pdf', 'size': 45678}
        ]
    }
]

# Create emails and attachments
created_count = 0
for i, email_data in enumerate(emails_data, 1):
    print(f"\n  Creating email {i}/3: {email_data['subject']}")
    
    # Create received email
    received_email = ReceivedEmail.objects.create(
        from_address=email_data['from'],
        to_address='test@mail.mason.build',
        cc_address='',
        subject=email_data['subject'],
        message_id=f'<test-{i}-{timezone.now().timestamp()}@mason.build>',
        body_text=email_data['body_text'],
        body_html=f'<html><body><pre>{email_data["body_text"]}</pre></body></html>',
        received_at=timezone.now() - timedelta(hours=i),
        s3_bucket='dev-emails',
        s3_key=f'emails/test-email-{i}.eml',
        is_processed=True,
        email_type='bill'
    )
    
    print(f"    ✓ Email created: {received_email.message_id}")
    
    # Create attachments with actual PDF files
    for j, attachment_data in enumerate(email_data['attachments'], 1):
        # Create actual PDF file locally
        pdf_filename = attachment_data['filename']
        pdf_path = os.path.join(dev_emails_dir, f'email-{i}-{pdf_filename}')
        
        # Generate PDF content based on filename
        if 'invoice' in pdf_filename.lower():
            pdf_content = [
                f"Invoice Number: {pdf_filename.replace('.pdf', '')}",
                f"Date: {timezone.now().strftime('%d/%m/%Y')}",
                "",
                "Bill To: Mason Build",
                "From: " + email_data['from'],
                "",
                "Description                    Amount",
                "Building Materials            $1,000.00",
                "Labour                          $250.00",
                "                              ----------",
                "Subtotal:                     $1,250.00",
                "GST (10%):                      $125.00",
                "Total:                        $1,375.00",
            ]
        else:
            pdf_content = [
                f"Document: {pdf_filename.replace('.pdf', '')}",
                f"Date: {timezone.now().strftime('%d/%m/%Y')}",
                "",
                "This is a supporting document",
                "for the invoice.",
            ]
        
        file_size = create_dummy_pdf(pdf_path, pdf_filename.replace('.pdf', ''), pdf_content)
        
        # Store relative path from MEDIA_ROOT
        relative_path = os.path.relpath(pdf_path, settings.MEDIA_ROOT)
        
        attachment = EmailAttachment.objects.create(
            email=received_email,
            filename=pdf_filename,
            content_type='application/pdf',
            size_bytes=file_size,
            s3_bucket='local',  # Use 'local' to indicate local storage
            s3_key=relative_path  # Store relative path for local files
        )
        print(f"    ✓ PDF created: {pdf_path}")
        print(f"    ✓ Attachment created: {attachment.filename} ({attachment.size_bytes} bytes)")
        
        # Create invoice for each PDF attachment
        invoice = Bills.objects.create(
            bill_status=-2,  # Inbox status
            received_email=received_email,
            email_attachment=attachment,
            xero_instance=None,
            contact_pk=None,
            project=None,
            supplier_bill_number='',
            total_net=None,
            total_gst=None
        )
        print(f"    ✓ Invoice created: ID {invoice.bill_pk} (status: Inbox)")
        created_count += 1

print(f"\n✅ Successfully created {len(emails_data)} emails with {created_count} invoices!")
print(f"\n📊 Summary:")
print(f"   - Emails: {ReceivedEmail.objects.count()}")
print(f"   - Attachments: {EmailAttachment.objects.count()}")
print(f"   - Invoices in Inbox: {Bills.objects.filter(bill_status=-2).count()}")
print(f"\n🎯 Ready to test Bills - Inbox workflow!")
