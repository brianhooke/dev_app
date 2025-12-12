"""
Bills/Claims service module.

DEPRECATED: HC claims functionality has been moved to construction/services/claims.py.
This module re-exports functions for backward compatibility.

All code that imports from core.services.invoices will continue to work,
but new code should import directly from construction.services.claims.
"""

# Re-export all functions from construction.services.claims for backward compatibility
from construction.services.claims import (
    get_hc_qs_totals,
    get_hc_claims_list,
    get_hc_variations_list,
    get_hc_variation_allocations_list,
    get_current_hc_claim,
    get_hc_claim_wip_adjustments,
    calculate_hc_prev_fixedonsite,
    calculate_hc_prev_claimed,
    calculate_qs_claimed,
    get_claim_category_totals,
    get_hc_claims_data_for_costing,
)

# Export __all__ for explicit public API
__all__ = [
    'get_hc_qs_totals',
    'get_hc_claims_list',
    'get_hc_variations_list',
    'get_hc_variation_allocations_list',
    'get_current_hc_claim',
    'get_hc_claim_wip_adjustments',
    'calculate_hc_prev_fixedonsite',
    'calculate_hc_prev_claimed',
    'calculate_qs_claimed',
    'get_claim_category_totals',
    'get_hc_claims_data_for_costing',
]
