"""
Contract Budget related views.

Template Rendering:
1. contract_budget_view - Render Contract Budget section template (supports project_pk, is_tender query params)

Data Updates:
2. update_uncommitted - Update uncommitted amount for a costing item
3. get_project_committed_amounts - Get committed amounts per item for a project
4. get_item_quote_allocations - Get individual quote allocations for an item with quote/contact details
"""

import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum

from ..models import Costing, Projects, Quotes, Quote_allocations, Categories, StaffHoursAllocations, EmployeePayRate

logger = logging.getLogger(__name__)


def contract_budget_view(request):
    """Render the Contract Budget section template with column configuration.
    
    Accepts query parameters:
    - project_pk: Project primary key
    - is_tender: '1' for tender mode (reduced columns), '0' for execution mode (full columns)
    
    Uses allocations_layout.html with hide_viewer=True, hide_allocations=True.
    Construction mode has subheadings: Uncommitted > Qty|Rate|Amount
    """
    project_pk = request.GET.get('project_pk')
    is_tender_param = request.GET.get('is_tender', '0')
    is_tender = is_tender_param == '1'
    is_construction = False
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            # Use rates_based flag from ProjectTypes instead of hardcoded project type names
            is_construction = (project.project_type and project.project_type.rates_based == 1)
        except Projects.DoesNotExist:
            pass
    
    # Column configurations for all 4 variants
    # Construction mode has subheadings: Uncommitted > Qty|Rate|Amount
    # parent_header, is_first_child, parent_colspan used for two-row header rendering
    
    has_subheadings = is_construction  # Only construction has subheadings
    
    if is_tender:
        if is_construction:
            # Tender + Construction: 10 columns with Uncommitted and Committed subheadings
            main_table_columns = [
                {'header': 'Category / Item', 'width': '22%', 'field': 'item'},
                {'header': 'Unit', 'width': '5%', 'field': 'unit'},
                {'header': 'Working Budget', 'width': '10%', 'field': 'working_budget'},
                {'header': 'Qty', 'width': '7%', 'field': 'uncommitted_qty', 'parent_header': 'Uncommitted', 'is_first_child': True, 'parent_colspan': 4, 'input': True},
                {'header': 'Rate', 'width': '7%', 'field': 'uncommitted_rate', 'parent_header': 'Uncommitted', 'input': True},
                {'header': 'Amount', 'width': '9%', 'field': 'uncommitted_amount', 'parent_header': 'Uncommitted', 'calculated': True},
                {'header': 'Notes', 'width': '4%', 'field': 'uncommitted_notes', 'parent_header': 'Uncommitted', 'icon': True},
                {'header': 'Qty', 'width': '7%', 'field': 'committed_qty', 'parent_header': 'Committed', 'is_first_child': True, 'parent_colspan': 3},
                {'header': 'Rate', 'width': '7%', 'field': 'committed_rate', 'parent_header': 'Committed'},
                {'header': 'Amount', 'width': '9%', 'field': 'committed_amount', 'parent_header': 'Committed'},
            ]
        else:
            # Tender + Non-construction: 6 columns (added Notes)
            main_table_columns = [
                {'header': 'Category / Item', 'width': '30%', 'field': 'item'},
                {'header': 'Unit', 'width': '8%', 'field': 'unit'},
                {'header': 'Working Budget', 'width': '16%', 'field': 'working_budget'},
                {'header': 'Uncommitted', 'width': '16%', 'field': 'uncommitted_amount', 'input': True},
                {'header': 'Notes', 'width': '6%', 'field': 'uncommitted_notes', 'icon': True},
                {'header': 'Committed', 'width': '16%', 'field': 'committed'},
            ]
    else:
        if is_construction:
            # Execution + Construction: 14 columns with Uncommitted and Committed subheadings
            main_table_columns = [
                {'header': 'Category / Item', 'width': '10%', 'field': 'item'},
                {'header': 'Unit', 'width': '4%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '8%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '8%', 'field': 'working_budget'},
                {'header': 'Qty', 'width': '6%', 'field': 'uncommitted_qty', 'parent_header': 'Uncommitted', 'is_first_child': True, 'parent_colspan': 4, 'input': True},
                {'header': 'Rate', 'width': '6%', 'field': 'uncommitted_rate', 'parent_header': 'Uncommitted', 'input': True},
                {'header': 'Amount', 'width': '7%', 'field': 'uncommitted_amount', 'parent_header': 'Uncommitted', 'calculated': True},
                {'header': 'Notes', 'width': '4%', 'field': 'uncommitted_notes', 'parent_header': 'Uncommitted', 'icon': True},
                {'header': 'Qty', 'width': '6%', 'field': 'committed_qty', 'parent_header': 'Committed', 'is_first_child': True, 'parent_colspan': 3},
                {'header': 'Rate', 'width': '6%', 'field': 'committed_rate', 'parent_header': 'Committed'},
                {'header': 'Amount', 'width': '8%', 'field': 'committed_amount', 'parent_header': 'Committed'},
                {'header': 'C2C', 'width': '7%', 'field': 'cost_to_complete'},
                {'header': 'Billed', 'width': '7%', 'field': 'billed'},
                {'header': 'Fixed on Site', 'width': '7%', 'field': 'fixed_on_site'},
            ]
        else:
            # Execution + Non-construction: 10 columns (added Notes)
            main_table_columns = [
                {'header': 'Category / Item', 'width': '12%', 'field': 'item'},
                {'header': 'Unit', 'width': '5%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '10%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '10%', 'field': 'working_budget'},
                {'header': 'Uncommitted', 'width': '10%', 'field': 'uncommitted_amount', 'input': True},
                {'header': 'Notes', 'width': '5%', 'field': 'uncommitted_notes', 'icon': True},
                {'header': 'Committed', 'width': '15%', 'field': 'committed'},
                {'header': 'C2C', 'width': '10%', 'field': 'cost_to_complete'},
                {'header': 'Billed', 'width': '10%', 'field': 'billed'},
                {'header': 'Fixed on Site', 'width': '10%', 'field': 'fixed_on_site'},
            ]
    
    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
        'is_tender': is_tender,
        'has_subheadings': has_subheadings,
        # For allocations_layout.html
        'section_id': 'contractBudget',
        'main_table_columns': main_table_columns,
        'hide_viewer': True,
        'hide_allocations': True,
    }
    return render(request, 'core/contract_budget.html', context)


@csrf_exempt
def update_uncommitted(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        
        try:
            costing = Costing.objects.get(costing_pk=costing_pk)
            
            # Only update fields that are provided in the request
            if 'uncommitted' in data:
                costing.uncommitted_amount = data['uncommitted']
            if 'notes' in data:
                # Truncate to 1000 chars to match model field
                notes = data['notes']
                if notes and len(notes) > 1000:
                    notes = notes[:1000]
                costing.uncommitted_notes = notes
            if 'uncommitted_qty' in data:
                costing.uncommitted_qty = data['uncommitted_qty']
            if 'uncommitted_rate' in data:
                costing.uncommitted_rate = data['uncommitted_rate']
            
            costing.save()
            return JsonResponse({'status': 'success'})
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Costing not found'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@require_http_methods(["GET"])
def get_project_committed_amounts(request, project_pk):
    """
    Get committed amounts (sum of quote allocations) per item for a project.
    For Internal category items, use contract_budget as committed amount.
    
    For construction/precast/pods projects, returns detailed data:
    {costing_pk: {qty: X, rate: Y, amount: Z}}
    
    For other project types, returns simple amounts:
    {costing_pk: amount}
    
    Query params:
    - tender_or_execution: '1' for tender, '2' for execution (default: '1')
    """
    try:
        project = get_object_or_404(Projects, pk=project_pk)
        # Use rates_based flag from ProjectTypes instead of hardcoded project type names
        is_construction = (project.project_type and project.project_type.rates_based == 1)
        
        # Get tender_or_execution filter (default to tender)
        tender_or_execution = int(request.GET.get('tender_or_execution', '1'))
        
        # Get all quotes for this project filtered by tender_or_execution
        project_quotes = Quotes.objects.filter(project=project, tender_or_execution=tender_or_execution)
        
        if is_construction:
            # For construction types, return qty, rate, amount per item
            # Check for multiple unique rates per costing item
            allocations = Quote_allocations.objects.filter(
                quotes_pk__in=project_quotes
            ).values('item__costing_pk', 'qty', 'rate', 'amount')
            
            # Group allocations by costing_pk
            from collections import defaultdict
            allocations_by_item = defaultdict(list)
            for alloc in allocations:
                allocations_by_item[alloc['item__costing_pk']].append(alloc)
            
            # Convert to dictionary with qty, rate, amount
            # If multiple unique rates exist for an item, mark has_multiple_rates
            committed_dict = {}
            for costing_pk, allocs in allocations_by_item.items():
                total_qty = sum(float(a['qty'] or 0) for a in allocs)
                total_amount = sum(float(a['amount'] or 0) for a in allocs)
                
                # Get unique non-null rates
                unique_rates = set(float(a['rate']) for a in allocs if a['rate'] is not None)
                
                if len(unique_rates) > 1:
                    # Multiple different rates - show "multiple" for qty and rate
                    committed_dict[costing_pk] = {
                        'qty': total_qty,
                        'rate': None,
                        'amount': total_amount,
                        'has_multiple_rates': True
                    }
                else:
                    # Single rate (or no rates) - show actual values
                    rate = list(unique_rates)[0] if unique_rates else 0
                    committed_dict[costing_pk] = {
                        'qty': total_qty,
                        'rate': round(rate, 2),
                        'amount': total_amount,
                        'has_multiple_rates': False
                    }
        else:
            # For non-construction, return simple amounts
            committed_amounts = Quote_allocations.objects.filter(
                quotes_pk__in=project_quotes
            ).values('item__costing_pk').annotate(
                total_committed=Sum('amount')
            )
            
            committed_dict = {
                item['item__costing_pk']: float(item['total_committed'])
                for item in committed_amounts
            }
        
        # For Internal category items, use contract_budget as committed amount
        # (since they don't use uncommitted or quote allocations)
        internal_items = Costing.objects.filter(
            project=project,
            category__category='Internal',
            tender_or_execution=tender_or_execution
        )
        
        for item in internal_items:
            if is_construction:
                committed_dict[item.costing_pk] = {
                    'qty': 0,
                    'rate': 0,
                    'amount': float(item.contract_budget or 0)
                }
            else:
                committed_dict[item.costing_pk] = float(item.contract_budget or 0)
        
        # For Labour category items (division=-5), calculate committed from StaffHoursAllocations
        # Sum of (hours * applicable pay rate) for each costing item
        labour_items = Costing.objects.filter(
            project=project,
            category__division=-5,  # Labour category
            tender_or_execution=tender_or_execution
        )
        
        for item in labour_items:
            # Get all staff hour allocations for this costing item
            allocations = StaffHoursAllocations.objects.filter(
                project=project,
                costing=item
            ).select_related('staff_hours__employee')
            
            total_amount = Decimal('0')
            for alloc in allocations:
                hours = alloc.hours or Decimal('0')
                if hours > 0:
                    # Get the pay rate for this employee as of the allocation date
                    employee = alloc.staff_hours.employee
                    target_date = alloc.staff_hours.date
                    
                    # Get applicable pay rate (most recent before or on target_date)
                    pay_rate = EmployeePayRate.objects.filter(
                        employee=employee,
                        effective_date__lte=target_date,
                        is_ordinary_rate=True
                    ).order_by('-effective_date').first()
                    
                    if pay_rate:
                        # Calculate hourly rate
                        hourly_rate = None
                        if pay_rate.rate_per_unit:
                            hourly_rate = float(pay_rate.rate_per_unit)
                        elif pay_rate.annual_salary and pay_rate.units_per_week:
                            weekly_hours = float(pay_rate.units_per_week)
                            if weekly_hours > 0:
                                hourly_rate = float(pay_rate.annual_salary) / (weekly_hours * 52)
                        
                        if hourly_rate:
                            total_amount += Decimal(str(float(hours) * hourly_rate))
            
            # Set committed amount for Labour items (no qty/rate, just amount)
            if is_construction:
                committed_dict[item.costing_pk] = {
                    'qty': None,
                    'rate': None,
                    'amount': float(total_amount),
                    'is_labour': True
                }
            else:
                committed_dict[item.costing_pk] = float(total_amount)
        
        return JsonResponse({
            'status': 'success',
            'committed_amounts': committed_dict,
            'is_construction': is_construction
        })
        
    except Exception as e:
        logger.error(f"Error getting committed amounts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting committed amounts: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_item_quote_allocations(request, item_pk):
    """
    Get individual quote allocations for a specific item with quote/contact details.
    Returns list of allocations with associated quote and contact information.
    """
    try:
        costing = get_object_or_404(Costing, pk=item_pk)
        
        # Get all quote allocations for this item
        allocations = Quote_allocations.objects.filter(
            item=costing
        ).select_related('quotes_pk', 'quotes_pk__contact_pk')
        
        allocations_list = []
        for alloc in allocations:
            quote = alloc.quotes_pk
            contact = quote.contact_pk if quote else None
            
            allocations_list.append({
                'allocation_pk': alloc.quote_allocations_pk,
                'qty': float(alloc.qty) if alloc.qty else 0,
                'rate': float(alloc.rate) if alloc.rate else 0,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'unit': alloc.unit or '',
                'notes': alloc.notes or '',
                'quote_pk': quote.quotes_pk if quote else None,
                'supplier_quote_number': quote.supplier_quote_number if quote else '',
                'contact_name': contact.name if contact else 'Unknown',
                'contact_pk': contact.contact_pk if contact else None,
            })
        
        return JsonResponse({
            'status': 'success',
            'allocations': allocations_list
        })
        
    except Exception as e:
        logger.error(f"Error getting item quote allocations: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting quote allocations: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def validate_fix_contract_budget(request, project_pk):
    """
    Validate that a project's costing items are ready to fix the contract budget.
    Checks:
    1. All Costing.xero_account_code must be not null (mandatory)
    2. All Costing.xero_tracking_category should be not null (warning only)
    """
    try:
        project = get_object_or_404(Projects, pk=project_pk)
        
        # Get all tender costing items for this project
        costing_items = Costing.objects.filter(project=project, tender_or_execution=1)
        
        missing_xero_account_codes = []
        missing_xero_tracking_categories = []
        
        for item in costing_items:
            if not item.xero_account_code or item.xero_account_code.strip() == '':
                missing_xero_account_codes.append({
                    'costing_pk': item.costing_pk,
                    'item': item.item
                })
            if not item.xero_tracking_category or item.xero_tracking_category.strip() == '':
                missing_xero_tracking_categories.append({
                    'costing_pk': item.costing_pk,
                    'item': item.item
                })
        
        return JsonResponse({
            'status': 'success',
            'missing_xero_account_codes': missing_xero_account_codes,
            'missing_xero_tracking_categories': missing_xero_tracking_categories
        })
        
    except Exception as e:
        logger.error(f"Error validating fix contract budget: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error validating: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def fix_contract_budget(request, project_pk):
    """
    Fix the contract budget - transition project from Tender to Execution mode.
    
    This performs the following operations:
    1. Mark all existing Costing entries as tender (tender_or_execution=1)
    2. Copy all Costing entries with tender_or_execution=2 and set contract_budget = uncommitted_amount + quote_allocations
    3. Mark all existing Quotes entries as tender (tender_or_execution=1)
    4. Copy all Quotes and Quote_allocations with tender_or_execution=2
    5. Set Projects.project_status=2 (execution mode)
    """
    try:
        from django.db import transaction
        
        project = get_object_or_404(Projects, pk=project_pk)
        
        # Verify project is in tender mode
        if project.project_status != 1:
            return JsonResponse({
                'status': 'error',
                'message': 'Project is not in Tender mode'
            }, status=400)
        
        with transaction.atomic():
            # Step 1: Get all tender costing items
            tender_costings = Costing.objects.filter(project=project, tender_or_execution=1)
            
            # Ensure all are marked as tender (should already be default)
            tender_costings.update(tender_or_execution=1)
            
            # Step 2: Copy costing entries for execution mode
            # Build a mapping of old costing_pk to new costing_pk for quote allocations
            costing_pk_mapping = {}
            
            # Check if project is rates_based
            rates_based = project.project_type.rates_based if project.project_type else 0
            
            logger.info(f"[fix_contract_budget] === Starting contract budget fix for project {project_pk} (rates_based={rates_based}) ===")
            
            for tender_costing in tender_costings:
                # Calculate contract_budget = uncommitted_value + sum of quote allocations
                quote_allocations = Quote_allocations.objects.filter(item=tender_costing)
                quote_alloc_sum = quote_allocations.aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                # For rates_based=1: calculate uncommitted from rate * qty
                # For rates_based=0: use uncommitted_amount directly
                if rates_based == 1:
                    uncommitted_rate = tender_costing.uncommitted_rate or Decimal('0')
                    uncommitted_qty = tender_costing.uncommitted_qty or Decimal('0')
                    uncommitted_amt = uncommitted_rate * uncommitted_qty
                else:
                    uncommitted_amt = tender_costing.uncommitted_amount or Decimal('0')
                
                new_contract_budget = uncommitted_amt + quote_alloc_sum
                
                # Debug logging
                logger.info(f"[fix_contract_budget] Costing PK={tender_costing.costing_pk}, Item='{tender_costing.item}'")
                logger.info(f"  - uncommitted_qty: {tender_costing.uncommitted_qty}")
                logger.info(f"  - uncommitted_rate: {tender_costing.uncommitted_rate}")
                logger.info(f"  - uncommitted_amount (raw): {tender_costing.uncommitted_amount}")
                logger.info(f"  - uncommitted_value (calculated): {uncommitted_amt} {'(rate*qty)' if rates_based == 1 else '(amount)'}")
                logger.info(f"  - Quote allocations count: {quote_allocations.count()}")
                for qa in quote_allocations:
                    logger.info(f"    - Quote Alloc PK={qa.quote_allocations_pk}, amount={qa.amount}, quote_pk={qa.quotes_pk_id}")
                logger.info(f"  - quote_alloc_sum: {quote_alloc_sum}")
                logger.info(f"  - NEW contract_budget: {new_contract_budget}")
                
                # Create execution copy
                old_pk = tender_costing.costing_pk
                
                # For Internal category items, zero out uncommitted fields in execution mode
                is_internal = tender_costing.category.category == 'Internal'
                exec_uncommitted_amount = Decimal('0') if is_internal else tender_costing.uncommitted_amount
                exec_uncommitted_qty = None if is_internal else tender_costing.uncommitted_qty
                exec_uncommitted_rate = None if is_internal else tender_costing.uncommitted_rate
                
                execution_costing = Costing.objects.create(
                    project=tender_costing.project,
                    project_type=tender_costing.project_type,
                    category=tender_costing.category,
                    item=tender_costing.item,
                    order_in_list=tender_costing.order_in_list,
                    xero_account_code=tender_costing.xero_account_code,
                    xero_tracking_category=tender_costing.xero_tracking_category,
                    contract_budget=new_contract_budget,
                    unit=tender_costing.unit,
                    rate=tender_costing.rate,
                    operator=tender_costing.operator,
                    operator_value=tender_costing.operator_value,
                    uncommitted_amount=exec_uncommitted_amount,
                    uncommitted_qty=exec_uncommitted_qty,
                    uncommitted_rate=exec_uncommitted_rate,
                    uncommitted_notes=tender_costing.uncommitted_notes,
                    fixed_on_site=Decimal('0'),
                    sc_invoiced=Decimal('0'),
                    sc_paid=Decimal('0'),
                    tender_or_execution=2  # Execution mode
                )
                costing_pk_mapping[old_pk] = execution_costing.costing_pk
                
                if is_internal:
                    logger.info(f"  - Internal category: zeroed uncommitted fields for execution")
            
            # Step 3: Mark all tender quotes
            tender_quotes = Quotes.objects.filter(project=project, tender_or_execution=1)
            tender_quotes.update(tender_or_execution=1)
            
            # Step 4: Copy quotes and quote allocations for execution mode
            quote_pk_mapping = {}
            
            for tender_quote in tender_quotes:
                old_quote_pk = tender_quote.quotes_pk
                
                # Create execution copy of quote
                execution_quote = Quotes.objects.create(
                    supplier_quote_number=tender_quote.supplier_quote_number,
                    total_cost=tender_quote.total_cost,
                    pdf=tender_quote.pdf,
                    contact_pk=tender_quote.contact_pk,
                    project=tender_quote.project,
                    tender_or_execution=2  # Execution mode
                )
                quote_pk_mapping[old_quote_pk] = execution_quote.quotes_pk
                
                # Copy quote allocations
                tender_allocations = Quote_allocations.objects.filter(quotes_pk=tender_quote)
                for alloc in tender_allocations:
                    # Map to the new execution costing item
                    new_costing_pk = costing_pk_mapping.get(alloc.item.costing_pk)
                    if new_costing_pk:
                        new_costing = Costing.objects.get(pk=new_costing_pk)
                        Quote_allocations.objects.create(
                            quotes_pk=execution_quote,
                            item=new_costing,
                            qty=alloc.qty,
                            rate=alloc.rate,
                            amount=alloc.amount,
                            unit=alloc.unit,
                            notes=alloc.notes
                        )
            
            # Step 5: Set project to execution mode
            project.project_status = 2
            project.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contract budget fixed successfully. Project is now in Execution mode.'
        })
        
    except Exception as e:
        logger.error(f"Error fixing contract budget: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error fixing contract budget: {str(e)}'
        }, status=500)
