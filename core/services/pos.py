"""
Purchase Orders (POs) service module.

Contains business logic for purchase order operations that is 
PROJECT_TYPE-agnostic and reusable across all project types.
"""

from datetime import date
from ..models import Po_globals, Po_orders, Po_order_detail, Contacts, Costing, Quotes


def get_po_globals():
    """
    Get PO global settings.
    
    Returns:
        Po_globals: PO global settings object or None
    """
    return Po_globals.objects.first()


def get_po_orders_list(division):
    """
    Get list of PO orders for a division with supplier details.
    
    Args:
        division: Division ID (1 or 2)
        
    Returns:
        list: List of PO order dictionaries
    """
    po_orders = Po_orders.objects.filter(
        po_supplier__division=division
    ).select_related('po_supplier').all()
    
    po_orders_list = []
    for order in po_orders:
        po_orders_list.append({
            'po_order_pk': order.po_order_pk,
            'po_supplier': order.po_supplier_id,
            'supplier_name': order.po_supplier.contact_name,
            'supplier_email': order.po_supplier.contact_email,
            'po_note_1': order.po_note_1,
            'po_note_2': order.po_note_2,
            'po_note_3': order.po_note_3,
            'po_sent': order.po_sent
        })
    
    return po_orders_list


def create_po_order(supplier_pk, notes, rows):
    """
    Create a new PO order with details.
    
    Args:
        supplier_pk: Primary key of the supplier contact
        notes: Dictionary with note1, note2, note3
        rows: List of row dictionaries with itemPk, quoteId, amount, notes
        
    Returns:
        Po_orders: Created PO order object
    """
    # Get supplier
    supplier = Contacts.objects.get(pk=supplier_pk)
    
    # Extract notes
    note1 = notes.get('note1', '')
    note2 = notes.get('note2', '')
    note3 = notes.get('note3', '')
    
    # Create Po_orders entry
    po_order = Po_orders.objects.create(
        po_supplier=supplier,
        po_note_1=note1,
        po_note_2=note2,
        po_note_3=note3
    )
    
    # Create order details
    for row in rows:
        item_pk = row.get('itemPk')
        quote_id = row.get('quoteId')
        amount = row.get('amount')
        variation_note = row.get('notes', '')
        
        # Ensure quote is optional
        quote = Quotes.objects.get(pk=quote_id) if quote_id else None
        costing = Costing.objects.get(pk=item_pk)
        
        Po_order_detail.objects.create(
            po_order_pk=po_order,
            date=date.today(),
            costing=costing,
            quote=quote,
            amount=amount,
            variation_note=variation_note if variation_note else None
        )
    
    return po_order


def get_po_order_details(po_order_pk):
    """
    Get PO order with its details.
    
    Args:
        po_order_pk: Primary key of the PO order
        
    Returns:
        tuple: (po_order, po_order_details queryset)
    """
    po_order = Po_orders.objects.get(pk=po_order_pk)
    po_order_details = Po_order_detail.objects.filter(
        po_order_pk=po_order_pk
    ).select_related('costing', 'quote')
    
    return po_order, po_order_details


def mark_po_as_sent(po_order_pk):
    """
    Mark a PO order as sent.
    
    Args:
        po_order_pk: Primary key of the PO order
        
    Returns:
        Po_orders: Updated PO order object
    """
    po_order = Po_orders.objects.get(pk=po_order_pk)
    po_order.po_sent = True
    po_order.save()
    return po_order
