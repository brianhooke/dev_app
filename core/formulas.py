"""Domain formulas / arithmetic helpers.

Anything that does GST math, AUD rounding, or "what counts as committed?"
should live here so the answer is the same in every view, every formula,
and every export. The ``Committed`` function below is preserved for now
because some legacy callers still import it; new code should prefer the
``BillAllocationsQuerySet.committed()`` manager method instead.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.db.models import Sum

from .models import Quote_allocations, Bill_allocations


# --- Money helpers ----------------------------------------------------------

GST_RATE = Decimal('0.10')  # Australian GST is 10% — change in one place.
TWO_PLACES = Decimal('0.01')


def to_decimal(value, default=Decimal('0')):
    """Coerce ``value`` to ``Decimal`` safely.

    Accepts ``None``, empty strings, ints, floats, Decimals, and numeric
    strings. Returns ``default`` for anything we can't parse. Floats are
    rounded by string conversion (avoids the binary float surprise).
    """
    if value is None or value == '':
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return default


def quantize_money(value):
    """Round to 2 dp using banker's-rounding-free HALF_UP (matches AUD)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def gst_from_net(net):
    """Return the GST component for a given net amount."""
    return quantize_money(to_decimal(net) * GST_RATE)


def gross_from_net(net):
    """Return net + gst, rounded to 2 dp."""
    net_d = to_decimal(net)
    return quantize_money(net_d + (net_d * GST_RATE))


def net_from_gross(gross):
    """Return the net component of a GST-inclusive figure."""
    return quantize_money(to_decimal(gross) / (Decimal('1') + GST_RATE))


def sum_decimals(values, default=Decimal('0')):
    """Decimal-safe sum that ignores ``None`` and empty strings."""
    total = default
    for v in values:
        total += to_decimal(v)
    return total


def Committed():
    # Sum of all quote allocations
    quote_sum = Quote_allocations.objects.aggregate(total=Sum('amount'))['total'] or 0
    # Sum of invoice allocations that meet:
    # bill_type in (0,1) OR (bill_type=2 AND allocation_type=1)
    invoice_sum = (
        Bill_allocations.objects
        .filter(
            models.Q(bill__bill_type__in=[0, 1]) |
            (models.Q(bill__bill_type=2) & models.Q(allocation_type=1))
        )
        .aggregate(total=Sum('amount'))['total']
        or 0
    )
    total_committed = quote_sum + invoice_sum
    # Break down by Costing
    invoice_by_costing = (
        Bill_allocations.objects
        .filter(
            models.Q(bill__bill_type__in=[0, 1]) |
            (models.Q(bill__bill_type=2) & models.Q(allocation_type=1))
        )
        .values('item__costing_pk')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )
    quote_by_costing = (
        Quote_allocations.objects
        .values('item__costing_pk')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )
    combined = {}
    # Merge invoice allocations
    for costing_pk, amount in invoice_by_costing:
        combined[costing_pk] = combined.get(costing_pk, 0) + (amount or 0)
    # Merge quote allocations
    for costing_pk, amount in quote_by_costing:
        combined[costing_pk] = combined.get(costing_pk, 0) + (amount or 0)
    # Convert dict to list of (costing_pk, amount)
    result = [(pk, amt) for pk, amt in combined.items()]

    return result
