"""
Quotes service module.

Contains business logic for quotes operations that is 
PROJECT_TYPE-agnostic and reusable across all project types.
"""

from django.db.models import Sum
from django.conf import settings
from ..models import Quotes, Quote_allocations, Contacts


def get_quote_allocations_for_division(division):
    """
    Get all quote allocations for a division with item details.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of quote allocation dictionaries with item names
    """
    from django.forms.models import model_to_dict
    
    quote_allocations = Quote_allocations.objects.filter(
        item__category__division=division
    ).select_related('item').all()
    
    return [{**model_to_dict(ca), 'item_name': ca.item.item} for ca in quote_allocations]


def get_quote_allocations_sums():
    """
    Calculate sum of quote allocations grouped by item.
    
    Returns:
        QuerySet: Quote allocations with total_amount per item
    """
    return Quote_allocations.objects.values('item').annotate(total_amount=Sum('amount'))


def get_quote_allocations_sums_dict():
    """
    Get quote allocation sums as a dictionary mapping item_pk to total_amount.
    
    Returns:
        dict: {item_pk: total_amount}
    """
    sums = get_quote_allocations_sums()
    return {i['item']: i['total_amount'] for i in sums}


def get_committed_quotes_list(division):
    """
    Get list of committed quotes for a division with PDF URLs.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of quote dictionaries with media URLs
    """
    committed_quotes = Quotes.objects.filter(
        contact_pk__division=division
    ).values(
        'quotes_pk', 'supplier_quote_number', 'total_cost', 'pdf',
        'contact_pk', 'contact_pk__contact_name'
    )
    
    committed_quotes_list = list(committed_quotes)
    
    # Add media URL to PDF paths
    for q in committed_quotes_list:
        if settings.DEBUG:
            q['pdf'] = settings.MEDIA_URL + q['pdf']
        else:
            q['pdf'] = settings.MEDIA_URL + q['pdf']
    
    return committed_quotes_list


def get_contacts_in_quotes(division):
    """
    Get contacts that have quotes with their quote details.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of contact dictionaries with nested quotes
    """
    from django.db.models import Prefetch
    
    contact_pks_in_quotes = Quotes.objects.filter(
        contact_pk__division=division
    ).values_list('contact_pk', flat=True).distinct()
    
    # OPTIMIZED: Use prefetch_related to avoid N+1 on quotes_set
    contacts_in_quotes = Contacts.objects.filter(
        pk__in=contact_pks_in_quotes,
        division=division
    ).prefetch_related(
        Prefetch('quotes_set', queryset=Quotes.objects.only(
            'quotes_pk', 'supplier_quote_number', 'total_cost', 'pdf', 'contact_pk'
        ))
    )
    
    contacts_in_quotes_list = []
    for contact in contacts_in_quotes:
        d = contact.__dict__.copy()  # Use copy to avoid modifying cached object
        d.pop('_state', None)  # Remove Django internal state
        d['quotes'] = list(contact.quotes_set.all().values(
            'quotes_pk', 'supplier_quote_number', 'total_cost', 'pdf', 'contact_pk'
        ))
        contacts_in_quotes_list.append(d)
    
    return contacts_in_quotes_list


def get_contacts_not_in_quotes(division):
    """
    Get contacts that don't have any quotes.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of contact dictionaries
    """
    contact_pks_in_quotes = Quotes.objects.filter(
        contact_pk__division=division
    ).values_list('contact_pk', flat=True).distinct()
    
    contacts_not_in_quotes = Contacts.objects.exclude(
        pk__in=contact_pks_in_quotes,
        division=division
    ).values()
    
    return list(contacts_not_in_quotes)


def get_progress_claim_quote_allocations():
    """
    Build progress claim quote allocations data structure.
    
    Groups quotes by contact with their allocations.
    
    Returns:
        list: List of contact entries with quote allocations
    
    OPTIMIZED: Reduced from O(contacts * quotes * allocations) queries to 1 query
    """
    from django.db.models import Prefetch
    from collections import defaultdict
    
    # Single query with all related data prefetched
    quotes = Quotes.objects.select_related('contact_pk').prefetch_related(
        Prefetch(
            'quote_allocations',
            queryset=Quote_allocations.objects.select_related('item')
        )
    )
    
    # Group by contact in Python (much faster than N+1 queries)
    contacts_dict = defaultdict(list)
    for q in quotes:
        alloc_list = [
            {
                "item_pk": qa.item.pk,
                "item_name": qa.item.item,
                "amount": str(qa.amount)
            }
            for qa in q.quote_allocations.all()
        ]
        
        contacts_dict[q.contact_pk_id].append({
            "quote_number": q.quotes_pk,
            "allocations": alloc_list
        })
    
    # Convert to expected format
    return [
        {"contact_pk": cid, "quotes": quotes_list}
        for cid, quotes_list in contacts_dict.items()
    ]


def get_committed_items_for_costing(costing_pk):
    """
    Get committed quote items for a specific costing.
    
    Args:
        costing_pk: Primary key of the costing item
        
    Returns:
        tuple: (committed_items_list, total_committed_amount)
    """
    quote_allocations = Quote_allocations.objects.filter(
        item_id=costing_pk
    ).select_related('quotes_pk__contact_pk')
    
    if not quote_allocations.exists():
        return [], 0.0
    
    committed_items = [{
        "supplier": qa.quotes_pk.contact_pk.contact_name if qa.quotes_pk and qa.quotes_pk.contact_pk else 'Unknown',
        "supplier_original": qa.quotes_pk.contact_pk.contact_name if qa.quotes_pk and qa.quotes_pk.contact_pk else 'Unknown',
        "quote_num": qa.quotes_pk.supplier_quote_number if qa.quotes_pk else '-',
        "amount": float(qa.amount)
    } for qa in quote_allocations]
    
    total_committed = sum(item["amount"] for item in committed_items)
    
    return committed_items, total_committed
