"""
Unit tests for invoice service functions.

Tests the business logic in core/services/invoices.py independently of views.
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from core.models import (
    Invoices, Invoice_allocations, Contacts, Costing, Categories,
    HC_claims, HC_claim_allocations, Quotes, Quote_allocations
)
from core.services import invoices as invoice_service


class InvoiceServiceTestCase(TestCase):
    """Base test case with common fixtures for invoice service tests."""
    
    def setUp(self):
        """Set up test data for invoice service tests."""
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
        
        # Create test contact
        self.contact = Contacts.objects.create(
            contact_name='Test Supplier',
            division=self.division,
            checked=True
        )
        
        # Create test invoices
        self.invoice1 = Invoices.objects.create(
            contact_pk=self.contact,
            invoice_division=self.division,
            invoice_status=0,  # Unallocated
            total_net=Decimal('1000.00'),
            total_gst=Decimal('100.00'),
            supplier_invoice_number='INV-001',
            invoice_date=date.today(),
            invoice_due_date=date.today() + timedelta(days=30),
            invoice_type=1  # Direct cost
        )
        
        self.invoice2 = Invoices.objects.create(
            contact_pk=self.contact,
            invoice_division=self.division,
            invoice_status=2,  # Paid
            total_net=Decimal('2000.00'),
            total_gst=Decimal('200.00'),
            supplier_invoice_number='INV-002',
            invoice_date=date.today(),
            invoice_due_date=date.today() + timedelta(days=30),
            invoice_type=2  # Progress claim
        )
        
        self.invoice3 = Invoices.objects.create(
            contact_pk=self.contact,
            invoice_division=self.division,
            invoice_status=1,  # Allocated
            total_net=Decimal('1500.00'),
            total_gst=Decimal('150.00'),
            supplier_invoice_number='INV-003',
            invoice_date=date.today(),
            invoice_due_date=date.today() + timedelta(days=30),
            invoice_type=1
        )
        
        # Create invoice allocations
        self.allocation1 = Invoice_allocations.objects.create(
            invoice_pk=self.invoice2,
            item=self.costing1,
            amount=Decimal('1500.00'),
            allocation_type=0
        )
        
        self.allocation2 = Invoice_allocations.objects.create(
            invoice_pk=self.invoice2,
            item=self.costing2,
            amount=Decimal('500.00'),
            allocation_type=0
        )
        
        self.allocation3 = Invoice_allocations.objects.create(
            invoice_pk=self.invoice3,
            item=self.costing1,
            amount=Decimal('1000.00'),
            allocation_type=1
        )


class TestGetInvoiceAllocationsSums(InvoiceServiceTestCase):
    """Test get_invoice_allocations_sums_dict function."""
    
    def test_returns_dict_with_item_totals(self):
        """Should return dictionary mapping item_pk to total allocation amount."""
        result = invoice_service.get_invoice_allocations_sums_dict()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result[self.costing1.costing_pk], Decimal('2500.00'))
        self.assertEqual(result[self.costing2.costing_pk], Decimal('500.00'))
    
    def test_empty_when_no_allocations(self):
        """Should return empty dict when no allocations exist."""
        Invoice_allocations.objects.all().delete()
        result = invoice_service.get_invoice_allocations_sums_dict()
        
        self.assertEqual(result, {})


class TestGetPaidInvoiceAllocations(InvoiceServiceTestCase):
    """Test get_paid_invoice_allocations_dict function."""
    
    def test_returns_only_paid_invoices(self):
        """Should return allocations only for invoices with status 2 or 3."""
        result = invoice_service.get_paid_invoice_allocations_dict()
        
        # Only invoice2 has status 2 (paid)
        self.assertEqual(result[self.costing1.costing_pk], Decimal('1500.00'))
        self.assertEqual(result[self.costing2.costing_pk], Decimal('500.00'))
    
    def test_excludes_unallocated_and_allocated_invoices(self):
        """Should not include invoices with status 0 or 1."""
        result = invoice_service.get_paid_invoice_allocations_dict()
        
        # allocation3 is on invoice3 (status 1), should not be included
        # Total for costing1 should be 1500 (from invoice2), not 2500
        self.assertEqual(result[self.costing1.costing_pk], Decimal('1500.00'))


class TestCalculateScInvoicedForCosting(InvoiceServiceTestCase):
    """Test calculate_sc_invoiced_for_costing function."""
    
    def test_returns_value_from_invoice_allocations(self):
        """Should return value from invoice_allocations_sums_dict."""
        sums_dict = invoice_service.get_invoice_allocations_sums_dict()
        result = invoice_service.calculate_sc_invoiced_for_costing(
            self.costing1.costing_pk,
            sums_dict
        )
        
        self.assertEqual(result, Decimal('2500.00'))
    
    def test_fallback_to_hc_claim_allocations(self):
        """Should fallback to HC_claim_allocations when invoice sum is 0."""
        # Create HC claim and allocation
        hc_claim = HC_claims.objects.create(
            date=date.today(),
            status=0,
            display_id='HC-001'
        )
        
        HC_claim_allocations.objects.create(
            hc_claim_pk=hc_claim,
            item=self.costing2,
            sc_invoiced=Decimal('750.00'),
            hc_claimed=Decimal('0.00'),
            qs_claimed=Decimal('0.00'),
            fixed_on_site=Decimal('0.00'),
            adjustment=Decimal('0.00'),
            contract_budget=Decimal('5000.00'),
            category=self.category
        )
        
        # Delete invoice allocations for costing2
        Invoice_allocations.objects.filter(item=self.costing2).delete()
        
        sums_dict = invoice_service.get_invoice_allocations_sums_dict()
        result = invoice_service.calculate_sc_invoiced_for_costing(
            self.costing2.costing_pk,
            sums_dict
        )
        
        self.assertEqual(result, Decimal('750.00'))
    
    def test_returns_zero_when_no_data(self):
        """Should return 0 when no invoice or HC allocations exist."""
        Invoice_allocations.objects.filter(item=self.costing2).delete()
        
        sums_dict = invoice_service.get_invoice_allocations_sums_dict()
        result = invoice_service.calculate_sc_invoiced_for_costing(
            self.costing2.costing_pk,
            sums_dict
        )
        
        self.assertEqual(result, 0)


class TestGetInvoicesList(InvoiceServiceTestCase):
    """Test get_invoices_list function."""
    
    def test_returns_list_of_invoice_dicts(self):
        """Should return list of invoice dictionaries for division."""
        result = invoice_service.get_invoices_list(self.division)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
    
    def test_includes_required_fields(self):
        """Should include all required invoice fields."""
        result = invoice_service.get_invoices_list(self.division)
        invoice_dict = result[0]
        
        required_fields = [
            'invoice_pk', 'invoice_status', 'contact_name', 'total_net',
            'total_gst', 'supplier_invoice_number', 'pdf_url',
            'associated_hc_claim', 'display_id', 'invoice_date', 'invoice_due_date'
        ]
        
        for field in required_fields:
            self.assertIn(field, invoice_dict)
    
    def test_filters_by_division(self):
        """Should only return invoices for specified division."""
        # Create invoice in different division
        other_contact = Contacts.objects.create(
            contact_name='Other Supplier',
            division=2,
            checked=True
        )
        Invoices.objects.create(
            contact_pk=other_contact,
            invoice_division=2,
            invoice_status=0,
            total_net=Decimal('999.00'),
            total_gst=Decimal('99.90'),
            supplier_invoice_number='INV-999',
            invoice_date=date.today(),
            invoice_due_date=date.today() + timedelta(days=30),
            invoice_type=1
        )
        
        result = invoice_service.get_invoices_list(self.division)
        
        # Should still only have 3 invoices for division 1
        self.assertEqual(len(result), 3)


class TestGetUnallocatedInvoices(InvoiceServiceTestCase):
    """Test get_unallocated_invoices function."""
    
    def test_returns_only_unallocated_invoices(self):
        """Should return only invoices with status 0."""
        result = invoice_service.get_unallocated_invoices(self.division)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['invoice_pk'], self.invoice1.invoice_pk)
        self.assertEqual(result[0]['invoice_status'], 0)
    
    def test_includes_possible_progress_claim_flag(self):
        """Should include possible_progress_claim flag based on quotes."""
        # Create quote for contact
        quote = Quotes.objects.create(
            contact_pk=self.contact,
            supplier_quote_number='Q-001',
            total_cost=Decimal('5000.00')
        )
        
        result = invoice_service.get_unallocated_invoices(self.division)
        
        self.assertEqual(result[0]['possible_progress_claim'], 1)
    
    def test_progress_claim_flag_zero_without_quotes(self):
        """Should set possible_progress_claim to 0 when no quotes exist."""
        result = invoice_service.get_unallocated_invoices(self.division)
        
        self.assertEqual(result[0]['possible_progress_claim'], 0)


class TestGetAllocatedInvoices(InvoiceServiceTestCase):
    """Test get_allocated_invoices function."""
    
    def test_returns_only_allocated_invoices(self):
        """Should return only invoices with status != 0."""
        result = invoice_service.get_allocated_invoices(self.division)
        
        self.assertEqual(len(result), 2)
        statuses = [inv['invoice_status'] for inv in result]
        self.assertNotIn(0, statuses)
    
    def test_includes_invoice_type(self):
        """Should include invoice_type field."""
        result = invoice_service.get_allocated_invoices(self.division)
        
        for invoice_dict in result:
            self.assertIn('invoice_type', invoice_dict)


class TestGetInvoiceTotalsByHcClaim(InvoiceServiceTestCase):
    """Test get_invoice_totals_by_hc_claim function."""
    
    def test_returns_dict_of_sc_totals(self):
        """Should return dictionary mapping hc_claim_pk to sc_total."""
        # Create HC claim and associate invoice
        hc_claim = HC_claims.objects.create(
            date=date.today(),
            status=1,
            display_id='HC-001'
        )
        
        self.invoice2.associated_hc_claim = hc_claim
        self.invoice2.save()
        
        result = invoice_service.get_invoice_totals_by_hc_claim()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result[hc_claim.hc_claim_pk], 2000.0)
    
    def test_excludes_invoices_without_hc_claim(self):
        """Should only include invoices with associated HC claims."""
        result = invoice_service.get_invoice_totals_by_hc_claim()
        
        # No invoices have HC claims yet
        self.assertEqual(result, {})


class TestGetProgressClaimInvoiceAllocations(InvoiceServiceTestCase):
    """Test get_progress_claim_invoice_allocations function."""
    
    def test_returns_list_grouped_by_contact(self):
        """Should return list of contact entries with invoice allocations."""
        result = invoice_service.get_progress_claim_invoice_allocations()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)  # One contact
        self.assertEqual(result[0]['contact_pk'], self.contact.pk)
    
    def test_includes_invoice_allocations(self):
        """Should include allocations for each invoice."""
        result = invoice_service.get_progress_claim_invoice_allocations()
        
        contact_entry = result[0]
        self.assertIn('invoices', contact_entry)
        self.assertEqual(len(contact_entry['invoices']), 2)  # 2 allocated invoices
    
    def test_includes_allocation_type_string(self):
        """Should include invoice_allocation_type as string."""
        result = invoice_service.get_progress_claim_invoice_allocations()
        
        invoice_entry = result[0]['invoices'][0]
        allocation = invoice_entry['allocations'][0]
        
        self.assertIn('invoice_allocation_type', allocation)
        self.assertIn(allocation['invoice_allocation_type'], ['progress_claim', 'direct_cost'])
    
    def test_excludes_unallocated_invoices(self):
        """Should not include invoices with status 0."""
        result = invoice_service.get_progress_claim_invoice_allocations()
        
        # Should have 2 invoices (invoice2 and invoice3), not invoice1
        contact_entry = result[0]
        invoice_numbers = [inv['invoice_number'] for inv in contact_entry['invoices']]
        self.assertNotIn(self.invoice1.invoice_pk, invoice_numbers)


class TestCalculateHcClaimInvoices(InvoiceServiceTestCase):
    """Test calculate_hc_claim_invoices function."""
    
    def test_calculates_current_and_previous_amounts(self):
        """Should return tuple of (hc_this_claim_invoices, hc_prev_invoiced)."""
        # Create HC claims
        hc_claim1 = HC_claims.objects.create(
            date=date.today() - timedelta(days=30),
            status=1,
            display_id='HC-001'
        )
        
        hc_claim2 = HC_claims.objects.create(
            date=date.today(),
            status=0,
            display_id='HC-002'
        )
        
        # Associate invoices with claims
        self.invoice2.associated_hc_claim = hc_claim1
        self.invoice2.save()
        
        self.invoice3.associated_hc_claim = hc_claim2
        self.invoice3.save()
        
        hc_this, hc_prev = invoice_service.calculate_hc_claim_invoices(
            self.costing1.costing_pk,
            hc_claim2
        )
        
        self.assertEqual(hc_this, Decimal('1000.00'))  # From invoice3
        self.assertEqual(hc_prev, Decimal('1500.00'))  # From invoice2
    
    def test_returns_zeros_when_no_allocations(self):
        """Should return (0, 0) when no allocations exist for item."""
        hc_claim = HC_claims.objects.create(
            date=date.today(),
            status=0,
            display_id='HC-001'
        )
        
        # Create new costing with no allocations
        costing_new = Costing.objects.create(
            item='New Item',
            category=self.category,
            contract_budget=Decimal('1000.00'),
            uncommitted=Decimal('1000.00'),
            fixed_on_site=Decimal('0.00')
        )
        
        hc_this, hc_prev = invoice_service.calculate_hc_claim_invoices(
            costing_new.costing_pk,
            hc_claim
        )
        
        self.assertEqual(hc_this, 0)
        self.assertEqual(hc_prev, 0)
