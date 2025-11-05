"""
Unit tests for claims (HC claims & variations) service functions.

Tests the business logic in core/services/bills.py independently of views.
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from core.models import (
    HC_claims, HC_claim_allocations, Hc_variation, Hc_variation_allocations,
    Costing, Categories
)
from core.services import bills as claims_service


class ClaimsServiceTestCase(TestCase):
    """Base test case with common fixtures for claims service tests."""
    
    def setUp(self):
        """Set up test data for claims service tests."""
        # Create test division
        self.division = 1
        
        # Create test category
        self.category = Categories.objects.create(
            category='Test Category',
            division=self.division,
            order_in_list=1,
            invoice_category='Test Invoice Category'
        )
        
        # Create test costing items
        self.costing1 = Costing.objects.create(
            item='Test Item 1',
            category=self.category,
            contract_budget=Decimal('10000.00'),
            uncommitted=Decimal('10000.00'),
            fixed_on_site=Decimal('0.00')
        )
        
        self.costing2 = Costing.objects.create(
            item='Test Item 2',
            category=self.category,
            contract_budget=Decimal('5000.00'),
            uncommitted=Decimal('5000.00'),
            fixed_on_site=Decimal('0.00')
        )
        
        # Create HC claims
        self.hc_claim1 = HC_claims.objects.create(
            date=date.today() - timedelta(days=60),
            status=1,  # Approved
            display_id='HC-001'
        )
        
        self.hc_claim2 = HC_claims.objects.create(
            date=date.today() - timedelta(days=30),
            status=1,  # Approved
            display_id='HC-002'
        )
        
        self.hc_claim_current = HC_claims.objects.create(
            date=date.today(),
            status=0,  # Current/WIP
            display_id='HC-003'
        )
        
        # Create HC claim allocations
        self.hc_alloc1 = HC_claim_allocations.objects.create(
            hc_claim_pk=self.hc_claim1,
            item=self.costing1,
            hc_claimed=Decimal('2000.00'),
            qs_claimed=Decimal('1800.00'),
            sc_invoiced=Decimal('2000.00'),
            fixed_on_site=Decimal('2000.00'),
            adjustment=Decimal('0.00'),
            contract_budget=Decimal('10000.00'),
            category=self.category
        )
        
        self.hc_alloc2 = HC_claim_allocations.objects.create(
            hc_claim_pk=self.hc_claim2,
            item=self.costing1,
            hc_claimed=Decimal('1500.00'),
            qs_claimed=Decimal('1400.00'),
            sc_invoiced=Decimal('1500.00'),
            fixed_on_site=Decimal('3500.00'),
            adjustment=Decimal('0.00'),
            contract_budget=Decimal('10000.00'),
            category=self.category
        )
        
        # Create variations
        self.variation1 = Hc_variation.objects.create(
            date=date.today() - timedelta(days=45)
        )
        
        self.variation2 = Hc_variation.objects.create(
            date=date.today() - timedelta(days=15)
        )
        
        # Create variation allocations
        self.var_alloc1 = Hc_variation_allocations.objects.create(
            hc_variation=self.variation1,
            costing=self.costing1,
            amount=Decimal('500.00'),
            notes='Variation 1 note'
        )
        
        self.var_alloc2 = Hc_variation_allocations.objects.create(
            hc_variation=self.variation2,
            costing=self.costing2,
            amount=Decimal('300.00'),
            notes='Variation 2 note'
        )


class TestGetHcQsTotals(ClaimsServiceTestCase):
    """Test get_hc_qs_totals function."""
    
    def test_returns_dict_with_totals(self):
        """Should return dictionary mapping hc_claim_pk to totals."""
        result = claims_service.get_hc_qs_totals()
        
        self.assertIsInstance(result, dict)
        self.assertIn(self.hc_claim1.hc_claim_pk, result)
        self.assertEqual(result[self.hc_claim1.hc_claim_pk]['hc_total'], 2000.0)
        self.assertEqual(result[self.hc_claim1.hc_claim_pk]['qs_total'], 1800.0)
    
    def test_handles_multiple_claims(self):
        """Should aggregate totals for each claim separately."""
        result = claims_service.get_hc_qs_totals()
        
        self.assertEqual(len(result), 2)  # Only approved claims have allocations
        self.assertIn(self.hc_claim2.hc_claim_pk, result)


class TestGetHcClaimsList(ClaimsServiceTestCase):
    """Test get_hc_claims_list function."""
    
    def test_returns_two_lists(self):
        """Should return tuple of (hc_claims_list, approved_claims_list)."""
        sc_totals_dict = {}
        hc_claims_list, approved_claims_list = claims_service.get_hc_claims_list(sc_totals_dict)
        
        self.assertIsInstance(hc_claims_list, list)
        self.assertIsInstance(approved_claims_list, list)
    
    def test_includes_all_claims(self):
        """Should include all HC claims in main list."""
        sc_totals_dict = {}
        hc_claims_list, approved_claims_list = claims_service.get_hc_claims_list(sc_totals_dict)
        
        self.assertEqual(len(hc_claims_list), 3)
    
    def test_approved_list_excludes_wip(self):
        """Should only include approved claims (status > 0) in approved list."""
        sc_totals_dict = {}
        hc_claims_list, approved_claims_list = claims_service.get_hc_claims_list(sc_totals_dict)
        
        self.assertEqual(len(approved_claims_list), 2)
        
        # Check that WIP claim is not in approved list
        approved_ids = [claim['display_id'] for claim in approved_claims_list]
        self.assertNotIn('HC-003', approved_ids)
    
    def test_includes_sc_totals(self):
        """Should include SC totals from provided dictionary."""
        sc_totals_dict = {self.hc_claim1.hc_claim_pk: 2500.0}
        hc_claims_list, _ = claims_service.get_hc_claims_list(sc_totals_dict)
        
        claim1_data = next(c for c in hc_claims_list if c['hc_claim_pk'] == self.hc_claim1.hc_claim_pk)
        self.assertEqual(claim1_data['sc_total'], 2500.0)


class TestGetHcVariationsList(ClaimsServiceTestCase):
    """Test get_hc_variations_list function."""
    
    def test_returns_list_of_variations(self):
        """Should return list of variation dictionaries."""
        result = claims_service.get_hc_variations_list()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
    
    def test_includes_items_list(self):
        """Should include items list for each variation."""
        result = claims_service.get_hc_variations_list()
        
        variation = result[0]
        self.assertIn('items', variation)
        self.assertGreater(len(variation['items']), 0)
    
    def test_calculates_claimed_status(self):
        """Should calculate claimed status based on approved claim dates."""
        result = claims_service.get_hc_variations_list()
        
        # variation1 is before hc_claim2, so should be claimed (1)
        var1 = next(v for v in result if v['hc_variation_pk'] == self.variation1.hc_variation_pk)
        self.assertEqual(var1['claimed'], 1)


class TestGetCurrentHcClaim(ClaimsServiceTestCase):
    """Test get_current_hc_claim function."""
    
    def test_returns_current_claim(self):
        """Should return HC claim with status 0."""
        result = claims_service.get_current_hc_claim()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.status, 0)
        self.assertEqual(result.display_id, 'HC-003')
    
    def test_returns_none_when_no_current(self):
        """Should return None when no current claim exists."""
        HC_claims.objects.filter(status=0).delete()
        result = claims_service.get_current_hc_claim()
        
        self.assertIsNone(result)


class TestGetHcClaimWipAdjustments(ClaimsServiceTestCase):
    """Test get_hc_claim_wip_adjustments function."""
    
    def test_returns_adjustments_dict(self):
        """Should return dictionary of adjustments."""
        result = claims_service.get_hc_claim_wip_adjustments(self.hc_claim_current)
        
        self.assertIsInstance(result, dict)
    
    def test_returns_empty_when_no_claim(self):
        """Should return empty dict when no claim provided."""
        result = claims_service.get_hc_claim_wip_adjustments(None)
        
        self.assertEqual(result, {})


class TestCalculateHcPrevFixedonsite(ClaimsServiceTestCase):
    """Test calculate_hc_prev_fixedonsite function."""
    
    def test_returns_previous_value(self):
        """Should return fixed_on_site from previous claim."""
        result = claims_service.calculate_hc_prev_fixedonsite(
            self.costing1.costing_pk,
            self.hc_claim_current
        )
        
        # Should get value from hc_claim2 (most recent before current)
        self.assertEqual(result, Decimal('3500.00'))
    
    def test_returns_zero_when_no_previous(self):
        """Should return 0 when no previous claims exist."""
        result = claims_service.calculate_hc_prev_fixedonsite(
            self.costing2.costing_pk,
            self.hc_claim_current
        )
        
        self.assertEqual(result, 0)


class TestCalculateHcPrevClaimed(ClaimsServiceTestCase):
    """Test calculate_hc_prev_claimed function."""
    
    def test_sums_previous_claims(self):
        """Should sum hc_claimed from all previous claims."""
        result = claims_service.calculate_hc_prev_claimed(
            self.costing1.costing_pk,
            self.hc_claim_current
        )
        
        # Should sum from hc_claim1 (2000) and hc_claim2 (1500)
        self.assertEqual(result, Decimal('3500.00'))
    
    def test_returns_zero_when_no_previous(self):
        """Should return 0 when no previous claims exist."""
        result = claims_service.calculate_hc_prev_claimed(
            self.costing2.costing_pk,
            self.hc_claim_current
        )
        
        self.assertEqual(result, 0)


class TestCalculateQsClaimed(ClaimsServiceTestCase):
    """Test calculate_qs_claimed function."""
    
    def test_sums_previous_qs_claims(self):
        """Should sum qs_claimed from all previous claims."""
        result = claims_service.calculate_qs_claimed(
            self.costing1.costing_pk,
            self.hc_claim_current
        )
        
        # Should sum from hc_claim1 (1800) and hc_claim2 (1400)
        self.assertEqual(result, Decimal('3200.00'))


class TestGetClaimCategoryTotals(ClaimsServiceTestCase):
    """Test get_claim_category_totals function."""
    
    def test_returns_queryset(self):
        """Should return QuerySet of claim category totals."""
        result = claims_service.get_claim_category_totals(self.division)
        
        self.assertIsNotNone(result)
        self.assertGreater(result.count(), 0)
    
    def test_groups_by_claim_and_category(self):
        """Should group by hc_claim_pk and invoice_category."""
        result = claims_service.get_claim_category_totals(self.division)
        
        # Should have entries for claims with allocations
        claim_pks = [item['hc_claim_pk'] for item in result]
        self.assertIn(self.hc_claim1.hc_claim_pk, claim_pks)
