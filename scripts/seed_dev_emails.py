"""
Development script to create sample emails with invoices
Simulates emails received via SES → Lambda → Django flow
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.local')
django.setup()

from django.utils import timezone
from core.models import ReceivedEmail, EmailAttachment, Invoices
from datetime import timedelta

print("📧 Creating sample emails for development...")

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
    
    # Create attachments
    for j, attachment_data in enumerate(email_data['attachments'], 1):
        attachment = EmailAttachment.objects.create(
            email=received_email,
            filename=attachment_data['filename'],
            content_type='application/pdf',
            size_bytes=attachment_data['size'],
            s3_bucket='dev-emails',
            s3_key=f'attachments/test-email-{i}-attachment-{j}.pdf'
        )
        print(f"    ✓ Attachment created: {attachment.filename} ({attachment.size_bytes} bytes)")
        
        # Create invoice for each PDF attachment
        invoice = Invoices.objects.create(
            invoice_status=-2,  # Inbox status
            received_email=received_email,
            email_attachment=attachment,
            xero_instance=None,
            contact_pk=None,
            project=None,
            supplier_invoice_number='',
            total_net=None,
            total_gst=None
        )
        print(f"    ✓ Invoice created: ID {invoice.invoice_pk} (status: Inbox)")
        created_count += 1

print(f"\n✅ Successfully created {len(emails_data)} emails with {created_count} invoices!")
print(f"\n📊 Summary:")
print(f"   - Emails: {ReceivedEmail.objects.count()}")
print(f"   - Attachments: {EmailAttachment.objects.count()}")
print(f"   - Invoices in Inbox: {Invoices.objects.filter(invoice_status=-2).count()}")
print(f"\n🎯 Ready to test Bills - Inbox workflow!")
