"""
Invoices service module.

Contains business logic for invoices operations that is 
PROJECT_TYPE-agnostic and reusable across all project types.
"""

from django.db.models import Sum, F
from ..models import Invoices, Invoice_allocations, HC_claim_allocations, Quotes

def get_invoice_allocations_sums():
    """
    Calculate sum of invoice allocations grouped by item.

    Returns:
        QuerySet: Invoice allocations with total_amount per item
    """
    return Invoice_allocations.objects.values('item').annotate(total_amount=Sum('amount'))

def get_invoice_allocations_sums_dict():
    """
    Get invoice allocation sums as a dictionary mapping item_pk to total_amount.

    Returns:
        dict: {item_pk: total_amount}
    """
    sums = get_invoice_allocations_sums()
    return {i['item']: i['total_amount'] for i in sums}

def get_paid_invoice_allocations():
    """
    Calculate sum of invoice allocations for paid/sent invoices (status 2 or 3).

    Returns:
        QuerySet: Paid invoice allocations with total_amount per item
    """
    return Invoice_allocations.objects.filter(
        invoice_pk__invoice_status__in=[2, 3]
    ).values('item').annotate(total_amount=Sum('amount'))

def get_paid_invoice_allocations_dict():
    """
    Get paid invoice allocation sums as a dictionary.

    Returns:
        dict: {item_pk: total_amount}
    """
    paid = get_paid_invoice_allocations()
    return {i['item']: i['total_amount'] for i in paid}

def calculate_sc_invoiced_for_costing(costing_pk, invoice_sums_dict):
    """
    Calculate sc_invoiced value for a costing item.

    Uses Invoice_allocations as primary source, with HC_claim_allocations as fallback.

    Args:
        costing_pk: Primary key of the costing item
        invoice_sums_dict: Dictionary of invoice allocation sums

    Returns:
        Decimal: The sc_invoiced amount
    """
    sc_invoiced = invoice_sums_dict.get(costing_pk, 0)

    # Fallback to HC_claim_allocations if sc_invoiced is 0
    if sc_invoiced == 0:
        hc_alloc = HC_claim_allocations.objects.filter(item=costing_pk).first()
        if hc_alloc and hc_alloc.sc_invoiced:
            sc_invoiced = hc_alloc.sc_invoiced

    return sc_invoiced


def get_invoices_list(division):
    """
    Get all invoices for a division with related data.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of invoice dictionaries
    """
    invoices = Invoices.objects.filter(
        invoice_division=division
    ).select_related('contact_pk', 'associated_hc_claim').order_by(
        F('associated_hc_claim__pk').desc(nulls_first=True)
    ).all()
    
    result = []
    for i in invoices:
        pdf_url = i.pdf.url if i.pdf else None
        logger.info(f"Invoice {i.invoice_pk} PDF URL: {pdf_url}")
        logger.info(f"  Storage class: {i.pdf.storage.__class__.__name__ if i.pdf else 'N/A'}")
        result.append({
            'invoice_pk': i.invoice_pk,
            'invoice_status': i.invoice_status,
            'contact_name': i.contact_pk.contact_name,
            'total_net': i.total_net,
            'total_gst': i.total_gst,
            'supplier_invoice_number': i.supplier_invoice_number,
            'pdf_url': pdf_url,
            'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,
            'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,
            'invoice_date': i.invoice_date,
            'invoice_due_date': i.invoice_due_date
        })
    return result


def get_unallocated_invoices(division):
    """
    Get unallocated invoices (status 0) for a division.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of unallocated invoice dictionaries with possible_progress_claim flag
    """
    invoices_unallocated = Invoices.objects.filter(
        invoice_status=0,
        invoice_division=division
    ).select_related('contact_pk', 'associated_hc_claim')
    
    quotes_contact_pks = set(Quotes.objects.values_list('contact_pk', flat=True))
    
    result = []
    for i in invoices_unallocated:
        pdf_url = i.pdf.url if i.pdf else None
        logger.info(f"Unallocated Invoice {i.invoice_pk} PDF URL: {pdf_url}")
        logger.info(f"  Storage class: {i.pdf.storage.__class__.__name__ if i.pdf else 'N/A'}")
        result.append({
            'invoice_pk': i.invoice_pk,
            'contact_pk': i.contact_pk.pk,
            'invoice_status': i.invoice_status,
            'contact_name': i.contact_pk.contact_name,
            'total_net': i.total_net,
            'total_gst': i.total_gst,
            'supplier_invoice_number': i.supplier_invoice_number,
            'pdf_url': pdf_url,
            'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,
            'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,
            'invoice_date': i.invoice_date,
            'invoice_due_date': i.invoice_due_date,
            'possible_progress_claim': 1 if i.contact_pk.pk in quotes_contact_pks else 0
        })
    
    return result


def get_allocated_invoices(division):
    """
    Get allocated invoices (status != 0) for a division.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of allocated invoice dictionaries
    """
    invoices_allocated = Invoices.objects.exclude(
        invoice_status=0
    ).filter(
        invoice_division=division
    ).select_related('contact_pk', 'associated_hc_claim')
    
    result = []
    for i in invoices_allocated:
        pdf_url = i.pdf.url if i.pdf else None
        logger.info(f"Allocated Invoice {i.invoice_pk} PDF URL: {pdf_url}")
        logger.info(f"  Storage class: {i.pdf.storage.__class__.__name__ if i.pdf else 'N/A'}")
        result.append({
            'invoice_pk': i.invoice_pk,
            'invoice_status': i.invoice_status,
            'contact_name': i.contact_pk.contact_name,
            'total_net': i.total_net,
            'total_gst': i.total_gst,
            'supplier_invoice_number': i.supplier_invoice_number,
            'pdf_url': pdf_url,
            'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,
            'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,
            'invoice_date': i.invoice_date,
            'invoice_due_date': i.invoice_due_date,
            'invoice_type': i.invoice_type
        })
    return result


def get_invoice_totals_by_hc_claim():
    """
    Calculate invoice totals (SC totals) grouped by HC claim.
    
    Returns:
        dict: {hc_claim_pk: sc_total}
    """
    sc_totals = Invoices.objects.filter(
        associated_hc_claim__isnull=False
    ).values('associated_hc_claim').annotate(
        sc_total=Sum('total_net')
    )
    return {item['associated_hc_claim']: float(item['sc_total'] or 0) for item in sc_totals}


def get_progress_claim_invoice_allocations():
    """
    Build progress claim invoice allocations data structure.
    
    Groups invoices by contact with their allocations and allocation types.
    
    Returns:
        list: List of contact entries with invoice allocations
    """
    distinct_contacts_invoices = Invoices.objects.exclude(
        invoice_status=0
    ).values_list("contact_pk", flat=True).distinct()
    
    progress_claim_invoice_allocations = []
    
    for cid in distinct_contacts_invoices:
        invs_for_c = Invoices.objects.filter(
            contact_pk=cid
        ).exclude(invoice_status=0).order_by("invoice_date")
        
        c_entry = {"contact_pk": cid, "invoices": []}
        
        for inv in invs_for_c:
            i_allocs = Invoice_allocations.objects.filter(invoice_pk=inv)
            alloc_list = []
            
            for ia in i_allocs:
                allocation_type_str = "progress_claim" if inv.invoice_type == 2 and ia.allocation_type == 0 else "direct_cost"
                alloc_list.append({
                    "item_pk": ia.item.pk,
                    "item_name": ia.item.item,
                    "amount": str(ia.amount),
                    "invoice_allocation_type": allocation_type_str
                })
            
            c_entry["invoices"].append({
                "invoice_number": inv.invoice_pk,
                "allocations": alloc_list
            })
        
        progress_claim_invoice_allocations.append(c_entry)
    
    return progress_claim_invoice_allocations


def calculate_hc_claim_invoices(costing_pk, current_hc_claim):
    """
    Calculate HC claim invoice amounts for a costing item.
    
    Args:
        costing_pk: Primary key of the costing item
        current_hc_claim: Current HC claim object
        
    Returns:
        tuple: (hc_this_claim_invoices, hc_prev_invoiced)
    """
    hc_this_claim_invoices = 0
    hc_prev_invoiced = 0
    
    allocs = Invoice_allocations.objects.filter(item=costing_pk)
    
    for al in allocs:
        inv = Invoices.objects.get(invoice_pk=al.invoice_pk.pk)
        if inv.associated_hc_claim and inv.associated_hc_claim.pk == current_hc_claim.pk:
            hc_this_claim_invoices += al.amount
        elif inv.associated_hc_claim and inv.associated_hc_claim.pk < current_hc_claim.pk:
            hc_prev_invoiced += al.amount
    
    return hc_this_claim_invoices, hc_prev_invoiced
