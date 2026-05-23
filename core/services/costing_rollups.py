"""
Costing rollups -- single source of truth for "how much has been
committed/paid/etc against this Costing item / project".

Why this exists: the Contract Budget view, the HC Claims view, the dashboard
action items, and a few exports each implement their own version of these
sums today. The numbers occasionally disagree because the filter clauses
have drifted (e.g. one place treats `bill_status=2` as "settled" and another
doesn't). Funnel everything through this module instead.

Design rules:
  * Only Decimal arithmetic. Never `float`. Use core/formulas.py helpers.
  * Filter sets come from the model's queryset methods
    (BillAllocationsQuerySet, BillsQuerySet) so a status semantic change
    only has to be made in one place.
  * Functions return Decimals (or dicts of Decimals), never JSON-encoded
    strings. The view layer is responsible for serialisation.

Audit context (A.M-R-02): this module is the canonical home for *all*
project-level rollups. ``compute_project_committed_billed`` powers Contract
Budget; ``hc_committed_amounts`` and ``hc_invoiced_amounts`` power HC
Claims. The two committed views are deliberately *different* — Contract
Budget includes Internal contract_budget + Labour wages + direct bills
(types 0/1) + snaps; HC Claims includes quotes + snaps only. That
difference reflects business intent, not formula drift, and is preserved
here intentionally. The point of co-locating them is so future changes
to the shared sub-clauses (e.g. the canonical bill_type filter) only
have to be made in one file.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict

from django.db.models import Sum

from ..formulas import sum_decimals, to_decimal
from ..models import (
    Bills,
    Bill_allocations,
    Categories,
    Costing,
    EmployeePayRate,
    Projects,
    Quote_allocations,
    Quotes,
    StaffHoursAllocations,
    StocktakeSnap,
    StocktakeSnapAllocation,
)


# ---------------------------------------------------------------------------
# Per-item rollups (small, simple primitives — used by callers that just
# need a single number, e.g. the dashboard action-item summary).
# ---------------------------------------------------------------------------

def committed_for_item(costing_pk) -> Decimal:
    """Total amount committed against a single Costing item.

    "Committed" = sum of all quote allocations + sum of all bill allocations
    on bills that have moved past STATUS_CREATED (i.e. allocated, approved,
    sent-to-Xero, or paid). PO progress claims are excluded (they only
    appear in the rollup once they reach STATUS_PO_APPROVED_BILL_UPLOADED
    via the bill_status range filter).
    """
    quote_total = Quote_allocations.objects.filter(
        item__costing_pk=costing_pk
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    bill_total = Bill_allocations.objects.committed().filter(
        item__costing_pk=costing_pk
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    return to_decimal(quote_total) + to_decimal(bill_total)


def settled_for_item(costing_pk) -> Decimal:
    """Sum of "settled" bill allocations against a Costing item.

    Settled set is whatever Bills.STATUSES_SETTLED_FOR_HC_CLAIM says.
    Quote allocations never count as settled — only invoiced money does.
    """
    return to_decimal(
        Bill_allocations.objects.filter(
            item__costing_pk=costing_pk,
        ).filter(
            bill__bill_status__in=Bills.STATUSES_SETTLED_FOR_HC_CLAIM,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    )


# ---------------------------------------------------------------------------
# Per-project rollups (small variant — used by callers that don't need
# Contract Budget's full {qty, rate, amount} dict shape).
# ---------------------------------------------------------------------------

def committed_by_costing_for_project(project_pk) -> Dict[int, Decimal]:
    """Return {costing_pk: committed_amount} for every item in a project.

    Used by Contract Budget. Returns a dict keyed by costing_pk so callers
    can join into their item lists without an N+1 query.
    """
    quote_rows = (
        Quote_allocations.objects
        .filter(item__project_id=project_pk)
        .values('item__costing_pk')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )
    bill_rows = (
        Bill_allocations.objects.committed()
        .filter(item__project_id=project_pk)
        .values('item__costing_pk')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )

    rollup: Dict[int, Decimal] = defaultdict(lambda: Decimal('0'))
    for pk, amount in quote_rows:
        rollup[pk] += to_decimal(amount)
    for pk, amount in bill_rows:
        rollup[pk] += to_decimal(amount)
    return dict(rollup)


def invoiced_amounts_for_project(
    project_pk,
    *,
    include_progress_claim_only: bool = True,
) -> Dict[int, Decimal]:
    """Return {costing_pk: invoiced_amount} for HC-claim purposes.

    HC claims should only see allocations on bills that look like a real
    cost commitment — direct costs, or progress-claim bills with their
    progress-claim flag set. ``include_progress_claim_only`` matches the
    historical behaviour of `core/services/quotes.py:get_invoiced_amounts`.

    NOTE: the audit (see BEST_PRACTICE_AUDIT.md, A.M-C-02 / A.M-C-03)
    flagged that previous code mistakenly included STATUS_APPROVED bills
    as "settled". This function uses STATUSES_SETTLED_FOR_HC_CLAIM, which
    today is {STATUS_APPROVED, STATUS_SENT_TO_XERO} — preserving the
    existing behaviour. Tightening to {STATUS_SENT_TO_XERO, STATUS_PAID}
    is a deliberate business call left for a follow-up PR.
    """
    qs = Bill_allocations.objects.filter(
        bill__project_id=project_pk,
        bill__bill_status__in=Bills.STATUSES_SETTLED_FOR_HC_CLAIM,
    )
    if include_progress_claim_only:
        qs = qs.counts_toward_hc_invoiced()

    rows = (
        qs.values('item__costing_pk')
          .annotate(amount=Sum('amount'))
          .values_list('item__costing_pk', 'amount')
    )

    rollup: Dict[int, Decimal] = defaultdict(lambda: Decimal('0'))
    for pk, amount in rows:
        rollup[pk] += to_decimal(amount)
    return dict(rollup)


def project_committed_total(project_pk) -> Decimal:
    """Return the project-wide committed total."""
    return sum_decimals(committed_by_costing_for_project(project_pk).values())


# ---------------------------------------------------------------------------
# Staff-hours wages helper (per-allocation realised cost).
#
# Lives here because both the Contract Budget rollup (Labour committed +
# every-item billed) and the per-item allocations endpoint use it. The
# proper home long-term is `core/services/staff_cost.py` (audit A.M-R-06)
# — when that batch service lands this can move and this module imports
# it instead.
#
# The Xero super-rate lookup is imported lazily because `staff_hours.py`
# is a view module and we don't want a service -> view import edge at
# module-load time. View-layer-from-service is a code smell; A.M-R-06
# is the planned cleanup.
# ---------------------------------------------------------------------------

def compute_staff_hours_allocation_amount(alloc):
    """
    Compute the realised wages cost (incl. superannuation) for one
    StaffHoursAllocation row.

    Mirrors the per-allocation maths used by the Labour-committed branch in
    ``compute_project_committed_billed`` so that StaffHours can be rolled up
    consistently into both Committed (Labour items only) and Billed
    (every item with project allocations) totals without drifting.

    Returns 0.0 when hours are non-positive, no applicable EmployeePayRate
    exists, or no derivable hourly rate can be obtained.
    """
    from ..views.staff_hours import get_employee_super_rate

    hours = alloc.hours or Decimal('0')
    if hours <= 0:
        return 0.0

    employee = alloc.staff_hours.employee
    target_date = alloc.staff_hours.date

    pay_rate = EmployeePayRate.objects.filter(
        employee=employee,
        effective_date__lte=target_date,
        is_ordinary_rate=True
    ).order_by('-effective_date').first()
    if not pay_rate:
        return 0.0

    hourly_rate = None
    if pay_rate.rate_per_unit:
        hourly_rate = float(pay_rate.rate_per_unit)
    elif pay_rate.annual_salary and pay_rate.units_per_week:
        weekly_hours = float(pay_rate.units_per_week)
        if weekly_hours > 0:
            hourly_rate = float(pay_rate.annual_salary) / (weekly_hours * 52)
    if not hourly_rate:
        return 0.0

    wages_cost = float(hours) * hourly_rate
    super_rate = get_employee_super_rate(
        employee.xero_instance_id,
        employee.xero_employee_id
    )
    if super_rate:
        wages_cost += wages_cost * (super_rate / 100)
    return wages_cost


# ---------------------------------------------------------------------------
# Contract Budget rollup — full {qty, rate, amount} dict shape.
#
# This is the function that drives the Contract Budget table for every
# project. It's the most opinionated of the rollups: it folds in quotes,
# Internal-category contract_budget, Labour wages/super, direct-cost
# bills (types 0/1), snaps, and (separately for billed) every bill type
# plus snaps plus realised wages.
# ---------------------------------------------------------------------------

def compute_project_committed_billed(project, tender_or_execution):
    """
    Pure-Python core of ``get_project_committed_amounts`` — produces the same
    ``committed_dict`` and ``billed_dict`` numbers the UI consumes, but without
    the JsonResponse wrapper, so other server-side callers (e.g. the
    Export C2C report) can reuse it.

    Returns:
        (committed_dict, billed_dict, is_construction)

        For construction projects ``committed_dict`` values are dicts with
        qty / rate / amount keys; for non-construction projects values are
        simple float amounts. ``billed_dict`` values are always floats.
    """
    is_construction = (project.project_type and project.project_type.rates_based == 1)

    # Get all quotes for this project filtered by tender_or_execution
    project_quotes = Quotes.objects.filter(project=project, tender_or_execution=tender_or_execution)

    if is_construction:
        # For construction types, return qty, rate, amount per item
        # Check for multiple unique rates per costing item
        allocations = Quote_allocations.objects.filter(
            quotes_pk__in=project_quotes
        ).values('item__costing_pk', 'qty', 'rate', 'amount')

        # Group allocations by costing_pk
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
    # Sum of (hours * applicable pay rate) for each costing item.
    # Per-allocation maths is delegated to ``compute_staff_hours_allocation_amount``
    # so the Labour branch can't drift away from the every-item Billed branch
    # below or the per-item allocations endpoint (audit A.M-H-03 calls out
    # the historical triplication; this module unifies two of the three —
    # the third lives in core/views/staff_hours.py and is a separate cleanup).
    labour_items = Costing.objects.filter(
        project=project,
        category__division=-5,  # Labour category
        tender_or_execution=tender_or_execution
    )

    for item in labour_items:
        allocations = StaffHoursAllocations.objects.filter(
            project=project,
            costing=item
        ).select_related('staff_hours__employee')

        total_amount = Decimal('0')
        for alloc in allocations:
            wages_amount = compute_staff_hours_allocation_amount(alloc)
            if wages_amount > 0:
                total_amount += Decimal(str(wages_amount))

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

    # Add stocktake snap allocations to committed amounts.
    #
    # A.M-C-13: previously this matched snap_item -> costing by **item name**
    # (string lookup against `Costing.item`), while HC Claims matched the
    # same relationship via the actual FK (`snap_item.item_id`). The two
    # paths produced different totals when item names collided across
    # projects or when a snap item had been re-pointed. We now use the FK
    # directly (HC's approach) and gate it by `project=project` so a snap
    # item belonging to another project doesn't leak in.
    snap_allocations = list(
        StocktakeSnapAllocation.objects
        .filter(project=project, snap_item__snap__status__gte=1)
        .values('snap_item__item_id', 'qty', 'rate', 'amount')
    )

    project_costing_pks = set(
        Costing.objects.filter(
            project=project,
            tender_or_execution=tender_or_execution,
        ).values_list('costing_pk', flat=True)
    )

    for snap_alloc in snap_allocations:
        costing_pk = snap_alloc['snap_item__item_id']
        if costing_pk not in project_costing_pks:
            # Snap item points at a costing that doesn't belong to this
            # project's current tender/execution scope. Skip silently — the
            # snap allocation either belongs to another project or to a
            # tender/execution scope we're not rendering right now.
            continue

        alloc_qty = float(snap_alloc['qty'] or 0)
        alloc_rate = float(snap_alloc['rate'] or 0)
        alloc_amount = float(snap_alloc['amount'] or 0)

        if is_construction:
            if costing_pk in committed_dict:
                # Add to existing committed data
                existing = committed_dict[costing_pk]
                existing['qty'] = (existing.get('qty') or 0) + alloc_qty
                existing['amount'] = (existing.get('amount') or 0) + alloc_amount
                # Check if rates differ
                if existing.get('rate') and existing['rate'] != alloc_rate:
                    existing['has_multiple_rates'] = True
                elif not existing.get('has_multiple_rates'):
                    existing['rate'] = alloc_rate
            else:
                committed_dict[costing_pk] = {
                    'qty': alloc_qty,
                    'rate': alloc_rate,
                    'amount': alloc_amount,
                    'has_multiple_rates': False
                }
        else:
            if costing_pk in committed_dict:
                committed_dict[costing_pk] += alloc_amount
            else:
                committed_dict[costing_pk] = alloc_amount

    # Add Bill_allocations for direct-cost bills (types 0 and 1) to committed totals.
    # Progress claims (bill_type=2) are excluded so working budget stays quote/snap-grounded:
    # they still count toward billed/C2C-only via billed_dict below.
    bill_allocations_direct = (
        Bill_allocations.objects
        .direct_cost_lines()
        .filter(bill__project=project, item__isnull=False)
        .values('item__costing_pk', 'qty', 'rate', 'amount')
    )

    # Group by costing_pk
    bill_allocs_by_item = defaultdict(list)
    for alloc in bill_allocations_direct:
        if alloc['item__costing_pk']:
            bill_allocs_by_item[alloc['item__costing_pk']].append(alloc)

    for costing_pk, allocs in bill_allocs_by_item.items():
        total_qty = sum(float(a['qty'] or 0) for a in allocs)
        total_amount = sum(float(a['amount'] or 0) for a in allocs)
        unique_rates = set(float(a['rate']) for a in allocs if a['rate'] is not None)

        if is_construction:
            if costing_pk in committed_dict:
                existing = committed_dict[costing_pk]
                existing['qty'] = (existing.get('qty') or 0) + total_qty
                existing['amount'] = (existing.get('amount') or 0) + total_amount
                # Check if rates differ
                if unique_rates:
                    if existing.get('rate') and existing['rate'] not in unique_rates:
                        existing['has_multiple_rates'] = True
                    elif len(unique_rates) > 1:
                        existing['has_multiple_rates'] = True
            else:
                rate = list(unique_rates)[0] if len(unique_rates) == 1 else None
                committed_dict[costing_pk] = {
                    'qty': total_qty,
                    'rate': rate,
                    'amount': total_amount,
                    'has_multiple_rates': len(unique_rates) > 1
                }
        else:
            if costing_pk in committed_dict:
                committed_dict[costing_pk] += total_amount
            else:
                committed_dict[costing_pk] = total_amount

    # Calculate Billed amounts — all Bill_allocations tied to bills on this project
    # (bill_type 0, 1, 2 all included).
    # This is the sum of all Bill_allocations.amount for this project
    all_project_bills = Bills.objects.filter(project=project)

    all_bill_allocations = Bill_allocations.objects.filter(
        bill__in=all_project_bills,
        item__isnull=False
    ).values('item__costing_pk').annotate(
        total_billed=Sum('amount')
    )

    billed_dict = {
        item['item__costing_pk']: float(item['total_billed'])
        for item in all_bill_allocations
        if item['item__costing_pk']
    }

    # Additionally fold StocktakeSnapAllocation amounts into Billed.
    # Snap allocations represent stock physically consumed against the
    # project, i.e. a realised cost — so they are already in Working
    # Budget (via committed_dict above) AND should now contribute to
    # Billed. Net effect on C2C (= WB − Billed) is zero, which is the
    # desired behaviour: consumed stock should not still be expected
    # cost-to-complete.
    #
    # AUDIT FIX: pre-A.M-C-13 this loop tried to access object attributes
    # on what is now a `.values(...)` queryset, AND referenced an
    # `item_name_to_costing` map that A.M-C-13 deleted from this function
    # — meaning the first finalised snap allocation on any project would
    # raise NameError/AttributeError in production. The code was never hit
    # because no snap allocations existed at the time A.M-C-13 landed.
    # Re-using the same FK path + project_costing_pks scope filter as the
    # committed-side loop above keeps the two halves consistent.
    for snap_alloc in snap_allocations:
        costing_pk = snap_alloc['snap_item__item_id']
        if not costing_pk or costing_pk not in project_costing_pks:
            continue
        billed_dict[costing_pk] = (
            billed_dict.get(costing_pk, 0.0) + float(snap_alloc['amount'] or 0)
        )

    # Additionally fold StaffHoursAllocations into Billed for every
    # costing in the current view (not just Labour). Wages paid are a
    # realised cost regardless of which costing item the hours were
    # booked against.
    staff_allocations_billed = StaffHoursAllocations.objects.filter(
        project=project,
        allocation_type=StaffHoursAllocations.ALLOCATION_TYPE_PROJECT,
        costing__isnull=False,
        costing__project=project,
        costing__tender_or_execution=tender_or_execution,
    ).select_related('staff_hours__employee', 'costing')

    for alloc in staff_allocations_billed:
        wages_amount = compute_staff_hours_allocation_amount(alloc)
        if wages_amount > 0:
            cpk = alloc.costing.costing_pk
            billed_dict[cpk] = billed_dict.get(cpk, 0.0) + wages_amount

    return committed_dict, billed_dict, is_construction


# ---------------------------------------------------------------------------
# HC Claims rollups.
#
# These are deliberately *narrower* than the Contract Budget version above:
# HC committed = quotes + finalised snaps only (no Internal contract_budget,
# no Labour wages, no direct bills). The audit (A.M-C-03) flagged the
# divergence as a risk; the team's resolution was that the two views are
# answering different business questions and should not be merged. The
# point of housing both in this module is so that shared sub-clauses
# (the canonical bill_type filter, the FK-based snap match, the settled
# status set) only have to be fixed in one place.
# ---------------------------------------------------------------------------

def hc_committed_amounts(project_pk):
    """Get committed amounts per item from quote and snap allocations.

    Returns dict with qty/rate/amount per costing_pk for construction
    projects (mirrors compute_project_committed_billed); for non-construction
    projects returns just the amount.

    Stocktake snap allocations are folded in for *both* project types.
    Pre-fix, snap allocations were skipped entirely on non-construction
    projects (B9) — yet a non-construction project with stock pulled
    from inventory would understate its committed total.

    Snap-allocation -> costing matching uses StocktakeSnapItem.item
    (which is itself an FK to Costing). The previous code matched by
    string `Costing.item` name, which silently broke if the costing
    line was renamed (B8).
    """
    project = Projects.objects.get(pk=project_pk)
    is_construction = (project.project_type and project.project_type.rates_based == 1)

    # Get quotes for execution mode (tender_or_execution=2)
    project_quotes = Quotes.objects.filter(project=project, tender_or_execution=2)

    # Snap allocations linked to this project, on finalised+ snaps. We
    # use snap_item.item_id directly — that's the FK on
    # StocktakeSnapItem -> Costing.
    snap_allocations = list(
        StocktakeSnapAllocation.objects
        .filter(project=project, snap_item__snap__status__gte=StocktakeSnap.STATUS_FINALISED)
        .values('snap_item__item_id', 'qty', 'rate', 'amount')
    )

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
                committed_dict[costing_pk] = {
                    'qty': total_qty,
                    'rate': None,
                    'amount': total_amount,
                    'has_multiple_rates': True,
                }
            else:
                rate = list(unique_rates)[0] if unique_rates else 0
                committed_dict[costing_pk] = {
                    'qty': total_qty,
                    'rate': round(rate, 2),
                    'amount': total_amount,
                    'has_multiple_rates': False,
                }

        # Fold in snap allocations (B8 + B9)
        for sa in snap_allocations:
            costing_pk = sa['snap_item__item_id']
            if not costing_pk:
                continue
            alloc_qty = float(sa['qty'] or 0)
            alloc_rate = float(sa['rate'] or 0)
            alloc_amount = float(sa['amount'] or 0)

            if costing_pk in committed_dict:
                existing = committed_dict[costing_pk]
                existing['qty'] = (existing.get('qty') or 0) + alloc_qty
                existing['amount'] = (existing.get('amount') or 0) + alloc_amount
                if existing.get('rate') is not None and existing['rate'] != alloc_rate:
                    existing['has_multiple_rates'] = True
            else:
                committed_dict[costing_pk] = {
                    'qty': alloc_qty,
                    'rate': alloc_rate,
                    'amount': alloc_amount,
                    'has_multiple_rates': False,
                }

        return committed_dict

    # Non-construction: just amounts per item, but include snap
    # allocations too (B9).
    quote_totals = (
        Quote_allocations.objects
        .filter(quotes_pk__in=project_quotes)
        .values('item__costing_pk')
        .annotate(total=Sum('amount'))
    )
    result = {r['item__costing_pk']: float(r['total'] or 0) for r in quote_totals}
    for sa in snap_allocations:
        costing_pk = sa['snap_item__item_id']
        if not costing_pk:
            continue
        result[costing_pk] = result.get(costing_pk, 0.0) + float(sa['amount'] or 0)
    return result


def hc_invoiced_amounts(project_pk, claim):
    """Get invoiced amounts per item from bill allocations.

    Returns dict with:
    - invoiced: total invoiced amount across bill allocations that
      represent a real cost commitment for HC purposes. This applies the
      same progress-claim filter that ``core/formulas.py:Committed`` used
      historically:

          bill_type in (0, 1)  OR  (bill_type == 2 AND allocation_type == 1)

      Without this filter, progress-claim "wrap-up" allocation rows get
      double-counted alongside their direct-cost siblings, inflating the
      invoiced figure (audit A.M-C-12).
    - paid: subset of `invoiced` whose bill is in
      ``Bills.STATUSES_SETTLED_FOR_HC_CLAIM`` (currently
      {STATUS_APPROVED, STATUS_SENT_TO_XERO}). The audit (A.M-C-02) flagged
      that calling merely-approved-but-not-yet-sent bills "paid" suppresses
      claimable amounts; the constant is the single point of edit when
      that business decision lands. Document and test the chosen meaning.
    - in_claim: subset of `invoiced` for bills attached to this specific
      HC claim.
    """
    costing_pks = Costing.objects.filter(project_id=project_pk).values_list('costing_pk', flat=True)

    # Canonical "counts toward HC invoiced" filter, owned by
    # ``BillAllocationsQuerySet.counts_toward_hc_invoiced`` (audit
    # A.M-R-03). The previous incarnation hand-rolled the Q-clause in
    # several places; now there is one home for the rule.
    allocations = (
        Bill_allocations.objects
        .filter(item__in=costing_pks)
        .counts_toward_hc_invoiced()
        .select_related('bill')
    )

    settled_statuses = Bills.STATUSES_SETTLED_FOR_HC_CLAIM
    claim_pk = claim.hc_claim_pk if claim else None

    result = {}
    for alloc in allocations:
        item_pk = alloc.item_id
        amount = float(alloc.amount or 0)
        bill = alloc.bill

        bucket = result.setdefault(item_pk, {'invoiced': 0, 'paid': 0, 'in_claim': 0})
        bucket['invoiced'] += amount

        if bill.bill_status in settled_statuses:
            bucket['paid'] += amount

        if claim_pk is not None and bill.associated_hc_claim_id == claim_pk:
            bucket['in_claim'] += amount

    return result
