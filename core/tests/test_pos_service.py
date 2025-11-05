"""
Unit tests for POS (Purchase Orders) service functions.

Tests the business logic in core/services/pos.py independently of views.
"""

from django.test import TestCase
from decimal import Decimal
from datetime import date
from core.models import (
    Po_globals, Po_orders, Po_order_detail, Contacts, Costing, 
    Categories, Quotes
)
from core.services import pos as pos_service


class POSServiceTestCase(TestCase):
    """Base test case with common fixtures for POS service tests."""
    
    def setUp(self):
        """Set up test data for POS service tests."""
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
            contact_email='supplier1@test.com',
            division=self.division,
            checked=True
        )
        
        self.contact2 = Contacts.objects.create(
            contact_name='Test Supplier 2',
            contact_email='supplier2@test.com',
            division=self.division,
            checked=True
        )
        
        # Create test quotes
        self.quote1 = Quotes.objects.create(
            contact_pk=self.contact1,
            supplier_quote_number='Q-001',
            total_cost=Decimal('3000.00')
        )
        
        # Create PO globals
        self.po_globals = Po_globals.objects.create(
            reference='PO-REF-001',
            invoicee='Test Company',
            ABN='12345678901',
            email='po@testcompany.com',
            address='123 Test St, Test City'
        )
        
        # Create test PO orders
        self.po_order1 = Po_orders.objects.create(
            po_supplier=self.contact1,
            po_note_1='Note 1',
            po_note_2='Note 2',
            po_note_3='Note 3',
            po_sent=False
        )
        
        self.po_order2 = Po_orders.objects.create(
            po_supplier=self.contact2,
            po_note_1='Order 2 Note',
            po_note_2='',
            po_note_3='',
            po_sent=True
        )
        
        # Create PO order details
        self.po_detail1 = Po_order_detail.objects.create(
            po_order_pk=self.po_order1,
            date=date.today(),
            costing=self.costing1,
            quote=self.quote1,
            amount=Decimal('2000.00'),
            variation_note='Test variation note'
        )
        
        self.po_detail2 = Po_order_detail.objects.create(
            po_order_pk=self.po_order1,
            date=date.today(),
            costing=self.costing2,
            quote=None,
            amount=Decimal('1000.00'),
            variation_note=None
        )


class TestGetPoGlobals(POSServiceTestCase):
    """Test get_po_globals function."""
    
    def test_returns_po_globals_object(self):
        """Should return PO globals object."""
        result = pos_service.get_po_globals()
        
        self.assertIsNotNone(result)
        self.assertEqual(result.reference, 'PO-REF-001')
        self.assertEqual(result.invoicee, 'Test Company')
    
    def test_returns_none_when_no_globals(self):
        """Should return None when no PO globals exist."""
        Po_globals.objects.all().delete()
        result = pos_service.get_po_globals()
        
        self.assertIsNone(result)


class TestGetPoOrdersList(POSServiceTestCase):
    """Test get_po_orders_list function."""
    
    def test_returns_list_of_po_orders(self):
        """Should return list of PO order dictionaries for division."""
        result = pos_service.get_po_orders_list(self.division)
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
    
    def test_includes_required_fields(self):
        """Should include all required PO order fields."""
        result = pos_service.get_po_orders_list(self.division)
        po_dict = result[0]
        
        required_fields = [
            'po_order_pk', 'po_supplier', 'supplier_name', 'supplier_email',
            'po_note_1', 'po_note_2', 'po_note_3', 'po_sent'
        ]
        
        for field in required_fields:
            self.assertIn(field, po_dict)
    
    def test_filters_by_division(self):
        """Should only return PO orders for specified division."""
        # Create contact and PO in different division
        other_contact = Contacts.objects.create(
            contact_name='Other Supplier',
            contact_email='other@test.com',
            division=2,
            checked=True
        )
        
        Po_orders.objects.create(
            po_supplier=other_contact,
            po_note_1='Other division order',
            po_note_2='',
            po_note_3='',
            po_sent=False
        )
        
        result = pos_service.get_po_orders_list(self.division)
        
        # Should still only have 2 orders for division 1
        self.assertEqual(len(result), 2)
    
    def test_includes_supplier_details(self):
        """Should include supplier name and email."""
        result = pos_service.get_po_orders_list(self.division)
        
        po_dict = result[0]
        self.assertEqual(po_dict['supplier_name'], 'Test Supplier 1')
        self.assertEqual(po_dict['supplier_email'], 'supplier1@test.com')


class TestCreatePoOrder(POSServiceTestCase):
    """Test create_po_order function."""
    
    def test_creates_po_order_successfully(self):
        """Should create PO order with details."""
        notes = {
            'note1': 'New order note 1',
            'note2': 'New order note 2',
            'note3': 'New order note 3'
        }
        
        rows = [
            {
                'itemPk': self.costing1.costing_pk,
                'quoteId': self.quote1.quotes_pk,
                'amount': '1500.00',
                'notes': 'Row note 1'
            },
            {
                'itemPk': self.costing2.costing_pk,
                'quoteId': None,
                'amount': '800.00',
                'notes': ''
            }
        ]
        
        po_order = pos_service.create_po_order(self.contact1.pk, notes, rows)
        
        self.assertIsNotNone(po_order)
        self.assertEqual(po_order.po_supplier, self.contact1)
        self.assertEqual(po_order.po_note_1, 'New order note 1')
        self.assertEqual(po_order.po_note_2, 'New order note 2')
        self.assertEqual(po_order.po_note_3, 'New order note 3')
    
    def test_creates_order_details(self):
        """Should create order details for each row."""
        notes = {'note1': 'Test', 'note2': '', 'note3': ''}
        rows = [
            {
                'itemPk': self.costing1.costing_pk,
                'quoteId': self.quote1.quotes_pk,
                'amount': '1500.00',
                'notes': 'Detail note'
            }
        ]
        
        po_order = pos_service.create_po_order(self.contact1.pk, notes, rows)
        
        details = Po_order_detail.objects.filter(po_order_pk=po_order)
        self.assertEqual(details.count(), 1)
        
        detail = details.first()
        self.assertEqual(detail.costing, self.costing1)
        self.assertEqual(detail.quote, self.quote1)
        self.assertEqual(detail.amount, Decimal('1500.00'))
        self.assertEqual(detail.variation_note, 'Detail note')
    
    def test_handles_optional_quote(self):
        """Should handle rows without quote IDs."""
        notes = {'note1': 'Test', 'note2': '', 'note3': ''}
        rows = [
            {
                'itemPk': self.costing1.costing_pk,
                'quoteId': None,
                'amount': '1000.00',
                'notes': ''
            }
        ]
        
        po_order = pos_service.create_po_order(self.contact1.pk, notes, rows)
        
        detail = Po_order_detail.objects.filter(po_order_pk=po_order).first()
        self.assertIsNone(detail.quote)
    
    def test_handles_empty_notes(self):
        """Should handle empty notes gracefully."""
        notes = {}
        rows = [
            {
                'itemPk': self.costing1.costing_pk,
                'quoteId': None,
                'amount': '1000.00',
                'notes': ''
            }
        ]
        
        po_order = pos_service.create_po_order(self.contact1.pk, notes, rows)
        
        self.assertEqual(po_order.po_note_1, '')
        self.assertEqual(po_order.po_note_2, '')
        self.assertEqual(po_order.po_note_3, '')


class TestGetPoOrderDetails(POSServiceTestCase):
    """Test get_po_order_details function."""
    
    def test_returns_order_and_details(self):
        """Should return tuple of (po_order, po_order_details)."""
        po_order, po_order_details = pos_service.get_po_order_details(
            self.po_order1.po_order_pk
        )
        
        self.assertEqual(po_order, self.po_order1)
        self.assertEqual(po_order_details.count(), 2)
    
    def test_details_include_related_objects(self):
        """Should include related costing and quote objects."""
        po_order, po_order_details = pos_service.get_po_order_details(
            self.po_order1.po_order_pk
        )
        
        detail = po_order_details.first()
        self.assertIsNotNone(detail.costing)
        self.assertEqual(detail.costing.item, 'Test Item 1')
    
    def test_handles_order_without_details(self):
        """Should handle PO orders with no details."""
        # Create order without details
        empty_order = Po_orders.objects.create(
            po_supplier=self.contact1,
            po_note_1='Empty order',
            po_note_2='',
            po_note_3='',
            po_sent=False
        )
        
        po_order, po_order_details = pos_service.get_po_order_details(
            empty_order.po_order_pk
        )
        
        self.assertEqual(po_order, empty_order)
        self.assertEqual(po_order_details.count(), 0)


class TestMarkPoAsSent(POSServiceTestCase):
    """Test mark_po_as_sent function."""
    
    def test_marks_order_as_sent(self):
        """Should update po_sent to True."""
        self.assertFalse(self.po_order1.po_sent)
        
        updated_order = pos_service.mark_po_as_sent(self.po_order1.po_order_pk)
        
        self.assertTrue(updated_order.po_sent)
        
        # Verify in database
        refreshed_order = Po_orders.objects.get(pk=self.po_order1.po_order_pk)
        self.assertTrue(refreshed_order.po_sent)
    
    def test_returns_updated_order(self):
        """Should return the updated PO order object."""
        updated_order = pos_service.mark_po_as_sent(self.po_order1.po_order_pk)
        
        self.assertIsInstance(updated_order, Po_orders)
        self.assertEqual(updated_order.po_order_pk, self.po_order1.po_order_pk)
    
    def test_idempotent_operation(self):
        """Should handle marking already-sent orders."""
        # Mark as sent twice
        pos_service.mark_po_as_sent(self.po_order1.po_order_pk)
        updated_order = pos_service.mark_po_as_sent(self.po_order1.po_order_pk)
        
        self.assertTrue(updated_order.po_sent)
