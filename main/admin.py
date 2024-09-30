from django.contrib import admin
from .models import Categories, Projects, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Models_3d, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Invoices, Invoice_allocations

class CategoriesAdmin(admin.ModelAdmin):
    list_display = ("categories_pk", "division", "category", "order_in_list")

class ProjectsAdmin(admin.ModelAdmin):
    list_display = ("projects_pk", "project")

class ContactsAdmin(admin.ModelAdmin):
    list_display = ("contact_pk", "xero_contact_id", "division", "checked", "contact_name", "contact_email")

class QuotesAdmin(admin.ModelAdmin):
    list_display = ("quotes_pk", "supplier_quote_number", "total_cost", "contact_pk", "pdf")

class CostingAdmin(admin.ModelAdmin):
    list_display = ("costing_pk", "category", "item", "xero_account_code", "contract_budget", "uncommitted", "sc_invoiced", "sc_paid")

class Quote_allocationsAdmin(admin.ModelAdmin):
    list_display = ("quote_allocations_pk", "quotes_pk", "item", "amount", "notes")

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

class Po_ordersAdmin(admin.ModelAdmin):
    list_display = ("po_order_pk", "po_supplier", "po_sent", "po_note_1", "po_note_2", "po_note_3")

class Po_order_detailAdmin(admin.ModelAdmin):
    list_display = ("po_order_detail_pk", "po_order_pk", "date", "costing", "quote", "amount", "variation_note")

class SPVDataAdmin(admin.ModelAdmin):
    list_display = ("address", "lot_size", "legal_owner", "folio_identifier", "bill_to", "email", "owner_address", "director_1", "director_2", "abn", "acn")

class LetterheadAdmin(admin.ModelAdmin):
    list_display = ("letterhead_path",)

class InvoicesAdmin(admin.ModelAdmin):
    list_display = ("invoice_pk", "invoice_division", "invoice_status", "invoice_xero_id", "supplier_invoice_number", "invoice_due_date", "invoice_due_date", "total_net", "pdf", "contact_pk", "total_gst")

class InvoiceAllocationsAdmin(admin.ModelAdmin):
    list_display = ("invoice_allocations_pk", "invoice_pk", "item", "amount", "gst_amount", "notes")

admin.site.register(Categories, CategoriesAdmin)
admin.site.register(Projects, ProjectsAdmin)
admin.site.register(Contacts, ContactsAdmin)
admin.site.register(Quotes, QuotesAdmin)
admin.site.register(Costing, CostingAdmin)
admin.site.register(Quote_allocations, Quote_allocationsAdmin)
admin.site.register(DesignCategories, DesignCategoriesAdmin)
admin.site.register(PlanPdfs, PlanPdfsAdmin)
admin.site.register(ReportCategories, ReportCategoriesAdmin)
admin.site.register(ReportPdfs, ReportPdfsAdmin)
admin.site.register(Models_3d, Models_3dAdmin)
admin.site.register(Po_globals, Po_globalsAdmin)
admin.site.register(Po_orders, Po_ordersAdmin)
admin.site.register(Po_order_detail, Po_order_detailAdmin)
admin.site.register(SPVData, SPVDataAdmin)
admin.site.register(Letterhead, LetterheadAdmin)
admin.site.register(Invoices, InvoicesAdmin)
admin.site.register(Invoice_allocations, InvoiceAllocationsAdmin)