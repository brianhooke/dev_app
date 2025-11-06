from django.db import models
from django.core.exceptions import ValidationError
import uuid

# ============================================================================
# GLOBAL MODELS
# ============================================================================

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
    xero_project_id = models.CharField(max_length=255, null=True)
    xero_sales_account = models.CharField(max_length=255, null=True)
    
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

# SERVICE: documents
class DesignCategories(models.Model):
    design_category_pk = models.AutoField(primary_key=True)
    design_category = models.CharField(max_length=100)
    def __str__(self):
        return self.design_category

# SERVICE: documents
class PlanPdfs(models.Model):
    file = models.FileField(upload_to='plans/')
    design_category = models.ForeignKey(DesignCategories, on_delete=models.CASCADE)
    plan_number = models.CharField(max_length=255)
    rev_number = models.CharField(max_length=255)

# SERVICE: documents
class Letterhead(models.Model):
    letterhead_path = models.FileField(upload_to='letterhead/')

# SERVICE: documents
class ReportCategories(models.Model):
    report_category_pk = models.AutoField(primary_key=True)
    report_category = models.CharField(max_length=100)
    def __str__(self):
        return self.report_category

# SERVICE: documents
class ReportPdfs(models.Model):
    file = models.FileField(upload_to='reports/')
    report_category = models.ForeignKey(ReportCategories, on_delete=models.CASCADE)
    report_reference = models.CharField(max_length=255)

# SERVICE: documents
class Models_3d(models.Model):
    file = models.FileField(upload_to='3d/')
    filename = models.CharField(max_length=255)

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
    def __str__(self):
        return f"Reference: {self.reference}, Invoicee: {self.invoicee}, Address: {self.address}, ABN: {self.ABN}, Email: {self.email}, Note1: {self.note1}, Note2: {self.note2}, Note3: {self.note3}"

# ============================================================================
# BUILDER/DEVELOPER MODEL SET 1
# ============================================================================

# SERVICE: costings
class Categories(models.Model):
    categories_pk = models.AutoField(primary_key=True)
    division = models.IntegerField()
    category = models.CharField(max_length=100)
    invoice_category = models.CharField(max_length=100)
    order_in_list = models.DecimalField(max_digits=10, decimal_places=0)
    def __str__(self):
        return self.category

# SERVICE: costings
class Costing(models.Model):
    costing_pk = models.AutoField(primary_key=True)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    xero_account_code = models.CharField(max_length=100) #per app line item, either to an MDG acc like loan-decora '753.8' or a mb account
    contract_budget = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted_notes = models.CharField(max_length=1000, null=True)
    fixed_on_site = models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced= models.DecimalField(max_digits=10, decimal_places=2)
    sc_paid= models.DecimalField(max_digits=10, decimal_places=2)
    def __str__(self):
        return f"{self.item} (Category: {self.category})"

# SERVICE: quotes
class Quotes(models.Model):
    quotes_pk = models.AutoField(primary_key=True)
    supplier_quote_number = models.CharField(max_length=255)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='pdfs/', null=True)
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE, null=True)
    def __str__(self):
        return f"Quote #{self.quotes_pk} - Cost: {self.total_cost}"

# SERVICE: quotes
class Quote_allocations(models.Model):
    quote_allocations_pk = models.AutoField(primary_key=True)
    quotes_pk = models.ForeignKey(Quotes, on_delete=models.CASCADE, related_name='quote_allocations')
    item = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=1000, null=True)
    def __str__(self):
        return f"Quote Allocation - PK: {self.quote_allocations_pk}, Quote PK: {self.quotes_pk.pk}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}"

# SERVICE: bills
class Invoices(models.Model):
    invoice_pk = models.AutoField(primary_key=True)
    invoice_division = models.IntegerField()
    invoice_status = models.IntegerField(default=0)  # 0 when invoice created, 1 when allocated, 2 when sent to Xero, 3 when paid.
    invoice_xero_id = models.CharField(max_length=255, null=True)
    supplier_invoice_number = models.CharField(max_length=255)
    invoice_date = models.DateField()
    invoice_due_date = models.DateField()
    total_net = models.DecimalField(max_digits=10, decimal_places=2)
    total_gst = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='invoices/')
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE)
    associated_hc_claim = models.ForeignKey('HC_claims', on_delete=models.CASCADE, null=True)
    invoice_type = models.IntegerField(default=0, choices=[(2, 'Progress Claim'), (1, 'Direct Cost')])
    def __str__(self):
        return f"Invoices #{self.invoice_pk} - Cost: {self.total_net}"

# SERVICE: bills
class Invoice_allocations(models.Model):
    invoice_allocations_pk = models.AutoField(primary_key=True)
    invoice_pk = models.ForeignKey(Invoices, on_delete=models.CASCADE, related_name='invoice_allocations')
    item = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=1000, null=True)
    allocation_type = models.IntegerField(default=0, choices=[
        (0, "as per invoice_type"),
        (1, "direct cost in progress claim")
    ])
    def __str__(self):
        return f"Invoice Allocation - PK: {self.invoice_allocations_pk}, Invoice PK: {self.invoice_pk.pk}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}, Allocation Type: {self.allocation_type}"

# SERVICE: invoices (claims)
class HC_claims(models.Model):
    hc_claim_pk = models.AutoField(primary_key=True)
    date = models.DateField()
    status = models.IntegerField(default=0) #0 for unapproved, 1 for approved, 2 for sent to Xero, 3 for payment received
    display_id = models.IntegerField(blank=True, null=True)
    invoicee = models.CharField(blank = True, null = True, max_length=255)
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
    def __str__(self):
        return f"HC Claim Allocation - PK: {self.hc_claim_allocations_pk}, HC Claim PK: {self.hc_claim_pk.pk}, Item: {self.item}, Committed: {self.committed}, Uncommitted: {self.uncommitted}, Fixed on Site: {self.fixed_on_site}, Fixed on Site Previous: {self.fixed_on_site_previous}, Fixed on Site This: {self.fixed_on_site_this}, SC Invoiced: {self.sc_invoiced}, SC Invoiced Previous: {self.sc_invoiced_previous}, Adjustment: {self.adjustment}, HC Claimed: {self.hc_claimed}, HC Claimed Previous: {self.hc_claimed_previous}, QS Claimed: {self.qs_claimed}, QS Claimed Previous: {self.qs_claimed_previous}"

# SERVICE: invoices (variations)
class Hc_variation(models.Model):
    hc_variation_pk = models.AutoField(primary_key=True)
    date = models.DateField()
    
    def __str__(self):
        return f"HC Variation PK: {self.hc_variation_pk} - Date: {self.date}"

# SERVICE: invoices (variations)
class Hc_variation_allocations(models.Model):
    hc_variation_allocation_pk = models.AutoField(primary_key=True)
    hc_variation = models.ForeignKey(Hc_variation, on_delete=models.CASCADE)
    costing = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=200, blank=True, null=True)
    
    def __str__(self):
        return f"HC Variation Allocation - Variation PK: {self.hc_variation.hc_variation_pk}, Costing: {self.costing.pk}, Amount: {self.amount}"

# ============================================================================
# BUILDER/DEVELOPER MODEL SET 2
# ============================================================================

# SERVICE: contacts
class Contacts(models.Model):
    contact_pk = models.AutoField(primary_key=True)
    xero_contact_id = models.CharField(max_length=255)
    division = models.IntegerField() #can delete this after "checked" is integrated
    checked = models.IntegerField(default=0)  # 0 for none, 1 for supplier, 2 for client
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField(max_length=254)
    def __str__(self):
        return self.contact_name

# SERVICE: pos
class Po_orders(models.Model):
    po_order_pk = models.AutoField(primary_key=True)
    po_supplier = models.ForeignKey(Contacts, on_delete=models.CASCADE)
    po_sent = models.BooleanField(default=False)
    po_note_1 = models.CharField(max_length=1000)
    po_note_2 = models.CharField(max_length=1000)
    po_note_3 = models.CharField(max_length=1000)
    def __str__(self):
        return f"PO Order - PK: {self.pk}, PO Note 1: {self.po_note_1}, PO Note 2: {self.po_note_2}, PO Note 3: {self.po_note_3}"

# SERVICE: pos
class Po_order_detail(models.Model):
    po_order_detail_pk = models.AutoField(primary_key=True)
    po_order_pk= models.ForeignKey(Po_orders, on_delete=models.CASCADE)
    date = models.DateField()
    costing = models.ForeignKey(Costing, on_delete=models.CASCADE)
    quote = models.ForeignKey(Quotes, on_delete=models.CASCADE, null=True) #if quote is null, then it is a variation.
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    variation_note = models.CharField(max_length=1000, null=True)
    def __str__(self):
        return f"PO Order Detail - PK: {self.po_order_detail_pk}, Date: {self.date}, Amount: {self.amount}, Variation_note: {self.variation_note}"