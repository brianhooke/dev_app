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
]
