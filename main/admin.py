from django.contrib import admin
from .models import Categories, Projects, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Models_3d, Po_globals, Po_orders, Po_order_detail

class CategoriesAdmin(admin.ModelAdmin):
    list_display = ("categories_pk", "category", "order_in_list")

class ProjectsAdmin(admin.ModelAdmin):
    list_display = ("projects_pk", "project")

class ContactsAdmin(admin.ModelAdmin):
    list_display = ("contact_pk", "contact_name", "contact_email")

class QuotesAdmin(admin.ModelAdmin):
    list_display = ("quotes_pk", "supplier_quote_number", "total_cost", "contact_pk", "pdf")

class CostingAdmin(admin.ModelAdmin):
    list_display = ("costing_pk", "category", "item", "contract_budget", "uncommitted", "sc_invoiced", "sc_paid")

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

admin.site.register(Categories, CategoriesAdmin),
admin.site.register(Projects, ProjectsAdmin),
admin.site.register(Contacts, ContactsAdmin),
admin.site.register(Quotes, QuotesAdmin),
admin.site.register(Costing, CostingAdmin),
admin.site.register(Quote_allocations, Quote_allocationsAdmin)
admin.site.register(DesignCategories, DesignCategoriesAdmin)
admin.site.register(PlanPdfs, PlanPdfsAdmin)
admin.site.register(ReportCategories, ReportCategoriesAdmin)
admin.site.register(ReportPdfs, ReportPdfsAdmin)
admin.site.register(Models_3d, Models_3dAdmin)
admin.site.register(Po_globals, Po_globalsAdmin)
admin.site.register(Po_orders, Po_ordersAdmin)
admin.site.register(Po_order_detail, Po_order_detailAdmin)
