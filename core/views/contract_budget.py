"""
Contract Budget related views.
"""

import json
import logging
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from ..models import Costing, Projects, Quotes, Quote_allocations

logger = logging.getLogger(__name__)


@csrf_exempt
def update_uncommitted(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        uncommitted = data.get('uncommitted')
        notes = data.get('notes')
        uncommitted_qty = data.get('uncommitted_qty')
        uncommitted_rate = data.get('uncommitted_rate')
        
        try:
            costing = Costing.objects.get(costing_pk=costing_pk)
            costing.uncommitted_amount = uncommitted
            costing.uncommitted_notes = notes
            
            # Update qty and rate if provided (for construction projects)
            if uncommitted_qty is not None:
                costing.uncommitted_qty = uncommitted_qty
            if uncommitted_rate is not None:
                costing.uncommitted_rate = uncommitted_rate
            
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
