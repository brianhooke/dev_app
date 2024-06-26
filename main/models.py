from django.db import models
from django.core.exceptions import ValidationError
import uuid

class Categories(models.Model):
    categories_pk = models.AutoField(primary_key=True)
    category = models.CharField(max_length=100)
    order_in_list = models.DecimalField(max_digits=10, decimal_places=0)
    def __str__(self):
        return self.category

class Costing(models.Model):
    costing_pk = models.AutoField(primary_key=True)
    category = models.ForeignKey(Categories, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    contract_budget = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted = models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced= models.DecimalField(max_digits=10, decimal_places=2)
    sc_paid= models.DecimalField(max_digits=10, decimal_places=2)
    # notes = models.CharField(max_length=500)
    def __str__(self):
        return f"{self.item} (Category: {self.category})"
    # def __str__(self):
    #     return f"Category: {self.category}, Item: {self.item}, Budget: {self.contract_budget}, Uncommitted: {self.uncommitted}, SC Invoiced: {self.sc_invoiced}, SC Paid: {self.sc_paid}"

class Projects(models.Model):
    projects_pk = models.AutoField(primary_key=True)
    project = models.CharField(max_length=100)
    def __str__(self):
        return self.project
    
class DesignCategories(models.Model):
    design_category_pk = models.AutoField(primary_key=True)
    design_category = models.CharField(max_length=100)
    def __str__(self):
        return self.design_category

class PlanPdfs(models.Model):
    file = models.FileField(upload_to='plans/')
    design_category = models.ForeignKey(DesignCategories, on_delete=models.CASCADE)
    plan_number = models.CharField(max_length=255)
    rev_number = models.CharField(max_length=255)  # Changed from IntegerField to CharField

class ReportCategories(models.Model):
    report_category_pk = models.AutoField(primary_key=True)
    report_category = models.CharField(max_length=100)
    def __str__(self):
        return self.report_category

class ReportPdfs(models.Model):
    file = models.FileField(upload_to='reports/')
    report_category = models.ForeignKey(ReportCategories, on_delete=models.CASCADE)
    report_reference = models.CharField(max_length=255)

class Contacts(models.Model):
    contact_pk = models.AutoField(primary_key=True)
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField(max_length=254)
    # contact_id = models.CharField(max_length=36, default=uuid.uuid4, editable=False)
    # contact_selectable = models.BooleanField(default=True)
    def __str__(self):
        return self.contact_name

class Quotes(models.Model):
    quotes_pk = models.AutoField(primary_key=True)
    supplier_quote_number = models.CharField(max_length=255)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='pdfs/')
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE)
    def __str__(self):
        return f"Quote #{self.quotes_pk} - Cost: {self.total_cost}"
    # def __str__(self):
    #     return f"Quote - PK: {self.quotes_pk}, Total Cost: {self.total_cost}, Contact PK: {self.contact_pk.pk}, PDF: {self.pdf}"

class Quote_allocations(models.Model):
    quote_allocations_pk = models.AutoField(primary_key=True)
    quotes_pk = models.ForeignKey(Quotes, on_delete=models.CASCADE)
    item = models.ForeignKey(Costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=100, null=True)
    def __str__(self):
        return f"Quote Allocation - PK: {self.quote_allocations_pk}, Quote PK: {self.quotes_pk.pk}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}"
    
class Models_3d(models.Model):
    file = models.FileField(upload_to='3d/')
    filename = models.CharField(max_length=255)

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
    
class Po_orders(models.Model):
    po_order_pk = models.AutoField(primary_key=True)
    po_supplier = models.ForeignKey(Contacts, on_delete=models.CASCADE)
    po_sent = models.BooleanField(default=False)
    po_note_1 = models.CharField(max_length=1000)
    po_note_2 = models.CharField(max_length=1000)
    po_note_3 = models.CharField(max_length=1000)
    def __str__(self):
        return f"PO Order - PK: {self.pk}, PO Note 1: {self.po_note_1}, PO Note 2: {self.po_note_2}, PO Note 3: {self.po_note_3}"

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
    # def __str__(self):
    #     return f"PO Order Detail - PK: {self.po_order_detail_pk}, PO Order PK: {self.po_order_pk.pk}, Date: {self.date}, Costing: {self.costing}, Quote: {self.quote}, Amount: {self.amount}"

class Build_categories(models.Model):
    category = models.CharField(max_length=100)
    order_in_list = models.DecimalField(max_digits=10, decimal_places=0)
    def __str__(self):
        return self.category

class Build_costing(models.Model):
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Build_categories, on_delete=models.CASCADE)
    item = models.CharField(max_length=100)
    contract_budget = models.DecimalField(max_digits=10, decimal_places=2)
    uncommitted = models.DecimalField(max_digits=10, decimal_places=2)
    complete_on_site = models.DecimalField(max_digits=10, decimal_places=2)
    hc_next_claim= models.DecimalField(max_digits=10, decimal_places=2)
    hc_received= models.DecimalField(max_digits=10, decimal_places=2)
    sc_invoiced= models.DecimalField(max_digits=10, decimal_places=2)
    sc_paid= models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=500)
    def __str__(self):
        return f"Category: {self.category}, Item: {self.item}, Budget: {self.contract_budget}, Uncommitted: {self.uncommitted}, Complete On Site: {self.complete_on_site}, HC Next Claim: {self.hc_next_claim}, HC Received: {self.hc_received}, SC Invoiced: {self.sc_invoiced}, SC Paid: {self.sc_paid}, Notes: {self.notes}"

class Committed_quotes(models.Model):
    quote = models.AutoField(primary_key=True)
    supplier_quote_number = models.CharField(max_length=255)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='pdfs/')
    contact_pk = models.ForeignKey('Contacts', on_delete=models.CASCADE)
    def __str__(self):
        return f"Quote: {self.quote}, Total Cost: {self.total_cost}, Contact PK: {self.contact_pk}, PDF: {self.pdf}"
       
class Committed_allocations(models.Model): #For Build Items
    quote = models.ForeignKey(Committed_quotes, on_delete=models.CASCADE)
    item = models.ForeignKey(Build_costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=100, null=True)
    def __str__(self):
        return f"Quote: {self.quote}, Item: {self.item}, Amount: {self.amount}, Notes: {self.notes}"
    
class Hc_claims(models.Model):
    hc_claim = models.AutoField(primary_key=True)
    def __str__(self):
        return f"HC Claim: {self.hc_claim}"

class Hc_claim_lines(models.Model):
    hc_claim = models.ForeignKey(Hc_claims, on_delete=models.CASCADE)
    item_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    def clean(self):
        # Check if the item exists in Costing
        if not Costing.objects.filter(id=self.item_id).exists():
            raise ValidationError({'item_id': "This item does not exist in Costing"})
    def save(self, *args, **kwargs):
        self.clean()
        super(Hc_claim_lines, self).save(*args, **kwargs)
    def __str__(self):
        return f"HC CLaim: {self.hc_claim}, Item ID: {self.item_id}, Amount: {self.amount}"

class Claims(models.Model):
    claim = models.AutoField(primary_key=True)
    supplier = models.ForeignKey(Contacts, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    pdf = models.FileField(upload_to='pdfs', null=True, blank=True)
    sent_to_xero = models.BooleanField(default=False)
    def get_supplier_name(self):
        return self.supplier.contact_name
    def __str__(self):
        return f"Claim: {self.claim}, Supplier: {self.supplier}, Total: {self.total}, PDF: {self.pdf}, Sent to Xero: {self.sent_to_xero}"
    
class Claim_allocations(models.Model):
    claim = models.ForeignKey(Claims, on_delete=models.CASCADE)
    item = models.ForeignKey(Build_costing, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    def __str__(self):
        return f"Claim: {self.claim}, Item: {self.item}, Amount: {self.amount}"