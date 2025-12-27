"""
Simplified seed script for test database - creates minimal test data
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.test')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile
from core.models import XeroInstances, Contacts, XeroAccounts, Bills, Projects, Categories, Costing
from decimal import Decimal
from reportlab.pdfgen import canvas
from io import BytesIO

User = get_user_model()

print("🌱 Seeding test database (simplified)...")

# Check if data exists
if Bills.objects.exists():
    print("  ⚠️  Data exists! Use 'npm run test:reset' to wipe.")
    exit(0)

print("  Creating minimal test data...")

# Helper function to create fake PDF
def create_fake_pdf(text):
    """Create a simple PDF with text"""
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, text)
    p.showPage()
    p.save()
    buffer.seek(0)
    return ContentFile(buffer.read())

# Helper function to create fake PNG image
def create_fake_image(text, width=200, height=100):
    """Create a simple PNG image with text"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a new image with a colored background
    img = Image.new('RGB', (width, height), color=(73, 109, 137))
    d = ImageDraw.Draw(img)
    
    # Add text to the image
    d.text((10, 40), text, fill=(255, 255, 255))
    
    # Save to BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return ContentFile(buffer.read())

# User
user = User.objects.create_user('testuser', 'test@test.com', 'testpass123')

# Xero Instance
xero = XeroInstances.objects.create(
    xero_name='Test Xero',
    xero_client_id='test-id'
)

# Suppliers (checked=1 means supplier)
supplier1 = Contacts.objects.create(
    name='Test Supplier 1',
    xero_instance=xero,
    xero_contact_id='contact-1',
    email='supplier1@test.com',
    status='ACTIVE',
    checked=1,  # 1 = supplier
    bank_bsb='123456',
    bank_account_number='12345678',
    tax_number='12345678901'
)

supplier2 = Contacts.objects.create(
    name='Test Supplier 2',
    xero_instance=xero,
    xero_contact_id='contact-2',
    email='supplier2@test.com',
    status='ACTIVE',
    checked=1,  # 1 = supplier
    bank_bsb='654321',
    bank_account_number='87654321',
    tax_number='10987654321'
)

# Xero Accounts (create before projects so we can assign sales accounts)
revenue_account = XeroAccounts.objects.create(
    xero_instance=xero,
    account_id='acc-revenue',
    account_name='Sales Revenue',
    account_code='4000',
    account_type='REVENUE',
    account_status='ACTIVE'
)

# More Xero Accounts
account1 = XeroAccounts.objects.create(
    xero_instance=xero,
    account_id='acc-1',
    account_name='Test Account 1',
    account_code='1000',
    account_type='EXPENSE',
    account_status='ACTIVE'
)

account2 = XeroAccounts.objects.create(
    xero_instance=xero,
    account_id='acc-2',
    account_name='Test Account 2',
    account_code='2000',
    account_type='EXPENSE',
    account_status='ACTIVE'
)

# Projects - 2 active (archived=0), 2 archived (archived=1)
project1 = Projects.objects.create(
    project='Active Project 1',
    xero_instance=xero,
    project_type='development',
    xero_sales_account='4000',
    archived=0
)
# Add background image (actual PNG, not PDF)
project1.background.save('project1_bg.png', create_fake_image('Project 1'))

project2 = Projects.objects.create(
    project='Active Project 2',
    xero_instance=xero,
    project_type='construction',
    xero_sales_account='4000',
    archived=0
)

project3 = Projects.objects.create(
    project='Archived Project 1',
    xero_instance=xero,
    project_type='precast',
    xero_sales_account='4000',
    archived=1
)
# Add background image (actual PNG, not PDF)
project3.background.save('project3_bg.png', create_fake_image('Archived 1'))

project4 = Projects.objects.create(
    project='Archived Project 2',
    xero_instance=xero,
    project_type='pods',
    archived=1
)

# Invoices - 6 in Inbox (enough for all tests that click Send), 2 in Direct (with PDFs)
invoice1 = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice1.pdf.save('test_invoice_1.pdf', create_fake_pdf('Test Invoice 1 - Inbox'))

invoice2 = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice2.pdf.save('test_invoice_2.pdf', create_fake_pdf('Test Invoice 2 - Inbox'))

invoice3_inbox = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice3_inbox.pdf.save('test_invoice_3_inbox.pdf', create_fake_pdf('Test Invoice 3 - Inbox'))

invoice4_inbox = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice4_inbox.pdf.save('test_invoice_4_inbox.pdf', create_fake_pdf('Test Invoice 4 - Inbox'))

invoice5_inbox = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice5_inbox.pdf.save('test_invoice_5_inbox.pdf', create_fake_pdf('Test Invoice 5 - Inbox'))

invoice6_inbox = Bills.objects.create(
    bill_status=-2,  # Inbox
    supplier_bill_number='',
    total_net=None,
    total_gst=None
)
invoice6_inbox.pdf.save('test_invoice_6_inbox.pdf', create_fake_pdf('Test Invoice 6 - Inbox'))

invoice3 = Bills.objects.create(
    bill_status=0,  # Direct
    xero_instance=xero,
    contact_pk=supplier1,
    supplier_bill_number='INV-001',
    total_net=Decimal('100.00'),
    total_gst=Decimal('10.00')
)
invoice3.pdf.save('test_invoice_3.pdf', create_fake_pdf('Test Invoice 3 - Direct'))

invoice4 = Bills.objects.create(
    bill_status=0,  # Direct
    xero_instance=xero,
    contact_pk=supplier2,
    supplier_bill_number='INV-002',
    total_net=Decimal('200.00'),
    total_gst=Decimal('20.00')
)
invoice4.pdf.save('test_invoice_4.pdf', create_fake_pdf('Test Invoice 4 - Direct'))

# Categories and Items (Costings) for Active Project 1 only
# Active Project 2 will have NO items (for testing empty state)

# Create categories for Project 1
cat1 = Categories.objects.create(
    project=project1,
    category='Electrical',
    invoice_category='Electrical',
    order_in_list=1,
    division=0
)

cat2 = Categories.objects.create(
    project=project1,
    category='Plumbing',
    invoice_category='Plumbing',
    order_in_list=2,
    division=0
)

cat3 = Categories.objects.create(
    project=project1,
    category='Carpentry',
    invoice_category='Carpentry',
    order_in_list=3,
    division=0
)

# Create items (Costings) for each category
# Electrical items
Costing.objects.create(
    project=project1,
    category=cat1,
    item='Wiring',
    order_in_list=1,
    xero_account_code='5000',
    contract_budget=Decimal('5000.00'),
    uncommitted_amount=Decimal('0.00'),
    fixed_on_site=Decimal('0.00'),
    sc_invoiced=Decimal('0.00'),
    sc_paid=Decimal('0.00')
)

Costing.objects.create(
    project=project1,
    category=cat1,
    item='Lighting Fixtures',
    order_in_list=2,
    xero_account_code='5001',
    contract_budget=Decimal('3000.00'),
    uncommitted_amount=Decimal('0.00'),
    fixed_on_site=Decimal('0.00'),
    sc_invoiced=Decimal('0.00'),
    sc_paid=Decimal('0.00')
)

# Plumbing items
Costing.objects.create(
    project=project1,
    category=cat2,
    item='Pipes',
    order_in_list=1,
    xero_account_code='5100',
    contract_budget=Decimal('4000.00'),
    uncommitted_amount=Decimal('0.00'),
    fixed_on_site=Decimal('0.00'),
    sc_invoiced=Decimal('0.00'),
    sc_paid=Decimal('0.00')
)

Costing.objects.create(
    project=project1,
    category=cat2,
    item='Fixtures',
    order_in_list=2,
    xero_account_code='5101',
    contract_budget=Decimal('2000.00'),
    uncommitted_amount=Decimal('0.00'),
    fixed_on_site=Decimal('0.00'),
    sc_invoiced=Decimal('0.00'),
    sc_paid=Decimal('0.00')
)

# Carpentry item
Costing.objects.create(
    project=project1,
    category=cat3,
    item='Framing',
    order_in_list=1,
    xero_account_code='5200',
    contract_budget=Decimal('8000.00'),
    uncommitted_amount=Decimal('0.00'),
    fixed_on_site=Decimal('0.00'),
    sc_invoiced=Decimal('0.00'),
    sc_paid=Decimal('0.00')
)

print("\n✅ Test database seeded!")
print(f"   - Users: {User.objects.count()}")
print(f"   - Xero Instances: {XeroInstances.objects.count()}")
print(f"   - Projects (Active): {Projects.objects.filter(archived=0).count()}")
print(f"   - Projects (Archived): {Projects.objects.filter(archived=1).count()}")
print(f"   - Suppliers: {Contacts.objects.count()}")
print(f"   - Xero Accounts: {XeroAccounts.objects.count()}")
print(f"   - Invoices (Inbox): {Bills.objects.filter(bill_status=-2).count()}")
print(f"   - Invoices (Direct): {Bills.objects.filter(bill_status=0).count()}")
print(f"   - Categories: {Categories.objects.count()}")
print(f"   - Items (Costings): {Costing.objects.count()}")
print("\n🎭 Ready for Playwright tests!")
