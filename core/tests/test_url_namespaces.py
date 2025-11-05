"""
Unit tests for URL namespace configuration.

Tests that all URL namespaces are properly configured and resolve correctly.
"""

from django.test import TestCase
from django.urls import reverse, resolve, NoReverseMatch


class URLNamespaceTestCase(TestCase):
    """Test URL namespace configuration."""
    
    def test_core_namespace_exists(self):
        """Should be able to reverse core URLs."""
        try:
            url = reverse('core:homepage')
            self.assertEqual(url, '/')
        except NoReverseMatch:
            self.fail("core:homepage URL pattern not found")
    
    def test_core_build_url(self):
        """Should resolve core:build URL."""
        url = reverse('core:build')
        self.assertEqual(url, '/build/')
    
    def test_core_drawings_url(self):
        """Should resolve core:drawings URL."""
        url = reverse('core:drawings')
        self.assertEqual(url, '/drawings/')
    
    def test_core_commit_data_url(self):
        """Should resolve core:commit_data URL."""
        url = reverse('core:commit_data')
        self.assertEqual(url, '/commit_data/')
    
    def test_core_create_po_order_url(self):
        """Should resolve core:create_po_order URL."""
        url = reverse('core:create_po_order')
        self.assertEqual(url, '/create_po_order/')
    
    def test_core_upload_invoice_url(self):
        """Should resolve core:upload_invoice URL."""
        url = reverse('core:upload_invoice')
        self.assertEqual(url, '/upload_invoice/')
    
    def test_development_namespace_exists(self):
        """Development namespace should be configured."""
        # Currently no URLs in development app, but namespace should exist
        # This will pass as long as the namespace is registered
        from django.urls import get_resolver
        resolver = get_resolver()
        self.assertIn('development', resolver.namespace_dict)
    
    def test_construction_namespace_exists(self):
        """Construction namespace should be configured."""
        from django.urls import get_resolver
        resolver = get_resolver()
        self.assertIn('construction', resolver.namespace_dict)
    
    def test_precast_namespace_exists(self):
        """Precast namespace should be configured."""
        from django.urls import get_resolver
        resolver = get_resolver()
        self.assertIn('precast', resolver.namespace_dict)
    
    def test_pods_namespace_exists(self):
        """Pods namespace should be configured."""
        from django.urls import get_resolver
        resolver = get_resolver()
        self.assertIn('pods', resolver.namespace_dict)
    
    def test_general_namespace_exists(self):
        """General namespace should be configured."""
        from django.urls import get_resolver
        resolver = get_resolver()
        self.assertIn('general', resolver.namespace_dict)
    
    def test_url_resolution_with_parameters(self):
        """Should resolve URLs with parameters correctly."""
        url = reverse('core:generate_po_pdf', kwargs={'po_order_pk': 123})
        self.assertEqual(url, '/generate_po_pdf/123/')
    
    def test_url_resolution_with_multiple_parameters(self):
        """Should resolve URLs with multiple parameters."""
        url = reverse('core:get_design_pdf_url_with_rev', kwargs={
            'design_category': 1,
            'plan_number': 'A101',
            'rev_number': 'R1'
        })
        self.assertEqual(url, '/get_design_pdf_url/1/A101/R1/')


class URLResolutionTestCase(TestCase):
    """Test that URLs resolve to correct views."""
    
    def test_homepage_resolves_to_homepage_view(self):
        """Homepage URL should resolve to homepage_view."""
        resolver = resolve('/')
        self.assertEqual(resolver.view_name, 'core:homepage')
    
    def test_build_resolves_to_build_view(self):
        """Build URL should resolve to build_view."""
        resolver = resolve('/build/')
        self.assertEqual(resolver.view_name, 'core:build')
    
    def test_drawings_resolves_to_drawings_view(self):
        """Drawings URL should resolve to drawings_view."""
        resolver = resolve('/drawings/')
        self.assertEqual(resolver.view_name, 'core:drawings')
