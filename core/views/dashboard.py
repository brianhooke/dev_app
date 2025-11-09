"""
Dashboard view for the main application homepage.
"""

from django.shortcuts import render
from ..models import SPVData, XeroInstances
from django.conf import settings


def dashboard_view(request):
    """
    Main dashboard view - serves as the application homepage.
    """
    spv_data = SPVData.objects.first()
    
    # Table configuration for dashboard
    table_columns = [
        "Fake 1", "Fake 2", "Fake 3", "Fake 4", "Fake 5",
        "Fake 6", "Fake 7", "Fake 8", "Fake 9", "Fake 10"
    ]
    
    # Navigation items for navbar
    nav_items = [
        {'label': 'Dashboard', 'url': '/core/', 'id': 'dashboardLink', 'page_id': 'dashboard'},
        {'divider': True},
        {'label': 'Bills', 'url': '#', 'id': 'billsLink', 'page_id': 'bills'},
        {'label': 'Stocktake', 'url': '#', 'id': 'stocktakeLink', 'page_id': 'stocktake'},
        {'label': 'Staff Hours', 'url': '#', 'id': 'staffHoursLink', 'page_id': 'staff_hours'},
        {'label': 'Suppliers', 'url': '#', 'id': 'suppliersLink', 'page_id': 'suppliers'},
        {'label': 'Xero', 'url': '#', 'id': 'xeroLink', 'page_id': 'xero'},
    ]
    
    # Contacts table configuration
    contacts_columns = ["Name", "Email Address"]
    contacts_rows = []  # No data for now
    
    # Get XeroInstances for dropdown
    xero_instances = XeroInstances.objects.all()
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
        "table_columns": table_columns,
        "table_rows": [],  # No data for now
        "show_totals": False,  # No totals row for dashboard
        "nav_items": nav_items,
        "contacts_columns": contacts_columns,
        "contacts_rows": contacts_rows,
        "xero_instances": xero_instances,
    }
    
    return render(request, "core/dashboard.html", context)
