"""
URL configuration for Dashboard app.

Routes:
- / and /dashboard/ - Main dashboard view
- Contact management - Pull, get, create, update, verify, archive contacts
- Bills management - Send bills to Xero or move to Direct workflow
"""

from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard homepage (accessible at both / and /dashboard/)
    path('', views.dashboard_view, name='dashboard'),
    path('dashboard/', views.dashboard_view, name='dashboard_alt'),
    
    # Contact management endpoints
    path('pull_xero_contacts/<int:instance_pk>/', views.pull_xero_contacts, name='pull_xero_contacts'),
    path('get_contacts_by_instance/<int:instance_pk>/', views.get_contacts_by_instance, name='get_contacts_by_instance'),
    path('create_contact/<int:instance_pk>/', views.create_contact, name='create_contact'),
    path('update_contact_details/<int:instance_pk>/<int:contact_pk>/', views.update_contact_details, name='update_contact_details'),
    path('update_contact_status/<int:instance_pk>/<int:contact_pk>/', views.update_contact_status, name='update_contact_status'),
    path('verify_contact_details/<int:contact_pk>/', views.verify_contact_details, name='verify_contact_details'),
    
    # Bills management endpoints
    path('send_bill/', views.send_bill, name='send_bill'),
    
    # PO email and download endpoints
    path('send_po_email/<int:project_pk>/<int:supplier_pk>/', views.send_po_email, name='send_po_email'),
    path('download_po_pdf/<int:project_pk>/<int:supplier_pk>/', views.download_po_pdf, name='download_po_pdf'),
    
    # Items (Categories & Costings) management endpoints
    path('get_project_categories/<int:project_pk>/', views.get_project_categories, name='get_project_categories'),
    path('get_project_items/<int:project_pk>/', views.get_project_items, name='get_project_items'),
    path('create_category/<int:project_pk>/', views.create_category, name='create_category'),
    path('create_item/<int:project_pk>/', views.create_item, name='create_item'),
    path('reorder_category/<int:project_pk>/<int:category_pk>/', views.reorder_category, name='reorder_category'),
    path('reorder_item/<int:project_pk>/<int:item_pk>/', views.reorder_item, name='reorder_item'),
    path('download_items_csv_template/', views.download_items_csv_template, name='download_items_csv_template'),
    path('upload_items_csv/<int:project_pk>/', views.upload_items_csv, name='upload_items_csv'),
    
    # Settings - Units management endpoints
    path('get_units/', views.get_units, name='get_units'),
    path('add_unit/', views.add_unit, name='add_unit'),
    path('reorder_unit/<int:unit_pk>/', views.reorder_unit, name='reorder_unit'),
    path('delete_unit/', views.delete_unit, name='delete_unit'),
]
