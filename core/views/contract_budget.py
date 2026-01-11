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

from ..models import Costing, Projects, Quotes, Quote_allocations

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
                {'header': 'Category / Item', 'width': '12%', 'field': 'item'},
                {'header': 'Unit', 'width': '4%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '10%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '10%', 'field': 'working_budget'},
                {'header': 'Qty', 'width': '5%', 'field': 'uncommitted_qty', 'parent_header': 'Uncommitted', 'is_first_child': True, 'parent_colspan': 4, 'input': True},
                {'header': 'Rate', 'width': '5%', 'field': 'uncommitted_rate', 'parent_header': 'Uncommitted', 'input': True},
                {'header': 'Amount', 'width': '7%', 'field': 'uncommitted_amount', 'parent_header': 'Uncommitted', 'calculated': True},
                {'header': 'Notes', 'width': '2%', 'field': 'uncommitted_notes', 'parent_header': 'Uncommitted', 'icon': True},
                {'header': 'Qty', 'width': '5%', 'field': 'committed_qty', 'parent_header': 'Committed', 'is_first_child': True, 'parent_colspan': 3},
                {'header': 'Rate', 'width': '5%', 'field': 'committed_rate', 'parent_header': 'Committed'},
                {'header': 'Amount', 'width': '7%', 'field': 'committed_amount', 'parent_header': 'Committed'},
                {'header': 'C2C', 'width': '6%', 'field': 'cost_to_complete'},
                {'header': 'Billed', 'width': '6%', 'field': 'billed'},
                {'header': 'Fixed on Site', 'width': '6%', 'field': 'fixed_on_site'},
            ]
        else:
            # Execution + Non-construction: 10 columns (added Notes)
            main_table_columns = [
                {'header': 'Category / Item', 'width': '18%', 'field': 'item'},
                {'header': 'Unit', 'width': '5%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '10%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '10%', 'field': 'working_budget'},
                {'header': 'Uncommitted', 'width': '10%', 'field': 'uncommitted_amount', 'input': True},
                {'header': 'Notes', 'width': '5%', 'field': 'uncommitted_notes', 'icon': True},
                {'header': 'Committed', 'width': '10%', 'field': 'committed'},
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
    """
    try:
        project = get_object_or_404(Projects, pk=project_pk)
        # Use rates_based flag from ProjectTypes instead of hardcoded project type names
        is_construction = (project.project_type and project.project_type.rates_based == 1)
        
        # Get all quotes for this project
        project_quotes = Quotes.objects.filter(project=project)
        
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
            category__category='Internal'
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
