from django.urls import path
from . import views
from .views import commit_data, commit_build_data, update_costing, update_complete_on_site, update_quote, create_contacts, delete_quote, upload_design_pdf, create_plan, send_test_email_view, model_viewer_view, upload_report_pdf, get_design_pdf_url, get_report_pdf_url, create_po_order, generate_po_pdf, view_po_pdf, send_po_email_view, upload_csv, update_costing, update_build_quote
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.main, name='main'),
    path('drawings/', views.drawings_view, name='drawings'),
    path('build/', views.build_view, name='build'),
    path('commit_data/', commit_data, name='commit_data'),
    path('commit_build_data/', commit_build_data, name='commit_build_data'),
    path('update_build_quote/', update_build_quote, name='update_build_quote'),
    path('update_costing/', update_costing, name='update_costing'),
    path('update_complete_on_site/', update_complete_on_site, name='update_complete_on_site'),
    path('model_viewer/', views.model_viewer_view, name='model_viewer'),
    path('update_costing/', update_costing, name='update_costing'),
    path('update_quote/', update_quote, name='update_quote'),
    path('create_contacts/', create_contacts, name='create_contacts'),
    path('delete_quote/', delete_quote, name='delete_quote'),
    path('upload_design_pdf/', upload_design_pdf, name='upload_design_pdf'),
    path('upload_report_pdf/', views.upload_report_pdf, name='upload_report_pdf'),
    path('create_plan/', create_plan, name='create_plan'),
    path('get_report_pdf_url/<int:report_category>/', views.get_report_pdf_url, name='get_report_pdf_url'),
    path('get_report_pdf_url/<int:report_category>/<str:report_reference>/', views.get_report_pdf_url, name='get_report_pdf_url_with_ref'),
    path('get_design_pdf_url/<int:design_category>/<str:plan_number>/', views.get_design_pdf_url, name='get_design_pdf_url_without_rev'),
    path('get_design_pdf_url/<int:design_category>/<str:plan_number>/<str:rev_number>/', views.get_design_pdf_url, name='get_design_pdf_url_with_rev'),
    path('send_test_email/', send_test_email_view, name='send_test_email'),
    path('get_quote_allocations/<int:supplier_id>/', views.get_quote_allocations, name='get_quote_allocations'),
    path('create_po_order/', create_po_order, name='create_po_order'),
    path('generate_po_pdf/<int:po_order_pk>/', generate_po_pdf, name='generate_po_pdf'),
    path('view_po_pdf/<int:po_order_pk>/', view_po_pdf, name='view_po_pdf'),
    path('send_po_emails/', send_po_email_view, name='send_po_emails'),
    path('upload_categories/', views.upload_categories, name='upload_categories'),
    path('upload_csv/', views.upload_csv, name='upload_csv'),
    # path('model_viewer/', views.model_viewer, name='model_viewer'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)