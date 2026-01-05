from django.urls import path
from django.views.generic import RedirectView
from . import views
from .views import commit_data, update_quote, create_contacts, delete_quote, delete_bill, upload_design_pdf, create_plan, send_test_email_view, upload_report_pdf, get_design_pdf_url, get_report_pdf_url, create_po_order, generate_po_pdf, send_po_email_view, upload_categories, upload_costings, upload_bill, associate_sc_claims_with_hc_claim, update_hc_claim_data, get_claim_table, get_bills_by_supplier, post_progress_claim_data, post_direct_cost_data, update_contract_budget_amounts, upload_margin_category_and_lines, create_variation, delete_variation, get_bill_allocations, wipe_database, view_po_by_unique_id, get_po_table_data_for_invoice
from .views.bills import update_bill, null_allocation_xero_fields, get_approved_bills
from .views.bills import bills_view, get_project_bills, get_allocated_bills, get_unallocated_bill_allocations, create_unallocated_invoice_allocation, update_unallocated_invoice_allocation, delete_unallocated_invoice_allocation, allocate_bill, unallocate_bill, approve_bill, update_allocated_bill
from .views.bills_global import (
    bills_global_inbox_view, bills_global_direct_view, bills_global_approvals_view, 
    send_bill_direct, return_bill_to_project,
    # Moved from bills.py:
    get_bills_list, archive_bill, return_to_inbox, 
    pull_xero_accounts_and_divisions, pull_xero_accounts, get_xero_accounts_by_instance,
    create_bill_allocation, update_bill_allocation, delete_bill_allocation
)
from .views.project_type import switch_project_type, switch_project, get_current_project_info, project_selector_view
from .views.projects import create_project, get_projects, update_project, toggle_project_archive, delete_category, delete_item, update_internal_committed
from .views.quotes import quotes_view, get_project_contacts, save_project_quote, get_project_quotes, get_quote_allocations_for_quote, create_quote_allocation, update_quote_allocation, delete_quote_allocation, save_quote_allocations
from .views.contract_budget import contract_budget_view, update_uncommitted, get_project_committed_amounts
from .views.hc_variations import (
    hc_variations_view, get_hc_variations, get_hc_variation_allocations,
    save_hc_variation, delete_hc_variation, update_hc_variation_allocation,
    delete_hc_variation_allocation
)
from .views.pos import get_quotes_by_supplier, po_view
from .views.documents import get_project_folders, create_folder, rename_folder, rename_file, delete_folder, upload_files, download_file, delete_file
from .views.xero import get_xero_instances, create_xero_instance, update_xero_instance, delete_xero_instance, test_xero_connection, migrate_xero_to_ssm
from .views.xero_oauth import xero_oauth_authorize, xero_oauth_callback
from .views.xero_diagnostics import xero_oauth_diagnostics
from .views.contacts import (
    verify_contact_details, pull_xero_contacts, get_contacts_by_instance,
    create_contact, create_supplier, update_contact_details, update_contact_status
)
from .views.database_diagnostics import database_diagnostics
from .views.email_receiver import receive_email, email_list
from .views.api_diagnostics import api_diagnostics
# Dashboard views (moved from dashboard app)
from .views.dashboard import (
    dashboard_view, send_bill,
    get_project_categories, get_project_items, create_category as dashboard_create_category,
    create_item as dashboard_create_item, reorder_category, reorder_item,
    download_items_csv_template, upload_items_csv, generate_po_html, get_po_status,
    preview_po, send_po_email as dashboard_send_po_email, download_po_pdf,
    get_units, add_unit, reorder_unit, delete_unit, get_recent_activities, get_action_items
)
from django.conf import settings
from django.conf.urls.static import static

app_name = 'core'

urlpatterns = [
    path('commit_data/', commit_data, name='commit_data'),
    path('update_uncommitted/', update_uncommitted, name='update_uncommitted'),
    path('update_fixedonsite/', views.update_fixedonsite, name='update_fixedonsite'),
    # path('update_costing/', update_costing, name='update_costing'),
    path('update_quote/', update_quote, name='update_quote'),
    path('create_contacts/', create_contacts, name='create_contacts'),
    path('delete_quote/', delete_quote, name='delete_quote'),
    path('delete_bill/', delete_bill, name='delete_bill'),
    path('upload_design_pdf/', upload_design_pdf, name='upload_design_pdf'),
    path('upload_report_pdf/', views.upload_report_pdf, name='upload_report_pdf'),
    path('create_plan/', create_plan, name='create_plan'),
    path('get_report_pdf_url/<int:report_category>/', views.get_report_pdf_url, name='get_report_pdf_url'),
    path('get_report_pdf_url/<int:report_category>/<str:report_reference>/', views.get_report_pdf_url, name='get_report_pdf_url_with_ref'),
    path('get_design_pdf_url/<int:design_category>/<str:plan_number>/', views.get_design_pdf_url, name='get_design_pdf_url_without_rev'),
    path('get_design_pdf_url/<int:design_category>/<str:plan_number>/<str:rev_number>/', views.get_design_pdf_url, name='get_design_pdf_url_with_rev'),
    path('upload_margin_category_and_lines/', upload_margin_category_and_lines, name='upload_margin_category_and_lines'),
    path('create_variation/', create_variation, name='create_variation'),
    path('send_test_email/', send_test_email_view, name='send_test_email'),
    path('get_quote_allocations/<int:supplier_id>/', views.get_quote_allocations, name='get_quote_allocations'),
    path('get_quote_allocations/', views.get_quote_allocations_by_quotes, name='get_quote_allocations_by_quotes'),
    path('create_po_order/', create_po_order, name='create_po_order'),
    path('generate_po_pdf/<int:po_order_pk>/', generate_po_pdf, name='generate_po_pdf'),
    path('send_po_emails/', send_po_email_view, name='send_po_emails'),
    path('upload_categories/', views.upload_categories, name='upload_categories'),
    path('upload_costings/', upload_costings, name='upload_costings'),
    path('update_contract_budget_amounts/', views.update_contract_budget_amounts, name='update_contract_budget_amounts'),
    path('upload_letterhead/', views.upload_letterhead, name='upload_letterhead'),
    path('upload_bill/', views.upload_bill, name='upload_bill'),
    path('upload_bill_allocations/', views.upload_bill_allocations, name='upload_bill_allocations'),
    path('send_hc_claim_to_xero/', views.send_hc_claim_to_xero, name='send_hc_claim_to_xero'),
    # DEPRECATED: get_xero_token and get_xero_contacts - use OAuth2 endpoints instead
    # path('get_xero_token/', views.get_xero_token, name='get_xero_token'),
    # path('get_xero_contacts/', views.get_xero_contacts, name='get_xero_contacts'),
    path('update_contacts', views.update_contacts, name='update_contacts'),
    path('post_bill/', views.post_bill, name='post_bill'),
    path('test_xero_bill/', views.test_xero_bill, name='test_xero_bill'),
    path('associate_sc_claims_with_hc_claim/', views.associate_sc_claims_with_hc_claim, name='associate_sc_claims_with_hc_claim'),
    path('update_hc_claim_data/', views.update_hc_claim_data, name='update_hc_claim_data'),
    path('get_claim_table/<int:claim_id>/', get_claim_table, name='get_claim_table'),
    path('get_bills_by_supplier/', get_bills_by_supplier, name='get_bills_by_supplier'),
    path('get_quotes_by_supplier/', views.get_quotes_by_supplier, name='get_quotes_by_supplier'),
    path('get_project_contacts/<int:project_pk>/', get_project_contacts, name='get_project_contacts'),
    path('save_project_quote/', save_project_quote, name='save_project_quote'),
    path('get_project_quotes/<int:project_pk>/', get_project_quotes, name='get_project_quotes'),
    path('get_project_committed_amounts/<int:project_pk>/', get_project_committed_amounts, name='get_project_committed_amounts'),
    path('get_bill_allocations/<int:invoice_id>/', get_bill_allocations, name='get_bill_allocations'),
    path('post_progress_claim_data/', views.post_progress_claim_data, name='post_progress_claim_data'),
    path('post_direct_cost_data/', views.post_direct_cost_data, name='post_direct_cost_data'),
    path('delete_variation/', delete_variation, name='delete_variation'),
    
    # PROJECT_TYPE management endpoints
    path('switch_project_type/', switch_project_type, name='switch_project_type'),
    path('switch_project/', switch_project, name='switch_project'),
    path('get_current_project_info/', get_current_project_info, name='get_current_project_info'),
    path('project_selector/', project_selector_view, name='project_selector'),
    
    # Projects management endpoints
    path('create_project/', create_project, name='create_project'),
    path('get_projects/', get_projects, name='get_projects'),
    path('update_project/<int:project_pk>/', update_project, name='update_project'),
    path('toggle_project_archive/<int:project_pk>/', toggle_project_archive, name='toggle_project_archive'),
    path('delete_category/<int:project_pk>/<int:category_pk>/', delete_category, name='delete_category'),
    path('delete_item/<int:project_pk>/<int:item_pk>/', delete_item, name='delete_item'),
    path('update_internal_committed/', update_internal_committed, name='update_internal_committed'),
    
    # Xero management endpoints (contact endpoints moved to dashboard app)
    path('get_xero_instances/', get_xero_instances, name='get_xero_instances'),
    path('create_xero_instance/', create_xero_instance, name='create_xero_instance'),
    path('update_xero_instance/<int:instance_pk>/', update_xero_instance, name='update_xero_instance'),
    path('delete_xero_instance/<int:instance_pk>/', delete_xero_instance, name='delete_xero_instance'),
    path('test_xero_connection/<int:instance_pk>/', test_xero_connection, name='test_xero_connection'),
    path('migrate_xero_to_ssm/', migrate_xero_to_ssm, name='migrate_xero_to_ssm'),
    
    # Xero OAuth2 endpoints
    path('xero_oauth_authorize/<int:instance_pk>/', xero_oauth_authorize, name='xero_oauth_authorize'),
    path('xero_oauth_callback/', xero_oauth_callback, name='xero_oauth_callback'),
    path('xero_oauth_diagnostics/<int:instance_pk>/', xero_oauth_diagnostics, name='xero_oauth_diagnostics'),
    
    # Database diagnostics
    path('database_diagnostics/', database_diagnostics, name='database_diagnostics'),
    path('wipe_database/', wipe_database, name='wipe_database'),
    
    # Bills management
    path('get_bills_list/', get_bills_list, name='get_bills_list'),
    path('archive_bill/', archive_bill, name='archive_bill'),
    path('return_to_inbox/', return_to_inbox, name='return_to_inbox'),
    path('pull_xero_accounts_and_divisions/', pull_xero_accounts_and_divisions, name='pull_xero_accounts_and_divisions'),
    path('pull_xero_accounts/<int:instance_pk>/', pull_xero_accounts, name='pull_xero_accounts'),
    path('get_xero_accounts/<int:instance_pk>/', get_xero_accounts_by_instance, name='get_xero_accounts_by_instance'),
    path('create_bill_allocation/', create_bill_allocation, name='create_bill_allocation'),
    path('update_bill_allocation/', update_bill_allocation, name='update_bill_allocation'),
    path('delete_bill_allocation/', delete_bill_allocation, name='delete_bill_allocation'),
    path('update_bill/', update_bill, name='update_bill'),
    path('null_allocation_xero_fields/', null_allocation_xero_fields, name='null_allocation_xero_fields'),
    path('get_approved_bills/', get_approved_bills, name='get_approved_bills'),
    path('return_bill_to_project/<int:invoice_id>/', return_bill_to_project, name='return_bill_to_project'),
    
    # Email receiving API
    path('api/receive_email/', receive_email, name='receive_email'),
    path('api/emails/', email_list, name='email_list'),
    path('api/diagnostics/', api_diagnostics, name='api_diagnostics'),
    
    # Bills section
    path('bills/', bills_view, name='bills'),
    path('bills/inbox/', bills_global_inbox_view, name='bills_global_inbox'),
    path('bills/direct/', bills_global_direct_view, name='bills_global_direct'),
    path('bills/approvals/', bills_global_approvals_view, name='bills_global_approvals'),
    path('get_project_bills/<int:project_pk>/', get_project_bills, name='get_project_bills'),
    path('get_allocated_bills/<int:project_pk>/', get_allocated_bills, name='get_allocated_bills'),
    path('get_unallocated_bill_allocations/<int:bill_pk>/', get_unallocated_bill_allocations, name='get_unallocated_bill_allocations'),
    path('create_unallocated_invoice_allocation/', create_unallocated_invoice_allocation, name='create_unallocated_invoice_allocation'),
    path('update_unallocated_invoice_allocation/<int:allocation_pk>/', update_unallocated_invoice_allocation, name='update_unallocated_invoice_allocation'),
    path('delete_unallocated_invoice_allocation/<int:allocation_pk>/', delete_unallocated_invoice_allocation, name='delete_unallocated_invoice_allocation'),
    path('allocate_bill/<int:bill_pk>/', allocate_bill, name='allocate_bill'),
    path('unallocate_bill/<int:bill_pk>/', unallocate_bill, name='unallocate_bill'),
    path('approve_bill/<int:bill_pk>/', approve_bill, name='approve_bill'),
    path('update_allocated_bill/<int:bill_pk>/', update_allocated_bill, name='update_allocated_bill'),
    path('get_po_table_data_for_invoice/<int:bill_pk>/', get_po_table_data_for_invoice, name='get_po_table_data_for_invoice'),
    
    # Quotes section (reusable template)
    path('quotes/', quotes_view, name='quotes'),
    path('get_allocations_for_quote/<int:quote_pk>/', get_quote_allocations_for_quote, name='get_quote_allocations_for_quote'),
    path('create_quote_allocation/', create_quote_allocation, name='create_quote_allocation'),
    path('update_quote_allocation/<int:allocation_pk>/', update_quote_allocation, name='update_quote_allocation'),
    path('delete_quote_allocation/<int:allocation_pk>/', delete_quote_allocation, name='delete_quote_allocation'),
    path('save_quote_allocations/', save_quote_allocations, name='save_quote_allocations'),
    
    # PO section (reusable template)
    path('po/', po_view, name='po'),
    
    # Contract Budget section (reusable template)
    path('contract_budget/', contract_budget_view, name='contract_budget'),
    
    # HC Variations section (reusable template)
    path('hc_variations/', hc_variations_view, name='hc_variations'),
    path('get_hc_variations/<int:project_pk>/', get_hc_variations, name='get_hc_variations'),
    path('get_hc_variation_allocations/<int:variation_pk>/', get_hc_variation_allocations, name='get_hc_variation_allocations'),
    path('save_hc_variation/', save_hc_variation, name='save_hc_variation'),
    path('delete_hc_variation/', delete_hc_variation, name='delete_hc_variation'),
    path('update_hc_variation_allocation/<int:allocation_pk>/', update_hc_variation_allocation, name='update_hc_variation_allocation'),
    path('delete_hc_variation_allocation/<int:allocation_pk>/', delete_hc_variation_allocation, name='delete_hc_variation_allocation'),
    
    # Document management endpoints
    path('get_project_folders/<int:project_pk>/', get_project_folders, name='get_project_folders'),
    path('create_folder/', create_folder, name='create_folder'),
    path('rename_folder/', rename_folder, name='rename_folder'),
    path('rename_file/', rename_file, name='rename_file'),
    path('delete_folder/', delete_folder, name='delete_folder'),
    path('upload_files/', upload_files, name='upload_files'),
    path('download_file/<int:file_pk>/', download_file, name='download_file'),
    path('delete_file/', delete_file, name='delete_file'),
    
    # PO public view - REDIRECT to top-level URL (backwards compatibility)
    # Development can continue in core/views/pos.py with the view function
    path('po/<str:unique_id>/', RedirectView.as_view(url='/po/%(unique_id)s/', permanent=True), name='view_po_by_unique_id_redirect'),
    
    # Dashboard routes (moved from dashboard app)
    path('pull_xero_contacts/<int:instance_pk>/', pull_xero_contacts, name='pull_xero_contacts'),
    path('get_contacts_by_instance/<int:instance_pk>/', get_contacts_by_instance, name='get_contacts_by_instance'),
    path('create_contact/<int:instance_pk>/', create_contact, name='create_contact'),
    path('create_supplier/', create_supplier, name='create_supplier'),
    path('update_contact_details/<int:instance_pk>/<int:contact_pk>/', update_contact_details, name='update_contact_details'),
    path('update_contact_status/<int:instance_pk>/<int:contact_pk>/', update_contact_status, name='update_contact_status'),
    path('verify_contact_details/<int:contact_pk>/', verify_contact_details, name='verify_contact_details'),
    path('send_bill/', send_bill, name='send_bill'),
    path('send_bill_direct/', send_bill_direct, name='send_bill_direct'),
    path('send_po_email/<int:project_pk>/<int:supplier_pk>/', dashboard_send_po_email, name='dashboard_send_po_email'),
    path('download_po_pdf/<int:project_pk>/<int:supplier_pk>/', download_po_pdf, name='download_po_pdf'),
    path('preview_po/<int:project_pk>/<int:supplier_pk>/', preview_po, name='preview_po'),
    path('get_po_status/<int:project_pk>/', get_po_status, name='get_po_status'),
    path('get_project_categories/<int:project_pk>/', get_project_categories, name='get_project_categories'),
    path('get_project_items/<int:project_pk>/', get_project_items, name='get_project_items'),
    path('dashboard_create_category/<int:project_pk>/', dashboard_create_category, name='dashboard_create_category'),
    path('dashboard_create_item/<int:project_pk>/', dashboard_create_item, name='dashboard_create_item'),
    path('reorder_category/<int:project_pk>/<int:category_pk>/', reorder_category, name='reorder_category'),
    path('reorder_item/<int:project_pk>/<int:item_pk>/', reorder_item, name='reorder_item'),
    path('download_items_csv_template/', download_items_csv_template, name='download_items_csv_template'),
    path('upload_items_csv/<int:project_pk>/', upload_items_csv, name='upload_items_csv'),
    path('get_units/', get_units, name='get_units'),
    path('add_unit/', add_unit, name='add_unit'),
    path('reorder_unit/<int:unit_pk>/', reorder_unit, name='reorder_unit'),
    path('delete_unit/', delete_unit, name='delete_unit'),
    path('get_recent_activities/', get_recent_activities, name='get_recent_activities'),
    path('get_action_items/', get_action_items, name='get_action_items'),
    
    # path('upload_csv/', views.upload_csv, name='upload_csv'),
    # path('model_viewer/', views.model_viewer, name='model_viewer'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)