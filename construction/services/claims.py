"""
Construction-specific claims service module.

Contains business logic for HC claims and variations operations that is
specific to the construction project type.
"""

from django.db.models import Sum, Max
from django.forms.models import model_to_dict
from core.models import HC_claims, HC_claim_allocations, Hc_variation, Hc_variation_allocations


def get_hc_qs_totals():
    """
    Get HC and QS claim totals from HC_claim_allocations.

    Returns:
        dict: {hc_claim_pk: {'hc_total': float, 'qs_total': float}}
    """
    hc_qs_totals = HC_claim_allocations.objects.values('hc_claim_pk').annotate(
        hc_total=Sum('hc_claimed'),
        qs_total=Sum('qs_claimed')
    )

    return {item['hc_claim_pk']: {
        'hc_total': float(item['hc_total'] or 0),
        'qs_total': float(item['qs_total'] or 0)
    } for item in hc_qs_totals}


def get_hc_claims_list(sc_totals_dict):
    """
    Get list of HC claims with totals.

    Args:
        sc_totals_dict: Dictionary of SC totals by HC claim

    Returns:
        tuple: (hc_claims_list, approved_claims_list)
    """
    hc_qs_totals_dict = get_hc_qs_totals()
    hc_claims_list = []
    approved_claims_list = []

    hc_claims_qs = HC_claims.objects.all().order_by('-display_id')

    for claim in hc_claims_qs:
        claim_totals = hc_qs_totals_dict.get(claim.hc_claim_pk, {'hc_total': 0.0, 'qs_total': 0.0})
        d = {
            'hc_claim_pk': claim.hc_claim_pk,
            'date': claim.date.strftime('%Y-%m-%d') if claim.date else None,
            'status': claim.status,
            'display_id': claim.display_id,
            'invoicee': claim.invoicee if claim.invoicee else None,
            'hc_total': claim_totals['hc_total'],
            'qs_total': claim_totals['qs_total'],
            'sc_total': sc_totals_dict.get(claim.hc_claim_pk, 0.0)
        }
        hc_claims_list.append(d)

        # Only add approved claims to the approved list for validation
        if claim.status > 0:
            approved_claims_list.append(d)

    return hc_claims_list, approved_claims_list


def get_hc_variations_list():
    """
    Get list of HC variations with items and claimed status.

    Returns:
        list: List of variation dictionaries with items
    """
    hc_variations_list = []

    # Get the maximum date of HC_claims with status not 0 (i.e., approved claims)
    max_approved_claim_date = HC_claims.objects.filter(status__gt=0).aggregate(Max('date'))['date__max']

    hc_variations_qs = Hc_variation.objects.all().order_by('date')

    for variation in hc_variations_qs:
        # Get the total amount for this variation
        variation_allocations = Hc_variation_allocations.objects.filter(hc_variation=variation)
        total_amount = sum(allocation.amount for allocation in variation_allocations)

        # Get a list of items for this variation
        items_list = []
        for allocation in variation_allocations:
            items_list.append({
                'item': allocation.costing.item,
                'amount': float(allocation.amount),
                'notes': allocation.notes,
                'category_order_in_list': allocation.costing.category.order_in_list
            })

        # Calculate the claimed status
        # 0 = claimed (part of HC claim), 1 = not claimed
        claimed = 0  # Default to claimed
        if max_approved_claim_date and variation.date <= max_approved_claim_date:
            claimed = 1  # Variation is claimed if its date is <= the max approved claim date

        # Create the variation dictionary
        v = {
            'hc_variation_pk': variation.hc_variation_pk,
            'date': variation.date.strftime('%Y-%m-%d') if variation.date else None,
            'claimed': claimed,
            'total_amount': float(total_amount),
            'items': items_list
        }
        hc_variations_list.append(v)

    return hc_variations_list


def get_hc_variation_allocations_list():
    """
    Get list of all HC variation allocations with variation details.

    Returns:
        list: List of allocation dictionaries with variation and costing details
    """
    hc_variation_allocations_list = []

    for allocation in Hc_variation_allocations.objects.all():
        # Convert model to dictionary, similar to costings format
        allocation_dict = model_to_dict(allocation)
        # Store relationship IDs
        variation_id = allocation_dict['hc_variation']
        costing_id = allocation_dict['costing']

        # Get related objects
        variation_obj = allocation.hc_variation
        costing_obj = allocation.costing

        # Add appropriate fields from related objects
        allocation_dict['hc_variation_pk'] = variation_id
        allocation_dict['variation_date'] = variation_obj.date.strftime('%Y-%m-%d')
        allocation_dict['costing_pk'] = costing_id
        allocation_dict['item'] = costing_obj.item

        # Get category details from costing object - following same pattern as costings section
        cat_obj = costing_obj.category
        category_id = model_to_dict(costing_obj)['category']  # Get the ID from the foreign key
        allocation_dict['category'] = cat_obj.category  # Category name
        allocation_dict['category_id'] = category_id  # Category ID for relationships
        allocation_dict['category_order_in_list'] = cat_obj.order_in_list

        # Convert Decimal fields to float for JSON serialization
        allocation_dict['amount'] = float(allocation.amount)

        hc_variation_allocations_list.append(allocation_dict)

    return hc_variation_allocations_list


def get_current_hc_claim():
    """
    Get the current HC claim (status 0).

    Returns:
        HC_claims: Current HC claim object or None
    """
    return HC_claims.objects.filter(status=0).first()


def get_hc_claim_wip_adjustments(current_hc_claim):
    """
    Get HC claim WIP adjustments for current claim.

    Args:
        current_hc_claim: Current HC claim object

    Returns:
        dict: {costing_pk: adjustment}
    """
    if not current_hc_claim:
        return {}

    hc_claim_allocs = HC_claim_allocations.objects.filter(hc_claim_pk=current_hc_claim.hc_claim_pk)
    return {a.item.costing_pk: a.adjustment for a in hc_claim_allocs}


def calculate_hc_prev_fixedonsite(costing_pk, current_hc_claim):
    """
    Calculate previous fixed on site value for a costing.

    Args:
        costing_pk: Primary key of the costing item
        current_hc_claim: Current HC claim object

    Returns:
        Decimal: Previous fixed on site value
    """
    if not current_hc_claim:
        return 0

    prev_alloc = (
        HC_claim_allocations.objects
        .filter(item=costing_pk, hc_claim_pk__lt=current_hc_claim.hc_claim_pk)
        .order_by('-hc_claim_pk')
        .first()
    )

    return prev_alloc.fixed_on_site if prev_alloc else 0


def calculate_hc_prev_claimed(costing_pk, current_hc_claim):
    """
    Calculate previous HC claimed value for a costing.

    Args:
        costing_pk: Primary key of the costing item
        current_hc_claim: Current HC claim object

    Returns:
        Decimal: Previous HC claimed value
    """
    hc_prev_claimed = 0
    allocs = HC_claim_allocations.objects.filter(item=costing_pk)

    for al in allocs:
        hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
        if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
            hc_prev_claimed += al.hc_claimed

    return hc_prev_claimed


def calculate_qs_claimed(costing_pk, current_hc_claim):
    """
    Calculate QS claimed value for a costing.

    Args:
        costing_pk: Primary key of the costing item
        current_hc_claim: Current HC claim object

    Returns:
        Decimal: QS claimed value
    """
    qs_claimed = 0
    allocs = HC_claim_allocations.objects.filter(item=costing_pk)

    for al in allocs:
        hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
        if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
            qs_claimed += al.qs_claimed

    return qs_claimed


def get_claim_category_totals(division):
    """
    Get claim category totals grouped by hc_claim_pk and invoice_category.

    Args:
        division: Division ID (1 or 2)

    Returns:
        QuerySet: Claim category totals
    """
    return (HC_claim_allocations.objects.filter(category__division=division)
        .values('hc_claim_pk', 'hc_claim_pk__display_id', 'category__invoice_category')
        .annotate(
            total_hc_claimed=Sum('hc_claimed'),
            total_qs_claimed=Sum('qs_claimed'),
            total_contract_budget=Sum('contract_budget'),
            max_order=Max('category__order_in_list'),
            latest_category=Max('category__category')
        ).order_by('hc_claim_pk', 'max_order'))


def get_hc_claims_data_for_costing(costing_pk, current_hc_claim, category_order_in_list):
    """
    Get HC claims data for a specific costing item.

    Args:
        costing_pk: Primary key of the costing item
        current_hc_claim: Current HC claim object
        category_order_in_list: Category order in list

    Returns:
        dict: HC claims data for the costing
    """
    if not current_hc_claim:
        return {
            'hc_prev_invoiced': 0,
            'hc_this_claim_invoices': 0
        }

    hc_prev_invoiced = 0
    hc_this_claim_invoices = 0

    # Handle margin items (category_order_in_list = -1) differently
    if category_order_in_list == -1:
        # For margin items, get sc_invoiced from HC_claim_allocations
        hc_alloc = HC_claim_allocations.objects.filter(
            hc_claim_pk=current_hc_claim,
            item=costing_pk
        ).first()
        if hc_alloc:
            hc_this_claim_invoices = hc_alloc.sc_invoiced

    return {
        'hc_prev_invoiced': hc_prev_invoiced,
        'hc_this_claim_invoices': hc_this_claim_invoices
    }
