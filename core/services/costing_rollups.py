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
"""
from decimal import Decimal
from collections import defaultdict
from typing import Dict, Iterable, Optional

from django.db.models import Sum, Q

from ..formulas import sum_decimals, to_decimal
from ..models import (
    Bills,
    Bill_allocations,
    Quote_allocations,
    Costing,
)


# ---------------------------------------------------------------------------
# Per-item rollups
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
# Per-project rollups
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
        qs = qs.filter(
            Q(bill__bill_type__in=[0, 1]) |
            (Q(bill__bill_type=2) & Q(allocation_type=1))
        )

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
