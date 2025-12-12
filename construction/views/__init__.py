"""
Construction views package.

This package contains view functions specific to the construction project type.
"""

from .claims import (
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
