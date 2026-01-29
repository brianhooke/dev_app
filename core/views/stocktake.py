"""
Stocktake views - handles stocktake configuration and data management.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_stocktake_inclusion(request):
    """
    Toggle the stocktake inclusion for a ProjectType or Costing item.
    
    Expected POST data:
    - type: 'project_type' or 'costing'
    - pk: int (project_type_pk or costing_pk)
    - included: bool (true = include, false = exclude)
    """
    try:
        from core.models import ProjectTypes, Costing
        
        data = json.loads(request.body)
        item_type = data.get('type')
        pk = data.get('pk')
        included = data.get('included', False)
        
        if not item_type or not pk:
            return JsonResponse({
                'status': 'error',
                'message': 'type and pk are required'
            }, status=400)
        
        stocktake_value = 1 if included else 0
        
        if item_type == 'project_type':
            try:
                project_type = ProjectTypes.objects.get(project_type_pk=pk)
                project_type.stocktake = stocktake_value
                project_type.save(update_fields=['stocktake', 'updated_at'])
                logger.info(f"Updated ProjectType {pk} stocktake to {stocktake_value}")
                return JsonResponse({
                    'status': 'success',
                    'message': f'Project type stocktake updated to {included}'
                })
            except ProjectTypes.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'ProjectType with pk {pk} not found'
                }, status=404)
                
        elif item_type == 'costing':
            try:
                costing = Costing.objects.get(costing_pk=pk)
                costing.stocktake = stocktake_value
                costing.save(update_fields=['stocktake', 'updated_at'])
                logger.info(f"Updated Costing {pk} stocktake to {stocktake_value}")
                return JsonResponse({
                    'status': 'success',
                    'message': f'Costing stocktake updated to {included}'
                })
            except Costing.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Costing with pk {pk} not found'
                }, status=404)
        else:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid type: {item_type}. Must be "project_type" or "costing"'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error toggling stocktake inclusion: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_stocktake_allocations(request, bill_pk):
    """
    Get all allocations for a stocktake bill.
    """
    try:
        from core.models import StocktakeAllocations
        
        allocations = StocktakeAllocations.objects.filter(
            bill_id=bill_pk
        ).select_related('item', 'item__unit').order_by('allocation_pk')
        
        allocations_list = []
        for alloc in allocations:
            allocations_list.append({
                'allocation_pk': alloc.allocation_pk,
                'bill_pk': alloc.bill_id,
                'project_type': alloc.project_type,
                'item_pk': alloc.item_id,
                'item_name': alloc.item.item if alloc.item else None,
                'unit': alloc.unit or (alloc.item.unit.unit_name if alloc.item and alloc.item.unit else ''),
                'qty': float(alloc.qty) if alloc.qty else None,
                'rate': float(alloc.rate) if alloc.rate else None,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'gst_amount': float(alloc.gst_amount) if alloc.gst_amount else 0,
                'notes': alloc.notes or ''
            })
        
        return JsonResponse({
            'status': 'success',
            'allocations': allocations_list
        })
        
    except Exception as e:
        logger.error(f"Error getting stocktake allocations: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_stocktake_allocation(request):
    """
    Create a new stocktake allocation for a bill.
    
    Expected POST data:
    - bill_pk: int
    """
    try:
        from core.models import StocktakeAllocations, Bills
        
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'bill_pk is required'
            }, status=400)
        
        # Verify bill exists
        try:
            bill = Bills.objects.get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Bill with pk {bill_pk} not found'
            }, status=404)
        
        # Create allocation
        allocation = StocktakeAllocations.objects.create(
            bill=bill,
            amount=0,
            gst_amount=0
        )
        
        logger.info(f"Created stocktake allocation {allocation.allocation_pk} for bill {bill_pk}")
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.allocation_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating stocktake allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_stocktake_allocation(request, allocation_pk):
    """
    Update a stocktake allocation.
    
    Expected POST data:
    - project_type: str (optional)
    - item_pk: int (optional)
    - unit: str (optional)
    - qty: decimal (optional)
    - rate: decimal (optional)
    - amount: decimal (optional)
    - gst_amount: decimal (optional)
    - notes: str (optional)
    """
    try:
        from core.models import StocktakeAllocations, Costing
        
        data = json.loads(request.body)
        
        try:
            allocation = StocktakeAllocations.objects.get(allocation_pk=allocation_pk)
        except StocktakeAllocations.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Allocation with pk {allocation_pk} not found'
            }, status=404)
        
        # Update fields
        if 'project_type' in data:
            allocation.project_type = data['project_type']
        if 'item_pk' in data:
            item_pk = data['item_pk']
            if item_pk:
                try:
                    allocation.item = Costing.objects.get(costing_pk=item_pk)
                except Costing.DoesNotExist:
                    allocation.item = None
            else:
                allocation.item = None
        if 'unit' in data:
            allocation.unit = data['unit']
        if 'qty' in data:
            allocation.qty = data['qty'] if data['qty'] else None
        if 'rate' in data:
            allocation.rate = data['rate'] if data['rate'] else None
        if 'amount' in data:
            allocation.amount = data['amount'] or 0
        if 'gst_amount' in data:
            allocation.gst_amount = data['gst_amount'] or 0
        if 'notes' in data:
            allocation.notes = data['notes']
        
        allocation.save()
        
        logger.info(f"Updated stocktake allocation {allocation_pk}")
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.allocation_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating stocktake allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_stocktake_allocation(request, allocation_pk):
    """
    Delete a stocktake allocation.
    """
    try:
        from core.models import StocktakeAllocations
        
        try:
            allocation = StocktakeAllocations.objects.get(allocation_pk=allocation_pk)
            allocation.delete()
            logger.info(f"Deleted stocktake allocation {allocation_pk}")
            return JsonResponse({'status': 'success'})
        except StocktakeAllocations.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Allocation with pk {allocation_pk} not found'
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error deleting stocktake allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def approve_stocktake_bill(request, bill_pk):
    """
    Approve a stocktake bill - updates bill status to 1 (allocated).
    """
    try:
        from core.models import Bills
        
        try:
            bill = Bills.objects.get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Bill with pk {bill_pk} not found'
            }, status=404)
        
        # Update bill status to allocated (1)
        bill.bill_status = 1
        bill.save(update_fields=['bill_status', 'updated_at'])
        
        logger.info(f"Approved stocktake bill {bill_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Bill approved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error approving stocktake bill: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)
