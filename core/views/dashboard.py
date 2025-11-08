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
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
    }
    
    return render(request, "core/dashboard.html", context)
