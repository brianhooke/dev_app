from django.db import models
from django.db.models import Sum
from .models import Quote_allocations, Bill_allocations

def Committed():
    # Sum of all quote allocations
    quote_sum = Quote_allocations.objects.aggregate(total=Sum('amount'))['total'] or 0
    # Sum of invoice allocations that meet:
    # bill_type=1 OR (bill_type=2 AND allocation_type=1)
    invoice_sum = (
        Bill_allocations.objects
        .filter(
            models.Q(bill_pk__bill_type=1) |
            (models.Q(bill_pk__bill_type=2) & models.Q(allocation_type=1))
        )
        .aggregate(total=Sum('amount'))['total']
        or 0
    )
    total_committed = quote_sum + invoice_sum
    # Break down by Costing
    invoice_by_costing = (
        Bill_allocations.objects
        .filter(
            models.Q(bill_pk__bill_type=1) |
            (models.Q(bill_pk__bill_type=2) & models.Q(allocation_type=1))
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
