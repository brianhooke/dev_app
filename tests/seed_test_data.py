"""
Seed test database with minimal data for Playwright E2E tests.
Run with: python manage.py shell < tests/seed_test_data.py --settings=dev_app.settings.test
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.test')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import (
    XeroInstances, Contacts, Projects, Invoices, 
    Invoice_allocations, XeroAccounts, ReceivedEmail, EmailAttachment
)
from decimal import Decimal

User = get_user_model()

print("🌱 Seeding test database...")

# Check if data already exists
if Invoices.objects.exists() or User.objects.filter(username='testuser').exists():
    print("  ⚠️  Data already exists! Use 'npm run test:reset' to wipe and recreate.")
    print("  Exiting without changes...")
    exit(0)

print("  Database is empty, creating test data...")

# Create test user
print("  Creating test user...")
user = User.objects.create_user(
    username='testuser',
    email='test@example.com',
    password='testpass123'
)

# Create Xero Instance
print("  Creating Xero instance...")
xero_instance = XeroInstances.objects.create(
    xero_name='Test Xero Instance',
    xero_client_id='test-client-id',
    oauth_tenant_id='test-tenant-123'
)

# Create Suppliers (Contacts)
print("  Creating suppliers...")
supplier1 = Contacts.objects.create(
    contact_pk=1,
    name='Test Supplier 1',
    xero_instance=xero_instance,
    xero_contact_id='contact-1',
    email='supplier1@test.com',
    status='active'
)

supplier2 = Contacts.objects.create(
    contact_pk=2,
    name='Test Supplier 2',
    xero_instance=xero_instance,
    xero_contact_id='contact-2',
    email='supplier2@test.com',
    status='active'
)

# Create Project
print("  Creating project...")
project = Projects.objects.create(
    projects_pk=1,
    project='Test Project',
    xero_instance=xero_instance,
    project_type='general'
)

# Create Xero Accounts
print("  Creating Xero accounts...")
account1 = XeroAccounts.objects.create(
    xero_account_pk=1,
    xero_instance=xero_instance,
    account_id='account-1',
    account_name='Test Account 1',
    account_code='1000'
)

account2 = XeroAccounts.objects.create(
    xero_account_pk=2,
    xero_instance=xero_instance,
    account_id='account-2',
    account_name='Test Account 2',
    account_code='2000'
)

# Create test emails and invoices
print("  Creating test invoices...")

# Invoice 1: In Inbox (status=-2)
email1 = ReceivedEmail.objects.create(
    from_address='supplier1@test.com',
    to_address='invoices@test.com',
    subject='Invoice INV-001',
    message_id='msg-001@test.com',
    body_text='Test invoice 1',
    body_html='<p>Test invoice 1</p>',
    received_at=timezone.now(),
    s3_bucket='local',
    s3_key='test/invoice1.pdf'
)

attachment1 = EmailAttachment.objects.create(
    received_email=email1,
    filename='invoice1.pdf',
    s3_bucket='local',
    s3_key='test/invoice1.pdf',
    file_size=1024
)

invoice1 = Invoices.objects.create(
    invoice_status=-2,  # Inbox
    received_email=email1,
    email_attachment=attachment1,
    xero_instance=None,
    contact_pk=None,
    project=None,
    supplier_invoice_number='',
    total_net=None,
    total_gst=None
)

# Invoice 2: In Direct with valid allocations (status=0)
email2 = ReceivedEmail.objects.create(
    received_email_pk=2,
    from_address='supplier2@test.com',
    subject='Invoice INV-002',
    body_text='Test invoice 2',
    body_html='<p>Test invoice 2</p>'
)

attachment2 = EmailAttachment.objects.create(
    email_attachment_pk=2,
    received_email=email2,
    filename='invoice2.pdf',
    s3_bucket='local',
    s3_key='test/invoice2.pdf'
)

invoice2 = Invoices.objects.create(
    invoice_pk=2,
    invoice_status=0,  # Direct
    received_email=email2,
    email_attachment=attachment2,
    xero_instance=xero_instance,
    contact_pk=supplier1,
    project=None,
    supplier_invoice_number='INV-002',
    total_net=Decimal('100.00'),
    total_gst=Decimal('10.00')
)

# Create allocation for invoice2
allocation1 = Invoice_allocations.objects.create(
    invoice_allocations_pk=1,
    invoice_pk=invoice2,
    xero_account=account1,
    amount=Decimal('100.00'),
    gst_amount=Decimal('10.00'),
    notes='Test allocation'
)

# Invoice 3: In Direct without allocations (status=0)
email3 = ReceivedEmail.objects.create(
    received_email_pk=3,
    from_address='supplier1@test.com',
    subject='Invoice INV-003',
    body_text='Test invoice 3',
    body_html='<p>Test invoice 3</p>'
)

attachment3 = EmailAttachment.objects.create(
    email_attachment_pk=3,
    received_email=email3,
    filename='invoice3.pdf',
    s3_bucket='local',
    s3_key='test/invoice3.pdf'
)

invoice3 = Invoices.objects.create(
    invoice_pk=3,
    invoice_status=0,  # Direct
    received_email=email3,
    email_attachment=attachment3,
    xero_instance=xero_instance,
    contact_pk=supplier2,
    project=None,
    supplier_invoice_number='INV-003',
    total_net=Decimal('200.00'),
    total_gst=Decimal('20.00')
)

# Invoice 4: Another inbox invoice
email4 = ReceivedEmail.objects.create(
    received_email_pk=4,
    from_address='supplier2@test.com',
    subject='Invoice INV-004',
    body_text='Test invoice 4',
    body_html='<p>Test invoice 4</p>'
)

attachment4 = EmailAttachment.objects.create(
    email_attachment_pk=4,
    received_email=email4,
    filename='invoice4.pdf',
    s3_bucket='local',
    s3_key='test/invoice4.pdf'
)

invoice4 = Invoices.objects.create(
    invoice_pk=4,
    invoice_status=-2,  # Inbox
    received_email=email4,
    email_attachment=attachment4,
    xero_instance=None,
    contact_pk=None,
    project=None,
    supplier_invoice_number='',
    total_net=None,
    total_gst=None
)

print("\n✅ Test database seeded successfully!")
print(f"   - Users: {User.objects.count()}")
print(f"   - Xero Instances: {XeroInstances.objects.count()}")
print(f"   - Suppliers: {Contacts.objects.count()}")
print(f"   - Projects: {Projects.objects.count()}")
print(f"   - Xero Accounts: {XeroAccounts.objects.count()}")
print(f"   - Invoices (Inbox): {Invoices.objects.filter(invoice_status=-2).count()}")
print(f"   - Invoices (Direct): {Invoices.objects.filter(invoice_status=0).count()}")
print(f"   - Allocations: {Invoice_allocations.objects.count()}")
print("\n🎭 Ready for Playwright tests!")
