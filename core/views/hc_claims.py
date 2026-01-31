"""
HC Claims-related views.

Template Rendering:
1. hc_claims_view - Render HC claims section template (supports project_pk query param)

Endpoints:
- get_hc_claims - Get list of all HC claims for a project
- get_hc_claim_data - Get detailed data for a specific claim including budget table
- create_hc_claim - Create a new HC claim with date and selected bills/stocktake snaps
- save_hc_claim - Save/update HC claim allocations
- get_available_bills - Get bills available for inclusion in a claim
- get_available_stocktake_snaps - Get stocktake snaps available for inclusion

Calculation Logic:
- QS Claim = Max(0, Min(Contract Budget - C2C, Fixed on Site) - Previous QS Claims)
  where C2C = Working Budget - Invoiced
  
- HC Claim = Min(Remaining Claimable, Max(0, Contract Budget - C2C - Previous HC Claims))
  where Remaining Claimable = Contract Budget - Previous HC Claims
  and C2C = Working Budget - (Paid Invoices + Invoices in This Claim)
"""

import json
import logging
from decimal import Decimal
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q

from ..models import (
    Projects, Categories, Costing, Quotes,
    HC_claims, HC_claim_allocations,
    Bills, Bill_allocations,
    StocktakeSnap, StocktakeSnapItem, StocktakeSnapAllocation,
    Quote_allocations, Hc_variation, Hc_variation_allocations
)

logger = logging.getLogger(__name__)


def hc_claims_view(request):
    """Render the HC claims section template.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/hc_claims/?project_pk=123
    """
    project_pk = request.GET.get('project_pk')
    is_construction = False
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            is_construction = (project.project_type and project.project_type.rates_based == 1)
        except Projects.DoesNotExist:
            pass
    
    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
    }
    return render(request, 'core/hc_claims.html', context)


@csrf_exempt
def get_hc_claims(request, project_pk):
    """Get all HC claims related to this project.
    
    Returns claims that have:
    - Allocations for items in this project, OR
    - Associated bills that belong to this project
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)
    
    try:
        # Get all costing items for this project
        costing_items = Costing.objects.filter(project_id=project_pk)
        costing_pks = list(costing_items.values_list('costing_pk', flat=True))
        
        # Get claims that have allocations for these items
        claims_with_allocations = HC_claim_allocations.objects.filter(
            item__in=costing_pks
        ).values_list('hc_claim_pk_id', flat=True).distinct()
        
        # Get claims that have associated bills for this project
        claims_with_bills = Bills.objects.filter(
            project_id=project_pk,
            associated_hc_claim__isnull=False
        ).values_list('associated_hc_claim_id', flat=True).distinct()
        
        # Combine both sets
        all_claim_pks = set(claims_with_allocations) | set(claims_with_bills)
        
        claims = HC_claims.objects.filter(hc_claim_pk__in=all_claim_pks).order_by('-date')
        
        claims_list = []
        for claim in claims:
            # Calculate total claimed amounts
            allocations = HC_claim_allocations.objects.filter(
                hc_claim_pk=claim,
                item__in=costing_pks
            )
            total_hc_claimed = sum(float(a.hc_claimed or 0) for a in allocations)
            total_qs_claimed = sum(float(a.qs_claimed or 0) for a in allocations)
            
            claims_list.append({
                'hc_claim_pk': claim.hc_claim_pk,
                'display_id': claim.display_id,
                'date': claim.date.isoformat() if claim.date else None,
                'status': claim.status,
                'status_display': get_status_display(claim.status),
                'invoicee': claim.invoicee,
                'total_hc_claimed': total_hc_claimed,
                'total_qs_claimed': total_qs_claimed,
            })
        
        return JsonResponse({'status': 'success', 'claims': claims_list})
    
    except Exception as e:
        logger.error(f"Error getting HC claims: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def get_status_display(status):
    """Convert status integer to display string."""
    status_map = {
        0: 'Draft',
        1: 'Approved',
        2: 'Sent to Xero',
        3: 'Payment Received'
    }
    return status_map.get(status, 'Unknown')


@csrf_exempt
def get_available_bills(request, project_pk):
    """Get bills available for inclusion in an HC claim.
    
    Returns bills that are:
    - Associated with this project (via bill allocations to project items)
    - Not already associated with an approved HC claim
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)
    
    try:
        # Get costing items for this project
        costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)
        
        # Get bills that have allocations to these items
        bill_pks = Bill_allocations.objects.filter(
            item__in=costing_pks
        ).values_list('bill_id', flat=True).distinct()
        
        # Filter to bills not already in an approved claim
        available_bills = Bills.objects.filter(
            bill_pk__in=bill_pks
        ).filter(
            Q(associated_hc_claim__isnull=True) | Q(associated_hc_claim__status=0)
        ).order_by('-bill_date')
        
        bills_list = []
        for bill in available_bills:
            # Get total amount from allocations
            total_amount = Bill_allocations.objects.filter(
                bill=bill,
                item__in=costing_pks
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            bills_list.append({
                'bill_pk': bill.bill_pk,
                'supplier': bill.contact_pk.name if bill.contact_pk else 'Unknown',
                'bill_date': bill.bill_date.isoformat() if bill.bill_date else None,
                'total_amount': float(total_amount),
                'bill_status': bill.bill_status,
                'already_in_claim': bill.associated_hc_claim_id is not None,
            })
        
        return JsonResponse({'status': 'success', 'bills': bills_list})
    
    except Exception as e:
        logger.error(f"Error getting available bills: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_available_stocktake_snaps(request, project_pk):
    """Get stocktake snaps available for inclusion in an HC claim.
    
    Returns finalised snaps that have allocations to this project.
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)
    
    try:
        # Get stocktake snaps that have allocations to this project
        snap_pks = StocktakeSnapAllocation.objects.filter(
            project_id=project_pk
        ).values_list('snap_item__snap_id', flat=True).distinct()
        
        snaps = StocktakeSnap.objects.filter(
            snap_pk__in=snap_pks,
            status=1  # Only finalised snaps
        ).order_by('-date')
        
        snaps_list = []
        for snap in snaps:
            # Get total allocated to this project from this snap
            total_allocated = StocktakeSnapAllocation.objects.filter(
                snap_item__snap=snap,
                project_id=project_pk
            ).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            snaps_list.append({
                'stocktake_snap_pk': snap.snap_pk,
                'snap_date': snap.date.isoformat() if snap.date else None,
                'total_allocated': float(total_allocated),
            })
        
        return JsonResponse({'status': 'success', 'snaps': snaps_list})
    
    except Exception as e:
        logger.error(f"Error getting available stocktake snaps: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def create_hc_claim(request):
    """Create a new HC claim with date and optionally associate bills."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        project_pk = data.get('project_pk')
        claim_date = data.get('date')
        selected_bill_pks = data.get('bill_pks', [])
        selected_snap_pks = data.get('snap_pks', [])
        
        if not project_pk or not claim_date:
            return JsonResponse({'error': 'project_pk and date required'}, status=400)
        
        # Check for existing draft claim
        if HC_claims.objects.filter(status=0).exists():
            return JsonResponse({
                'error': 'There is already a draft HC claim in progress. Complete or delete it first.'
            }, status=400)
        
        # Create the claim
        claim_date_obj = datetime.strptime(claim_date, '%Y-%m-%d').date()
        claim = HC_claims.objects.create(date=claim_date_obj, status=0)
        
        # Associate selected bills
        if selected_bill_pks:
            Bills.objects.filter(bill_pk__in=selected_bill_pks).update(associated_hc_claim=claim)
        
        logger.info(f"Created HC claim {claim.hc_claim_pk} with {len(selected_bill_pks)} bills")
        
        return JsonResponse({
            'status': 'success',
            'hc_claim_pk': claim.hc_claim_pk,
            'display_id': claim.display_id
        })
    
    except Exception as e:
        logger.error(f"Error creating HC claim: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_hc_claim_data(request, claim_pk):
    """Get detailed data for an HC claim including the budget table data.
    
    Returns:
    - Claim metadata (date, status, etc.)
    - Budget items with calculated fields:
      - Contract Budget, Working Budget, Uncommitted, Committed
      - Fixed on Site (editable)
      - Invoiced amounts
      - Previous HC/QS claims
      - This claim HC/QS amounts (calculated)
    """
    try:
        claim = HC_claims.objects.get(hc_claim_pk=claim_pk)
        
        # Get project_pk from request or from claim allocations
        project_pk = request.GET.get('project_pk')
        if not project_pk:
            # Try to get from existing allocations
            alloc = HC_claim_allocations.objects.filter(hc_claim_pk=claim).first()
            if alloc:
                project_pk = alloc.item.project_id
        
        if not project_pk:
            return JsonResponse({'error': 'project_pk required'}, status=400)
        
        # Check if construction mode (rates_based)
        project = Projects.objects.get(pk=project_pk)
        is_construction = (project.project_type and project.project_type.rates_based == 1)
        
        # Get all categories and items for this project (execution mode only, tender_or_execution=2)
        categories = Categories.objects.filter(project_id=project_pk).order_by('order_in_list')
        items = Costing.objects.filter(project_id=project_pk, tender_or_execution=2).order_by('category__order_in_list', 'order_in_list')
        
        # Get existing allocations for this claim
        existing_allocations = {
            a.item_id: a for a in HC_claim_allocations.objects.filter(hc_claim_pk=claim)
        }
        
        # Calculate previous claims (from approved claims only)
        previous_claims = get_previous_claim_totals(project_pk, claim_pk)
        
        # Get committed amounts (from quote allocations)
        committed_amounts = get_committed_amounts(project_pk)
        
        # Get invoiced amounts (from bill allocations)
        invoiced_amounts = get_invoiced_amounts(project_pk, claim)
        
        # Get HC variations up to claim date
        variation_amounts = get_variation_amounts(project_pk, claim.date)
        
        # Build budget data per item
        budget_data = []
        for item in items:
            item_pk = item.costing_pk
            
            # Get or calculate values
            existing = existing_allocations.get(item_pk)
            
            contract_budget = float(item.contract_budget or 0) + variation_amounts.get(item_pk, 0)
            committed_data = committed_amounts.get(item_pk, {})
            if isinstance(committed_data, dict):
                committed = committed_data.get('amount', 0) or 0
            else:
                committed = float(committed_data or 0)
            
            # Uncommitted calculation differs by project type (matching contract_budget.html)
            if is_construction:
                # Construction: uncommitted = qty * rate
                uncommitted = float(item.uncommitted_qty or 0) * float(item.uncommitted_rate or 0)
            else:
                # Non-construction: use uncommitted_amount directly
                uncommitted = float(item.uncommitted_amount or 0)
            
            # Working Budget = Uncommitted + Committed
            working_budget = uncommitted + committed
            
            # Fixed on site - use existing allocation or item default
            if existing:
                fixed_on_site = float(existing.fixed_on_site or 0)
            else:
                fixed_on_site = float(item.fixed_on_site or 0)
            
            # Invoiced and paid amounts
            invoiced_data = invoiced_amounts.get(item_pk, {'invoiced': 0, 'paid': 0, 'in_claim': 0})
            invoiced = invoiced_data['invoiced']
            paid_invoices = invoiced_data['paid']
            invoices_in_claim = invoiced_data['in_claim']
            
            # Previous claims
            prev = previous_claims.get(item_pk, {'hc': 0, 'qs': 0})
            prev_hc_claimed = prev['hc']
            prev_qs_claimed = prev['qs']
            
            # Calculate This Claim amounts using formulas
            # QS Claim = Max(0, Min(Contract Budget - C2C_qs, Fixed on Site) - Previous QS Claims)
            # where C2C_qs = Working Budget - Invoiced
            c2c_qs = working_budget - invoiced
            qs_claim = max(0, min(contract_budget - c2c_qs, fixed_on_site) - prev_qs_claimed)
            
            # HC Claim = Min(Remaining Claimable, Max(0, Contract Budget - C2C_hc - Previous HC Claims))
            # where Remaining Claimable = Contract Budget - Previous HC Claims
            # and C2C_hc = Working Budget - (Paid Invoices + Invoices in This Claim)
            remaining_claimable = contract_budget - prev_hc_claimed
            c2c_hc = working_budget - paid_invoices - invoices_in_claim
            hc_claim = min(remaining_claimable, max(0, contract_budget - c2c_hc - prev_hc_claimed))
            
            # Get committed qty/rate from committed_data (already fetched above)
            if isinstance(committed_data, dict):
                committed_qty = committed_data.get('qty', 0) or 0
                committed_rate = committed_data.get('rate', 0) or 0
            else:
                committed_qty = 0
                committed_rate = 0
            
            # Invoiced This = bills/stocktakes associated with this claim
            invoiced_this = invoices_in_claim
            
            # Invoiced Prev = sum of previous HC_claim_allocations.sc_invoiced for this item
            invoiced_prev = HC_claim_allocations.objects.filter(
                item_id=item_pk,
                hc_claim_pk__hc_claim_pk__lt=claim.hc_claim_pk
            ).aggregate(total=Sum('sc_invoiced'))['total'] or 0
            
            budget_data.append({
                'costing_pk': item_pk,
                'category': item.category.category if item.category else '',
                'category_pk': item.category_id,
                'item': item.item,
                'unit': item.unit.unit_name if item.unit else '',
                'contract_budget': contract_budget,
                'working_budget': working_budget,
                'uncommitted': uncommitted,
                'uncommitted_qty': float(item.uncommitted_qty or 0),
                'uncommitted_rate': float(item.uncommitted_rate or 0),
                'uncommitted_notes': item.uncommitted_notes or '',
                'committed': committed,
                'committed_qty': committed_qty,
                'committed_rate': committed_rate,
                'fixed_on_site': fixed_on_site,
                'invoiced_prev': float(invoiced_prev),
                'invoiced_this': float(invoiced_this),
                'paid_invoices': paid_invoices,
                'invoices_in_claim': invoices_in_claim,
                'prev_hc_claimed': prev_hc_claimed,
                'prev_qs_claimed': prev_qs_claimed,
                'this_hc_claim': round(hc_claim, 2),
                'this_qs_claim': round(qs_claim, 2),
                'c2c_hc': c2c_hc,
                'c2c_qs': c2c_qs,
            })
        
        # Get associated bills
        associated_bills = Bills.objects.filter(associated_hc_claim=claim).values(
            'bill_pk', 'contact_pk__name', 'bill_date', 'total_net'
        )
        
        return JsonResponse({
            'status': 'success',
            'claim': {
                'hc_claim_pk': claim.hc_claim_pk,
                'display_id': claim.display_id,
                'date': claim.date.isoformat() if claim.date else None,
                'status': claim.status,
                'status_display': get_status_display(claim.status),
                'invoicee': claim.invoicee,
            },
            'budget_data': budget_data,
            'associated_bills': list(associated_bills),
        })
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting HC claim data: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def get_previous_claim_totals(project_pk, exclude_claim_pk=None):
    """Get total previous HC and QS claims per item from approved claims."""
    costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)
    
    query = HC_claim_allocations.objects.filter(
        item__in=costing_pks,
        hc_claim_pk__status__gte=1  # Approved or higher
    )
    
    if exclude_claim_pk:
        query = query.exclude(hc_claim_pk_id=exclude_claim_pk)
    
    totals = {}
    for alloc in query:
        item_pk = alloc.item_id
        if item_pk not in totals:
            totals[item_pk] = {'hc': 0, 'qs': 0}
        totals[item_pk]['hc'] += float(alloc.hc_claimed or 0)
        totals[item_pk]['qs'] += float(alloc.qs_claimed or 0)
    
    return totals


def get_committed_amounts(project_pk):
    """Get committed amounts per item from quote allocations.
    
    Returns dict with qty, rate, amount for construction projects (like contract_budget.py).
    """
    from collections import defaultdict
    
    project = Projects.objects.get(pk=project_pk)
    is_construction = (project.project_type and project.project_type.rates_based == 1)
    
    # Get quotes for execution mode (tender_or_execution=2)
    project_quotes = Quotes.objects.filter(project=project, tender_or_execution=2)
    
    if is_construction:
        # For construction types, return qty, rate, amount per item
        allocations = Quote_allocations.objects.filter(
            quotes_pk__in=project_quotes
        ).values('item__costing_pk', 'qty', 'rate', 'amount')
        
        # Group allocations by costing_pk
        allocations_by_item = defaultdict(list)
        for alloc in allocations:
            allocations_by_item[alloc['item__costing_pk']].append(alloc)
        
        # Convert to dictionary with qty, rate, amount
        committed_dict = {}
        for costing_pk, allocs in allocations_by_item.items():
            total_qty = sum(float(a['qty'] or 0) for a in allocs)
            total_amount = sum(float(a['amount'] or 0) for a in allocs)
            
            # Get unique non-null rates
            unique_rates = set(float(a['rate']) for a in allocs if a['rate'] is not None)
            
            if len(unique_rates) > 1:
                # Multiple different rates
                committed_dict[costing_pk] = {
                    'qty': total_qty,
                    'rate': None,
                    'amount': total_amount,
                    'has_multiple_rates': True
                }
            else:
                rate = list(unique_rates)[0] if unique_rates else 0
                committed_dict[costing_pk] = {
                    'qty': total_qty,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'has_multiple_rates': False
                }
        
        # Add stocktake snap allocations
        snap_allocations = StocktakeSnapAllocation.objects.filter(
            project=project,
            snap_item__snap__status__gte=1
        ).select_related('snap_item__snap', 'snap_item__item')
        
        project_costings = Costing.objects.filter(project=project, tender_or_execution=2)
        item_name_to_costing = {c.item: c.costing_pk for c in project_costings}
        
        for snap_alloc in snap_allocations:
            snap_item = snap_alloc.snap_item.item
            if not snap_item:
                continue
            costing_pk = item_name_to_costing.get(snap_item.item)
            if not costing_pk:
                continue
            
            alloc_qty = float(snap_alloc.qty or 0)
            alloc_rate = float(snap_alloc.rate or 0)
            alloc_amount = float(snap_alloc.amount or 0)
            
            if costing_pk in committed_dict:
                existing = committed_dict[costing_pk]
                existing['qty'] = (existing.get('qty') or 0) + alloc_qty
                existing['amount'] = (existing.get('amount') or 0) + alloc_amount
                if existing.get('rate') and existing['rate'] != alloc_rate:
                    existing['has_multiple_rates'] = True
            else:
                committed_dict[costing_pk] = {
                    'qty': alloc_qty,
                    'rate': alloc_rate,
                    'amount': alloc_amount,
                    'has_multiple_rates': False
                }
        
        return committed_dict
    else:
        # Non-construction - simple amounts
        result = Quote_allocations.objects.filter(
            quotes_pk__in=project_quotes
        ).values('item__costing_pk').annotate(
            total=Sum('amount')
        )
        return {r['item__costing_pk']: float(r['total'] or 0) for r in result}


def get_invoiced_amounts(project_pk, claim):
    """Get invoiced amounts per item from bill allocations.
    
    Returns dict with:
    - invoiced: total invoiced amount
    - paid: paid invoices amount
    - in_claim: invoices associated with this claim
    """
    costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)
    
    allocations = Bill_allocations.objects.filter(
        item__in=costing_pks
    ).select_related('bill')
    
    result = {}
    for alloc in allocations:
        item_pk = alloc.item_id
        amount = float(alloc.amount or 0)
        
        if item_pk not in result:
            result[item_pk] = {'invoiced': 0, 'paid': 0, 'in_claim': 0}
        
        result[item_pk]['invoiced'] += amount
        
        # Check if bill is paid (bill_status = 2 or 3)
        if alloc.bill.bill_status in [2, 3]:
            result[item_pk]['paid'] += amount
        
        # Check if bill is associated with this claim
        if alloc.bill.associated_hc_claim_id == claim.hc_claim_pk:
            result[item_pk]['in_claim'] += amount
    
    return result


def get_variation_amounts(project_pk, up_to_date):
    """Get HC variation amounts per item up to a date."""
    costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)
    
    allocations = Hc_variation_allocations.objects.filter(
        costing__in=costing_pks,
        hc_variation__date__lte=up_to_date
    )
    
    result = {}
    for alloc in allocations:
        item_pk = alloc.costing_id
        if item_pk not in result:
            result[item_pk] = 0
        result[item_pk] += float(alloc.amount or 0)
    
    return result


@csrf_exempt
def save_hc_claim(request):
    """Save/update HC claim allocations."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        claim_pk = data.get('hc_claim_pk')
        allocations_data = data.get('allocations', [])
        finalize = data.get('finalize', False)
        
        if not claim_pk:
            return JsonResponse({'error': 'hc_claim_pk required'}, status=400)
        
        claim = HC_claims.objects.get(hc_claim_pk=claim_pk)
        
        # Can only edit draft claims
        if claim.status != 0:
            return JsonResponse({'error': 'Can only edit draft claims'}, status=400)
        
        # Save allocations
        for alloc_data in allocations_data:
            item_pk = alloc_data.get('costing_pk')
            if not item_pk:
                continue
            
            item = Costing.objects.get(costing_pk=item_pk)
            category = item.category
            
            HC_claim_allocations.objects.update_or_create(
                hc_claim_pk=claim,
                item=item,
                defaults={
                    'category': category,
                    'contract_budget': alloc_data.get('contract_budget', 0),
                    'working_budget': alloc_data.get('working_budget', 0),
                    'uncommitted': alloc_data.get('uncommitted', 0),
                    'committed': alloc_data.get('committed', 0),
                    'fixed_on_site': alloc_data.get('fixed_on_site', 0),
                    'fixed_on_site_previous': alloc_data.get('fixed_on_site_previous', 0),
                    'fixed_on_site_this': alloc_data.get('fixed_on_site_this', 0),
                    'sc_invoiced': alloc_data.get('invoiced', 0),
                    'sc_invoiced_previous': alloc_data.get('sc_invoiced_previous', 0),
                    'adjustment': alloc_data.get('adjustment', 0),
                    'hc_claimed': alloc_data.get('this_hc_claim', 0),
                    'hc_claimed_previous': alloc_data.get('prev_hc_claimed', 0),
                    'qs_claimed': alloc_data.get('this_qs_claim', 0),
                    'qs_claimed_previous': alloc_data.get('prev_qs_claimed', 0),
                }
            )
        
        # Finalize if requested
        if finalize:
            claim.status = 1  # Approved
            claim.save()
            logger.info(f"Finalized HC claim {claim_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Claim saved successfully',
            'hc_claim_pk': claim.hc_claim_pk
        })
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error saving HC claim: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_hc_claim(request):
    """Delete an HC claim (only draft claims can be deleted)."""
    if request.method not in ['POST', 'DELETE']:
        return JsonResponse({'error': 'POST or DELETE required'}, status=405)
    
    try:
        data = json.loads(request.body)
        claim_pk = data.get('hc_claim_pk')
        
        if not claim_pk:
            return JsonResponse({'error': 'hc_claim_pk required'}, status=400)
        
        claim = HC_claims.objects.get(hc_claim_pk=claim_pk)
        
        # Can only delete draft claims
        if claim.status != 0:
            return JsonResponse({'error': 'Can only delete draft claims'}, status=400)
        
        # Unassociate bills
        Bills.objects.filter(associated_hc_claim=claim).update(associated_hc_claim=None)
        
        # Delete claim (cascades to allocations)
        claim.delete()
        
        logger.info(f"Deleted HC claim {claim_pk}")
        return JsonResponse({'status': 'success', 'message': 'Claim deleted'})
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC claim: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt 
def update_claim_bills(request, claim_pk):
    """Update which bills are associated with an HC claim."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_pks = data.get('bill_pks', [])
        
        claim = HC_claims.objects.get(hc_claim_pk=claim_pk)
        
        if claim.status != 0:
            return JsonResponse({'error': 'Can only modify draft claims'}, status=400)
        
        # Remove all current associations
        Bills.objects.filter(associated_hc_claim=claim).update(associated_hc_claim=None)
        
        # Add new associations
        Bills.objects.filter(bill_pk__in=bill_pks).update(associated_hc_claim=claim)
        
        return JsonResponse({'status': 'success'})
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error updating claim bills: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def finalize_hc_claim(request):
    """Finalize an HC claim - creates HC_claim_allocations entries and sets status to approved."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        claim_pk = data.get('hc_claim_pk')
        allocations_data = data.get('allocations', [])
        
        if not claim_pk:
            return JsonResponse({'error': 'hc_claim_pk required'}, status=400)
        
        claim = HC_claims.objects.get(hc_claim_pk=claim_pk)
        
        # Can only finalize draft claims
        if claim.status != 0:
            return JsonResponse({'error': 'Can only finalize draft claims'}, status=400)
        
        # Create/update allocations for all items
        for alloc_data in allocations_data:
            item_pk = alloc_data.get('costing_pk')
            category_pk = alloc_data.get('category_pk')
            if not item_pk:
                continue
            
            item = Costing.objects.get(costing_pk=item_pk)
            category = Categories.objects.get(pk=category_pk) if category_pk else item.category
            
            HC_claim_allocations.objects.update_or_create(
                hc_claim_pk=claim,
                item=item,
                defaults={
                    'category': category,
                    'contract_budget': alloc_data.get('contract_budget', 0),
                    'working_budget': alloc_data.get('working_budget', 0),
                    'uncommitted': alloc_data.get('uncommitted', 0),
                    'committed': alloc_data.get('committed', 0),
                    'fixed_on_site': alloc_data.get('fixed_on_site', 0),
                    'fixed_on_site_previous': alloc_data.get('fixed_on_site_previous', 0),
                    'fixed_on_site_this': alloc_data.get('fixed_on_site_this', 0),
                    'sc_invoiced_previous': alloc_data.get('sc_invoiced_previous', 0),
                    'sc_invoiced': alloc_data.get('sc_invoiced', 0),
                    'adjustment': 0,  # Not used for now
                    'hc_claimed_previous': alloc_data.get('hc_claimed_previous', 0),
                    'hc_claimed': alloc_data.get('hc_claimed', 0),
                    'qs_claimed_previous': alloc_data.get('qs_claimed_previous', 0),
                    'qs_claimed': alloc_data.get('qs_claimed', 0),
                }
            )
        
        # Set claim status to approved (1)
        claim.status = 1
        claim.save()
        
        logger.info(f"Finalized HC claim {claim_pk} with {len(allocations_data)} allocations")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Claim finalized successfully',
            'hc_claim_pk': claim.hc_claim_pk
        })
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error finalizing HC claim: {e}")
        return JsonResponse({'error': str(e)}, status=500)
