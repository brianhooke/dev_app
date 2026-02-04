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


@csrf_exempt
@require_http_methods(["POST"])
def toggle_xero_instance_stocktake(request):
    """
    Toggle the stocktake inclusion for a Xero instance.
    
    Expected POST data:
    - xero_instance_pk: int
    - included: bool (true = include, false = exclude)
    """
    try:
        from core.models import XeroInstances
        
        data = json.loads(request.body)
        xero_instance_pk = data.get('xero_instance_pk')
        included = data.get('included', False)
        
        if not xero_instance_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_pk is required'
            }, status=400)
        
        stocktake_value = 1 if included else 0
        
        try:
            xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_pk)
            xero_instance.stocktake = stocktake_value
            xero_instance.save(update_fields=['stocktake', 'updated_at'])
            logger.info(f"Updated XeroInstance {xero_instance_pk} stocktake to {stocktake_value}")
            return JsonResponse({
                'status': 'success',
                'message': f'Xero instance stocktake updated to {included}'
            })
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'XeroInstance with pk {xero_instance_pk} not found'
            }, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error toggling Xero instance stocktake: {str(e)}", exc_info=True)
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


# =============================================================================
# STOCKTAKE SNAP APIs
# =============================================================================

from decimal import Decimal
from django.db.models import Sum, F
from datetime import date


def calculate_stock_ledger_for_item(item_pk, as_of_date=None):
    """
    Calculate current stock qty and weighted average rate for an item.
    
    Stock comes from:
    1. Opening balance (StocktakeOpeningBalance)
    2. Bill allocations to stocktake (StocktakeAllocations where bill.is_stocktake=True and bill.bill_status >= 1)
    3. Minus: Snap allocations consumed (StocktakeSnapAllocation where snap.status >= 1)
    
    Returns dict with qty, total_value, avg_rate
    """
    from core.models import (
        StocktakeOpeningBalance, StocktakeAllocations, 
        StocktakeSnapAllocation, StocktakeSnap
    )
    
    if as_of_date is None:
        as_of_date = date.today()
    
    total_qty = Decimal('0')
    total_value = Decimal('0')
    
    # 1. Opening balance
    opening = StocktakeOpeningBalance.objects.filter(
        item_id=item_pk,
        date__lte=as_of_date
    ).order_by('-date').first()
    
    if opening:
        total_qty += opening.qty
        total_value += opening.qty * opening.rate
    
    # 2. Stock IN from approved stocktake bills
    stock_in = StocktakeAllocations.objects.filter(
        item_id=item_pk,
        bill__is_stocktake=True,
        bill__bill_status__gte=1,  # Approved or later
        bill__created_at__date__lte=as_of_date
    ).aggregate(
        total_qty=Sum('qty'),
        total_value=Sum(F('qty') * F('rate'))
    )
    
    if stock_in['total_qty']:
        total_qty += stock_in['total_qty']
    if stock_in['total_value']:
        total_value += stock_in['total_value']
    
    # 3. Stock OUT from finalised snaps
    stock_out = StocktakeSnapAllocation.objects.filter(
        snap_item__item_id=item_pk,
        snap_item__snap__status__gte=StocktakeSnap.STATUS_FINALISED,
        snap_item__snap__date__lte=as_of_date
    ).aggregate(
        total_qty=Sum('qty'),
        total_value=Sum('amount')
    )
    
    if stock_out['total_qty']:
        total_qty -= stock_out['total_qty']
    if stock_out['total_value']:
        total_value -= stock_out['total_value']
    
    # Calculate weighted average rate
    avg_rate = (total_value / total_qty) if total_qty > 0 else Decimal('0')
    
    return {
        'qty': float(total_qty),
        'total_value': float(total_value),
        'avg_rate': float(avg_rate)
    }


def get_stock_entries_for_item(item_pk, as_of_date=None, exclude_snap_pk=None):
    """
    Get all stock entries for an item in chronological order for FIFO/LIFO calculation.
    Returns list of {date, qty, rate, remaining_qty} entries.
    exclude_snap_pk: Optionally exclude a specific snap's allocations from consumed calculation.
    """
    from core.models import StocktakeOpeningBalance, StocktakeAllocations, StocktakeSnapAllocation, StocktakeSnap
    
    if as_of_date is None:
        as_of_date = date.today()
    
    entries = []
    
    # Opening balance
    opening = StocktakeOpeningBalance.objects.filter(
        item_id=item_pk,
        date__lte=as_of_date
    ).order_by('-date').first()
    
    if opening:
        entries.append({
            'date': opening.date,
            'qty': float(opening.qty),
            'rate': float(opening.rate),
            'remaining_qty': float(opening.qty),
            'source': 'opening'
        })
    
    # Bill allocations (stock in) - use bill_date for filtering and sorting
    allocations = StocktakeAllocations.objects.filter(
        item_id=item_pk,
        bill__is_stocktake=True,
        bill__bill_status__gte=1,
        bill__bill_date__lte=as_of_date,
        qty__isnull=False,
        rate__isnull=False
    ).select_related('bill').order_by('bill__bill_date')
    
    for alloc in allocations:
        entries.append({
            'date': alloc.bill.bill_date,
            'qty': float(alloc.qty),
            'rate': float(alloc.rate),
            'remaining_qty': float(alloc.qty),
            'source': 'bill',
            'bill_pk': alloc.bill_id
        })
    
    # Sort by date
    entries.sort(key=lambda x: x['date'])
    
    # Deduct consumed quantities from finalised snaps (excluding the current snap if specified)
    consumed_qs = StocktakeSnapAllocation.objects.filter(
        snap_item__item_id=item_pk,
        snap_item__snap__status__gte=StocktakeSnap.STATUS_FINALISED,
        snap_item__snap__date__lte=as_of_date
    )
    if exclude_snap_pk:
        consumed_qs = consumed_qs.exclude(snap_item__snap__snap_pk=exclude_snap_pk)
    consumed = consumed_qs.aggregate(total=Sum('qty'))
    
    consumed_qty = float(consumed['total'] or 0)
    
    # Apply FIFO consumption to calculate remaining
    for entry in entries:
        if consumed_qty <= 0:
            break
        deduct = min(entry['remaining_qty'], consumed_qty)
        entry['remaining_qty'] -= deduct
        consumed_qty -= deduct
    
    # Filter out fully consumed entries
    entries = [e for e in entries if e['remaining_qty'] > 0]
    
    return entries


def calculate_rate_for_qty(item_pk, qty_needed, method='FIFO', as_of_date=None, exclude_snap_pk=None):
    """
    Calculate the rate for consuming a given qty using FIFO, LIFO, or AVG method.
    Returns {rate, total_amount, breakdown}
    exclude_snap_pk: Exclude this snap's allocations from consumed calculation (prevents circular deduction).
    """
    if method == 'AVG':
        ledger = calculate_stock_ledger_for_item(item_pk, as_of_date)
        return {
            'rate': ledger['avg_rate'],
            'total_amount': ledger['avg_rate'] * qty_needed,
            'breakdown': [{'qty': qty_needed, 'rate': ledger['avg_rate']}]
        }
    
    entries = get_stock_entries_for_item(item_pk, as_of_date, exclude_snap_pk)
    
    if method == 'LIFO':
        entries = list(reversed(entries))
    
    remaining_needed = qty_needed
    total_amount = 0
    breakdown = []
    
    for entry in entries:
        if remaining_needed <= 0:
            break
        take_qty = min(entry['remaining_qty'], remaining_needed)
        total_amount += take_qty * entry['rate']
        breakdown.append({
            'qty': take_qty,
            'rate': entry['rate'],
            'date': str(entry['date'])
        })
        remaining_needed -= take_qty
    
    avg_rate = (total_amount / qty_needed) if qty_needed > 0 else 0
    
    return {
        'rate': avg_rate,
        'total_amount': total_amount,
        'breakdown': breakdown
    }


@require_http_methods(["GET"])
def get_stock_ledger(request):
    """
    Get current stock ledger - qty and avg rate for all stocktake items.
    Uses today's date as the reference date for stock calculations.
    """
    try:
        from core.models import Costing, StocktakeAllocations
        
        today = date.today()
        
        # Get all items marked for stocktake
        items = Costing.objects.filter(
            stocktake=1
        ).select_related('unit').order_by('item')
        
        # Count future bills (bill_date > today) per item
        future_bills_by_item = {}
        future_bills = StocktakeAllocations.objects.filter(
            bill__is_stocktake=True,
            bill__bill_status__gte=1,
            bill__bill_date__gt=today
        ).values('item_id').annotate(
            future_qty=Sum('qty')
        )
        for fb in future_bills:
            future_bills_by_item[fb['item_id']] = float(fb['future_qty'] or 0)
        
        ledger = []
        for item in items:
            stock = calculate_stock_ledger_for_item(item.costing_pk, today)
            future_qty = future_bills_by_item.get(item.costing_pk, 0)
            ledger.append({
                'item_pk': item.costing_pk,
                'item_name': item.item,
                'unit': item.unit.unit_name if item.unit else '',
                'project_type': item.project_type,
                'qty': stock['qty'],
                'avg_rate': stock['avg_rate'],
                'total_value': stock['total_value'],
                'future_qty': future_qty
            })
        
        return JsonResponse({
            'status': 'success',
            'ledger': ledger,
            'as_of_date': today.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        logger.error(f"Error getting stock ledger: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_snap_list(request):
    """
    Get list of all stocktake snaps.
    """
    try:
        from core.models import StocktakeSnap
        
        snaps = StocktakeSnap.objects.all().order_by('-date', '-created_at')
        
        snap_list = []
        for snap in snaps:
            item_count = snap.snap_items.count()
            snap_list.append({
                'snap_pk': snap.snap_pk,
                'date': snap.date.strftime('%Y-%m-%d'),
                'date_display': snap.date.strftime('%d %b %Y'),
                'costing_method': snap.costing_method,
                'status': snap.status,
                'status_display': snap.get_status_display(),
                'item_count': item_count,
                'notes': snap.notes or ''
            })
        
        return JsonResponse({
            'status': 'success',
            'snaps': snap_list
        })
        
    except Exception as e:
        logger.error(f"Error getting snap list: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_snap(request):
    """
    Create a new stocktake snap with all stocktake items.
    """
    try:
        from core.models import StocktakeSnap, StocktakeSnapItem, Costing
        
        data = json.loads(request.body)
        snap_date = data.get('date', date.today().strftime('%Y-%m-%d'))
        costing_method = data.get('costing_method', 'FIFO')
        
        # Create snap
        snap = StocktakeSnap.objects.create(
            date=snap_date,
            costing_method=costing_method,
            status=StocktakeSnap.STATUS_DRAFT
        )
        
        # Get all stocktake items and create snap items with book qty
        items = Costing.objects.filter(stocktake=1)
        
        for item in items:
            stock = calculate_stock_ledger_for_item(item.costing_pk, snap.date)
            StocktakeSnapItem.objects.create(
                snap=snap,
                item=item,
                book_qty=Decimal(str(stock['qty']))
            )
        
        logger.info(f"Created snap {snap.snap_pk} with {items.count()} items")
        
        return JsonResponse({
            'status': 'success',
            'snap_pk': snap.snap_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_snap(request, snap_pk):
    """
    Get a snap with all its items and allocations.
    """
    try:
        from core.models import StocktakeSnap, Costing, Projects, StocktakeAllocations
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        # Get all active execution projects
        active_projects = Projects.objects.filter(
            archived=0,
            project_status=2
        ).order_by('project')
        
        # Build a map of item_name -> list of project PKs that have that item
        item_to_projects = {}
        project_costings = Costing.objects.filter(
            project__in=active_projects
        ).values('item', 'project_id')
        
        for c in project_costings:
            item_name = c['item']
            if item_name not in item_to_projects:
                item_to_projects[item_name] = set()
            item_to_projects[item_name].add(c['project_id'])
        
        # Build project lookup
        project_lookup = {p.projects_pk: p.project for p in active_projects}
        
        # Count future bills (bill_date > snap.date) per item
        future_bills_by_item = {}
        future_bills = StocktakeAllocations.objects.filter(
            bill__is_stocktake=True,
            bill__bill_status__gte=1,
            bill__bill_date__gt=snap.date
        ).values('item_id').annotate(
            future_qty=Sum('qty')
        )
        for fb in future_bills:
            future_bills_by_item[fb['item_id']] = float(fb['future_qty'] or 0)
        
        items = []
        for snap_item in snap.snap_items.select_related('item', 'item__unit').all():
            allocations = []
            for alloc in snap_item.allocations.select_related('project').all():
                allocations.append({
                    'allocation_pk': alloc.snap_allocation_pk,
                    'project_pk': alloc.project_id,
                    'project_name': alloc.project.project if alloc.project else '',
                    'qty': float(alloc.qty),
                    'rate': float(alloc.rate),
                    'amount': float(alloc.amount)
                })
            
            # Get project type name (CharField, not FK)
            project_type_name = ''
            if snap_item.item and snap_item.item.project_type:
                project_type_name = snap_item.item.project_type
            
            # Get projects that have this item
            item_name = snap_item.item.item if snap_item.item else ''
            valid_project_pks = item_to_projects.get(item_name, set())
            valid_projects = [
                {'project_pk': pk, 'project_name': project_lookup[pk]}
                for pk in valid_project_pks
                if pk in project_lookup
            ]
            valid_projects.sort(key=lambda x: x['project_name'])
            
            future_qty = future_bills_by_item.get(snap_item.item_id, 0)
            items.append({
                'snap_item_pk': snap_item.snap_item_pk,
                'item_pk': snap_item.item_id,
                'item_name': item_name,
                'unit': snap_item.item.unit.unit_name if snap_item.item and snap_item.item.unit else '',
                'project_type': project_type_name,
                'book_qty': float(snap_item.book_qty),
                'counted_qty': float(snap_item.counted_qty) if snap_item.counted_qty is not None else None,
                'variance_qty': float(snap_item.variance_qty) if snap_item.variance_qty is not None else None,
                'allocations': allocations,
                'valid_projects': valid_projects,
                'future_qty': future_qty
            })
        
        # Check if this is the most recent snap
        most_recent_snap = StocktakeSnap.objects.order_by('-date', '-snap_pk').first()
        is_most_recent = most_recent_snap and most_recent_snap.snap_pk == snap.snap_pk
        
        return JsonResponse({
            'status': 'success',
            'snap': {
                'snap_pk': snap.snap_pk,
                'date': snap.date.strftime('%Y-%m-%d'),
                'costing_method': snap.costing_method,
                'status': snap.status,
                'status_display': snap.get_status_display(),
                'notes': snap.notes or '',
                'items': items,
                'is_most_recent': is_most_recent
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_snap(request, snap_pk):
    """
    Update snap fields (date, costing_method, notes).
    """
    try:
        from core.models import StocktakeSnap
        
        data = json.loads(request.body)
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        if snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot update a finalised snap'
            }, status=400)
        
        if 'date' in data:
            snap.date = data['date']
        if 'costing_method' in data:
            snap.costing_method = data['costing_method']
        if 'notes' in data:
            snap.notes = data['notes']
        
        snap.save()
        
        return JsonResponse({
            'status': 'success',
            'snap_pk': snap.snap_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_snap(request, snap_pk):
    """
    Delete a draft snap.
    """
    try:
        from core.models import StocktakeSnap
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        if snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot delete a finalised snap'
            }, status=400)
        
        snap.delete()
        logger.info(f"Deleted snap {snap_pk}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error deleting snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_snap_item(request, snap_item_pk):
    """
    Update a snap item's counted qty.
    """
    try:
        from core.models import StocktakeSnapItem, StocktakeSnap
        
        data = json.loads(request.body)
        
        try:
            snap_item = StocktakeSnapItem.objects.select_related('snap').get(snap_item_pk=snap_item_pk)
        except StocktakeSnapItem.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap item {snap_item_pk} not found'
            }, status=404)
        
        if snap_item.snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot update items in a finalised snap'
            }, status=400)
        
        if 'counted_qty' in data:
            counted = data['counted_qty']
            snap_item.counted_qty = Decimal(str(counted)) if counted is not None else None
            snap_item.save()  # save() auto-calculates variance
        
        return JsonResponse({
            'status': 'success',
            'snap_item_pk': snap_item.snap_item_pk,
            'variance_qty': float(snap_item.variance_qty) if snap_item.variance_qty is not None else None
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating snap item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_snap_allocation(request):
    """
    Create a project allocation for a snap item's variance.
    """
    try:
        from core.models import StocktakeSnapItem, StocktakeSnapAllocation, StocktakeSnap, Projects
        
        data = json.loads(request.body)
        snap_item_pk = data.get('snap_item_pk')
        project_pk = data.get('project_pk')
        qty = data.get('qty', 0)
        
        if not snap_item_pk or not project_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'snap_item_pk and project_pk are required'
            }, status=400)
        
        try:
            snap_item = StocktakeSnapItem.objects.select_related('snap').get(snap_item_pk=snap_item_pk)
        except StocktakeSnapItem.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap item {snap_item_pk} not found'
            }, status=404)
        
        if snap_item.snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot add allocations to a finalised snap'
            }, status=400)
        
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Project {project_pk} not found'
            }, status=404)
        
        # Calculate rate based on snap's costing method (exclude current snap to avoid circular deduction)
        rate_info = calculate_rate_for_qty(
            snap_item.item_id,
            float(qty),
            snap_item.snap.costing_method,
            snap_item.snap.date,
            exclude_snap_pk=snap_item.snap.snap_pk
        )
        
        allocation = StocktakeSnapAllocation.objects.create(
            snap_item=snap_item,
            project=project,
            qty=Decimal(str(qty)),
            rate=Decimal(str(rate_info['rate'])),
            amount=Decimal(str(rate_info['total_amount']))
        )
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.snap_allocation_pk,
            'rate': float(allocation.rate),
            'amount': float(allocation.amount)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating snap allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_snap_allocation(request, allocation_pk):
    """
    Update a snap allocation (qty or project).
    """
    try:
        from core.models import StocktakeSnapAllocation, StocktakeSnap, Projects
        
        data = json.loads(request.body)
        
        try:
            allocation = StocktakeSnapAllocation.objects.select_related(
                'snap_item', 'snap_item__snap'
            ).get(snap_allocation_pk=allocation_pk)
        except StocktakeSnapAllocation.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Allocation {allocation_pk} not found'
            }, status=404)
        
        if allocation.snap_item.snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot update allocations in a finalised snap'
            }, status=400)
        
        if 'project_pk' in data:
            try:
                allocation.project = Projects.objects.get(projects_pk=data['project_pk'])
            except Projects.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Project {data["project_pk"]} not found'
                }, status=404)
        
        if 'qty' in data:
            qty = float(data['qty'])
            allocation.qty = Decimal(str(qty))
            
            # Recalculate rate (exclude current snap to avoid circular deduction)
            rate_info = calculate_rate_for_qty(
                allocation.snap_item.item_id,
                qty,
                allocation.snap_item.snap.costing_method,
                allocation.snap_item.snap.date,
                exclude_snap_pk=allocation.snap_item.snap.snap_pk
            )
            allocation.rate = Decimal(str(rate_info['rate']))
            allocation.amount = Decimal(str(rate_info['total_amount']))
        
        allocation.save()
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.snap_allocation_pk,
            'rate': float(allocation.rate),
            'amount': float(allocation.amount)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating snap allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_snap_allocation(request, allocation_pk):
    """
    Delete a snap allocation.
    """
    try:
        from core.models import StocktakeSnapAllocation, StocktakeSnap
        
        try:
            allocation = StocktakeSnapAllocation.objects.select_related(
                'snap_item__snap'
            ).get(snap_allocation_pk=allocation_pk)
        except StocktakeSnapAllocation.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Allocation {allocation_pk} not found'
            }, status=404)
        
        if allocation.snap_item.snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot delete allocations from a finalised snap'
            }, status=400)
        
        allocation.delete()
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error deleting snap allocation: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def finalise_snap(request, snap_pk):
    """
    Finalise a snap - locks it from further editing.
    Validates that all variance is allocated before finalising.
    """
    try:
        from core.models import StocktakeSnap
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        if snap.status >= StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Snap is already finalised'
            }, status=400)
        
        # Validate all negative variances are fully allocated
        for snap_item in snap.snap_items.all():
            if snap_item.variance_qty is not None and snap_item.variance_qty < 0:
                allocated_qty = sum(
                    float(a.qty) for a in snap_item.allocations.all()
                )
                variance_abs = abs(float(snap_item.variance_qty))
                if abs(allocated_qty - variance_abs) > 0.001:  # Allow small rounding
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Item {snap_item.item.item}: variance not fully allocated ({allocated_qty} of {variance_abs})'
                    }, status=400)
        
        snap.status = StocktakeSnap.STATUS_FINALISED
        snap.save()
        
        logger.info(f"Finalised snap {snap_pk}")
        
        return JsonResponse({
            'status': 'success',
            'snap_pk': snap.snap_pk
        })
        
    except Exception as e:
        logger.error(f"Error finalising snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def unfinalise_snap(request, snap_pk):
    """
    Unfinalise a snap - allows editing again.
    Only works on the most recent snap that is finalised (not sent to Xero).
    """
    try:
        from core.models import StocktakeSnap
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        # Check if this is the most recent snap
        most_recent = StocktakeSnap.objects.order_by('-date', '-snap_pk').first()
        if not most_recent or most_recent.snap_pk != snap.snap_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Only the most recent snap can be edited'
            }, status=400)
        
        if snap.status == StocktakeSnap.STATUS_SENT_TO_XERO:
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot edit a snap that has been sent to Xero'
            }, status=400)
        
        if snap.status == StocktakeSnap.STATUS_DRAFT:
            return JsonResponse({
                'status': 'error',
                'message': 'Snap is already in draft mode'
            }, status=400)
        
        snap.status = StocktakeSnap.STATUS_DRAFT
        snap.save()
        
        logger.info(f"Unfinalised snap {snap_pk}")
        
        return JsonResponse({
            'status': 'success',
            'snap_pk': snap.snap_pk
        })
        
    except Exception as e:
        logger.error(f"Error unfinalising snap: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def send_snap_to_xero(request, snap_pk):
    """
    Send a finalised snap to Xero as a manual journal.
    
    Journal structure:
    - DEBIT: Project expense accounts (materials consumed)
    - CREDIT: Stock/inventory account (stock reduction)
    
    Requires the snap to be finalised first.
    """
    import requests
    from .xero import get_xero_auth
    
    try:
        from core.models import StocktakeSnap, XeroInstances, XeroAccounts
        
        data = json.loads(request.body) if request.body else {}
        xero_instance_pk = data.get('xero_instance_pk')
        stock_account_code = data.get('stock_account_code')  # Credit account for stock
        
        try:
            snap = StocktakeSnap.objects.get(snap_pk=snap_pk)
        except StocktakeSnap.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Snap {snap_pk} not found'
            }, status=404)
        
        if snap.status < StocktakeSnap.STATUS_FINALISED:
            return JsonResponse({
                'status': 'error',
                'message': 'Snap must be finalised before sending to Xero'
            }, status=400)
        
        if snap.status >= StocktakeSnap.STATUS_SENT_TO_XERO:
            return JsonResponse({
                'status': 'error',
                'message': 'Snap has already been sent to Xero'
            }, status=400)
        
        if not xero_instance_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'xero_instance_pk is required'
            }, status=400)
        
        if not stock_account_code:
            return JsonResponse({
                'status': 'error',
                'message': 'stock_account_code is required (credit account for stock reduction)'
            }, status=400)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Build journal lines
        journal_lines = []
        total_amount = Decimal('0')
        
        # Get all allocations with project expense accounts
        for snap_item in snap.snap_items.select_related('item').prefetch_related('allocations__project'):
            for alloc in snap_item.allocations.all():
                # Get the expense account for this project (from project's xero tracking or default)
                # For now, we'll need the expense account code from the item or a default
                expense_account_code = None
                
                # Try to get account from the item's xero_account
                if snap_item.item and hasattr(snap_item.item, 'xero_account_code') and snap_item.item.xero_account_code:
                    expense_account_code = snap_item.item.xero_account_code
                
                if not expense_account_code:
                    # Use a default expense account - this should be configured
                    expense_account_code = '300'  # Default cost of goods sold account
                
                amount = float(alloc.amount)
                total_amount += Decimal(str(amount))
                
                # DEBIT line (positive) - expense to project
                journal_lines.append({
                    "AccountCode": expense_account_code,
                    "Description": f"Stocktake: {snap_item.item.item if snap_item.item else 'Unknown'} - {alloc.project.project if alloc.project else 'Unknown project'}",
                    "LineAmount": amount,
                    "TaxType": "NONE"
                })
        
        if not journal_lines:
            return JsonResponse({
                'status': 'error',
                'message': 'No allocations to send to Xero'
            }, status=400)
        
        # CREDIT line (negative) - reduce stock
        journal_lines.append({
            "AccountCode": stock_account_code,
            "Description": f"Stocktake snap {snap.date.strftime('%d %b %Y')} - Stock consumed",
            "LineAmount": -float(total_amount),  # Negative for credit
            "TaxType": "NONE"
        })
        
        # Build journal payload
        journal_payload = {
            "Narration": f"Stocktake Snap - {snap.date.strftime('%d %b %Y')}",
            "Date": snap.date.strftime('%Y-%m-%d'),
            "JournalLines": journal_lines,
            "Status": "POSTED"
        }
        
        logger.info(f"Sending journal to Xero: {json.dumps(journal_payload, indent=2)}")
        
        # Send to Xero API
        response = requests.post(
            'https://api.xero.com/api.xro/2.0/ManualJournals',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json={"ManualJournals": [journal_payload]},
            timeout=30
        )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Xero API error: {response.status_code} - {error_text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Xero API error: {response.status_code}',
                'details': error_text
            }, status=response.status_code)
        
        # Success - parse response
        xero_response = response.json()
        logger.info(f"Xero response: {json.dumps(xero_response, indent=2)}")
        
        # Extract journal ID
        journal_id = None
        if 'ManualJournals' in xero_response and len(xero_response['ManualJournals']) > 0:
            journal_id = xero_response['ManualJournals'][0].get('ManualJournalID')
        
        # Update snap status
        snap.status = StocktakeSnap.STATUS_SENT_TO_XERO
        snap.xero_journal_id = journal_id
        snap.save()
        
        logger.info(f"Snap {snap_pk} sent to Xero with journal ID: {journal_id}")
        
        return JsonResponse({
            'status': 'success',
            'snap_pk': snap.snap_pk,
            'xero_journal_id': journal_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error sending snap to Xero: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


# =============================================================================
# OPENING BALANCE APIs
# =============================================================================

@require_http_methods(["GET"])
def get_opening_balances(request):
    """
    Get all opening balances for stocktake items.
    Also returns whether each item has been used in a stocktake snap (locked).
    """
    try:
        from core.models import StocktakeOpeningBalance, StocktakeSnapItem
        
        # Get items that have been used in a stocktake snap
        items_in_snaps = set(
            StocktakeSnapItem.objects.values_list('item_id', flat=True).distinct()
        )
        
        balances = StocktakeOpeningBalance.objects.select_related(
            'item', 'item__unit'
        ).order_by('item__item', '-date')
        
        balance_list = []
        for bal in balances:
            is_locked = bal.item_id in items_in_snaps
            balance_list.append({
                'opening_balance_pk': bal.opening_balance_pk,
                'item_pk': bal.item_id,
                'item_name': bal.item.item if bal.item else '',
                'unit': bal.item.unit.unit_name if bal.item and bal.item.unit else '',
                'date': bal.date.strftime('%Y-%m-%d'),
                'date_display': bal.date.strftime('%d %b %Y'),
                'qty': float(bal.qty),
                'rate': float(bal.rate),
                'total_value': float(bal.qty * bal.rate),
                'notes': bal.notes or '',
                'is_locked': is_locked
            })
        
        return JsonResponse({
            'status': 'success',
            'balances': balance_list
        })
        
    except Exception as e:
        logger.error(f"Error getting opening balances: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_opening_balance(request):
    """
    Create or update an opening balance for an item.
    If an opening balance exists for this item+date, update it.
    Otherwise create a new one.
    """
    try:
        from core.models import StocktakeOpeningBalance, Costing
        
        data = json.loads(request.body)
        item_pk = data.get('item_pk')
        balance_date = data.get('date')
        qty = data.get('qty')
        rate = data.get('rate')
        notes = data.get('notes', '')
        
        if not item_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'item_pk is required'
            }, status=400)
        
        if qty is None or rate is None:
            return JsonResponse({
                'status': 'error',
                'message': 'qty and rate are required'
            }, status=400)
        
        try:
            item = Costing.objects.get(costing_pk=item_pk)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Item {item_pk} not found'
            }, status=404)
        
        if not balance_date:
            balance_date = date.today()
        elif isinstance(balance_date, str):
            # Parse date string (YYYY-MM-DD format)
            from datetime import datetime
            balance_date = datetime.strptime(balance_date, '%Y-%m-%d').date()
        
        # Create or update
        balance, created = StocktakeOpeningBalance.objects.update_or_create(
            item=item,
            date=balance_date,
            defaults={
                'qty': Decimal(str(qty)),
                'rate': Decimal(str(rate)),
                'notes': notes
            }
        )
        
        action = 'Created' if created else 'Updated'
        logger.info(f"{action} opening balance for item {item_pk}: qty={qty}, rate={rate}")
        
        return JsonResponse({
            'status': 'success',
            'opening_balance_pk': balance.opening_balance_pk,
            'created': created
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error saving opening balance: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_opening_balance(request, balance_pk):
    """
    Update an existing opening balance.
    Cannot update if item has been used in a stocktake snap.
    """
    try:
        from core.models import StocktakeOpeningBalance, StocktakeSnapItem
        
        data = json.loads(request.body)
        qty = data.get('qty')
        rate = data.get('rate')
        
        if qty is None or rate is None:
            return JsonResponse({
                'status': 'error',
                'message': 'qty and rate are required'
            }, status=400)
        
        try:
            balance = StocktakeOpeningBalance.objects.get(opening_balance_pk=balance_pk)
        except StocktakeOpeningBalance.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Opening balance {balance_pk} not found'
            }, status=404)
        
        # Check if item has been used in a snap
        if StocktakeSnapItem.objects.filter(item_id=balance.item_id).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot update: item has been used in a stocktake snap'
            }, status=400)
        
        balance.qty = Decimal(str(qty))
        balance.rate = Decimal(str(rate))
        balance.save()
        
        logger.info(f"Updated opening balance {balance_pk}: qty={qty}, rate={rate}")
        
        return JsonResponse({
            'status': 'success',
            'opening_balance_pk': balance.opening_balance_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating opening balance: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_opening_balance(request, balance_pk):
    """
    Delete an opening balance.
    """
    try:
        from core.models import StocktakeOpeningBalance
        
        try:
            balance = StocktakeOpeningBalance.objects.get(opening_balance_pk=balance_pk)
            balance.delete()
            logger.info(f"Deleted opening balance {balance_pk}")
            return JsonResponse({'status': 'success'})
        except StocktakeOpeningBalance.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Opening balance {balance_pk} not found'
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error deleting opening balance: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_projects_for_allocation(request):
    """
    Get list of active projects for snap allocation dropdown.
    """
    try:
        from core.models import Projects
        
        projects = Projects.objects.filter(
            archived=0,
            project_status=2  # Only execution projects
        ).order_by('project')
        
        project_list = [{
            'project_pk': p.projects_pk,
            'project_name': p.project
        } for p in projects]
        
        return JsonResponse({
            'status': 'success',
            'projects': project_list
        })
        
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_item_history(request, item_pk):
    """
    Get chronological history of an item's stock movements.
    Includes opening balances and stocktake bill allocations.
    """
    try:
        from core.models import Costing, StocktakeOpeningBalance, StocktakeAllocations, Bills
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'Item {item_pk} not found'
            }, status=404)
        
        history = []
        
        # Get opening balances
        opening_balances = StocktakeOpeningBalance.objects.filter(
            item=item
        ).order_by('date')
        
        for ob in opening_balances:
            history.append({
                'type': 'opening_balance',
                'date': ob.date.isoformat(),
                'date_display': ob.date.strftime('%d %b %Y'),
                'qty': float(ob.qty) if ob.qty else 0,
                'rate': float(ob.rate) if ob.rate else 0,
                'amount': float(ob.qty * ob.rate) if ob.qty and ob.rate else 0,
                'description': 'Opening Balance',
                'notes': ob.notes or '',
                'sort_key': ob.date.isoformat() + '_0'  # Opening balances first on same day
            })
        
        # Get stocktake bill allocations (Bills.is_stocktake=True)
        stocktake_allocations = StocktakeAllocations.objects.filter(
            item=item,
            bill__is_stocktake=True
        ).select_related('bill', 'bill__contact_pk').order_by('bill__bill_date')
        
        for alloc in stocktake_allocations:
            bill = alloc.bill
            supplier_name = bill.contact_pk.name if bill.contact_pk else 'Unknown Supplier'
            
            history.append({
                'type': 'stock_in',
                'date': bill.bill_date.isoformat() if bill.bill_date else None,
                'date_display': bill.bill_date.strftime('%d %b %Y') if bill.bill_date else 'No date',
                'qty': float(alloc.qty) if alloc.qty else 0,
                'rate': float(alloc.rate) if alloc.rate else 0,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'description': f'Stock In - {supplier_name}',
                'supplier': supplier_name,
                'bill_pk': bill.bill_pk,
                'bill_number': bill.supplier_bill_number or f'Bill #{bill.bill_pk}',
                'notes': alloc.notes or '',
                'sort_key': (bill.bill_date.isoformat() if bill.bill_date else '9999-99-99') + '_1'
            })
        
        # Sort by date (and sort_key for same-day ordering)
        history.sort(key=lambda x: x['sort_key'])
        
        # Calculate running totals
        running_qty = 0
        running_value = 0
        for entry in history:
            if entry['type'] == 'opening_balance':
                running_qty = entry['qty']
                running_value = entry['amount']
            else:
                running_qty += entry['qty']
                running_value += entry['amount']
            entry['running_qty'] = running_qty
            entry['running_value'] = running_value
            entry['running_avg_rate'] = running_value / running_qty if running_qty > 0 else 0
        
        # Get project type name
        project_type_name = ''
        if item.project_type:
            try:
                project_type_name = item.project_type.project_type
            except:
                project_type_name = str(item.project_type) if item.project_type else ''
        
        # Get unit name
        unit_name = ''
        if item.unit:
            try:
                unit_name = item.unit.unit if hasattr(item.unit, 'unit') else str(item.unit)
            except:
                unit_name = str(item.unit) if item.unit else ''
        
        return JsonResponse({
            'status': 'success',
            'item': {
                'item_pk': item.costing_pk,
                'item_name': item.item,
                'unit': unit_name,
                'project_type': project_type_name
            },
            'history': history,
            'summary': {
                'total_qty': running_qty,
                'total_value': running_value,
                'avg_rate': running_value / running_qty if running_qty > 0 else 0
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting item history: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)
