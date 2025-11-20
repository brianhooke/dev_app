"""
Simplified seed script for test database - creates minimal test data
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.test')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import XeroInstances, Contacts, XeroAccounts, Invoices
from decimal import Decimal

User = get_user_model()

print("🌱 Seeding test database (simplified)...")

# Check if data exists
if Invoices.objects.exists():
    print("  ⚠️  Data exists! Use 'npm run test:reset' to wipe.")
    exit(0)

print("  Creating minimal test data...")

# User
user = User.objects.create_user('testuser', 'test@test.com', 'testpass123')

# Xero Instance
xero = XeroInstances.objects.create(
    xero_name='Test Xero',
    xero_client_id='test-id'
)

# Suppliers
supplier1 = Contacts.objects.create(
    name='Test Supplier 1',
    xero_instance=xero,
    xero_contact_id='contact-1',
    email='supplier1@test.com',
    status='active'
)

supplier2 = Contacts.objects.create(
    name='Test Supplier 2',
    xero_instance=xero,
    xero_contact_id='contact-2',
    email='supplier2@test.com',
    status='active'
)

# Xero Accounts
account1 = XeroAccounts.objects.create(
    xero_instance=xero,
    account_id='acc-1',
    account_name='Test Account 1',
    account_code='1000'
)

account2 = XeroAccounts.objects.create(
    xero_instance=xero,
    account_id='acc-2',
    account_name='Test Account 2',
    account_code='2000'
)

# Invoices - 2 in Inbox, 2 in Direct
Invoices.objects.create(
    invoice_status=-2,  # Inbox
    supplier_invoice_number='',
    total_net=None,
    total_gst=None
)

Invoices.objects.create(
    invoice_status=-2,  # Inbox
    supplier_invoice_number='',
    total_net=None,
    total_gst=None
)

Invoices.objects.create(
    invoice_status=0,  # Direct
    xero_instance=xero,
    contact_pk=supplier1,
    supplier_invoice_number='INV-001',
    total_net=Decimal('100.00'),
    total_gst=Decimal('10.00')
)

Invoices.objects.create(
    invoice_status=0,  # Direct
    xero_instance=xero,
    contact_pk=supplier2,
    supplier_invoice_number='INV-002',
    total_net=Decimal('200.00'),
    total_gst=Decimal('20.00')
)

print("\n✅ Test database seeded!")
print(f"   - Users: {User.objects.count()}")
print(f"   - Xero Instances: {XeroInstances.objects.count()}")
print(f"   - Suppliers: {Contacts.objects.count()}")
print(f"   - Xero Accounts: {XeroAccounts.objects.count()}")
print(f"   - Invoices (Inbox): {Invoices.objects.filter(invoice_status=-2).count()}")
print(f"   - Invoices (Direct): {Invoices.objects.filter(invoice_status=0).count()}")
print("\n🎭 Ready for Playwright tests!")
