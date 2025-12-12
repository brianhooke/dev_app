"""
URL configuration for Construction app.

Contains HC claims, variations, and construction-specific endpoints.
"""

from django.urls import path
from .views import claims

app_name = 'construction'

urlpatterns = [
    # HC Claims endpoints
    path('associate_sc_claims_with_hc_claim/', claims.associate_sc_claims_with_hc_claim, name='associate_sc_claims_with_hc_claim'),
    path('update_hc_claim_data/', claims.update_hc_claim_data, name='update_hc_claim_data'),
    path('get_claim_table/<int:claim_id>/', claims.get_claim_table, name='get_claim_table'),
    path('send_hc_claim_to_xero/', claims.send_hc_claim_to_xero, name='send_hc_claim_to_xero'),
    path('update_fixedonsite/', claims.update_fixedonsite, name='update_fixedonsite'),
    
    # Variations endpoints
    path('create_variation/', claims.create_variation, name='create_variation'),
    path('delete_variation/', claims.delete_variation, name='delete_variation'),
    
    # Progress claims and direct costs
    path('post_progress_claim_data/', claims.post_progress_claim_data, name='post_progress_claim_data'),
    path('post_direct_cost_data/', claims.post_direct_cost_data, name='post_direct_cost_data'),
]
