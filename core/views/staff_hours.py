"""
Staff Hours Module - Server-side views

This module handles staff data from Xero Payroll API including:
- Employee list with active status
- Leave balances
- Pay templates (wages/earnings)
- Superannuation details

Xero Payroll AU API Reference:
https://developer.xero.com/documentation/api/payrollau/employees
"""

import json
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from core.models import XeroInstances as XeroInstance
from core.views.xero import get_xero_auth

logger = logging.getLogger(__name__)

# Xero Payroll AU API base URL
XERO_PAYROLL_AU_URL = 'https://api.xero.com/payroll.xro/1.0'


@login_required
def staff_hours(request):
    """
    Render the Staff Hours page.
    """
    xero_instances = XeroInstance.objects.all()
    
    # Navigation items for navbar (same as dashboard)
    nav_items = [
        {'label': 'Dashboard', 'url': '/', 'id': 'dashboardLink', 'page_id': 'dashboard', 'icon': 'fa-home'},
        {'divider': True},
        {'label': 'Bills', 'url': '#', 'id': 'billsLink', 'page_id': 'bills', 'icon': 'fa-file-invoice-dollar'},
        {'label': 'Projects', 'url': '#', 'id': 'projectsLink', 'page_id': 'projects', 'icon': 'fa-project-diagram'},
        {'label': 'Stocktake', 'url': '#', 'id': 'stocktakeLink', 'page_id': 'stocktake', 'disabled': True, 'icon': 'fa-boxes'},
        {'label': 'Staff Hours', 'url': '/core/staff_hours/', 'id': 'staffHoursLink', 'page_id': 'staff_hours', 'icon': 'fa-user-clock'},
        {'label': 'Rates', 'url': '#', 'id': 'ratesLink', 'page_id': 'rates', 'icon': 'fa-percentage'},
        {'divider': True},
        {'label': 'Settings', 'url': '#', 'id': 'settingsLink', 'page_id': 'settings', 'icon': 'fa-cog'},
    ]
    
    return render(request, 'core/staff_hours.html', {
        'xero_instances': xero_instances,
        'nav_items': nav_items,
        'current_page': 'staff_hours',
    })


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_employees(request):
    """
    Fetch employees from Xero Payroll API.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    - status: Optional filter - 'ACTIVE' or 'TERMINATED'
    
    Returns employee data including:
    - Basic info (name, email, start date)
    - Status (active/terminated)
    - Leave balances
    - Pay template details
    - Super membership
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        status_filter = request.GET.get('status', 'ACTIVE')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Fetch employees from Xero Payroll API
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        # Build URL with optional status filter
        url = f'{XERO_PAYROLL_AU_URL}/Employees'
        if status_filter:
            url += f'?where=Status=="{status_filter}"'
        
        logger.info(f"Fetching employees from Xero: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Xero API error: {response.status_code} - {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        employees = data.get('Employees', [])
        
        # Process employee data
        processed_employees = []
        for emp in employees:
            processed_emp = {
                'employee_id': emp.get('EmployeeID'),
                'first_name': emp.get('FirstName'),
                'last_name': emp.get('LastName'),
                'email': emp.get('Email'),
                'status': emp.get('Status'),
                'start_date': emp.get('StartDate'),
                'termination_date': emp.get('TerminationDate'),
                'date_of_birth': emp.get('DateOfBirth'),
                'gender': emp.get('Gender'),
                'phone': emp.get('Phone'),
                'mobile': emp.get('Mobile'),
                'job_title': emp.get('JobTitle'),
                'classification': emp.get('Classification'),
                'ordinary_earnings_rate_id': emp.get('OrdinaryEarningsRateID'),
                'payroll_calendar_id': emp.get('PayrollCalendarID'),
                
                # Leave balances
                'leave_balances': emp.get('LeaveBalances', []),
                
                # Pay template (wages info)
                'pay_template': emp.get('PayTemplate', {}),
                
                # Super membership
                'super_memberships': emp.get('SuperMemberships', []),
                
                # Bank accounts (for reference)
                'bank_accounts': emp.get('BankAccounts', []),
            }
            processed_employees.append(processed_emp)
        
        logger.info(f"Fetched {len(processed_employees)} employees from Xero")
        
        return JsonResponse({
            'status': 'success',
            'employees': processed_employees,
            'count': len(processed_employees)
        })
        
    except Exception as e:
        logger.error(f"Error fetching employees: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_employee_detail(request, employee_id):
    """
    Fetch detailed information for a specific employee.
    
    Path params:
    - employee_id: Xero Employee ID
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        url = f'{XERO_PAYROLL_AU_URL}/Employees/{employee_id}'
        logger.info(f"Fetching employee detail: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Xero API error: {response.status_code} - {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        employees = data.get('Employees', [])
        
        if not employees:
            return JsonResponse({
                'status': 'error',
                'message': 'Employee not found'
            }, status=404)
        
        return JsonResponse({
            'status': 'success',
            'employee': employees[0]
        })
        
    except Exception as e:
        logger.error(f"Error fetching employee detail: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_leave_balances(request):
    """
    Fetch leave balances for all employees or a specific employee.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    - employee_id: Optional - specific employee ID
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        employee_id = request.GET.get('employee_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        # Fetch employees with leave balance info
        if employee_id:
            url = f'{XERO_PAYROLL_AU_URL}/Employees/{employee_id}'
        else:
            url = f'{XERO_PAYROLL_AU_URL}/Employees?where=Status=="ACTIVE"'
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        employees = data.get('Employees', [])
        
        # Extract leave balances
        leave_data = []
        for emp in employees:
            emp_leave = {
                'employee_id': emp.get('EmployeeID'),
                'name': f"{emp.get('FirstName', '')} {emp.get('LastName', '')}".strip(),
                'leave_balances': emp.get('LeaveBalances', [])
            }
            leave_data.append(emp_leave)
        
        return JsonResponse({
            'status': 'success',
            'leave_data': leave_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching leave balances: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_pay_items(request):
    """
    Fetch pay items (earnings rates, deduction types, leave types) from Xero.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        url = f'{XERO_PAYROLL_AU_URL}/PayItems'
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        pay_items = data.get('PayItems', {})
        
        return JsonResponse({
            'status': 'success',
            'earnings_rates': pay_items.get('EarningsRates', []),
            'deduction_types': pay_items.get('DeductionTypes', []),
            'leave_types': pay_items.get('LeaveTypes', []),
            'reimbursement_types': pay_items.get('ReimbursementTypes', [])
        })
        
    except Exception as e:
        logger.error(f"Error fetching pay items: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_payroll_calendars(request):
    """
    Fetch payroll calendars from Xero.
    Note: These are pay run schedules, NOT public holiday calendars.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        url = f'{XERO_PAYROLL_AU_URL}/PayrollCalendars'
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        
        return JsonResponse({
            'status': 'success',
            'payroll_calendars': data.get('PayrollCalendars', [])
        })
        
    except Exception as e:
        logger.error(f"Error fetching payroll calendars: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_super_funds(request):
    """
    Fetch super funds from Xero.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        url = f'{XERO_PAYROLL_AU_URL}/SuperFunds'
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        data = response.json()
        
        return JsonResponse({
            'status': 'success',
            'super_funds': data.get('SuperFunds', [])
        })
        
    except Exception as e:
        logger.error(f"Error fetching super funds: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# Australian Public Holidays (hardcoded as Xero doesn't expose this via API)
# These need to be updated annually or fetched from a third-party API
AUSTRALIAN_PUBLIC_HOLIDAYS_2026 = {
    'national': [
        {'date': '2026-01-01', 'name': "New Year's Day"},
        {'date': '2026-01-26', 'name': 'Australia Day'},
        {'date': '2026-04-03', 'name': 'Good Friday'},
        {'date': '2026-04-04', 'name': 'Easter Saturday'},
        {'date': '2026-04-06', 'name': 'Easter Monday'},
        {'date': '2026-04-25', 'name': 'Anzac Day'},
        {'date': '2026-06-08', 'name': "Queen's Birthday"},  # Most states
        {'date': '2026-12-25', 'name': 'Christmas Day'},
        {'date': '2026-12-26', 'name': 'Boxing Day'},
    ],
    # State-specific holidays can be added here
    'NSW': [],
    'VIC': [
        {'date': '2026-11-03', 'name': 'Melbourne Cup Day'},  # Melbourne metro only
    ],
    'QLD': [
        {'date': '2026-08-12', 'name': 'Royal Queensland Show'},  # Brisbane only
    ],
    'SA': [
        {'date': '2026-03-09', 'name': 'Adelaide Cup Day'},
        {'date': '2026-12-24', 'name': 'Christmas Eve (from 7pm)'},
        {'date': '2026-12-31', 'name': "New Year's Eve (from 7pm)"},
    ],
    'WA': [
        {'date': '2026-06-01', 'name': 'Western Australia Day'},
    ],
    'TAS': [],
    'NT': [
        {'date': '2026-05-04', 'name': 'May Day'},
        {'date': '2026-08-03', 'name': 'Picnic Day'},
    ],
    'ACT': [
        {'date': '2026-03-09', 'name': 'Canberra Day'},
        {'date': '2026-05-25', 'name': 'Reconciliation Day'},
    ],
}


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_public_holidays(request):
    """
    Get Australian public holidays.
    Note: This is hardcoded as Xero doesn't expose public holidays via API.
    
    Query params:
    - year: Year to get holidays for (default: current year)
    - state: Australian state code (e.g., 'NSW', 'VIC')
    """
    try:
        year = request.GET.get('year', '2026')
        state = request.GET.get('state', '').upper()
        
        # For now, return 2026 holidays
        holidays = AUSTRALIAN_PUBLIC_HOLIDAYS_2026.get('national', []).copy()
        
        # Add state-specific holidays if requested
        if state and state in AUSTRALIAN_PUBLIC_HOLIDAYS_2026:
            holidays.extend(AUSTRALIAN_PUBLIC_HOLIDAYS_2026[state])
        
        # Sort by date
        holidays.sort(key=lambda x: x['date'])
        
        return JsonResponse({
            'status': 'success',
            'year': year,
            'state': state or 'ALL',
            'holidays': holidays,
            'note': 'Public holidays are not available from Xero API. This data is hardcoded and may need updating.'
        })
        
    except Exception as e:
        logger.error(f"Error fetching public holidays: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
