"""
Dashboard view for the main application homepage.
"""

from django.shortcuts import render
from ..models import SPVData
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
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
        "table_columns": table_columns,
        "table_rows": [],  # No data for now
        "show_totals": False,  # No totals row for dashboard
    }
    
    return render(request, "core/dashboard.html", context)
