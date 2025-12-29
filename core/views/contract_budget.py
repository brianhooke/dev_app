"""
Contract Budget related views.

Template Rendering:
1. contract_budget_view - Render Contract Budget section template (supports project_pk, is_tender query params)

Data Updates:
2. update_uncommitted - Update uncommitted amount for a costing item
3. get_project_committed_amounts - Get committed amounts per item for a project
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
            is_construction = (project.project_type == 'construction')
        except Projects.DoesNotExist:
            pass
    
    # Column configurations for all 4 variants
    # Construction mode has subheadings: Uncommitted > Qty|Rate|Amount
    # parent_header, is_first_child, parent_colspan used for two-row header rendering
    
    has_subheadings = is_construction  # Only construction has subheadings
    
    if is_tender:
        if is_construction:
            # Tender + Construction: 8 columns with Uncommitted subheadings (Qty|Rate|Amount|Notes)
            main_table_columns = [
                {'header': 'Category / Item', 'width': '28%', 'field': 'item'},
                {'header': 'Unit', 'width': '6%', 'field': 'unit'},
                {'header': 'Working Budget', 'width': '12%', 'field': 'working_budget'},
                {'header': 'Qty', 'width': '8%', 'field': 'uncommitted_qty', 'parent_header': 'Uncommitted', 'is_first_child': True, 'parent_colspan': 4, 'input': True},
                {'header': 'Rate', 'width': '8%', 'field': 'uncommitted_rate', 'parent_header': 'Uncommitted', 'input': True},
                {'header': 'Amount', 'width': '12%', 'field': 'uncommitted_amount', 'parent_header': 'Uncommitted', 'calculated': True},
                {'header': 'Notes', 'width': '6%', 'field': 'uncommitted_notes', 'parent_header': 'Uncommitted', 'icon': True},
                {'header': 'Committed', 'width': '12%', 'field': 'committed'},
            ]
        else:
            # Tender + Non-construction: 5 columns
            main_table_columns = [
                {'header': 'Category / Item', 'width': '35%', 'field': 'item'},
                {'header': 'Unit', 'width': '10%', 'field': 'unit'},
                {'header': 'Working Budget', 'width': '18%', 'field': 'working_budget'},
                {'header': 'Uncommitted', 'width': '18%', 'field': 'uncommitted_amount', 'input': True},
                {'header': 'Committed', 'width': '19%', 'field': 'committed'},
            ]
    else:
        if is_construction:
            # Execution + Construction: 12 columns with Uncommitted subheadings (Qty|Rate|Amount|Notes)
            main_table_columns = [
                {'header': 'Category / Item', 'width': '16%', 'field': 'item'},
                {'header': 'Unit', 'width': '6%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '9%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '9%', 'field': 'working_budget'},
                {'header': 'Qty', 'width': '10%', 'field': 'uncommitted_qty', 'parent_header': 'Uncommitted', 'is_first_child': True, 'parent_colspan': 4, 'input': True},
                {'header': 'Rate', 'width': '10%', 'field': 'uncommitted_rate', 'parent_header': 'Uncommitted', 'input': True},
                {'header': 'Amount', 'width': '10%', 'field': 'uncommitted_amount', 'parent_header': 'Uncommitted', 'calculated': True},
                {'header': 'Notes', 'width': '3%', 'field': 'uncommitted_notes', 'parent_header': 'Uncommitted', 'icon': True},
                {'header': 'Committed', 'width': '9%', 'field': 'committed'},
                {'header': 'Cost to Complete', 'width': '8%', 'field': 'cost_to_complete'},
                {'header': 'Billed', 'width': '6%', 'field': 'billed'},
                {'header': 'Fixed on Site', 'width': '6%', 'field': 'fixed_on_site'},
            ]
        else:
            # Execution + Non-construction: 9 columns
            main_table_columns = [
                {'header': 'Category / Item', 'width': '20%', 'field': 'item'},
                {'header': 'Unit', 'width': '6%', 'field': 'unit'},
                {'header': 'Contract Budget', 'width': '12%', 'field': 'contract_budget'},
                {'header': 'Working Budget', 'width': '12%', 'field': 'working_budget'},
                {'header': 'Uncommitted', 'width': '12%', 'field': 'uncommitted_amount', 'input': True},
                {'header': 'Committed', 'width': '12%', 'field': 'committed'},
                {'header': 'Cost to Complete', 'width': '9%', 'field': 'cost_to_complete'},
                {'header': 'Billed', 'width': '9%', 'field': 'billed'},
                {'header': 'Fixed on Site', 'width': '8%', 'field': 'fixed_on_site'},
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
    Returns a dictionary of {costing_pk: total_committed_amount}
    """
    try:
        project = get_object_or_404(Projects, pk=project_pk)
        
        # Get all quotes for this project
        project_quotes = Quotes.objects.filter(project=project)
        
        # Get all quote allocations for these quotes and aggregate by item
        committed_amounts = Quote_allocations.objects.filter(
            quotes_pk__in=project_quotes
        ).values('item__costing_pk').annotate(
            total_committed=Sum('amount')
        )
        
        # Convert to dictionary {costing_pk: amount}
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
            committed_dict[item.costing_pk] = float(item.contract_budget or 0)
        
        return JsonResponse({
            'status': 'success',
            'committed_amounts': committed_dict
        })
        
    except Exception as e:
        logger.error(f"Error getting committed amounts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting committed amounts: {str(e)}'
        }, status=500)
