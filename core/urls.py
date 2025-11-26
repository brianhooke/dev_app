from django.urls import path
from . import views
from .views import commit_data, update_quote, create_contacts, delete_quote, delete_invoice, upload_design_pdf, create_plan, send_test_email_view, model_viewer_view, upload_report_pdf, get_design_pdf_url, get_report_pdf_url, create_po_order, generate_po_pdf, view_po_pdf, send_po_email_view, update_uncommitted, upload_categories, upload_costings, upload_invoice, associate_sc_claims_with_hc_claim, update_hc_claim_data, get_claim_table, get_invoices_by_supplier, get_quotes_by_supplier, post_progress_claim_data, post_direct_cost_data, update_contract_budget_amounts, upload_margin_category_and_lines, create_variation, delete_variation, get_invoice_allocations, wipe_database
from .views.bills import get_bills_list, archive_bill, return_to_inbox, pull_xero_accounts_and_divisions, get_xero_accounts_by_instance, create_invoice_allocation, update_invoice_allocation, delete_invoice_allocation, update_invoice, null_allocation_xero_fields
from .views.project_type import switch_project_type, switch_project, get_current_project_info, project_selector_view
from .views.projects import create_project, get_projects, update_project, toggle_project_archive, delete_category, delete_item, update_internal_committed
from .views.quotes import get_project_contacts, save_project_quote, get_project_quotes, get_project_committed_amounts
from .views.documents import get_project_folders, create_folder, rename_folder, delete_folder, upload_files, download_file, delete_file
from .views.xero import get_xero_instances, create_xero_instance, update_xero_instance, delete_xero_instance, test_xero_connection
from .views.xero_oauth import xero_oauth_authorize, xero_oauth_callback
from .views.xero_diagnostics import xero_oauth_diagnostics
from .views.database_diagnostics import database_diagnostics
from .views.email_receiver import receive_email, email_list
from .views.api_diagnostics import api_diagnostics
from django.conf import settings
from django.conf.urls.static import static

app_name = 'core'

urlpatterns = [
    # Old homepage at /core/developer/
    path('developer/', views.homepage_view, name='homepage'),
    path('drawings/', views.drawings_view, name='drawings'),
    path('build/', views.build_view, name='build'),
    path('commit_data/', commit_data, name='commit_data'),
    # path('commit_build_data/', commit_build_data, name='commit_build_data'),
    # path('get_build_quote_allocations/<int:supplier_id>/', views.get_build_quote_allocations, name='get_build_quote_allocations'),
    # path('update_build_quote/', update_build_quote, name='update_build_quote'),
    # path('create_build_po_order/', views.create_build_po_order, name='create_build_po_order'),
    path('update_uncommitted/', update_uncommitted, name='update_uncommitted'),
    path('update_fixedonsite/', views.update_fixedonsite, name='update_fixedonsite'),
    # path('update_complete_on_site/', update_complete_on_site, name='update_complete_on_site'),
    path('model_viewer/', views.model_viewer_view, name='model_viewer'),
    # path('update_costing/', update_costing, name='update_costing'),
    path('update_quote/', update_quote, name='update_quote'),
    path('create_contacts/', create_contacts, name='create_contacts'),
    path('delete_quote/', delete_quote, name='delete_quote'),
    path('delete_invoice/', delete_invoice, name='delete_invoice'),
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
    path('create_po_order/', create_po_order, name='create_po_order'),
    path('generate_po_pdf/<int:po_order_pk>/', generate_po_pdf, name='generate_po_pdf'),
    path('view_po_pdf/<int:po_order_pk>/', view_po_pdf, name='view_po_pdf'),
    path('send_po_emails/', send_po_email_view, name='send_po_emails'),
    path('upload_categories/', views.upload_categories, name='upload_categories'),
    path('upload_costings/', upload_costings, name='upload_costings'),
    path('update_contract_budget_amounts/', views.update_contract_budget_amounts, name='update_contract_budget_amounts'),
    path('upload_letterhead/', views.upload_letterhead, name='upload_letterhead'),
    path('upload_invoice/', views.upload_invoice, name='upload_invoice'),
    path('mark_sent_to_boutique/', views.mark_sent_to_boutique, name='mark_sent_to_boutique'),
    path('upload_invoice_allocations/', views.upload_invoice_allocations, name='upload_invoice_allocations'),
    path('send_hc_claim_to_xero/', views.send_hc_claim_to_xero, name='send_hc_claim_to_xero'),
    path('xeroapi/', views.xeroapi, name='xeroapi'),
    # DEPRECATED: get_xero_token and get_xero_contacts - use OAuth2 endpoints instead
    # path('get_xero_token/', views.get_xero_token, name='get_xero_token'),
    # path('get_xero_contacts/', views.get_xero_contacts, name='get_xero_contacts'),
    path('update_contacts', views.update_contacts, name='update_contacts'),
    path('post_invoice/', views.post_invoice, name='post_invoice'),
    path('test_xero_invoice/', views.test_xero_invoice, name='test_xero_invoice'),
    path('test_contact_id/', views.test_contact_id, name='test_contact_id'),
    path('associate_sc_claims_with_hc_claim/', views.associate_sc_claims_with_hc_claim, name='associate_sc_claims_with_hc_claim'),
    path('update_hc_claim_data/', views.update_hc_claim_data, name='update_hc_claim_data'),
    path('get_claim_table/<int:claim_id>/', get_claim_table, name='get_claim_table'),
    path('get_invoices_by_supplier/', get_invoices_by_supplier, name='get_invoices_by_supplier'),
    path('get_quotes_by_supplier/', views.get_quotes_by_supplier, name='get_quotes_by_supplier'),
    path('get_project_contacts/<int:project_pk>/', get_project_contacts, name='get_project_contacts'),
    path('save_project_quote/', save_project_quote, name='save_project_quote'),
    path('get_project_quotes/<int:project_pk>/', get_project_quotes, name='get_project_quotes'),
    path('get_project_committed_amounts/<int:project_pk>/', get_project_committed_amounts, name='get_project_committed_amounts'),
    path('get_invoice_allocations/<int:invoice_id>/', get_invoice_allocations, name='get_invoice_allocations'),
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
    path('get_xero_accounts/<int:instance_pk>/', get_xero_accounts_by_instance, name='get_xero_accounts_by_instance'),
    path('create_invoice_allocation/', create_invoice_allocation, name='create_invoice_allocation'),
    path('update_invoice_allocation/', update_invoice_allocation, name='update_invoice_allocation'),
    path('delete_invoice_allocation/', delete_invoice_allocation, name='delete_invoice_allocation'),
    path('update_invoice/', update_invoice, name='update_invoice'),
    path('null_allocation_xero_fields/', null_allocation_xero_fields, name='null_allocation_xero_fields'),
    
    # Email receiving API
    path('api/receive_email/', receive_email, name='receive_email'),
    path('api/emails/', email_list, name='email_list'),
    path('api/diagnostics/', api_diagnostics, name='api_diagnostics'),
    
    # Document management endpoints
    path('get_project_folders/<int:project_pk>/', get_project_folders, name='get_project_folders'),
    path('create_folder/', create_folder, name='create_folder'),
    path('rename_folder/', rename_folder, name='rename_folder'),
    path('delete_folder/', delete_folder, name='delete_folder'),
    path('upload_files/', upload_files, name='upload_files'),
    path('download_file/<int:file_pk>/', download_file, name='download_file'),
    path('delete_file/', delete_file, name='delete_file'),
    
    # path('upload_csv/', views.upload_csv, name='upload_csv'),
    # path('model_viewer/', views.model_viewer, name='model_viewer'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)