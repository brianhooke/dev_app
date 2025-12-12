"""
Claims-related views.

DEPRECATED: This module has been moved to construction/views/claims.py.
This file re-exports all functions for backward compatibility.

All code that imports from core.views.claims will continue to work,
but new code should import directly from construction.views.claims.
"""

# Re-export all functions from construction.views.claims for backward compatibility
from construction.views.claims import (
    associate_sc_claims_with_hc_claim,
    update_fixedonsite,
    update_hc_claim_data,
    get_claim_table,
    send_hc_claim_to_xero,
    delete_variation,
    create_variation,
    post_progress_claim_data,
    post_direct_cost_data,
)

# Export __all__ for explicit public API
__all__ = [
    'associate_sc_claims_with_hc_claim',
    'update_fixedonsite',
    'update_hc_claim_data',
    'get_claim_table',
    'send_hc_claim_to_xero',
    'delete_variation',
    'create_variation',
    'post_progress_claim_data',
    'post_direct_cost_data',
]