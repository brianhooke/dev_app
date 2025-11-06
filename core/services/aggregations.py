"""
Aggregations service module.

Contains business logic for dashboard aggregations and totals that operate
across multiple service domains.

No direct models - operates on aggregated data from other services.
"""


def calculate_dashboard_totals(costings):
    """
    Calculate all dashboard totals from costings.
    
    This is a convenience function that aggregates multiple totals
    for dashboard display.
    
    Args:
        costings: List of costing dictionaries with calculated fields
        
    Returns:
        dict: Dictionary with all dashboard totals
    """
    return {
        'total_contract_budget': sum(c.get('contract_budget', 0) for c in costings),
        'total_uncommitted': sum(c.get('uncommitted', 0) for c in costings),
        'total_committed': sum(c.get('committed', 0) for c in costings),
        'total_forecast_budget': sum(c.get('committed', 0) + c.get('uncommitted', 0) for c in costings),
        'total_sc_invoiced': sum(c.get('sc_invoiced', 0) for c in costings),
        'total_fixed_on_site': sum(c.get('fixed_on_site', 0) for c in costings),
        'total_sc_paid': sum(c.get('sc_paid', 0) for c in costings),
        'total_c2c': sum(c.get('c2c', 0) for c in costings),
    }
