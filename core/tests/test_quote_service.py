"""
Unit tests for quote service functions.

Tests the business logic in core/services/quotes.py independently of views.
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date
from core.models import (
    Quotes, Quote_allocations, Contacts, Costing, Categories
)
from core.services import quotes as quote_service


class QuoteServiceTestCase(TestCase):
    """Base test case with common fixtures for quote service tests."""
    
    def setUp(self):
        """Set up test data for quote service tests."""
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
        
        # Create test contacts
        self.contact1 = Contacts.objects.create(
            contact_name='Test Supplier 1',
            division=self.division,
            checked=True
        )
        
        self.contact2 = Contacts.objects.create(
            contact_name='Test Supplier 2',
            division=self.division,
            checked=True
        )
        
        self.contact_no_quotes = Contacts.objects.create(
            contact_name='Supplier Without Quotes',
            division=self.division,
            checked=True
        )
        
        # Create test quotes
        self.quote1 = Quotes.objects.create(
            contact_pk=self.contact1,
            supplier_quote_number='Q-001',
            total_cost=Decimal('3000.00')
        )
        
        self.quote2 = Quotes.objects.create(
            contact_pk=self.contact1,
            supplier_quote_number='Q-002',
            total_cost=Decimal('2000.00')
        )
        
        self.quote3 = Quotes.objects.create(
            contact_pk=self.contact2,
            supplier_quote_number='Q-003',
            total_cost=Decimal('1500.00')
        )
        
        # Create quote allocations
        self.allocation1 = Quote_allocations.objects.create(
            quotes_pk=self.quote1,
            item=self.costing1,
            amount=Decimal('2000.00'),
            notes='First allocation'
        )
        
        self.allocation2 = Quote_allocations.objects.create(
            quotes_pk=self.quote1,
            item=self.costing2,
            amount=Decimal('1000.00'),
            notes='Second allocation'
        )
        
        self.allocation3 = Quote_allocations.objects.create(
            quotes_pk=self.quote2,
            item=self.costing1,
            amount=Decimal('1500.00'),
            notes='Third allocation'
        )
        
        self.allocation4 = Quote_allocations.objects.create(
            quotes_pk=self.quote3,
            item=self.costing2,
            amount=Decimal('1500.00'),
            notes='Fourth allocation'
        )


class TestGetQuoteAllocationsForDivision(QuoteServiceTestCase):
    """Test get_quote_allocations_for_division function."""
    
    def test_returns_list_with_item_names(self):
        """Should return list of quote allocations with item names."""
        result = quote_service.get_quote_allocations_for_division(self.division)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)
        
        # Check that item_name is included
        for alloc in result:
            self.assertIn('item_name', alloc)
    
    def test_filters_by_division(self):
        """Should only return allocations for specified division."""
        # Create category and costing in different division
        other_category = Categories.objects.create(
            category='Other Category',
            division=2,
            order_in_list=1,
            invoice_category='Other Invoice Category'
        )
        
        other_costing = Costing.objects.create(
            item='Other Item',
            category=other_category,
            contract_budget=Decimal('1000.00'),
            uncommitted=Decimal('1000.00'),
            fixed_on_site=Decimal('0.00')
        )
        
        other_contact = Contacts.objects.create(
            contact_name='Other Supplier',
            division=2,
            checked=True
        )
        
        other_quote = Quotes.objects.create(
            contact_pk=other_contact,
            supplier_quote_number='Q-999',
            total_cost=Decimal('1000.00')
        )
        
        Quote_allocations.objects.create(
            quotes_pk=other_quote,
            item=other_costing,
            amount=Decimal('1000.00')
        )
        
        result = quote_service.get_quote_allocations_for_division(self.division)
        
        # Should still only have 4 allocations for division 1
        self.assertEqual(len(result), 4)


class TestGetQuoteAllocationsSums(QuoteServiceTestCase):
    """Test get_quote_allocations_sums_dict function."""
    
    def test_returns_dict_with_item_totals(self):
        """Should return dictionary mapping item_pk to total allocation amount."""
        result = quote_service.get_quote_allocations_sums_dict()
        
        self.assertIsInstance(result, dict)
        # costing1 has allocations of 2000 + 1500 = 3500
        self.assertEqual(result[self.costing1.costing_pk], Decimal('3500.00'))
        # costing2 has allocations of 1000 + 1500 = 2500
        self.assertEqual(result[self.costing2.costing_pk], Decimal('2500.00'))
    
    def test_empty_when_no_allocations(self):
        """Should return empty dict when no allocations exist."""
        Quote_allocations.objects.all().delete()
        result = quote_service.get_quote_allocations_sums_dict()
        
        self.assertEqual(result, {})


class TestGetCommittedQuotesList(QuoteServiceTestCase):
    """Test get_committed_quotes_list function."""
    
    def test_returns_list_of_quote_dicts(self):
        """Should return list of quote dictionaries for division."""
        result = quote_service.get_committed_quotes_list(self.division)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
    
    def test_includes_required_fields(self):
        """Should include all required quote fields."""
        result = quote_service.get_committed_quotes_list(self.division)
        quote_dict = result[0]
        
        required_fields = [
            'quotes_pk', 'supplier_quote_number', 'total_cost', 'pdf',
            'contact_pk', 'contact_pk__contact_name'
        ]
        
        for field in required_fields:
            self.assertIn(field, quote_dict)
    
    def test_filters_by_division(self):
        """Should only return quotes for specified division."""
        # Create quote in different division
        other_contact = Contacts.objects.create(
            contact_name='Other Supplier',
            division=2,
            checked=True
        )
        
        Quotes.objects.create(
            contact_pk=other_contact,
            supplier_quote_number='Q-999',
            total_cost=Decimal('999.00')
        )
        
        result = quote_service.get_committed_quotes_list(self.division)
        
        # Should still only have 3 quotes for division 1
        self.assertEqual(len(result), 3)


class TestGetContactsInQuotes(QuoteServiceTestCase):
    """Test get_contacts_in_quotes function."""
    
    def test_returns_contacts_with_quotes(self):
        """Should return only contacts that have quotes."""
        result = quote_service.get_contacts_in_quotes(self.division)
        
        self.assertEqual(len(result), 2)  # contact1 and contact2
        
        # Check that contact_no_quotes is not included
        contact_names = [c['contact_name'] for c in result]
        self.assertNotIn('Supplier Without Quotes', contact_names)
    
    def test_includes_nested_quotes(self):
        """Should include nested quotes for each contact."""
        result = quote_service.get_contacts_in_quotes(self.division)
        
        # Find contact1 in results
        contact1_data = next(c for c in result if c['contact_name'] == 'Test Supplier 1')
        
        self.assertIn('quotes', contact1_data)
        self.assertEqual(len(contact1_data['quotes']), 2)  # quote1 and quote2


class TestGetContactsNotInQuotes(QuoteServiceTestCase):
    """Test get_contacts_not_in_quotes function."""
    
    def test_returns_contacts_without_quotes(self):
        """Should return only contacts that don't have quotes."""
        result = quote_service.get_contacts_not_in_quotes(self.division)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['contact_name'], 'Supplier Without Quotes')
    
    def test_excludes_contacts_with_quotes(self):
        """Should not include contacts that have quotes."""
        result = quote_service.get_contacts_not_in_quotes(self.division)
        
        contact_names = [c['contact_name'] for c in result]
        self.assertNotIn('Test Supplier 1', contact_names)
        self.assertNotIn('Test Supplier 2', contact_names)


class TestGetProgressClaimQuoteAllocations(QuoteServiceTestCase):
    """Test get_progress_claim_quote_allocations function."""
    
    def test_returns_list_grouped_by_contact(self):
        """Should return list of contact entries with quote allocations."""
        result = quote_service.get_progress_claim_quote_allocations()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)  # Two contacts with quotes
    
    def test_includes_quote_allocations(self):
        """Should include allocations for each quote."""
        result = quote_service.get_progress_claim_quote_allocations()
        
        # Find contact1 entry
        contact1_entry = next(c for c in result if c['contact_pk'] == self.contact1.pk)
        
        self.assertIn('quotes', contact1_entry)
        self.assertEqual(len(contact1_entry['quotes']), 2)  # quote1 and quote2
        
        # Check first quote has allocations
        quote1_entry = contact1_entry['quotes'][0]
        self.assertIn('allocations', quote1_entry)
        self.assertGreater(len(quote1_entry['allocations']), 0)
    
    def test_allocation_structure(self):
        """Should have correct structure for allocations."""
        result = quote_service.get_progress_claim_quote_allocations()
        
        contact_entry = result[0]
        quote_entry = contact_entry['quotes'][0]
        allocation = quote_entry['allocations'][0]
        
        required_fields = ['item_pk', 'item_name', 'amount']
        for field in required_fields:
            self.assertIn(field, allocation)
        
        # Amount should be string
        self.assertIsInstance(allocation['amount'], str)


class TestGetCommittedItemsForCosting(QuoteServiceTestCase):
    """Test get_committed_items_for_costing function."""
    
    def test_returns_tuple_of_items_and_total(self):
        """Should return tuple of (committed_items_list, total_committed_amount)."""
        committed_items, total_committed = quote_service.get_committed_items_for_costing(
            self.costing1.costing_pk
        )
        
        self.assertIsInstance(committed_items, list)
        self.assertIsInstance(total_committed, float)
    
    def test_calculates_correct_total(self):
        """Should calculate correct total from all allocations."""
        committed_items, total_committed = quote_service.get_committed_items_for_costing(
            self.costing1.costing_pk
        )
        
        # costing1 has allocations of 2000 + 1500 = 3500
        self.assertEqual(total_committed, 3500.0)
        self.assertEqual(len(committed_items), 2)
    
    def test_includes_supplier_and_quote_info(self):
        """Should include supplier name and quote number for each item."""
        committed_items, _ = quote_service.get_committed_items_for_costing(
            self.costing1.costing_pk
        )
        
        item = committed_items[0]
        required_fields = ['supplier', 'supplier_original', 'quote_num', 'amount']
        
        for field in required_fields:
            self.assertIn(field, item)
    
    def test_returns_empty_for_no_allocations(self):
        """Should return empty list and 0.0 when no allocations exist."""
        # Create new costing with no allocations
        costing_new = Costing.objects.create(
            item='New Item',
            category=self.category,
            contract_budget=Decimal('1000.00'),
            uncommitted=Decimal('1000.00'),
            fixed_on_site=Decimal('0.00')
        )
        
        committed_items, total_committed = quote_service.get_committed_items_for_costing(
            costing_new.costing_pk
        )
        
        self.assertEqual(committed_items, [])
        self.assertEqual(total_committed, 0.0)
    
    def test_handles_missing_contact_gracefully(self):
        """Should handle quotes without contacts gracefully."""
        # Create quote without proper contact
        orphan_quote = Quotes.objects.create(
            contact_pk=self.contact1,
            supplier_quote_number='Q-ORPHAN',
            total_cost=Decimal('500.00')
        )
        
        Quote_allocations.objects.create(
            quotes_pk=orphan_quote,
            item=self.costing2,
            amount=Decimal('500.00')
        )
        
        # Delete the contact to simulate orphaned quote
        orphan_quote.contact_pk = None
        orphan_quote.save()
        
        committed_items, total_committed = quote_service.get_committed_items_for_costing(
            self.costing2.costing_pk
        )
        
        # Should still work, with 'Unknown' as supplier
        self.assertGreater(len(committed_items), 0)
        unknown_items = [item for item in committed_items if item['supplier'] == 'Unknown']
        self.assertGreater(len(unknown_items), 0)
