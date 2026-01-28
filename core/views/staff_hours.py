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

from core.models import XeroInstances as XeroInstance, PublicHolidayCalendar, PublicHoliday, Employee, EmployeePayRate, StaffHours, StaffHoursAllocations, Projects, Costing
from datetime import datetime, date
import hashlib
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
    
    # Find the first instance with staff_hours_tracking=1 for default selection
    default_instance = XeroInstance.objects.filter(staff_hours_tracking=1).first()
    default_instance_pk = default_instance.xero_instance_pk if default_instance else None
    
    # Staff Hours is now integrated into the dashboard SPA
    # Redirect to dashboard - user navigates via navbar
    from django.shortcuts import redirect
    return redirect('/')


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
        status_filter = request.GET.get('status')
        # Default to ACTIVE only if status param not provided at all
        # Empty string means "All" (no filter)
        if status_filter is None:
            status_filter = 'ACTIVE'
        
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
        
        # Fetch individual employee details to get leave balances
        # The list endpoint doesn't return leave balances
        processed_employees = []
        for emp in employees:
            employee_id = emp.get('EmployeeID')
            leave_balances = []
            
            # Fetch individual employee to get leave balances
            if employee_id:
                detail_url = f'{XERO_PAYROLL_AU_URL}/Employees/{employee_id}'
                try:
                    detail_response = requests.get(detail_url, headers=headers, timeout=15)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        detail_employees = detail_data.get('Employees', [])
                        if detail_employees:
                            leave_balances = detail_employees[0].get('LeaveBalances', [])
                except Exception as e:
                    logger.warning(f"Could not fetch leave balances for employee {employee_id}: {e}")
            
            processed_emp = {
                'employee_id': employee_id,
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
                
                # Leave balances (fetched from individual employee detail)
                'leave_balances': leave_balances,
                
                # Pay template (wages info)
                'pay_template': emp.get('PayTemplate', {}),
                
                # Super membership
                'super_memberships': emp.get('SuperMemberships', []),
                
                # Bank accounts (for reference)
                'bank_accounts': emp.get('BankAccounts', []),
            }
            processed_employees.append(processed_emp)
        
        # Sync employees to local database
        xero_instance_obj = XeroInstance.objects.get(xero_instance_pk=xero_instance_id)
        for emp_data in processed_employees:
            start_date = None
            if emp_data.get('start_date'):
                try:
                    # Xero returns dates as /Date(timestamp)/ or ISO format
                    start_str = emp_data['start_date']
                    if '/Date(' in start_str:
                        timestamp = int(start_str.replace('/Date(', '').replace('+0000)/', '').replace(')/', ''))
                        start_date = datetime.fromtimestamp(timestamp / 1000).date()
                    else:
                        start_date = datetime.strptime(start_str[:10], '%Y-%m-%d').date()
                except Exception as e:
                    logger.warning(f"Could not parse start_date for {emp_data.get('employee_id')}: {e}")
            
            Employee.objects.update_or_create(
                xero_instance=xero_instance_obj,
                xero_employee_id=emp_data['employee_id'],
                defaults={
                    'name': f"{emp_data.get('first_name', '')} {emp_data.get('last_name', '')}".strip(),
                    'status': emp_data.get('status', 'ACTIVE'),
                    'start_date': start_date,
                }
            )
        
        logger.info(f"Fetched and synced {len(processed_employees)} employees from Xero")
        
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
@require_http_methods(["POST"])
@login_required
def sync_employee_pay_rates(request):
    """
    Sync employee pay rates from Xero to local database.
    Creates new record only if rates have changed, max one entry per day if unchanged.
    
    POST body:
    - xero_instance_id: ID of the Xero instance to use
    """
    try:
        data = json.loads(request.body) if request.body else {}
        xero_instance_id = data.get('xero_instance_id') or request.GET.get('xero_instance_id')
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id is required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        xero_instance_obj = XeroInstance.objects.get(xero_instance_pk=xero_instance_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        # Fetch all employees (list endpoint - minimal data)
        url = f'{XERO_PAYROLL_AU_URL}/Employees'
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}'
            }, status=response.status_code)
        
        employees_list = response.json().get('Employees', [])
        today = date.today()
        
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        
        # Fetch PayItems to get earnings rate names
        pay_items_url = f'{XERO_PAYROLL_AU_URL}/PayItems'
        pay_items_response = requests.get(pay_items_url, headers=headers, timeout=30)
        earnings_rates_map = {}
        if pay_items_response.status_code == 200:
            pay_items = pay_items_response.json().get('PayItems', {})
            for rate in pay_items.get('EarningsRates', []):
                earnings_rates_map[rate.get('EarningsRateID')] = rate.get('Name', '')
        
        for emp_summary in employees_list:
            xero_employee_id = emp_summary.get('EmployeeID')
            
            # Fetch individual employee to get full PayTemplate
            emp_url = f'{XERO_PAYROLL_AU_URL}/Employees/{xero_employee_id}'
            emp_response = requests.get(emp_url, headers=headers, timeout=15)
            if emp_response.status_code != 200:
                logger.warning(f"Could not fetch employee {xero_employee_id}")
                continue
            
            emp_data = emp_response.json().get('Employees', [])
            if not emp_data:
                continue
            emp = emp_data[0]
            
            ordinary_rate_id = emp.get('OrdinaryEarningsRateID')
            pay_template = emp.get('PayTemplate', {})
            earnings_lines = pay_template.get('EarningsLines', [])
            
            # Get or create local Employee record
            employee_obj, _ = Employee.objects.get_or_create(
                xero_instance=xero_instance_obj,
                xero_employee_id=xero_employee_id,
                defaults={
                    'name': f"{emp.get('FirstName', '')} {emp.get('LastName', '')}".strip(),
                    'status': emp.get('Status', 'ACTIVE'),
                }
            )
            
            # Process each earnings line
            for line in earnings_lines:
                earnings_rate_id = line.get('EarningsRateID')
                rate_per_unit = line.get('RatePerUnit')
                units_per_week = line.get('NumberOfUnitsPerWeek')
                annual_salary = line.get('AnnualSalary')
                
                # Determine pay basis
                pay_basis = 'SALARY' if annual_salary else 'HOURLY'
                
                # Create hash for change detection
                rate_data = f"{earnings_rate_id}|{rate_per_unit}|{units_per_week}|{annual_salary}|{pay_basis}"
                rate_hash = hashlib.sha256(rate_data.encode()).hexdigest()[:32]
                
                # Check if this exact rate already exists for this employee
                latest_rate = EmployeePayRate.objects.filter(
                    employee=employee_obj,
                    earnings_rate_id=earnings_rate_id
                ).order_by('-effective_date').first()
                
                if latest_rate:
                    if latest_rate.rate_hash == rate_hash:
                        # No change - check if we already have an entry for today
                        if latest_rate.effective_date == today:
                            unchanged_count += 1
                            continue
                        else:
                            # Update the effective_date to today (no rate change)
                            unchanged_count += 1
                            continue
                    else:
                        # Rate changed - create new record
                        EmployeePayRate.objects.create(
                            employee=employee_obj,
                            effective_date=today,
                            earnings_rate_id=earnings_rate_id,
                            earnings_rate_name=earnings_rates_map.get(earnings_rate_id, ''),
                            rate_per_unit=rate_per_unit,
                            units_per_week=units_per_week,
                            annual_salary=annual_salary,
                            pay_basis=pay_basis,
                            is_ordinary_rate=(earnings_rate_id == ordinary_rate_id),
                            rate_hash=rate_hash,
                        )
                        updated_count += 1
                else:
                    # First record for this employee/rate - use employee start_date or far past
                    initial_date = employee_obj.start_date or date(2020, 1, 1)
                    EmployeePayRate.objects.create(
                        employee=employee_obj,
                        effective_date=initial_date,
                        earnings_rate_id=earnings_rate_id,
                        earnings_rate_name=earnings_rates_map.get(earnings_rate_id, ''),
                        rate_per_unit=rate_per_unit,
                        units_per_week=units_per_week,
                        annual_salary=annual_salary,
                        pay_basis=pay_basis,
                        is_ordinary_rate=(earnings_rate_id == ordinary_rate_id),
                        rate_hash=rate_hash,
                    )
                    created_count += 1
        
        logger.info(f"Pay rates sync: {created_count} created, {updated_count} updated, {unchanged_count} unchanged")
        
        return JsonResponse({
            'status': 'success',
            'created': created_count,
            'updated': updated_count,
            'unchanged': unchanged_count,
        })
        
    except Exception as e:
        logger.error(f"Error syncing pay rates: {str(e)}", exc_info=True)
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


# ============================================================================
# PUBLIC HOLIDAY CALENDAR MANAGEMENT
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_public_holidays(request):
    """
    Get public holidays from database.
    
    Query params:
    - calendar_pk: Specific calendar to get holidays from
    - state: Filter by state code (e.g., 'NSW', 'VIC') - finds calendar by state
    - year: Filter holidays by year
    """
    try:
        calendar_pk = request.GET.get('calendar_pk')
        state = request.GET.get('state', '').upper()
        year = request.GET.get('year')
        
        if calendar_pk:
            # Get holidays from specific calendar by PK
            holidays = PublicHoliday.objects.filter(
                calendar_id=calendar_pk,
                calendar__archived=0
            )
        elif state:
            # Get holidays from calendar matching the state
            state_calendar = PublicHolidayCalendar.objects.filter(
                state=state, archived=0
            ).first()
            if state_calendar:
                holidays = PublicHoliday.objects.filter(calendar=state_calendar)
            else:
                # Fallback to default calendar
                default_calendar = PublicHolidayCalendar.objects.filter(is_default=1, archived=0).first()
                if default_calendar:
                    holidays = PublicHoliday.objects.filter(calendar=default_calendar)
                else:
                    holidays = PublicHoliday.objects.filter(calendar__archived=0)
        else:
            # Get holidays from default calendar or all non-archived calendars
            default_calendar = PublicHolidayCalendar.objects.filter(is_default=1, archived=0).first()
            if default_calendar:
                holidays = PublicHoliday.objects.filter(calendar=default_calendar)
            else:
                holidays = PublicHoliday.objects.filter(calendar__archived=0)
        
        # Filter by year if provided
        if year:
            holidays = holidays.filter(date__year=year)
        
        holidays_list = [{
            'holiday_pk': h.holiday_pk,
            'calendar_pk': h.calendar_id,
            'calendar_name': h.calendar.name,
            'name': h.name,
            'date': h.date.isoformat()
        } for h in holidays.order_by('date')]
        
        return JsonResponse({
            'status': 'success',
            'holidays': holidays_list
        })
        
    except Exception as e:
        logger.error(f"Error fetching public holidays: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_holiday_calendars(request):
    """Get all public holiday calendars."""
    try:
        include_archived = request.GET.get('include_archived', '0') == '1'
        
        calendars = PublicHolidayCalendar.objects.all()
        if not include_archived:
            calendars = calendars.filter(archived=0)
        
        calendars_list = [{
            'calendar_pk': c.calendar_pk,
            'name': c.name,
            'state': c.state,
            'state_display': c.get_state_display(),
            'is_default': c.is_default,
            'archived': c.archived,
            'holiday_count': c.holidays.count()
        } for c in calendars]
        
        return JsonResponse({
            'status': 'success',
            'calendars': calendars_list
        })
        
    except Exception as e:
        logger.error(f"Error fetching holiday calendars: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_holiday_calendar(request):
    """Create a new public holiday calendar."""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        state = data.get('state', 'NAT')
        is_default = int(data.get('is_default', 0))
        
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Calendar name is required'
            }, status=400)
        
        # If setting as default, unset any existing default
        if is_default:
            PublicHolidayCalendar.objects.filter(is_default=1).update(is_default=0)
        
        calendar = PublicHolidayCalendar.objects.create(
            name=name,
            state=state,
            is_default=is_default
        )
        
        return JsonResponse({
            'status': 'success',
            'calendar': {
                'calendar_pk': calendar.calendar_pk,
                'name': calendar.name,
                'state': calendar.state,
                'state_display': calendar.get_state_display(),
                'is_default': calendar.is_default,
                'holiday_count': 0
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating holiday calendar: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def update_holiday_calendar(request, calendar_pk):
    """Update a public holiday calendar."""
    try:
        calendar = PublicHolidayCalendar.objects.get(calendar_pk=calendar_pk)
        data = json.loads(request.body)
        
        if 'name' in data:
            calendar.name = data['name'].strip()
        if 'state' in data:
            calendar.state = data['state']
        if 'is_default' in data:
            is_default = int(data['is_default'])
            if is_default and not calendar.is_default:
                # Unset any existing default
                PublicHolidayCalendar.objects.filter(is_default=1).update(is_default=0)
            calendar.is_default = is_default
        if 'archived' in data:
            calendar.archived = int(data['archived'])
        
        calendar.save()
        
        return JsonResponse({
            'status': 'success',
            'calendar': {
                'calendar_pk': calendar.calendar_pk,
                'name': calendar.name,
                'state': calendar.state,
                'state_display': calendar.get_state_display(),
                'is_default': calendar.is_default,
                'archived': calendar.archived,
                'holiday_count': calendar.holidays.count()
            }
        })
        
    except PublicHolidayCalendar.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Calendar not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating holiday calendar: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_holiday_calendar(request, calendar_pk):
    """Delete a public holiday calendar and all its holidays."""
    try:
        calendar = PublicHolidayCalendar.objects.get(calendar_pk=calendar_pk)
        calendar.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Calendar deleted'
        })
        
    except PublicHolidayCalendar.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Calendar not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting holiday calendar: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_calendar_holidays(request, calendar_pk):
    """Get all holidays for a specific calendar."""
    try:
        calendar = PublicHolidayCalendar.objects.get(calendar_pk=calendar_pk)
        year = request.GET.get('year')
        
        holidays = calendar.holidays.all()
        if year:
            holidays = holidays.filter(date__year=year)
        
        holidays_list = [{
            'holiday_pk': h.holiday_pk,
            'name': h.name,
            'date': h.date.isoformat()
        } for h in holidays.order_by('date')]
        
        return JsonResponse({
            'status': 'success',
            'calendar': {
                'calendar_pk': calendar.calendar_pk,
                'name': calendar.name
            },
            'holidays': holidays_list
        })
        
    except PublicHolidayCalendar.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Calendar not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching calendar holidays: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_holiday(request, calendar_pk):
    """Create a new public holiday in a calendar."""
    try:
        calendar = PublicHolidayCalendar.objects.get(calendar_pk=calendar_pk)
        data = json.loads(request.body)
        
        name = data.get('name', '').strip()
        date = data.get('date')
        
        if not name or not date:
            return JsonResponse({
                'status': 'error',
                'message': 'Holiday name and date are required'
            }, status=400)
        
        from datetime import datetime
        holiday_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Check for duplicate date in same calendar
        if PublicHoliday.objects.filter(calendar=calendar, date=holiday_date).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'A holiday already exists on this date in this calendar'
            }, status=400)
        
        holiday = PublicHoliday.objects.create(
            calendar=calendar,
            name=name,
            date=holiday_date
        )
        
        return JsonResponse({
            'status': 'success',
            'holiday': {
                'holiday_pk': holiday.holiday_pk,
                'name': holiday.name,
                'date': holiday.date.isoformat()
            }
        })
        
    except PublicHolidayCalendar.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Calendar not found'
        }, status=404)
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid date format: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating holiday: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def update_holiday(request, holiday_pk):
    """Update a public holiday."""
    try:
        holiday = PublicHoliday.objects.get(holiday_pk=holiday_pk)
        data = json.loads(request.body)
        
        if 'name' in data:
            holiday.name = data['name'].strip()
        if 'date' in data:
            from datetime import datetime
            holiday.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        
        holiday.save()
        
        return JsonResponse({
            'status': 'success',
            'holiday': {
                'holiday_pk': holiday.holiday_pk,
                'name': holiday.name,
                'date': holiday.date.isoformat()
            }
        })
        
    except PublicHoliday.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Holiday not found'
        }, status=404)
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid date format: {str(e)}'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating holiday: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_holiday(request, holiday_pk):
    """Delete a public holiday."""
    try:
        holiday = PublicHoliday.objects.get(holiday_pk=holiday_pk)
        holiday.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Holiday deleted'
        })
        
    except PublicHoliday.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Holiday not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error deleting holiday: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ============================================================================
# TIMESHEETS AND LEAVE APPLICATIONS (from Xero API)
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_timesheets(request):
    """
    Fetch timesheets from Xero Payroll API.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    - employee_id: Optional - filter by specific employee
    - start_date: Optional - filter timesheets starting from this date (YYYY-MM-DD)
    - end_date: Optional - filter timesheets up to this date (YYYY-MM-DD)
    
    Returns timesheet data including daily hours worked.
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        employee_id = request.GET.get('employee_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
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
        
        # Build URL with filters
        url = f'{XERO_PAYROLL_AU_URL}/Timesheets'
        filters = []
        if employee_id:
            filters.append(f'EmployeeID==Guid("{employee_id}")')
        if start_date:
            filters.append(f'StartDate>=DateTime({start_date.replace("-", ",")})')
        if end_date:
            filters.append(f'EndDate<=DateTime({end_date.replace("-", ",")})')
        
        if filters:
            url += '?where=' + ' AND '.join(filters)
        
        logger.info(f"Fetching timesheets from Xero: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Xero API error: {response.status_code} - {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}',
                'details': response.text
            }, status=response.status_code)
        
        data = response.json()
        timesheets = data.get('Timesheets', [])
        
        # Process timesheet data
        processed_timesheets = []
        for ts in timesheets:
            # Parse Xero date format /Date(timestamp+offset)/
            start_date_raw = ts.get('StartDate', '')
            end_date_raw = ts.get('EndDate', '')
            
            processed_ts = {
                'timesheet_id': ts.get('TimesheetID'),
                'employee_id': ts.get('EmployeeID'),
                'start_date': _parse_xero_date(start_date_raw),
                'end_date': _parse_xero_date(end_date_raw),
                'status': ts.get('Status'),
                'hours': ts.get('Hours', 0),
                'timesheet_lines': []
            }
            
            # Process timesheet lines (daily hours by earnings type)
            for line in ts.get('TimesheetLines', []):
                processed_line = {
                    'earnings_rate_id': line.get('EarningsRateID'),
                    'tracking_item_id': line.get('TrackingItemID'),
                    'number_of_units': line.get('NumberOfUnits', []),  # Array of 7 values (Mon-Sun)
                }
                processed_ts['timesheet_lines'].append(processed_line)
            
            processed_timesheets.append(processed_ts)
        
        logger.info(f"Fetched {len(processed_timesheets)} timesheets from Xero")
        
        return JsonResponse({
            'status': 'success',
            'timesheets': processed_timesheets,
            'count': len(processed_timesheets)
        })
        
    except Exception as e:
        logger.error(f"Error fetching timesheets: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_leave_applications(request):
    """
    Fetch leave applications from Xero Payroll API.
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    - employee_id: Optional - filter by specific employee
    - status: Optional - filter by status (PENDING, APPROVED, REJECTED)
    
    Returns leave application data including dates and leave type.
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        employee_id = request.GET.get('employee_id')
        status_filter = request.GET.get('status')
        
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
        
        # Build URL with filters
        url = f'{XERO_PAYROLL_AU_URL}/LeaveApplications'
        filters = []
        if employee_id:
            filters.append(f'EmployeeID==Guid("{employee_id}")')
        if status_filter:
            filters.append(f'PayRunStatus=="{status_filter}"')
        
        if filters:
            url += '?where=' + ' AND '.join(filters)
        
        logger.info(f"Fetching leave applications from Xero: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Xero API error: {response.status_code} - {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}',
                'details': response.text
            }, status=response.status_code)
        
        data = response.json()
        leave_applications = data.get('LeaveApplications', [])
        
        # Process leave application data
        processed_applications = []
        for la in leave_applications:
            processed_la = {
                'leave_application_id': la.get('LeaveApplicationID'),
                'employee_id': la.get('EmployeeID'),
                'leave_type_id': la.get('LeaveTypeID'),
                'title': la.get('Title', ''),
                'start_date': _parse_xero_date(la.get('StartDate', '')),
                'end_date': _parse_xero_date(la.get('EndDate', '')),
                'description': la.get('Description', ''),
                'pay_out_type': la.get('PayOutType'),
                'leave_periods': []
            }
            
            # Process leave periods (individual days)
            for period in la.get('LeavePeriods', []):
                processed_period = {
                    'pay_period_start_date': _parse_xero_date(period.get('PayPeriodStartDate', '')),
                    'pay_period_end_date': _parse_xero_date(period.get('PayPeriodEndDate', '')),
                    'leave_period_status': period.get('LeavePeriodStatus'),
                    'number_of_units': period.get('NumberOfUnits', 0)
                }
                processed_la['leave_periods'].append(processed_period)
            
            processed_applications.append(processed_la)
        
        logger.info(f"Fetched {len(processed_applications)} leave applications from Xero")
        
        return JsonResponse({
            'status': 'success',
            'leave_applications': processed_applications,
            'count': len(processed_applications)
        })
        
    except Exception as e:
        logger.error(f"Error fetching leave applications: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_employee_calendar_data(request):
    """
    Get combined calendar data for an employee including:
    - Public holidays
    - Timesheets (worked days)
    - Leave applications (sick leave, annual leave)
    
    Query params:
    - xero_instance_id: ID of the Xero instance to use
    - employee_id: Xero Employee ID
    - year: Year to fetch data for (default: current year)
    - month: Optional - specific month (1-12)
    - state: State for public holidays (default: NSW)
    """
    try:
        from datetime import datetime, date, timedelta
        
        xero_instance_id = request.GET.get('xero_instance_id')
        employee_id = request.GET.get('employee_id')
        year = int(request.GET.get('year', datetime.now().year))
        month = request.GET.get('month')
        state = request.GET.get('state', 'NSW').upper()
        
        if not xero_instance_id or not employee_id:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id and employee_id are required'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json'
        }
        
        # Calculate date range
        if month:
            month = int(month)
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
        else:
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        
        # 1. Get public holidays from database
        state_calendar = PublicHolidayCalendar.objects.filter(state=state, archived=0).first()
        if not state_calendar:
            state_calendar = PublicHolidayCalendar.objects.filter(is_default=1, archived=0).first()
        
        holidays = []
        if state_calendar:
            holiday_qs = PublicHoliday.objects.filter(
                calendar=state_calendar,
                date__gte=start_date,
                date__lte=end_date
            )
            holidays = [{
                'date': h.date.isoformat(),
                'name': h.name
            } for h in holiday_qs]
        
        # 2. Get timesheets from Xero
        timesheets_url = f'{XERO_PAYROLL_AU_URL}/Timesheets?where=EmployeeID==Guid("{employee_id}")'
        ts_response = requests.get(timesheets_url, headers=headers, timeout=30)
        
        worked_days = []
        if ts_response.status_code == 200:
            ts_data = ts_response.json()
            for ts in ts_data.get('Timesheets', []):
                ts_start = _parse_xero_date(ts.get('StartDate', ''))
                if ts_start:
                    ts_start_date = datetime.strptime(ts_start, '%Y-%m-%d').date()
                    # Process each day in timesheet (Mon-Sun)
                    for line in ts.get('TimesheetLines', []):
                        units = line.get('NumberOfUnits', [])
                        for i, hours in enumerate(units):
                            if hours and float(hours) > 0:
                                day_date = ts_start_date + timedelta(days=i)
                                if start_date <= day_date <= end_date:
                                    worked_days.append({
                                        'date': day_date.isoformat(),
                                        'hours': float(hours),
                                        'earnings_rate_id': line.get('EarningsRateID')
                                    })
        
        # 3. Get leave applications from Xero
        leave_url = f'{XERO_PAYROLL_AU_URL}/LeaveApplications?where=EmployeeID==Guid("{employee_id}")'
        leave_response = requests.get(leave_url, headers=headers, timeout=30)
        
        leave_days = []
        if leave_response.status_code == 200:
            leave_data = leave_response.json()
            for la in leave_data.get('LeaveApplications', []):
                la_start = _parse_xero_date(la.get('StartDate', ''))
                la_end = _parse_xero_date(la.get('EndDate', ''))
                leave_type_id = la.get('LeaveTypeID', '')
                title = la.get('Title', '')
                leave_periods = la.get('LeavePeriods', [])
                
                logger.info(f"Leave application: start={la_start}, end={la_end}, title={title}, periods={leave_periods}")
                
                if la_start and la_end:
                    la_start_date = datetime.strptime(la_start, '%Y-%m-%d').date()
                    la_end_date = datetime.strptime(la_end, '%Y-%m-%d').date()
                    
                    # Calculate total leave hours from periods
                    total_leave_hours = sum(p.get('NumberOfUnits', 0) for p in leave_periods)
                    
                    # Fallback: try to parse hours from title (format: "X hours leave")
                    if total_leave_hours == 0 and title:
                        import re
                        match = re.search(r'([\d.]+)\s*hours?', title, re.IGNORECASE)
                        if match:
                            total_leave_hours = float(match.group(1))
                            logger.info(f"Parsed {total_leave_hours} hours from title: {title}")
                    
                    # If single day leave, use total hours; otherwise estimate per day
                    days_count = (la_end_date - la_start_date).days + 1
                    hours_per_day = total_leave_hours / days_count if days_count > 0 else total_leave_hours
                    
                    # Generate each day of leave
                    current_date = la_start_date
                    while current_date <= la_end_date:
                        if start_date <= current_date <= end_date:
                            leave_days.append({
                                'date': current_date.isoformat(),
                                'leave_type_id': leave_type_id,
                                'title': title,
                                'hours': hours_per_day
                            })
                        current_date += timedelta(days=1)
        
        # 4. Get leave types for mapping
        pay_items_url = f'{XERO_PAYROLL_AU_URL}/PayItems'
        pay_items_response = requests.get(pay_items_url, headers=headers, timeout=30)
        
        leave_types = {}
        if pay_items_response.status_code == 200:
            pay_items_data = pay_items_response.json()
            for lt in pay_items_data.get('PayItems', {}).get('LeaveTypes', []):
                leave_types[lt.get('LeaveTypeID')] = {
                    'name': lt.get('Name', ''),
                    'type_of_units': lt.get('TypeOfUnits'),
                    'is_paid_leave': lt.get('IsPaidLeave', False)
                }
        
        return JsonResponse({
            'status': 'success',
            'employee_id': employee_id,
            'year': year,
            'month': month,
            'state': state,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'public_holidays': holidays,
            'worked_days': worked_days,
            'leave_days': leave_days,
            'leave_types': leave_types
        })
        
    except Exception as e:
        logger.error(f"Error fetching employee calendar data: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def save_timesheet(request):
    """
    Create or update a timesheet entry in Xero.
    
    POST body:
    {
        "xero_instance_id": "xxx",
        "employee_id": "xxx",
        "date": "YYYY-MM-DD",
        "hours": 8.0,
        "earnings_rate_id": "xxx" (optional - uses employee's ordinary earnings rate if not provided)
    }
    """
    from datetime import datetime, timedelta
    
    try:
        data = json.loads(request.body)
        xero_instance_id = data.get('xero_instance_id')
        employee_id = data.get('employee_id')
        date_str = data.get('date')
        hours = float(data.get('hours', 0))
        earnings_rate_id = data.get('earnings_rate_id')
        
        if not all([xero_instance_id, employee_id, date_str]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields: xero_instance_id, employee_id, date'
            }, status=400)
        
        # Get Xero auth - pass the integer ID, get_xero_auth fetches the instance
        xero_instance, access_token, tenant_id = get_xero_auth(int(xero_instance_id))
        
        if not xero_instance:
            # access_token contains the error JsonResponse when xero_instance is None
            return access_token
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Parse the target date
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get employee details to find their payroll calendar and ordinary earnings rate
        emp_url = f'{XERO_PAYROLL_AU_URL}/Employees/{employee_id}'
        emp_response = requests.get(emp_url, headers=headers, timeout=15)
        
        if emp_response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to fetch employee details: {emp_response.status_code}'
            }, status=emp_response.status_code)
        
        emp_data = emp_response.json()
        employee = emp_data.get('Employees', [{}])[0]
        payroll_calendar_id = employee.get('PayrollCalendarID')
        
        if not earnings_rate_id:
            earnings_rate_id = employee.get('OrdinaryEarningsRateID')
        
        if not earnings_rate_id:
            return JsonResponse({
                'status': 'error',
                'message': 'No earnings rate ID available for this employee'
            }, status=400)
        
        # Get payroll calendar to determine pay period
        period_days = 7  # Default
        calendar_start_date = None
        
        if payroll_calendar_id:
            cal_url = f'{XERO_PAYROLL_AU_URL}/PayrollCalendars/{payroll_calendar_id}'
            cal_response = requests.get(cal_url, headers=headers, timeout=15)
            
            if cal_response.status_code == 200:
                cal_data = cal_response.json()
                calendars = cal_data.get('PayrollCalendars', [])
                if calendars:
                    calendar = calendars[0]
                    calendar_type = calendar.get('CalendarType', 'WEEKLY')
                    
                    # Get the calendar's reference start date
                    start_date_str = calendar.get('StartDate')
                    if start_date_str:
                        calendar_start_date = _parse_xero_date(start_date_str)
                        if calendar_start_date:
                            calendar_start_date = datetime.strptime(calendar_start_date, '%Y-%m-%d').date()
                    
                    # Determine period length
                    if calendar_type == 'WEEKLY':
                        period_days = 7
                    elif calendar_type == 'FORTNIGHTLY':
                        period_days = 14
                    elif calendar_type == 'FOURWEEKLY':
                        period_days = 28
                    elif calendar_type == 'MONTHLY':
                        period_days = 30  # Monthly is more complex, may need special handling
                    else:
                        period_days = 7
        
        # Calculate the pay period containing the target date
        # Must align with the payroll calendar's start date
        if calendar_start_date:
            # Calculate days since the calendar's reference start
            days_since_start = (target_date - calendar_start_date).days
            # Find which period we're in
            periods_elapsed = days_since_start // period_days
            period_start = calendar_start_date + timedelta(days=periods_elapsed * period_days)
            period_end = period_start + timedelta(days=period_days - 1)
        else:
            # Fallback: assume weeks start on Monday
            days_since_monday = target_date.weekday()
            period_start = target_date - timedelta(days=days_since_monday)
            period_end = period_start + timedelta(days=period_days - 1)
        
        # Calculate which day index in the period (0-based)
        day_index = (target_date - period_start).days
        
        # Check for existing timesheet for this period
        timesheets_url = f'{XERO_PAYROLL_AU_URL}/Timesheets'
        params = {
            'where': f'EmployeeID==Guid("{employee_id}")'
        }
        
        existing_response = requests.get(timesheets_url, headers=headers, params=params, timeout=30)
        existing_timesheet = None
        
        if existing_response.status_code == 200:
            existing_data = existing_response.json()
            for ts in existing_data.get('Timesheets', []):
                ts_start = _parse_xero_date(ts.get('StartDate'))
                if ts_start:
                    ts_start_date = datetime.strptime(ts_start, '%Y-%m-%d').date()
                    if ts_start_date == period_start and ts.get('Status') == 'DRAFT':
                        existing_timesheet = ts
                        break
        
        # Build the TimesheetLines array, preserving existing lines
        timesheet_lines = []
        number_of_units = [0] * period_days
        found_matching_line = False
        
        if existing_timesheet:
            # Preserve all existing timesheet lines
            for line in existing_timesheet.get('TimesheetLines', []):
                line_rate_id = line.get('EarningsRateID')
                line_units = list(line.get('NumberOfUnits', [0] * period_days))
                
                if line_rate_id == earnings_rate_id:
                    # This is the line we want to update
                    found_matching_line = True
                    # Ensure the array is the right length
                    while len(line_units) < period_days:
                        line_units.append(0)
                    # Set the hours for the target day
                    if day_index < len(line_units):
                        line_units[day_index] = hours
                    timesheet_lines.append({
                        'EarningsRateID': line_rate_id,
                        'NumberOfUnits': [float(u) for u in line_units]
                    })
                else:
                    # Keep other lines unchanged
                    timesheet_lines.append({
                        'EarningsRateID': line_rate_id,
                        'NumberOfUnits': [float(u) for u in line_units]
                    })
        
        # If we didn't find a matching line, add a new one
        if not found_matching_line:
            number_of_units[day_index] = hours
            timesheet_lines.append({
                'EarningsRateID': earnings_rate_id,
                'NumberOfUnits': [float(u) for u in number_of_units]
            })
        
        # Convert date to Xero format
        start_timestamp = int(datetime.combine(period_start, datetime.min.time()).timestamp() * 1000)
        end_timestamp = int(datetime.combine(period_end, datetime.min.time()).timestamp() * 1000)
        
        timesheet_payload = {
            'EmployeeID': employee_id,
            'StartDate': f'/Date({start_timestamp})/',
            'EndDate': f'/Date({end_timestamp})/',
            'Status': 'DRAFT',
            'TimesheetLines': timesheet_lines
        }
        
        if existing_timesheet:
            timesheet_payload['TimesheetID'] = existing_timesheet.get('TimesheetID')
        
        logger.info(f"Sending timesheet payload: {timesheet_payload}")
        
        # Submit to Xero - Xero expects an array, not an object with 'Timesheets' key
        response = requests.post(
            timesheets_url,
            headers=headers,
            json=[timesheet_payload],
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result_data = response.json()
            return JsonResponse({
                'status': 'success',
                'message': 'Timesheet saved successfully',
                'timesheet': result_data.get('Timesheets', [{}])[0]
            })
        else:
            logger.error(f"Xero timesheet API error: {response.status_code} - {response.text}")
            # Try to parse error details from Xero response
            error_details = response.text
            try:
                error_json = response.json()
                if 'Message' in error_json:
                    error_details = error_json['Message']
                elif 'Elements' in error_json:
                    # Xero validation errors
                    elements = error_json.get('Elements', [])
                    if elements and 'ValidationErrors' in elements[0]:
                        errors = elements[0]['ValidationErrors']
                        error_details = '; '.join([e.get('Message', '') for e in errors])
            except:
                pass
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {error_details}',
                'details': response.text
            }, status=400)
        
    except XeroInstance.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Xero instance not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error saving timesheet: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def _parse_xero_date(xero_date_str):
    """
    Parse Xero's date format /Date(timestamp+offset)/ to YYYY-MM-DD.
    Returns None if parsing fails.
    """
    if not xero_date_str:
        return None
    
    try:
        import re
        from datetime import datetime
        
        # Match /Date(1234567890000+0000)/ or /Date(1234567890000)/
        match = re.search(r'/Date\((\d+)([+-]\d+)?\)/', xero_date_str)
        if match:
            timestamp_ms = int(match.group(1))
            timestamp_s = timestamp_ms / 1000
            dt = datetime.fromtimestamp(timestamp_s)
            return dt.strftime('%Y-%m-%d')
        
        # If it's already in YYYY-MM-DD format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', xero_date_str):
            return xero_date_str
        
        return None
    except Exception:
        return None


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_projects_for_allocation(request):
    """
    Get active projects for hour allocation dropdown.
    Only returns projects with status=2 (execution).
    """
    try:
        # Get all execution-phase, non-archived projects (no xero_instance filter for now)
        projects = Projects.objects.filter(archived=0, project_status=2)
        
        projects_list = []
        for p in projects.order_by('project'):
            try:
                type_name = p.project_type.project_type_name if p.project_type else None
            except:
                type_name = None
            projects_list.append({
                'id': p.projects_pk,
                'name': p.project,
                'type': type_name
            })
        
        return JsonResponse({
            'status': 'success',
            'projects': projects_list
        })
    except Exception as e:
        import traceback
        logger.error(f"Error getting projects: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_costings_for_project(request):
    """
    Get costing items for a specific project.
    """
    try:
        project_id = request.GET.get('project_id')
        
        if not project_id:
            return JsonResponse({'status': 'error', 'message': 'project_id required'}, status=400)
        
        costings = Costing.objects.filter(
            project_id=project_id,
            category__division=-5,  # Only Labour categories
            tender_or_execution=2  # Only execution mode costings
        ).order_by('order_in_list')
        
        costings_list = [{
            'id': c.costing_pk,
            'item': c.item,
            'category': c.category.category if c.category else None
        } for c in costings]
        
        return JsonResponse({
            'status': 'success',
            'costings': costings_list
        })
    except Exception as e:
        logger.error(f"Error getting costings: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_employee_pay_rate(employee, target_date):
    """
    Get the applicable hourly pay rate for an employee as of a specific date.
    Returns the most recent EmployeePayRate where effective_date <= target_date.
    
    For hourly employees: uses rate_per_unit directly
    For salaried employees: calculates hourly rate from annual_salary / (units_per_week * 52)
    """
    pay_rate = EmployeePayRate.objects.filter(
        employee=employee,
        effective_date__lte=target_date,
        is_ordinary_rate=True
    ).order_by('-effective_date').first()
    
    if not pay_rate:
        return None
    
    # Try rate_per_unit first (hourly employees)
    if pay_rate.rate_per_unit:
        return float(pay_rate.rate_per_unit)
    
    # Fallback for salaried employees: calculate hourly rate
    if pay_rate.annual_salary and pay_rate.units_per_week:
        # annual_salary / (hours_per_week * 52 weeks)
        weekly_hours = float(pay_rate.units_per_week)
        if weekly_hours > 0:
            hourly_rate = float(pay_rate.annual_salary) / (weekly_hours * 52)
            return round(hourly_rate, 4)
    
    return None


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_allocations(request):
    """
    Get hour allocations for a specific employee and date.
    Also calculates daily cost based on hours × applicable pay rate.
    """
    try:
        xero_instance_id = request.GET.get('xero_instance_id')
        employee_id = request.GET.get('employee_id')
        date_str = request.GET.get('date')
        
        if not all([xero_instance_id, employee_id, date_str]):
            return JsonResponse({'status': 'error', 'message': 'Missing required params'}, status=400)
        
        # Find the employee
        employee = Employee.objects.filter(
            xero_instance_id=xero_instance_id,
            xero_employee_id=employee_id
        ).first()
        
        if not employee:
            return JsonResponse({'status': 'success', 'allocations': [], 'daily_cost': None})
        
        # Find staff hours record for this date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid date format'}, status=400)
        
        staff_hours = StaffHours.objects.filter(employee=employee, date=target_date).first()
        
        # Get hours from request param (Xero data) or local StaffHours
        hours_param = request.GET.get('hours')
        if hours_param:
            total_hours = float(hours_param)
        elif staff_hours:
            total_hours = float(staff_hours.hours) if staff_hours.hours else 0
        else:
            total_hours = 0
        
        allocations_list = []
        if staff_hours:
            allocations = StaffHoursAllocations.objects.filter(staff_hours=staff_hours)
            for a in allocations:
                alloc_data = {
                    'id': a.allocation_pk,
                    'allocation_type': a.allocation_type,
                    'allocation_type_display': a.get_allocation_type_display(),
                    'hours': float(a.hours),
                    'note': a.note or ''
                }
                if a.allocation_type == 1 and a.project and a.costing:  # Project
                    alloc_data['project_id'] = a.project_id
                    alloc_data['project_name'] = a.project.project
                    alloc_data['costing_id'] = a.costing_id
                    alloc_data['costing_item'] = a.costing.item
                else:
                    alloc_data['project_id'] = None
                    alloc_data['project_name'] = None
                    alloc_data['costing_id'] = None
                    alloc_data['costing_item'] = None
                allocations_list.append(alloc_data)
        
        total_allocated = sum(a['hours'] for a in allocations_list)
        
        # Calculate daily cost using applicable pay rate
        rate_per_unit = get_employee_pay_rate(employee, target_date)
        daily_cost = None
        if rate_per_unit and total_hours > 0:
            daily_cost = round(total_hours * rate_per_unit, 2)
        
        return JsonResponse({
            'status': 'success',
            'allocations': allocations_list,
            'total_allocated': total_allocated,
            'total_hours': total_hours,
            'rate_per_unit': rate_per_unit,
            'daily_cost': daily_cost
        })
    except Exception as e:
        logger.error(f"Error getting allocations: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def save_allocation(request):
    """
    Save or update an hour allocation.
    Supports: Project (type=1), Unchargeable (type=2), Other Chargeable (type=3)
    """
    try:
        data = json.loads(request.body)
        xero_instance_id = data.get('xero_instance_id')
        employee_id = data.get('employee_id')
        date_str = data.get('date')
        allocation_type = int(data.get('allocation_type', 1))  # Default to Project
        project_id = data.get('project_id')
        costing_id = data.get('costing_id')
        hours = data.get('hours')
        note = data.get('note', '')
        
        # Validate based on allocation type
        if allocation_type == 1:  # Project
            if not all([xero_instance_id, employee_id, date_str, project_id, costing_id, hours is not None]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields for Project allocation'}, status=400)
        else:  # Unchargeable or Other Chargeable
            if not all([xero_instance_id, employee_id, date_str, hours is not None]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
            if not note:
                return JsonResponse({'status': 'error', 'message': 'Note is required for Unchargeable/Other Chargeable allocations'}, status=400)
        
        # Find employee
        employee = Employee.objects.filter(
            xero_instance_id=xero_instance_id,
            xero_employee_id=employee_id
        ).first()
        
        if not employee:
            return JsonResponse({'status': 'error', 'message': 'Employee not found'}, status=404)
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get or create StaffHours record
        staff_hours, _ = StaffHours.objects.get_or_create(
            employee=employee,
            date=target_date,
            defaults={'hours': 0}
        )
        
        # Create or update allocation based on type
        if allocation_type == 1:  # Project allocation
            allocation, created = StaffHoursAllocations.objects.update_or_create(
                staff_hours=staff_hours,
                allocation_type=allocation_type,
                project_id=project_id,
                costing_id=costing_id,
                defaults={'hours': hours, 'note': note}
            )
        else:  # Unchargeable or Other Chargeable
            allocation, created = StaffHoursAllocations.objects.update_or_create(
                staff_hours=staff_hours,
                allocation_type=allocation_type,
                defaults={'hours': hours, 'note': note, 'project': None, 'costing': None}
            )
        
        return JsonResponse({
            'status': 'success',
            'allocation_id': allocation.allocation_pk,
            'created': created
        })
    except Exception as e:
        logger.error(f"Error saving allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
@login_required
def delete_allocation(request, allocation_pk):
    """
    Delete an hour allocation.
    """
    try:
        allocation = StaffHoursAllocations.objects.get(allocation_pk=allocation_pk)
        allocation.delete()
        
        return JsonResponse({'status': 'success'})
    except StaffHoursAllocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_leave_application(request):
    """
    Create a leave application in Xero Payroll AU.
    
    POST body (JSON):
    - xero_instance_id: ID of the Xero instance
    - employee_id: Xero Employee ID
    - leave_type_id: Xero Leave Type ID
    - date: Date for the leave (YYYY-MM-DD)
    - hours: Number of hours (supports partial days)
    - description: Optional comment/reason for leave
    """
    try:
        import json
        from datetime import datetime
        
        data = json.loads(request.body)
        xero_instance_id = data.get('xero_instance_id')
        employee_id = data.get('employee_id')
        leave_type_id = data.get('leave_type_id')
        date_str = data.get('date')
        hours = float(data.get('hours', 8))
        description = data.get('description', '')
        
        if not all([xero_instance_id, employee_id, leave_type_id, date_str]):
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_id, employee_id, leave_type_id, and date are required'
            }, status=400)
        
        # Parse date
        leave_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Xero-tenant-id': tenant_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Build leave application payload for Xero AU
        # Format date as Xero expects: /Date(milliseconds+timezone)/
        import time
        import calendar
        # Use UTC timestamp to avoid timezone issues
        date_ms = int(calendar.timegm(leave_date.timetuple()) * 1000)
        
        # For partial day leave, we need to specify units
        # Use Title to specify hours for partial leave
        leave_payload = {
            'EmployeeID': employee_id,
            'LeaveTypeID': leave_type_id,
            'Title': f'{hours} hours leave',
            'Description': description or '',
            'StartDate': f'/Date({date_ms}+0000)/',
            'EndDate': f'/Date({date_ms}+0000)/',
        }
        
        # Only add LeavePeriods if partial day (less than standard day)
        if hours < 7.6:
            leave_payload['LeavePeriods'] = [{
                'NumberOfUnits': hours,
                'LeavePeriodStatus': 'SCHEDULED'
            }]
        
        logger.info(f"Creating leave application for employee {employee_id}: {leave_payload}")
        
        # POST to Xero - Xero AU expects array directly, not wrapped in object
        url = f'{XERO_PAYROLL_AU_URL}/LeaveApplications'
        response = requests.post(url, headers=headers, json=[leave_payload], timeout=30)
        
        if response.status_code not in [200, 201]:
            logger.error(f"Xero leave application error: {response.status_code} - {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.text}'
            }, status=response.status_code)
        
        result = response.json()
        leave_applications = result.get('LeaveApplications', [])
        
        if leave_applications:
            created_la = leave_applications[0]
            logger.info(f"Leave application created: {created_la.get('LeaveApplicationID')}")
            return JsonResponse({
                'status': 'success',
                'leave_application_id': created_la.get('LeaveApplicationID'),
                'message': 'Leave application created successfully'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'No leave application returned from Xero'
            }, status=500)
        
    except Exception as e:
        logger.error(f"Error creating leave application: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
