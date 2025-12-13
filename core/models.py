from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone
from cryptography.fernet import Fernet
import uuid
import base64

# ============================================================================
# GLOBAL MODELS
# ============================================================================

# SERVICE: projects
class XeroInstances(models.Model):
    xero_instance_pk = models.AutoField(primary_key=True)
    xero_name = models.CharField(max_length=255)
    xero_client_id = models.CharField(max_length=255)
    xero_client_secret_encrypted = models.BinaryField(null=True, blank=True)
    oauth_access_token_encrypted = models.BinaryField(null=True, blank=True)
    oauth_refresh_token_encrypted = models.BinaryField(null=True, blank=True)
    oauth_token_expires_at = models.DateTimeField(null=True, blank=True)
    oauth_tenant_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def _get_cipher(self):
        """Get Fernet cipher using encryption key from settings."""
        key = getattr(settings, 'XERO_ENCRYPTION_KEY', None)
        if not key:
            # Generate a key if not set (for development)
            key = Fernet.generate_key()
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)
    
    def set_client_secret(self, secret):
        """Encrypt and store the client secret."""
        if secret:
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(secret.encode())
            self.xero_client_secret_encrypted = encrypted
    
    def get_client_secret(self):
        """Decrypt and return the client secret."""
        if self.xero_client_secret_encrypted:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(bytes(self.xero_client_secret_encrypted))
            return decrypted.decode()
        return None
    
    def set_oauth_access_token(self, token):
        """Encrypt and store OAuth access token."""
        if token:
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(token.encode())
            self.oauth_access_token_encrypted = encrypted
    
    def get_oauth_access_token(self):
        """Decrypt and return OAuth access token."""
        if self.oauth_access_token_encrypted:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(bytes(self.oauth_access_token_encrypted))
            return decrypted.decode()
        return None
    
    def set_oauth_refresh_token(self, token):
        """Encrypt and store OAuth refresh token."""
        if token:
            cipher = self._get_cipher()
            encrypted = cipher.encrypt(token.encode())
            self.oauth_refresh_token_encrypted = encrypted
    
    def get_oauth_refresh_token(self):
        """Decrypt and return OAuth refresh token."""
        if self.oauth_refresh_token_encrypted:
            cipher = self._get_cipher()
            decrypted = cipher.decrypt(bytes(self.oauth_refresh_token_encrypted))
            return decrypted.decode()
        return None
    
    def __str__(self):
        return self.xero_name

# SERVICE: xero
class XeroAccounts(models.Model):
    xero_account_pk = models.AutoField(primary_key=True)
    xero_instance = models.ForeignKey(
        XeroInstances, 
        on_delete=models.CASCADE, 
        related_name='xero_accounts'
    )
    account_name = models.CharField(max_length=255)
    account_code = models.CharField(max_length=50)
    account_id = models.CharField(max_length=255)  # Xero's AccountID (unique per instance)
    account_status = models.CharField(max_length=50, null=True, blank=True)  # ACTIVE, ARCHIVED, etc.
    account_type = models.CharField(max_length=100, null=True, blank=True)  # EXPENSE, REVENUE, etc.
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    class Meta:
        db_table = 'xero_accounts'
        verbose_name = 'Xero Account'
        verbose_name_plural = 'Xero Accounts'
        unique_together = ['xero_instance', 'account_code']
    def __str__(self):
        return f"{self.account_code} - {self.account_name}"

# SERVICE: projects
class Projects(models.Model):
    PROJECT_TYPE_CHOICES = [
        ('general', 'General'),
        ('development', 'Development'),
        ('construction', 'Construction'),
        ('precast', 'Precast'),
        ('pods', 'Pods'),
    ]
    projects_pk = models.AutoField(primary_key=True)
    project = models.CharField(max_length=100)
    project_type = models.CharField(
        max_length=20,
        choices=PROJECT_TYPE_CHOICES,
        default='general',
        help_text='Type of project determines which app features are available'
    )
    xero_instance = models.ForeignKey(
        XeroInstances, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects'
    )
    xero_sales_account = models.CharField(max_length=255, null=True, blank=True)
    background = models.ImageField(upload_to='project_backgrounds/', null=True, blank=True)
    archived = models.IntegerField(default=0)  # 0 = active, 1 = archived
    project_status = models.IntegerField(default=0)  # 0=tender, 1=won_not_started, 2=started, 3=finished
    manager = models.CharField(max_length=255, null=True, blank=True)
    manager_email = models.CharField(max_length=255, null=True, blank=True)
    contracts_admin_emails = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return self.project

# SERVICE: projects
class SPVData(models.Model):
    address = models.CharField(max_length=255)
    lot_size = models.CharField(max_length=255)
    legal_owner = models.CharField(max_length=255)
    folio_identifier = models.CharField(max_length=255)
    bill_to = models.CharField(max_length=255)
    email = models.EmailField()
    owner_address = models.CharField(max_length=255)
    director_1 = models.CharField(max_length=255)
    director_2 = models.CharField(max_length=255)
    abn = models.CharField(max_length=255)
    acn = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

# SERVICE: documents
class DesignCategories(models.Model):
    design_category_pk = models.AutoField(primary_key=True)
    design_category = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return self.design_category

# SERVICE: documents
class PlanPdfs(models.Model):
    file = models.FileField(upload_to='plans/')
    design_category = models.ForeignKey(DesignCategories, on_delete=models.CASCADE)
    plan_number = models.CharField(max_length=255)
    rev_number = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

# SERVICE: documents
class Letterhead(models.Model):
    letterhead_path = models.FileField(upload_to='letterhead/')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

# SERVICE: documents
class ReportCategories(models.Model):
    report_category_pk = models.AutoField(primary_key=True)
    report_category = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return self.report_category

# SERVICE: documents
class ReportPdfs(models.Model):
    file = models.FileField(upload_to='reports/')
    report_category = models.ForeignKey(ReportCategories, on_delete=models.CASCADE)
    report_reference = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

# SERVICE: documents
class Models_3d(models.Model):
    file = models.FileField(upload_to='3d/')
    filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

# SERVICE: pos
class Po_globals(models.Model):
    reference = models.CharField(max_length=255)
    invoicee = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    project_address = models.CharField(max_length=255)
    ABN = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    note1 = models.CharField(max_length=1000)
    note2 = models.CharField(max_length=1000)
    note3 = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return f"Reference: {self.reference}, Invoicee: {self.invoicee}, Address: {self.address}, ABN: {self.ABN}, Email: {self.email}, Note1: {self.note1}, Note2: {self.note2}, Note3: {self.note3}"

# ============================================================================
# BUILDER/DEVELOPER MODEL SET 1
# ============================================================================

# SERVICE: costings
class Categories(models.Model):
    categories_pk = models.AutoField(primary_key=True)
    project = models.ForeignKey('Projects', on_delete=models.CASCADE, null=True, blank=True)
    division = models.IntegerField()
    category = models.CharField(max_length=100)
    invoice_category = models.CharField(max_length=100)
    order_in_list = models.DecimalField(max_digits=10, decimal_places=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return self.category

# SERVICE: units
class Units(models.Model):
    unit_pk = models.AutoField(primary_key=True)
    unit_name = models.CharField(max_length=50, unique=True)
    order_in_list = models.IntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        ordering = ['order_in_list']
        verbose_name_plural = "Units"
    
    def __str__(self):
        return self.unit_name

# SERVICE: costings
class Costing(models.Model):
    costing_pk = models.AutoField(primary_key=True)
    project = models.ForeignKey('Projects', on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    order_in_list = models.DecimalField(max_digits=10, decimal_places=0, default=1)
    xero_account_code = models.CharField(max_length=100) #per app line item, either to an MDG acc like loan-decora '753.8' or a mb account
    contract_budget = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.ForeignKey(Units, on_delete=models.SET_NULL, null=True, blank=True)
    uncommitted_amount = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted_qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    uncommitted_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    uncommitted_notes = models.CharField(max_length=1000, null=True)
    fixed_on_site = models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced= models.DecimalField(max_digits=10, decimal_places=2)
    sc_paid= models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['project', 'category']),
            models.Index(fields=['category']),
        ]
        ordering = ['category__order_in_list', 'order_in_list']
    
    def __str__(self):
        return f"{self.item} (Category: {self.category})"

# SERVICE: quotes
class Quotes(models.Model):
    quotes_pk = models.AutoField(primary_key=True)
    supplier_quote_number = models.CharField(max_length=255)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='pdfs/', null=True)
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE, null=True)
    project = models.ForeignKey('Projects', on_delete=models.CASCADE, null=True, related_name='quotes')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return f"Quote #{self.quotes_pk} - Cost: {self.total_cost}"

# SERVICE: quotes
class Quote_allocations(models.Model):
    quote_allocations_pk = models.AutoField(primary_key=True)
    quotes_pk = models.ForeignKey(Quotes, on_delete=models.CASCADE, related_name='quote_allocations')
    item = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=1000, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['quotes_pk']),
            models.Index(fields=['item']),
        ]
    
    def __str__(self):
        return f"Quote Allocation - PK: {self.quote_allocations_pk}, Quote PK: {self.quotes_pk.pk}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}"

# SERVICE: documents
class Document_folders(models.Model):
    folder_pk = models.AutoField(primary_key=True)
    project = models.ForeignKey('Projects', on_delete=models.CASCADE, related_name='document_folders')
    folder_name = models.CharField(max_length=255)
    parent_folder = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_index = models.IntegerField(default=0)  # For custom ordering
    
    class Meta:
        ordering = ['order_index', 'folder_name']
    
    def __str__(self):
        return f"{self.folder_name} (Project: {self.project.project})"

class Document_files(models.Model):
    file_pk = models.AutoField(primary_key=True)
    folder = models.ForeignKey(Document_folders, on_delete=models.CASCADE, related_name='files')
    file_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='project_documents/')
    file_type = models.CharField(max_length=50, null=True, blank=True)  # pdf, jpg, png, etc.
    file_size = models.IntegerField(null=True, blank=True)  # in bytes
    uploaded_by = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['file_name']
    
    def __str__(self):
        return f"{self.file_name} in {self.folder.folder_name}"

# SERVICE: bills
class Invoices(models.Model):
    invoice_pk = models.AutoField(primary_key=True)
    # Replaced invoice_division with FK to Projects
    project = models.ForeignKey('Projects', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    xero_instance = models.ForeignKey('XeroInstances', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    invoice_status = models.IntegerField(default=0)  # -2 for unprocessed email bill, -1 for archived, 0 when invoice created, 1 when allocated, 2 when approved, 3 when sent to Xero, 4 when paid, 99 for PO progress claim rejected, 100 for PO progress claim submitted awaiting approval, 101 is approved in PO URL but no invoice uploaded, 102 is approved in PO URL and invoice uploaded, 103 is PO approved, invoice uploaded & approved for payment, 104 if sent to xero
    invoice_xero_id = models.CharField(max_length=255, null=True, blank=True)
    supplier_invoice_number = models.CharField(max_length=255, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    invoice_due_date = models.DateField(null=True, blank=True)
    total_net = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_gst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pdf = models.FileField(upload_to='invoices/', null=True, blank=True)
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE, null=True, blank=True)
    associated_hc_claim = models.ForeignKey('HC_claims', on_delete=models.CASCADE, null=True, blank=True)
    invoice_type = models.IntegerField(default=0, choices=[(2, 'Progress Claim'), (1, 'Direct Cost')])
    received_email = models.ForeignKey('ReceivedEmail', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    email_attachment = models.ForeignKey('EmailAttachment', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    auto_created = models.BooleanField(default=False)  # Track if created automatically from email
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['invoice_status']),
            models.Index(fields=['contact_pk']),
            models.Index(fields=['project']),
            models.Index(fields=['invoice_type']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        if self.total_net:
            return f"Invoices #{self.invoice_pk} - Cost: {self.total_net}"
        return f"Invoices #{self.invoice_pk} - Email: {self.received_email_id if self.received_email else 'N/A'}"

# SERVICE: bills
class Invoice_allocations(models.Model):
    invoice_allocations_pk = models.AutoField(primary_key=True)
    invoice_pk = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name='invoice_allocations')
    item = models.ForeignKey(Costing, on_delete=models.CASCADE, null=True, blank=True)  # Make nullable since we're using Xero accounts now
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=1000, null=True, blank=True)
    allocation_type = models.IntegerField(default=0, choices=[
        (0, "as per invoice_type"),
        (1, "direct cost in progress claim")
    ])
    xero_account = models.ForeignKey('XeroAccounts', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_allocations')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['invoice_pk']),
            models.Index(fields=['item']),
        ]
    
    def __str__(self):
        return f"Invoice Allocation - PK: {self.invoice_allocations_pk}, Invoice PK: {self.invoice_pk.pk}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}, Allocation Type: {self.allocation_type}"

# SERVICE: invoices (claims)
class HC_claims(models.Model):
    hc_claim_pk = models.AutoField(primary_key=True)
    date = models.DateField()
    status = models.IntegerField(default=0) #0 for unapproved, 1 for approved, 2 for sent to Xero, 3 for payment received
    display_id = models.IntegerField(blank=True, null=True)
    invoicee = models.CharField(blank = True, null = True, max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def save(self, *args, **kwargs):
        if not self.display_id:
            # Get the highest display_id in the table
            highest_display_id = HC_claims.objects.order_by('-display_id').values('display_id').first()
            if highest_display_id:
                self.display_id = highest_display_id['display_id'] + 1
            else:
                self.display_id = 1
        super().save(*args, **kwargs)
    def __str__(self):
        return f"HC Claim - PK: {self.hc_claim_pk}, Date: {self.date}, Status: {self.status}, Display ID: {self.display_id}"

# SERVICE: invoices (claims)
class HC_claim_allocations(models.Model):
    hc_claim_allocations_pk = models.AutoField(primary_key=True)
    hc_claim_pk = models.ForeignKey(HC_claims, on_delete=models.CASCADE)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    item = models.ForeignKey(Costing, on_delete=models.CASCADE)
    contract_budget = models.DecimalField(max_digits=10, decimal_places=2)
    working_budget = models.DecimalField(max_digits=10, decimal_places=2)
    committed = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted = models.DecimalField(max_digits=10, decimal_places=2)
    fixed_on_site = models.DecimalField(max_digits=10, decimal_places=2)
    fixed_on_site_previous = models.DecimalField(max_digits=10, decimal_places=2)
    fixed_on_site_this = models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced_previous = models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced = models.DecimalField(max_digits=10, decimal_places=2)
    adjustment = models.DecimalField(max_digits=10, decimal_places=2)
    hc_claimed_previous = models.DecimalField(max_digits=10, decimal_places=2)
    hc_claimed = models.DecimalField(max_digits=10, decimal_places=2)
    qs_claimed_previous = models.DecimalField(max_digits=10, decimal_places=2)
    qs_claimed = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return f"HC Claim Allocation - PK: {self.hc_claim_allocations_pk}, HC Claim PK: {self.hc_claim_pk.pk}, Item: {self.item}, Committed: {self.committed}, Uncommitted: {self.uncommitted}, Fixed on Site: {self.fixed_on_site}, Fixed on Site Previous: {self.fixed_on_site_previous}, Fixed on Site This: {self.fixed_on_site_this}, SC Invoiced: {self.sc_invoiced}, SC Invoiced Previous: {self.sc_invoiced_previous}, Adjustment: {self.adjustment}, HC Claimed: {self.hc_claimed}, HC Claimed Previous: {self.hc_claimed_previous}, QS Claimed: {self.qs_claimed}, QS Claimed Previous: {self.qs_claimed_previous}"

# SERVICE: invoices (variations)
class Hc_variation(models.Model):
    hc_variation_pk = models.AutoField(primary_key=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return f"HC Variation PK: {self.hc_variation_pk} - Date: {self.date}"

# SERVICE: invoices (variations)
class Hc_variation_allocations(models.Model):
    hc_variation_allocation_pk = models.AutoField(primary_key=True)
    hc_variation = models.ForeignKey(Hc_variation, on_delete=models.CASCADE)
    costing = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return f"HC Variation Allocation - Variation PK: {self.hc_variation.hc_variation_pk}, Costing: {self.costing.pk}, Amount: {self.amount}"

# ============================================================================
# BUILDER/DEVELOPER MODEL SET 2
# ============================================================================

# SERVICE: contacts
class Contacts(models.Model):
    contact_pk = models.AutoField(primary_key=True)
    xero_instance = models.ForeignKey(XeroInstances, on_delete=models.CASCADE)
    xero_contact_id = models.CharField(max_length=255)
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=254)
    status = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True, null=True)  # Legacy field - will be deprecated
    first_name = models.CharField(max_length=100, blank=True, null=True)  # From Xero top-level FirstName
    last_name = models.CharField(max_length=100, blank=True, null=True)  # From Xero top-level LastName
    bank_details = models.TextField(blank=True, null=True)  # Legacy field - keeping for reference
    bank_bsb = models.CharField(max_length=20, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_details_verified = models.IntegerField(default=0)  # 0 for no, 1 for yes
    tax_number = models.CharField(max_length=100, blank=True, null=True)
    division = models.IntegerField(null=True, blank=True) #can delete this after "checked" is integrated
    checked = models.IntegerField(default=0)  # 0 for none, 1 for supplier, 2 for client
    
    # Verified fields - independently stored verified contact details
    verified_name = models.CharField(max_length=200, blank=True, null=True)
    verified_email = models.EmailField(max_length=254, blank=True, null=True)
    verified_bank_bsb = models.CharField(max_length=20, blank=True, null=True)
    verified_bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    verified_tax_number = models.CharField(max_length=100, blank=True, null=True)
    verified_notes = models.CharField(max_length=500, blank=True, null=True)
    
    @property
    def verified_status(self):
        """
        Calculate verified status for this contact.
        
        Returns:
            int: 0 = not verified
                 1 = verified and matches current data
                 2 = verified but data has changed
        """
        # Check if any verified fields have data
        has_verified_data = any([
            self.verified_name,
            self.verified_email,
            self.verified_bank_bsb,
            self.verified_bank_account_number
        ])
        
        if not has_verified_data:
            return 0  # Not verified
        
        # Check if verified fields match current fields
        if (self.verified_name == self.name and
            self.verified_email == self.email and
            self.verified_bank_bsb == self.bank_bsb and
            self.verified_bank_account_number == self.bank_account_number):
            return 1  # Verified and matches
        
        return 2  # Verified but data has changed
    
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return self.name

# SERVICE: pos
class Po_orders(models.Model):
    po_order_pk = models.AutoField(primary_key=True)
    po_supplier = models.ForeignKey(Contacts, on_delete=models.CASCADE)
    project = models.ForeignKey(Projects, on_delete=models.CASCADE, null=True, blank=True)
    unique_id = models.CharField(max_length=64, unique=True, db_index=True, null=True, blank=True)  # UUID for shareable URL
    pdf = models.FileField(upload_to='po_pdfs/', null=True, blank=True)  # Stored PDF for record keeping
    po_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    def __str__(self):
        return f"PO Order #{self.po_order_pk} - {self.po_supplier.name}" + (f" ({self.unique_id})" if self.unique_id else "")

# SERVICE: pos
class Po_order_detail(models.Model):
    po_order_detail_pk = models.AutoField(primary_key=True)
    po_order_pk= models.ForeignKey(Po_orders, on_delete=models.CASCADE)
    date = models.DateField()
    costing = models.ForeignKey(Costing, on_delete=models.CASCADE)
    quote = models.ForeignKey(Quotes, on_delete=models.CASCADE, null=True) #if quote is null, then it is a variation.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variation_note = models.CharField(max_length=1000, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    def __str__(self):
        return f"PO Order Detail - PK: {self.po_order_detail_pk}, Date: {self.date}, Amount: {self.amount}, Variation_note: {self.variation_note}"


# ============================================================================
# EMAIL RECEIVING MODELS
# ============================================================================

class ReceivedEmail(models.Model):
    """
    Stores emails received via SES → Lambda → API
    """
    # Email metadata
    from_address = models.EmailField(max_length=255)
    to_address = models.EmailField(max_length=255)
    cc_address = models.TextField(blank=True, default='')
    subject = models.CharField(max_length=500)
    message_id = models.CharField(max_length=255, unique=True)
    
    # Email content
    body_text = models.TextField(blank=True, default='')
    body_html = models.TextField(blank=True, default='')
    
    # Timestamps
    received_at = models.DateTimeField()
    processed_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    # S3 storage locations
    s3_bucket = models.CharField(max_length=100)
    s3_key = models.CharField(max_length=500)  # Location of raw email
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_notes = models.TextField(blank=True, default='')
    
    # Email type/category (for future filtering)
    email_type = models.CharField(
        max_length=50,
        choices=[
            ('bill', 'Bill/Invoice'),
            ('quote', 'Quote'),
            ('receipt', 'Receipt'),
            ('other', 'Other'),
        ],
        default='other'
    )
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at']),
            models.Index(fields=['from_address']),
            models.Index(fields=['message_id']),
        ]
    
    def __str__(self):
        return f"{self.from_address} - {self.subject[:50]}"
    
    def get_s3_url(self):
        """Get S3 URL for raw email"""
        return f"s3://{self.s3_bucket}/{self.s3_key}"
    
    @property
    def attachment_count(self):
        """Count of attachments"""
        return self.attachments.count()


class EmailAttachment(models.Model):
    """
    Stores email attachments uploaded to S3
    """
    email = models.ForeignKey(
        ReceivedEmail,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    
    # File metadata
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.IntegerField()
    
    # S3 storage location
    s3_bucket = models.CharField(max_length=100)
    s3_key = models.CharField(max_length=500)
    
    # Timestamps
    uploaded_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    
    class Meta:
        ordering = ['filename']
    
    def __str__(self):
        return f"{self.filename} ({self.size_bytes} bytes)"
    
    def get_s3_url(self):
        """Get S3 URL for attachment"""
        return f"s3://{self.s3_bucket}/{self.s3_key}"
    
    def get_download_url(self, inline=True):
        """Generate presigned URL for viewing/downloading attachment (or local URL in DEBUG mode)
        
        Args:
            inline: If True, sets Content-Disposition to inline for viewing in browser.
                   If False, sets to attachment for downloading.
        """
        from django.conf import settings
        
        # For local testing, return media URL
        if settings.DEBUG and self.s3_bucket == 'local':
            return f"{settings.MEDIA_URL}{self.s3_key}"
        
        # For production, generate S3 presigned URL
        import boto3
        from botocore.exceptions import ClientError
        
        try:
            s3_client = boto3.client('s3')
            
            params = {
                'Bucket': self.s3_bucket,
                'Key': self.s3_key
            }
            
            # Set Content-Disposition to inline for viewing in browser (not downloading)
            if inline:
                params['ResponseContentDisposition'] = 'inline'
                # Also set content type for PDFs to help browser display correctly
                if self.filename and self.filename.lower().endswith('.pdf'):
                    params['ResponseContentType'] = 'application/pdf'
            
            url = s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=3600  # URL valid for 1 hour
            )
            return url
        except ClientError as e:
            print(f"Error generating presigned URL: {e}")
            return None