from django.contrib import admin
from django import forms
from .models import (
    Categories, Projects, ProjectTypes, XeroInstances, XeroAccounts, XeroTrackingCategories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories,
    PlanPdfs, ReportPdfs, ReportCategories, Models_3d, Po_globals, Po_orders, Po_order_detail,
    SPVData, Letterhead, Bills, Bill_allocations, HC_claims, HC_claim_allocations,
    Hc_variation, Hc_variation_allocations, ReceivedEmail, EmailAttachment, Units,
    Document_folders, Document_files,
    Employee, EmployeePayRate, StaffHours, StaffHoursAllocations
)

# Helper function to set nullable fields as not required
def set_nullable_fields_not_required(form, nullable_fields):
    for field_name in nullable_fields:
        if field_name in form.fields:
            form.fields[field_name].required = False

# Custom forms for models with `null=True` fields
class ProjectsForm(forms.ModelForm):
    class Meta:
        model = Projects
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['xero_instance'])

class CostingForm(forms.ModelForm):
    class Meta:
        model = Costing
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['uncommitted_notes'])

class QuotesForm(forms.ModelForm):
    class Meta:
        model = Quotes
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['pdf'])

class QuoteAllocationsForm(forms.ModelForm):
    class Meta:
        model = Quote_allocations
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['notes'])

class PoOrderDetailForm(forms.ModelForm):
    class Meta:
        model = Po_order_detail
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['quote', 'variation_note'])

class BillsForm(forms.ModelForm):
    class Meta:
        model = Bills
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['bill_xero_id', 'associated_hc_claim', 'xero_instance', 'project'])

class BillAllocationsForm(forms.ModelForm):
    class Meta:
        model = Bill_allocations
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['notes'])

class HcVariationForm(forms.ModelForm):
    class Meta:
        model = Hc_variation
        fields = '__all__'    

class HcVariationAllocationsForm(forms.ModelForm):
    class Meta:
        model = Hc_variation_allocations
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['notes'])

# Custom admin classes
class CategoriesAdmin(admin.ModelAdmin):
    list_display = ("categories_pk", "project", "project_type", "category", "invoice_category", "order_in_list")
    list_filter = ('project', 'project_type')

class UnitsAdmin(admin.ModelAdmin):
    list_display = ("unit_pk", "project", "project_type", "unit_name", "unit_qty", "order_in_list")
    list_filter = ('project', 'project_type')

class ProjectTypesAdmin(admin.ModelAdmin):
    list_display = ("project_type_pk", "project_type", "xero_instance", "archived", "created_at", "updated_at")
    list_filter = ('xero_instance', 'archived')
    search_fields = ('project_type',)

class XeroInstancesAdmin(admin.ModelAdmin):
    list_display = ("xero_instance_pk", "xero_name", "xero_client_id")

class XeroAccountsAdmin(admin.ModelAdmin):
    list_display = ("xero_account_pk", "xero_instance", "account_code", "account_name", "account_type", "account_status")
    list_filter = ('xero_instance', 'account_type', 'account_status')
    search_fields = ('account_code', 'account_name', 'account_id')

class XeroTrackingCategoriesAdmin(admin.ModelAdmin):
    list_display = ("tracking_category_pk", "xero_instance", "tracking_category_id", "name", "status", "option_id", "option_name")
    list_filter = ('xero_instance', 'status', 'name')
    search_fields = ('name', 'option_name', 'tracking_category_id')


class ProjectsAdmin(admin.ModelAdmin):
    form = ProjectsForm
    list_display = ("projects_pk", "project", "project_type", "xero_instance", "xero_sales_account", "background", "archived", "project_status")
    list_filter = ('project_type', 'archived', 'project_status')

class ContactsAdmin(admin.ModelAdmin):
    list_display = ("contact_pk", "xero_instance", "xero_contact_id", "name", "first_name", "last_name", "email", "status", "bank_details_verified", "checked")

class QuotesAdmin(admin.ModelAdmin):
    form = QuotesForm
    list_display = ("quotes_pk", "supplier_quote_number", "total_cost", "contact_pk", "pdf", "tender_or_execution")
    list_filter = ('project', 'tender_or_execution')

class CostingAdmin(admin.ModelAdmin):
    form = CostingForm
    list_display = ("costing_pk", "project", "project_type", "category", "item", "order_in_list", "xero_account_code", "xero_tracking_category", "contract_budget", "unit", "rate", "operator", "operator_value", "uncommitted_amount", "uncommitted_qty", "uncommitted_rate", "uncommitted_notes", "fixed_on_site", "sc_invoiced", "sc_paid", "tender_or_execution")
    list_filter = ('project', 'project_type', 'category', 'tender_or_execution')

class QuoteAllocationsAdmin(admin.ModelAdmin):
    form = QuoteAllocationsForm
    list_display = ("quote_allocations_pk", "quotes_pk", "item", "amount", "qty", "unit", "rate", "notes")

class DesignCategoriesAdmin(admin.ModelAdmin):
    list_display = ("design_category_pk", "design_category")

class PlanPdfsAdmin(admin.ModelAdmin):
    list_display = ("design_category", "file", "plan_number", "rev_number")

class ReportCategoriesAdmin(admin.ModelAdmin):
    list_display = ("report_category_pk", "report_category")

class ReportPdfsAdmin(admin.ModelAdmin):
    list_display = ("report_category", "file", "report_reference")

class Models_3dAdmin(admin.ModelAdmin):
    list_display = ("file", "filename")

class Po_globalsAdmin(admin.ModelAdmin):
    list_display = ("reference", "invoicee", "address", "project_address", "ABN", "email", "note1", "note2", "note3")

class Po_ordersForm(forms.ModelForm):
    class Meta:
        model = Po_orders
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        set_nullable_fields_not_required(self, ['pdf', 'project'])

class Po_ordersAdmin(admin.ModelAdmin):
    form = Po_ordersForm
    list_display = ("po_order_pk", "po_supplier", "project", "unique_id", "pdf", "po_sent", "created_at")
    readonly_fields = ("unique_id", "created_at")  # Removed pdf from readonly to allow re-uploading

class PoOrderDetailAdmin(admin.ModelAdmin):
    form = PoOrderDetailForm
    list_display = ("po_order_detail_pk", "po_order_pk", "date", "costing", "quote", "amount", "variation_note")

class SPVDataAdmin(admin.ModelAdmin):
    list_display = ("address", "lot_size", "legal_owner", "folio_identifier", "bill_to", "email", "owner_address", "director_1", "director_2", "abn", "acn")

class LetterheadAdmin(admin.ModelAdmin):
    list_display = ("letterhead_path",)

class BillsAdmin(admin.ModelAdmin):
    form = BillsForm
    list_display = (
        "bill_pk", "contact_pk", "project", "bill_status", "bill_xero_id", "supplier_bill_number", 
        "bill_date", "bill_due_date", "total_net", "total_gst", "pdf", "associated_hc_claim", 
        "bill_type", "auto_created", "received_email", "email_attachment"
    )
    list_filter = ('bill_status', 'auto_created', 'bill_type', 'project')
    search_fields = ('supplier_bill_number', 'contact_pk__contact_name', 'bill_xero_id')
class BillAllocationsAdmin(admin.ModelAdmin):
    form = BillAllocationsForm
    list_display = ("bill_allocation_pk", "bill", "item", "xero_account", "tracking_category", "amount", "gst_amount", "notes", "allocation_type")
    list_filter = ('bill__bill_status', 'allocation_type', 'xero_account')
    search_fields = ('bill__supplier_bill_number', 'notes')

class HC_claimsAdmin(admin.ModelAdmin):
    list_display = ("hc_claim_pk", "date", "status", "display_id")

class HC_claim_allocationsAdmin(admin.ModelAdmin):
    list_display = ('hc_claim_pk', 'item', 'contract_budget', 'working_budget', 'committed', 'uncommitted', 'fixed_on_site', 'fixed_on_site_previous', 'fixed_on_site_this', 'sc_invoiced', 'sc_invoiced_previous', 'adjustment', 'hc_claimed', 'hc_claimed_previous', 'qs_claimed', 'qs_claimed_previous')

class HcVariationAdmin(admin.ModelAdmin):
    form = HcVariationForm
    list_display = ('hc_variation_pk', 'date')
    
class HcVariationAllocationsAdmin(admin.ModelAdmin):
    form = HcVariationAllocationsForm
    list_display = ('hc_variation_allocation_pk', 'hc_variation', 'costing', 'amount', 'notes')

# Register models with custom admin classes
admin.site.register(Categories, CategoriesAdmin)
admin.site.register(Units, UnitsAdmin)
admin.site.register(ProjectTypes, ProjectTypesAdmin)
admin.site.register(XeroInstances, XeroInstancesAdmin)
admin.site.register(XeroAccounts, XeroAccountsAdmin)
admin.site.register(XeroTrackingCategories, XeroTrackingCategoriesAdmin)
admin.site.register(Projects, ProjectsAdmin)
admin.site.register(Contacts, ContactsAdmin)
admin.site.register(Quotes, QuotesAdmin)
admin.site.register(Costing, CostingAdmin)
admin.site.register(Quote_allocations, QuoteAllocationsAdmin)
admin.site.register(DesignCategories, DesignCategoriesAdmin)
admin.site.register(PlanPdfs, PlanPdfsAdmin)
admin.site.register(ReportCategories, ReportCategoriesAdmin)
admin.site.register(ReportPdfs, ReportPdfsAdmin)
admin.site.register(Models_3d, Models_3dAdmin)
admin.site.register(Po_globals, Po_globalsAdmin)
admin.site.register(Po_orders, Po_ordersAdmin)
admin.site.register(Po_order_detail, PoOrderDetailAdmin)
admin.site.register(SPVData, SPVDataAdmin)
admin.site.register(Letterhead, LetterheadAdmin)
admin.site.register(Bills, BillsAdmin)
admin.site.register(Bill_allocations, BillAllocationsAdmin)
admin.site.register(HC_claims, HC_claimsAdmin)
admin.site.register(HC_claim_allocations, HC_claim_allocationsAdmin)
admin.site.register(Hc_variation, HcVariationAdmin)
admin.site.register(Hc_variation_allocations, HcVariationAllocationsAdmin)

# Document management models
class DocumentFoldersAdmin(admin.ModelAdmin):
    list_display = ("folder_pk", "project", "folder_name", "parent_folder", "order_index", "created_at")
    list_filter = ('project',)
    search_fields = ('folder_name',)

class DocumentFilesAdmin(admin.ModelAdmin):
    list_display = ("file_pk", "folder", "file_name", "file_type", "file_size", "uploaded_by", "uploaded_at")
    list_filter = ('file_type', 'folder__project')
    search_fields = ('file_name', 'description')

admin.site.register(Document_folders, DocumentFoldersAdmin)
admin.site.register(Document_files, DocumentFilesAdmin)

# Email receiving models
class EmailAttachmentInline(admin.TabularInline):
    model = EmailAttachment
    extra = 0
    readonly_fields = ('filename', 'content_type', 'size_bytes', 's3_bucket', 's3_key', 'uploaded_at')
    can_delete = False

class ReceivedEmailAdmin(admin.ModelAdmin):
    list_display = ('id', 'from_address', 'to_address', 'subject', 'body_preview', 'received_at', 'attachment_count', 'is_processed', 'email_type')
    list_filter = ('is_processed', 'email_type', 'to_address', 'received_at')
    search_fields = ('from_address', 'to_address', 'subject', 'body_text', 'message_id')
    
    def body_preview(self, obj):
        """Show first 100 characters of body text"""
        if obj.body_text:
            return obj.body_text[:100] + '...' if len(obj.body_text) > 100 else obj.body_text
        return '(no text body)'
    body_preview.short_description = 'Body Preview'
    readonly_fields = ('from_address', 'to_address', 'cc_address', 'subject', 'message_id', 
                       'body_text', 'body_html', 'received_at', 'processed_at', 
                       's3_bucket', 's3_key', 'attachment_count')
    fieldsets = (
        ('Email Info', {
            'fields': ('from_address', 'to_address', 'cc_address', 'subject', 'message_id')
        }),
        ('Content', {
            'fields': ('body_text', 'body_html'),
        }),
        ('Metadata', {
            'fields': ('received_at', 'processed_at', 'is_processed', 'email_type', 'processing_notes')
        }),
        ('Storage', {
            'fields': ('s3_bucket', 's3_key'),
            'classes': ('collapse',)
        }),
    )
    inlines = [EmailAttachmentInline]
    date_hierarchy = 'received_at'

class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'filename', 'content_type', 'size_bytes', 'uploaded_at')
    list_filter = ('content_type', 'uploaded_at')
    search_fields = ('filename', 'email__subject', 'email__from_address')
    readonly_fields = ('email', 'filename', 'content_type', 'size_bytes', 's3_bucket', 's3_key', 'uploaded_at')

admin.site.register(ReceivedEmail, ReceivedEmailAdmin)
admin.site.register(EmailAttachment, EmailAttachmentAdmin)

# Staff Hours models
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_pk', 'xero_instance', 'xero_employee_id', 'name', 'status', 'start_date', 'created_at')
    list_filter = ('xero_instance', 'status')
    search_fields = ('name', 'xero_employee_id')

class EmployeePayRateAdmin(admin.ModelAdmin):
    list_display = ('payrate_pk', 'employee', 'effective_date', 'earnings_rate_name', 'rate_per_unit', 'annual_salary', 'units_per_week', 'pay_basis', 'is_ordinary_rate', 'created_at')
    list_filter = ('employee__xero_instance', 'pay_basis', 'is_ordinary_rate', 'effective_date')
    search_fields = ('employee__name', 'earnings_rate_name')
    date_hierarchy = 'effective_date'

class StaffHoursAdmin(admin.ModelAdmin):
    list_display = ('staff_hours_pk', 'employee', 'date', 'hours', 'payrate', 'created_at')
    list_filter = ('employee__xero_instance', 'date')
    search_fields = ('employee__name',)
    date_hierarchy = 'date'

class StaffHoursAllocationsAdmin(admin.ModelAdmin):
    list_display = ('allocation_pk', 'staff_hours', 'project', 'costing', 'hours', 'created_at')
    list_filter = ('project', 'staff_hours__employee__xero_instance')
    search_fields = ('staff_hours__employee__name', 'project__project', 'costing__item')

admin.site.register(Employee, EmployeeAdmin)
admin.site.register(EmployeePayRate, EmployeePayRateAdmin)
admin.site.register(StaffHours, StaffHoursAdmin)
admin.site.register(StaffHoursAllocations, StaffHoursAllocationsAdmin)
