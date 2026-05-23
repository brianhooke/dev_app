"""
HC Claims-related views.

Template Rendering:
1. hc_claims_view - Render HC claims section template (supports project_pk query param)

Endpoints:
- get_hc_claims - Get list of all HC claims for a project
- get_hc_claim_data - Get detailed data for a specific claim including budget table
- create_hc_claim - Create a new HC claim with date and selected bills/stocktake snaps
- finalize_hc_claim - Snapshot allocations and approve a draft claim
- delete_hc_claim - Delete a draft claim and detach its bills/snaps
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
from django.db import transaction
from django.db.models import Sum, Q

from ..models import (
    Projects, Categories, Costing, Quotes,
    HC_claims, HC_claim_allocations,
    Bills, Bill_allocations,
    StocktakeSnap, StocktakeSnapItem, StocktakeSnapAllocation,
    Quote_allocations, Hc_variation, Hc_variation_allocations
)
from ..services.costing_rollups import (
    hc_committed_amounts,
    hc_invoiced_amounts,
)

# Backwards-compatible aliases for the legacy module-private names. The
# canonical home is ``core/services/costing_rollups.py`` (audit
# A.M-R-02 / P-5). The old names are preserved so any debug shell or
# orphan import path keeps working; in-module callers below use the
# new aliases.
get_committed_amounts = hc_committed_amounts
get_invoiced_amounts = hc_invoiced_amounts

logger = logging.getLogger(__name__)


def hc_claims_view(request):
    """Render the HC claims section template.

    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/hc_claims/?project_pk=123

    Note: the construction-screen 'HC Claims' nav button is hidden for
    non-revenue projects, so users can't reach this view through the
    UI in that case. The server-side guard against creating a claim
    for a non-revenue project lives in create_hc_claim (B16).
    """
    project_pk = request.GET.get('project_pk')
    is_construction = False
    # Default to True so projects without an assigned type still get
    # the historical (HC + QS) layout. The settings.html "QS" toggle
    # on the project type is the only way to flip this off.
    has_qs = True

    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            ptype = project.project_type
            if ptype:
                is_construction = (ptype.rates_based == 1)
                has_qs = bool(ptype.qs)
        except Projects.DoesNotExist:
            pass

    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
        'has_qs': has_qs,
    }
    return render(request, 'core/hc_claims.html', context)


@csrf_exempt
def get_hc_claims(request, project_pk):
    """Get all HC claims for this project.

    Uses the direct HC_claims.project FK (added in migration 0074). The
    legacy "discover claims via allocations or bills" logic is preserved
    only as a safety net for any orphan claim that the backfill could
    not link — those are surfaced too if they happen to share an
    allocation/bill with this project.
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)

    try:
        # Primary path: claim.project FK
        primary = set(
            HC_claims.objects
            .filter(project_id=project_pk)
            .values_list('hc_claim_pk', flat=True)
        )

        # Safety net for orphan claims (project IS NULL on the claim row
        # but the claim still relates to this project via allocations or
        # attached bills). Should be empty in practice once 0074 has run.
        costing_pks = list(
            Costing.objects.filter(project_id=project_pk)
            .values_list('costing_pk', flat=True)
        )
        orphan_via_alloc = set()
        if costing_pks:
            orphan_via_alloc = set(
                HC_claim_allocations.objects
                .filter(item__in=costing_pks, hc_claim_pk__project__isnull=True)
                .values_list('hc_claim_pk_id', flat=True)
            )
        orphan_via_bill = set(
            Bills.objects
            .filter(project_id=project_pk,
                    associated_hc_claim__isnull=False,
                    associated_hc_claim__project__isnull=True)
            .values_list('associated_hc_claim_id', flat=True)
        )

        all_claim_pks = primary | orphan_via_alloc | orphan_via_bill
        claims = HC_claims.objects.filter(hc_claim_pk__in=all_claim_pks).order_by('-date')

        claims_list = []
        for claim in claims:
            allocations = HC_claim_allocations.objects.filter(
                hc_claim_pk=claim,
                item__in=costing_pks,
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
        return JsonResponse({'error': 'Internal server error'}, status=500)


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
    """Get bills available for inclusion in an HC claim for THIS project.

    A bill is available if:
      - it belongs to this project (Bills.project_id matches), AND
      - it is either unattached to any claim, OR attached only to a
        draft (status=0) claim of this same project.

    Bills attached to *another* project's draft claim are deliberately
    excluded — picking them in the new claim's checkbox list would
    silently re-assign them away from that draft (B2 in the review).
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)

    try:
        costing_pks = list(
            Costing.objects.filter(project_id=project_pk)
            .values_list('costing_pk', flat=True)
        )

        # Bills with at least one allocation against a costing line in
        # this project. Restricting Bills.project to this project too
        # belt-and-braces against the (rare) bill that has cross-project
        # allocations.
        bill_pks = Bill_allocations.objects.filter(
            item__in=costing_pks,
        ).values_list('bill_id', flat=True).distinct()

        available_bills = Bills.objects.filter(
            bill_pk__in=bill_pks,
            project_id=project_pk,
        ).filter(
            Q(associated_hc_claim__isnull=True) |
            Q(associated_hc_claim__status=0,
              associated_hc_claim__project_id=project_pk)
        ).select_related('contact_pk', 'associated_hc_claim').order_by('-bill_date')

        bills_list = []
        for bill in available_bills:
            project_allocations = (
                Bill_allocations.objects
                .filter(bill=bill, item__in=costing_pks)
                .select_related('item__category')
            )
            total_amount = project_allocations.aggregate(total=Sum('amount'))['total'] or 0

            # Categories / costings the bill touches *on this project*.
            # A bill can span multiple lines, so we surface them as a
            # de-duplicated list (in allocation order) and let the
            # frontend decide how to render. Empty strings are dropped.
            categories = []
            costings = []
            for alloc in project_allocations:
                if alloc.item is None:
                    continue
                cat_name = alloc.item.category.category if alloc.item.category_id else ''
                cost_name = alloc.item.item or ''
                if cat_name and cat_name not in categories:
                    categories.append(cat_name)
                if cost_name and cost_name not in costings:
                    costings.append(cost_name)

            bills_list.append({
                'bill_pk': bill.bill_pk,
                'supplier': bill.contact_pk.name if bill.contact_pk else 'Unknown',
                'bill_date': bill.bill_date.isoformat() if bill.bill_date else None,
                'total_amount': float(total_amount),
                'total_net': float(bill.total_net) if bill.total_net is not None else None,
                'bill_status': bill.bill_status,
                'categories': categories,
                'costings': costings,
                'already_in_claim': bill.associated_hc_claim_id is not None,
            })

        return JsonResponse({'status': 'success', 'bills': bills_list})

    except Exception as e:
        logger.error(f"Error getting available bills: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
def get_available_stocktake_snaps(request, project_pk):
    """Get stocktake snaps available for inclusion in an HC claim for THIS project.

    A snap is available if:
      - it is finalised (status >= STATUS_FINALISED), AND
      - it has allocations against this project, AND
      - it is either unattached to any claim, OR attached only to a
        draft (status=0) claim of this same project.

    Mirrors the bill rules in get_available_bills (B2 / B7 in the
    review).
    """
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)

    try:
        snap_pks = StocktakeSnapAllocation.objects.filter(
            project_id=project_pk,
        ).values_list('snap_item__snap_id', flat=True).distinct()

        snaps = StocktakeSnap.objects.filter(
            snap_pk__in=snap_pks,
            status__gte=StocktakeSnap.STATUS_FINALISED,
        ).filter(
            Q(associated_hc_claim__isnull=True) |
            Q(associated_hc_claim__status=0,
              associated_hc_claim__project_id=project_pk)
        ).select_related('associated_hc_claim').order_by('-date')

        snaps_list = []
        for snap in snaps:
            project_allocations = (
                StocktakeSnapAllocation.objects
                .filter(snap_item__snap=snap, project_id=project_pk)
                .select_related('snap_item__item__category')
            )
            total_allocated = project_allocations.aggregate(total=Sum('amount'))['total'] or 0

            categories = []
            costings = []
            for alloc in project_allocations:
                costing = alloc.snap_item.item if alloc.snap_item_id else None
                if costing is None:
                    continue
                cat_name = costing.category.category if costing.category_id else ''
                cost_name = costing.item or ''
                if cat_name and cat_name not in categories:
                    categories.append(cat_name)
                if cost_name and cost_name not in costings:
                    costings.append(cost_name)

            snaps_list.append({
                'stocktake_snap_pk': snap.snap_pk,
                'snap_date': snap.date.isoformat() if snap.date else None,
                'total_allocated': float(total_allocated),
                'categories': categories,
                'costings': costings,
                'already_in_claim': snap.associated_hc_claim_id is not None,
            })

        return JsonResponse({'status': 'success', 'snaps': snaps_list})

    except Exception as e:
        logger.error(f"Error getting available stocktake snaps: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
def create_hc_claim(request):
    """Create a new HC claim with date and optionally associate bills/snaps.

    Project-scoped guards:
      - reject if the project is_revenue_project=False (B16)
      - reject if a draft already exists for this project (B1)

    Cross-project leak guards (drop, don't error):
      - bill_pks must belong to this project (B2)
      - snap_pks must have allocations against this project AND must
        not currently be attached to another project's draft (B7)
    """
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

        try:
            project = Projects.objects.get(pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({'error': 'Project not found'}, status=404)

        # B16: non-revenue projects (internal R&D etc.) don't have HC
        # claims at all. The frontend already hides the button, but
        # the endpoint needs its own guard.
        if not getattr(project, 'is_revenue_project', True):
            return JsonResponse({
                'error': (
                    'This project is marked as not a revenue project, so '
                    'HC claims cannot be created against it.'
                ),
            }, status=400)

        # B1: project-scoped draft guard
        if HC_claims.objects.filter(status=0, project=project).exists():
            return JsonResponse({
                'error': (
                    'There is already a draft HC claim in progress for '
                    'this project. Complete or delete it first.'
                ),
            }, status=400)

        claim_date_obj = datetime.strptime(claim_date, '%Y-%m-%d').date()

        # B.V-C-12: claim header + bill attachments + snap attachments must
        # land or fail together. A partial create would leave the operator
        # with bills wired to a draft that doesn't exist, or a draft that
        # silently dropped half its attachments.
        with transaction.atomic():
            claim = HC_claims.objects.create(
                date=claim_date_obj, status=0, project=project,
            )

            # B2: only attach bills that belong to this project AND are
            # either unattached or attached to *this* project's draft.
            valid_bill_pks = list(
                Bills.objects
                .filter(bill_pk__in=selected_bill_pks, project=project)
                .filter(
                    Q(associated_hc_claim__isnull=True) |
                    Q(associated_hc_claim__project_id=project.pk,
                      associated_hc_claim__status=0)
                )
                .values_list('bill_pk', flat=True)
            )
            if valid_bill_pks:
                Bills.objects.filter(bill_pk__in=valid_bill_pks).update(associated_hc_claim=claim)

            # B7: only attach snaps that
            #   - have at least one allocation against this project, AND
            #   - are finalised, AND
            #   - are either unattached or attached to *this* project's draft.
            valid_snap_pks = list(
                StocktakeSnap.objects
                .filter(
                    snap_pk__in=selected_snap_pks,
                    status__gte=StocktakeSnap.STATUS_FINALISED,
                    snap_items__allocations__project=project,
                )
                .filter(
                    Q(associated_hc_claim__isnull=True) |
                    Q(associated_hc_claim__project_id=project.pk,
                      associated_hc_claim__status=0)
                )
                .distinct()
                .values_list('snap_pk', flat=True)
            )
            if valid_snap_pks:
                StocktakeSnap.objects.filter(snap_pk__in=valid_snap_pks).update(associated_hc_claim=claim)

        logger.info(
            "Created HC claim %s for project %s with %s bills (%s requested) "
            "and %s snaps (%s requested)",
            claim.hc_claim_pk, project.pk,
            len(valid_bill_pks), len(selected_bill_pks),
            len(valid_snap_pks), len(selected_snap_pks),
        )

        return JsonResponse({
            'status': 'success',
            'hc_claim_pk': claim.hc_claim_pk,
            'display_id': claim.display_id,
            'bills_attached': len(valid_bill_pks),
            'bills_requested': len(selected_bill_pks),
            'snaps_attached': len(valid_snap_pks),
            'snaps_requested': len(selected_snap_pks),
        })

    except Exception as e:
        logger.error(f"Error creating HC claim: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


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
        items = (
            Costing.objects
            .filter(project_id=project_pk, tender_or_execution=2)
            .select_related('category', 'unit')
            .order_by('category__order_in_list', 'order_in_list')
        )
        
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
        
        # Get HC variations up to claim date, plus a "previous-period"
        # snapshot so the finalised report can split variations into
        # the "this claim" and "prev claims" columns. The split point
        # is the date of the most recent prior approved claim
        # (variations dated <= prev_claim_date count as "prev"; those
        # dated > prev_claim_date and <= this claim's date count as
        # "this"). If there is no prior approved claim everything
        # counts as "this".
        variation_amounts = get_variation_amounts(project_pk, claim.date)
        prev_claim_date = (
            HC_claims.objects
            .filter(project_id=project_pk, status=1, date__lt=claim.date)
            .exclude(hc_claim_pk=claim.hc_claim_pk)
            .order_by('-date', '-hc_claim_pk')
            .values_list('date', flat=True)
            .first()
        )
        prev_variation_amounts = (
            get_variation_amounts(project_pk, prev_claim_date)
            if prev_claim_date is not None else {}
        )
        
        # Build budget data per item
        budget_data = []
        for item in items:
            item_pk = item.costing_pk
            
            # Get or calculate values
            existing = existing_allocations.get(item_pk)
            
            base_contract_budget = float(item.contract_budget or 0)
            total_variations = float(variation_amounts.get(item_pk, 0))
            prev_variations = float(prev_variation_amounts.get(item_pk, 0))
            this_variations = total_variations - prev_variations
            contract_budget = base_contract_budget + total_variations
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
            prev = previous_claims.get(
                item_pk,
                {'hc': 0, 'qs': 0, 'fixed_on_site': 0, 'sc_invoiced': 0},
            )
            prev_hc_claimed = prev['hc']
            prev_qs_claimed = prev['qs']
            prev_fixed_on_site = prev.get('fixed_on_site', 0)
            prev_sc_invoiced = prev.get('sc_invoiced', 0)
            
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

            # Invoiced Prev = sum of prior approved claims' sc_invoiced
            # for this item. Mirrors what the authoritative finalize
            # snapshot will record for sc_invoiced_previous.
            invoiced_prev = prev_sc_invoiced
            
            budget_data.append({
                'costing_pk': item_pk,
                'category': item.category.category if item.category else '',
                'category_pk': item.category_id,
                # Sentinel exposed so the JS can branch on Internal (-10)
                # / Labour (-5) categories without string-matching the
                # category name (B6 in the review).
                'division': int(item.category.division) if item.category and item.category.division is not None else 0,
                'item': item.item,
                'unit': item.unit.unit_name if item.unit else '',
                'contract_budget': contract_budget,
                # Base contract budget excludes HC variations. The
                # finalised report displays variations in their own
                # columns, so we surface base separately as well.
                'base_contract_budget': base_contract_budget,
                'this_hc_variations': this_variations,
                'prev_hc_variations': prev_variations,
                'working_budget': working_budget,
                'uncommitted': uncommitted,
                'uncommitted_qty': float(item.uncommitted_qty or 0),
                'uncommitted_rate': float(item.uncommitted_rate or 0),
                'uncommitted_notes': item.uncommitted_notes or '',
                'committed': committed,
                'committed_qty': committed_qty,
                'committed_rate': committed_rate,
                'fixed_on_site': fixed_on_site,
                # The latest fixed_on_site recorded on a prior approved
                # claim (B19). Surfacing it lets the frontend display
                # the snapshot at finalize time alongside the
                # current-period delta.
                'fixed_on_site_previous': float(prev_fixed_on_site),
                # invoiced is the TOTAL invoiced for this item across all
                # bills (regardless of which claim they're attached to)
                # — it is what the QS-claim formula uses. The split
                # invoiced_prev/invoiced_this fields are for the table
                # display and are computed differently. Surfacing
                # invoiced explicitly so the frontend recalculation
                # matches the backend (B5 in the review).
                'invoiced': float(invoiced),
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
        return JsonResponse({'error': 'Internal server error'}, status=500)


def get_previous_claim_totals(project_pk, exclude_claim_pk=None):
    """Get totals from prior approved claims, per costing item.

    Returns a dict keyed by costing_pk with keys:
      hc            — sum of hc_claimed across prior approved claims
      qs            — sum of qs_claimed across prior approved claims
      fixed_on_site — fixed_on_site value from the latest prior
                      approved claim (NOT a sum — fixed_on_site is a
                      cumulative running value, not a per-period delta)
      sc_invoiced   — sum of sc_invoiced across prior approved claims

    These power the authoritative server-side snapshot at finalize time
    (B12/B19/B20 in the review) — the frontend's "_previous" fields are
    ignored.
    """
    costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)

    query = HC_claim_allocations.objects.filter(
        item__in=costing_pks,
        hc_claim_pk__status__gte=1,  # Approved or higher
    ).select_related('hc_claim_pk').order_by('hc_claim_pk__date', 'hc_claim_pk_id')

    if exclude_claim_pk:
        query = query.exclude(hc_claim_pk_id=exclude_claim_pk)

    totals = {}
    for alloc in query:
        item_pk = alloc.item_id
        bucket = totals.setdefault(
            item_pk,
            {'hc': 0.0, 'qs': 0.0, 'fixed_on_site': 0.0, 'sc_invoiced': 0.0},
        )
        bucket['hc'] += float(alloc.hc_claimed or 0)
        bucket['qs'] += float(alloc.qs_claimed or 0)
        bucket['sc_invoiced'] += float(alloc.sc_invoiced or 0)
        # fixed_on_site is cumulative, not a per-period delta — keep
        # the latest seen value (queryset is ordered by claim date).
        bucket['fixed_on_site'] = float(alloc.fixed_on_site or 0)

    return totals


# Note: ``get_committed_amounts`` and ``get_invoiced_amounts`` previously
# lived here as ~170 lines of inline rollup code. They have been moved
# verbatim into ``core/services/costing_rollups.py`` (audit
# A.M-R-02 / P-5) and re-exported above as legacy aliases so existing
# in-module callers and any external imports keep working.


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
        
        # B.V-C-12: detach bills/snaps and delete the claim atomically. A
        # half-completed delete would leave bills detached from a claim
        # that still exists, or a deleted claim with bills still pointing
        # at it (FK constraint will then refuse the next operation).
        with transaction.atomic():
            Bills.objects.filter(associated_hc_claim=claim).update(associated_hc_claim=None)
            StocktakeSnap.objects.filter(associated_hc_claim=claim).update(associated_hc_claim=None)
            claim.delete()
        
        logger.info(f"Deleted HC claim {claim_pk}")
        return JsonResponse({'status': 'success', 'message': 'Claim deleted'})
    
    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC claim: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt
def finalize_hc_claim(request):
    """Finalize an HC claim.

    Persists one HC_claim_allocations row per costing line that has
    real activity in this claim, then flips the claim status to
    approved (1).

    Snapshot semantics — the `*_previous` fields are NOT trusted from
    the client; they are recomputed server-side from prior approved
    claims (B12/B19/B20 in the review). The client supplies the
    "current period" values:
        - fixed_on_site (current cumulative on-site value)
        - hc_claimed    (this period's HC claim)
        - qs_claimed    (this period's QS claim)
        - sc_invoiced   (this period's SC invoiced — bills attached
                        to this claim)
    plus the contextual fields it already passes:
        - contract_budget, working_budget, uncommitted, committed,
          category_pk

    Server then derives:
        fixed_on_site_previous = prior approved fixed_on_site for item
        fixed_on_site_this     = fixed_on_site - fixed_on_site_previous
        sc_invoiced_previous   = sum of prior approved sc_invoiced
        hc_claimed_previous    = sum of prior approved hc_claimed
        qs_claimed_previous    = sum of prior approved qs_claimed

    Empty-claim guard (B17): if every row is zero-activity we refuse
    to finalize. Skipping zero-activity rows (B3) is preserved.
    """
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

        # Project FK is mandatory at this point (claims created before
        # 0074's backfill will have it; new claims set it directly).
        project_pk = claim.project_id
        if not project_pk:
            return JsonResponse(
                {'error': 'Claim is not linked to a project; cannot finalize'},
                status=400,
            )

        # Pull the authoritative prior totals once.
        prev_totals = get_previous_claim_totals(project_pk, exclude_claim_pk=claim_pk)

        def _is_zero_activity(d):
            keys = ('hc_claimed', 'qs_claimed', 'sc_invoiced')
            for k in keys:
                try:
                    if abs(float(d.get(k, 0) or 0)) > 1e-6:
                        return False
                except (TypeError, ValueError):
                    return False
            return True

        # B17: refuse to finalize a claim with no activity anywhere.
        if not any((not _is_zero_activity(a)) for a in allocations_data):
            return JsonResponse({
                'error': (
                    'This claim has no claimed or invoiced amounts. '
                    'Enter at least one HC claim, QS claim, or invoiced '
                    'amount before finalizing.'
                ),
            }, status=400)

        kept = 0
        skipped = 0
        # B.V-C-12: persist all allocations and the status flip atomically.
        # If any single row fails we leave the claim as-is, in draft, with
        # no half-written allocations.
        with transaction.atomic():
            for alloc_data in allocations_data:
                item_pk = alloc_data.get('costing_pk')
                category_pk = alloc_data.get('category_pk')
                if not item_pk:
                    continue

                if _is_zero_activity(alloc_data):
                    skipped += 1
                    continue

                item = Costing.objects.get(costing_pk=item_pk)
                category = Categories.objects.get(pk=category_pk) if category_pk else item.category

                # Server-derived "previous" snapshot from prior approved claims
                prev = prev_totals.get(
                    item_pk,
                    {'hc': 0.0, 'qs': 0.0, 'fixed_on_site': 0.0, 'sc_invoiced': 0.0},
                )
                prev_fos = float(prev.get('fixed_on_site') or 0)

                try:
                    fos_now = float(alloc_data.get('fixed_on_site') or 0)
                except (TypeError, ValueError):
                    fos_now = 0.0

                HC_claim_allocations.objects.update_or_create(
                    hc_claim_pk=claim,
                    item=item,
                    defaults={
                        'category': category,
                        'contract_budget': alloc_data.get('contract_budget', 0),
                        'working_budget': alloc_data.get('working_budget', 0),
                        'uncommitted': alloc_data.get('uncommitted', 0),
                        'committed': alloc_data.get('committed', 0),
                        # fixed_on_site is the current cumulative value;
                        # _previous comes from server (B19), _this is the
                        # delta the server computes.
                        'fixed_on_site': fos_now,
                        'fixed_on_site_previous': prev_fos,
                        'fixed_on_site_this': fos_now - prev_fos,
                        # sc_invoiced split: backend computes _previous (B20)
                        'sc_invoiced_previous': float(prev.get('sc_invoiced') or 0),
                        'sc_invoiced': alloc_data.get('sc_invoiced', 0),
                        'adjustment': 0,  # Not used for now
                        # hc/qs split: backend computes _previous (B20)
                        'hc_claimed_previous': float(prev.get('hc') or 0),
                        'hc_claimed': alloc_data.get('hc_claimed', 0),
                        'qs_claimed_previous': float(prev.get('qs') or 0),
                        'qs_claimed': alloc_data.get('qs_claimed', 0),
                    },
                )
                kept += 1

            # Set claim status to approved (1)
            claim.status = 1
            claim.save()

        logger.info(
            "Finalized HC claim %s for project %s: persisted %s allocations "
            "(skipped %s zero-activity rows of %s posted)",
            claim_pk, claim.project_id, kept, skipped, len(allocations_data),
        )

        return JsonResponse({
            'status': 'success',
            'message': 'Claim finalized successfully',
            'hc_claim_pk': claim.hc_claim_pk,
        })

    except HC_claims.DoesNotExist:
        return JsonResponse({'error': 'Claim not found'}, status=404)
    except Exception as e:
        logger.error(f"Error finalizing HC claim: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
