"""
Costings service module.

Contains business logic for costing operations that is PROJECT_TYPE-agnostic
and reusable across all project types.

Models used: Costing, Categories
"""

from django.db.models import Sum, Max
from django.forms.models import model_to_dict
from ..models import Costing, Categories


def get_costings_for_division(division):
    """
    Get all costings for a division with enriched category metadata.
    
    Args:
        division: Division ID
        
    Returns:
        list: List of costing dictionaries with category metadata
    """
    # OPTIMIZED: Added select_related to avoid N+1 queries on category
    costings = Costing.objects.filter(
        category__division=division
    ).select_related('category').order_by('category__order_in_list', 'category__category', 'item')
    
    costings_data = []
    for costing in costings:
        costing_dict = model_to_dict(costing)
        # Keep original category ID
        category_id = costing_dict['category']
        # Add category name and order_in_list
        cat_obj = costing.category
        costing_dict['category'] = cat_obj.category  # Keep the name for display
        costing_dict['category_id'] = category_id    # Keep the ID for relationships
        costing_dict['category_order_in_list'] = cat_obj.order_in_list  # Add this for quotes modal
        costings_data.append(costing_dict)
    
    return costings_data


def enrich_costings_with_committed(costings, committed_values):
    """
    Add committed values to costings.
    
    Args:
        costings: List of costing dictionaries
        committed_values: Dictionary mapping costing_pk to committed amount
        
    Returns:
        list: Costings with committed field added
    """
    for c in costings:
        c['committed'] = committed_values.get(c['costing_pk'], 0)
    return costings


def enrich_costings_with_bill_data(costings, invoice_allocations_sums_dict, paid_invoice_allocations_dict):
    """
    Add bill-related calculations to costings (sc_invoiced, sc_paid, c2c).
    
    Args:
        costings: List of costing dictionaries
        invoice_allocations_sums_dict: Dictionary mapping costing_pk to total invoice allocations
        paid_invoice_allocations_dict: Dictionary mapping costing_pk to paid invoice allocations
        
    Returns:
        list: Costings with sc_invoiced, sc_paid, and c2c fields added
    """
    for c in costings:
        # Get sc_invoiced from invoice allocations
        c['sc_invoiced'] = invoice_allocations_sums_dict.get(c['costing_pk'], 0)
        
        # Get paid amount from paid_invoice_allocations_dict (invoices with status 2 or 3)
        c['sc_paid'] = paid_invoice_allocations_dict.get(c['costing_pk'], 0)
        
        # Calculate C2C (Cost to Complete) as committed + uncommitted - sc_paid
        c['c2c'] = c['committed'] + c['uncommitted'] - c['sc_paid']
    
    return costings


def calculate_category_totals(costings, field='sc_invoiced'):
    """
    Calculate totals grouped by category.
    
    Args:
        costings: List of costing dictionaries
        field: Field name to sum (default: 'sc_invoiced')
        
    Returns:
        dict: Dictionary mapping category name to total
    """
    category_totals = {}
    for c in costings:
        cat = c['category']
        if cat not in category_totals:
            category_totals[cat] = 0
        category_totals[cat] += c.get(field, 0)
    
    return category_totals


def calculate_costing_totals(costings):
    """
    Calculate aggregate totals across all costings.
    
    Args:
        costings: List of costing dictionaries
        
    Returns:
        dict: Dictionary with total_contract_budget, total_uncommitted, total_committed,
              total_forecast_budget, total_sc_invoiced, total_fixed_on_site, 
              total_sc_paid, total_c2c
    """
    return {
        'total_contract_budget': sum(c['contract_budget'] for c in costings),
        'total_uncommitted': sum(c['uncommitted'] for c in costings),
        'total_committed': sum(c['committed'] for c in costings),
        'total_forecast_budget': sum(c['committed'] + c['uncommitted'] for c in costings),
        'total_sc_invoiced': sum(c['sc_invoiced'] for c in costings),
        'total_fixed_on_site': sum(c['fixed_on_site'] for c in costings),
        'total_sc_paid': sum(c['sc_paid'] for c in costings),
        'total_c2c': sum(c['c2c'] for c in costings),
    }


def get_items_list(costings):
    """
    Extract simplified items list from costings.
    
    Args:
        costings: List of costing dictionaries
        
    Returns:
        list: List of item dictionaries with item, uncommitted, committed, order_in_list
    """
    return [
        {
            'item': c['item'],
            'uncommitted': c['uncommitted'],
            'committed': c['committed'],
            'order_in_list': c['category_order_in_list']
        }
        for c in costings
    ]


def get_contract_budget_totals(division):
    """
    Generate contract budget totals grouped by invoice_category.
    
    Args:
        division: Division ID
        
    Returns:
        QuerySet: Contract budget totals grouped by invoice_category
    """
    return (Costing.objects.filter(category__division=division)
        .values('category__invoice_category')
        .annotate(
            total_contract_budget=Sum('contract_budget'),
            max_order=Max('category__order_in_list'),
            latest_category=Max('category__category')
        ).order_by('max_order'))
