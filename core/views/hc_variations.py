"""
HC Variations-related views.

Template Rendering:
1. hc_variations_view - Render HC variations section template (supports project_pk query param)
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from ..models import Costing, Hc_variation, Hc_variation_allocations, Projects

logger = logging.getLogger(__name__)


def hc_variations_view(request):
    """Render the HC variations section template.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/hc_variations/?project_pk=123
    
    Returns construction-specific columns when project_type == 'construction'.
    """
    project_pk = request.GET.get('project_pk')
    is_construction = False
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            is_construction = (project.project_type in ['construction', 'pods', 'precast'])
        except Projects.DoesNotExist:
            pass
    
    # Main table columns - HC Variations list
    main_table_columns = [
        {'header': 'Date', 'width': '30%', 'sortable': True},
        {'header': '$ Amount', 'width': '25%', 'sortable': True},
        {'header': 'Update', 'width': '15%', 'class': 'col-action-first'},
        {'header': 'Delete', 'width': '10%', 'class': 'col-action'},
    ]
    
    # Allocations columns differ by project type
    if is_construction:
        allocations_columns = [
            {'header': 'Item', 'width': '25%'},
            {'header': 'Unit', 'width': '8%'},
            {'header': 'Qty', 'width': '10%'},
            {'header': 'Rate', 'width': '12%'},
            {'header': '$ Amount', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '25%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    else:
        allocations_columns = [
            {'header': 'Item', 'width': '40%'},
            {'header': '$ Amount', 'width': '25%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '30%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    
    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
        'main_table_columns': main_table_columns,
        'allocations_columns': allocations_columns,
    }
    return render(request, 'core/hc_variations.html', context)


@csrf_exempt
def get_hc_variations(request, project_pk):
    """Get all HC variations for a project."""
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)
    
    try:
        # Get all costing items for this project
        costing_items = Costing.objects.filter(project_id=project_pk)
        costing_pks = list(costing_items.values_list('costing_pk', flat=True))
        
        # Get all variation allocations for these costing items
        allocations = Hc_variation_allocations.objects.filter(
            costing__in=costing_pks
        ).select_related('hc_variation', 'costing')
        
        # Group by variation - use amount from Hc_variation model
        variations_dict = {}
        for alloc in allocations:
            var_pk = alloc.hc_variation.hc_variation_pk
            if var_pk not in variations_dict:
                variations_dict[var_pk] = {
                    'hc_variation_pk': var_pk,
                    'date': alloc.hc_variation.date.isoformat() if alloc.hc_variation.date else None,
                    'total_amount': float(alloc.hc_variation.amount) if alloc.hc_variation.amount else 0,
                    'allocations': []
                }
            
            alloc_data = {
                'hc_variation_allocation_pk': alloc.hc_variation_allocation_pk,
                'costing_pk': alloc.costing.costing_pk,
                'item': alloc.costing.item,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': alloc.unit,
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes or '',
            }
            variations_dict[var_pk]['allocations'].append(alloc_data)
        
        variations_list = list(variations_dict.values())
        return JsonResponse({'status': 'success', 'variations': variations_list})
    
    except Exception as e:
        logger.error(f"Error getting HC variations: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_hc_variation_allocations(request, variation_pk):
    """Get allocations for a specific HC variation."""
    try:
        allocations = Hc_variation_allocations.objects.filter(
            hc_variation_id=variation_pk
        ).select_related('costing', 'costing__unit')
        
        allocations_list = []
        for alloc in allocations:
            allocations_list.append({
                'hc_variation_allocation_pk': alloc.hc_variation_allocation_pk,
                'costing_pk': alloc.costing.costing_pk,
                'item': alloc.costing.item,
                'item_pk': alloc.costing.costing_pk,
                'item_name': alloc.costing.item,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': alloc.unit or (alloc.costing.unit.unit_name if alloc.costing.unit else None),
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes or '',
            })
        
        return JsonResponse({'status': 'success', 'allocations': allocations_list})
    
    except Exception as e:
        logger.error(f"Error getting HC variation allocations: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def save_hc_variation(request):
    """Save a new HC variation with allocations, or update allocations for existing variation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        variation_pk = data.get('pk')  # If provided, this is an update
        allocations_data = data.get('allocations', [])
        
        if variation_pk:
            # UPDATE existing variation's allocations
            try:
                variation = Hc_variation.objects.get(hc_variation_pk=variation_pk)
            except Hc_variation.DoesNotExist:
                return JsonResponse({'error': 'Variation not found'}, status=404)
            
            # Delete existing allocations and recreate
            Hc_variation_allocations.objects.filter(hc_variation=variation).delete()
            
            # Create new allocations
            for alloc_data in allocations_data:
                costing_pk = alloc_data.get('item_pk')
                if not costing_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(costing_pk=costing_pk)
                    
                    # Handle construction mode (qty/rate) vs simple mode (amount)
                    qty = alloc_data.get('qty')
                    rate = alloc_data.get('rate')
                    if qty is not None and rate is not None:
                        amount = float(qty) * float(rate)
                    else:
                        amount = alloc_data.get('amount', 0)
                    
                    Hc_variation_allocations.objects.create(
                        hc_variation=variation,
                        costing=costing,
                        amount=amount,
                        qty=qty,
                        unit=alloc_data.get('unit', ''),
                        rate=rate,
                        notes=alloc_data.get('notes', '')
                    )
                except Costing.DoesNotExist:
                    logger.warning(f"Costing {costing_pk} not found for variation allocation")
            
            logger.info(f"Updated HC variation {variation_pk} with {len(allocations_data)} allocations")
            return JsonResponse({
                'status': 'success',
                'hc_variation_pk': variation.hc_variation_pk
            })
        
        else:
            # CREATE new variation
            project_pk = data.get('project_pk')
            date = data.get('date')
            total_amount = data.get('total_amount', 0)
            
            if not project_pk or not date:
                return JsonResponse({'error': 'project_pk and date required'}, status=400)
            
            # Create the variation with amount
            from datetime import datetime
            variation_date = datetime.strptime(date, '%Y-%m-%d').date()
            variation = Hc_variation.objects.create(date=variation_date, amount=total_amount)
            
            # Create allocations
            for alloc_data in allocations_data:
                costing_pk = alloc_data.get('item_pk')
                if not costing_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(costing_pk=costing_pk)
                    
                    # Handle construction mode (qty/rate) vs simple mode (amount)
                    qty = alloc_data.get('qty')
                    rate = alloc_data.get('rate')
                    if qty is not None and rate is not None:
                        amount = float(qty) * float(rate)
                    else:
                        amount = alloc_data.get('amount', 0)
                    
                    Hc_variation_allocations.objects.create(
                        hc_variation=variation,
                        costing=costing,
                        amount=amount,
                        qty=qty,
                        unit=alloc_data.get('unit', ''),
                        rate=rate,
                        notes=alloc_data.get('notes', '')
                    )
                except Costing.DoesNotExist:
                    logger.warning(f"Costing {costing_pk} not found for variation allocation")
            
            logger.info(f"Created HC variation {variation.hc_variation_pk} with {len(allocations_data)} allocations")
            return JsonResponse({
                'status': 'success',
                'hc_variation_pk': variation.hc_variation_pk
            })
    
    except Exception as e:
        logger.error(f"Error saving HC variation: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_hc_variation(request):
    """Delete an HC variation and its allocations."""
    if request.method != 'DELETE' and request.method != 'POST':
        return JsonResponse({'error': 'DELETE or POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Support pk or hc_variation_pk for consistency with quotes pattern
        variation_pk = data.get('pk') or data.get('hc_variation_pk')
        
        if not variation_pk:
            return JsonResponse({'status': 'error', 'message': 'Variation PK is required'}, status=400)
        
        variation = Hc_variation.objects.get(hc_variation_pk=variation_pk)
        variation.delete()  # Cascades to allocations
        
        logger.info(f"Deleted HC variation {variation_pk}")
        return JsonResponse({'status': 'success', 'message': f'Variation deleted successfully'})
    
    except Hc_variation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Variation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC variation: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_hc_variation_allocation(request, allocation_pk):
    """Update an HC variation allocation."""
    if request.method != 'POST' and request.method != 'PUT':
        return JsonResponse({'error': 'POST or PUT required'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation = Hc_variation_allocations.objects.get(hc_variation_allocation_pk=allocation_pk)
        
        if 'amount' in data:
            allocation.amount = data['amount']
        if 'qty' in data:
            allocation.qty = data['qty']
        if 'rate' in data:
            allocation.rate = data['rate']
        if 'notes' in data:
            allocation.notes = data['notes']
        if 'item_pk' in data:
            allocation.costing_id = data['item_pk']
        
        allocation.save()
        return JsonResponse({'status': 'success'})
    
    except Hc_variation_allocations.DoesNotExist:
        return JsonResponse({'error': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error updating HC variation allocation: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_hc_variation_allocation(request, allocation_pk):
    """Delete an HC variation allocation."""
    if request.method != 'DELETE' and request.method != 'POST':
        return JsonResponse({'error': 'DELETE or POST required'}, status=405)
    
    try:
        allocation = Hc_variation_allocations.objects.get(hc_variation_allocation_pk=allocation_pk)
        allocation.delete()
        return JsonResponse({'status': 'success'})
    
    except Hc_variation_allocations.DoesNotExist:
        return JsonResponse({'error': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC variation allocation: {e}")
        return JsonResponse({'error': str(e)}, status=500)
