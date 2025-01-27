from django.db import models
from django.db.models import Sum
from .models import Quote_allocations, Invoice_allocations, Invoices, Costing

def Committed():
    quote_sum = Quote_allocations.objects.aggregate(total=Sum('amount'))['total'] or 0
    invoice_sum = Invoice_allocations.objects.filter(
        models.Q(allocation_type=1) | 
        (models.Q(allocation_type=0) & models.Q(invoice_pk__invoice_type=2))
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Combine both sums
    total_committed = quote_sum + invoice_sum

    # Group by Costing.costing_pk to return a list of tuples
    committed_by_costing = (
        Invoice_allocations.objects
        .filter(
            models.Q(allocation_type=1) | 
            (models.Q(allocation_type=0) & models.Q(invoice_pk__invoice_type=2))
        )
        .values('item')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )
    quote_by_costing = (
        Quote_allocations.objects
        .values('item')
        .annotate(amount=Sum('amount'))
        .values_list('item__costing_pk', 'amount')
    )
    
    # Combine both lists, summing amounts for matching costing_pks
    combined = {}
    for costing_pk, amount in committed_by_costing:
        combined[costing_pk] = combined.get(costing_pk, 0) + (amount or 0)  # Use 'or 0' to ensure we have a number
    for costing_pk, amount in quote_by_costing:
        combined[costing_pk] = combined.get(costing_pk, 0) + (amount or 0)  # Similarly here

    # Convert dict to list of tuples, but ensure all 'amount' values are explicitly set
    result = [(pk, amount if amount is not None else 0) for pk, amount in combined.items()]
    
    return result