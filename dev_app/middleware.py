"""
Custom middleware for the dev_app project.
"""

from django.http import HttpResponsePermanentRedirect, HttpResponse
from django.core.exceptions import DisallowedHost


class CanonicalHostRedirectMiddleware:
    """
    Middleware to redirect requests from non-canonical hostnames.
    
    Redirects:
    - mason.build -> https://www.mason.build (company landing page)
    - www.app.mason.build -> https://app.mason.build
    
    This ensures the app only responds on app.mason.build and redirects
    apex domain requests to the actual company website.
    
    Also handles ELB health checks that use internal IPs as HTTP_HOST.
    """
    
    # Where to redirect mason.build requests (your company landing page)
    LANDING_PAGE_URL = 'https://www.mason.build'
    
    # The canonical hostname for this app
    CANONICAL_HOST = 'app.mason.build'
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is an ELB health check (uses internal IPs)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if 'ELB-HealthChecker' in user_agent:
            # Return OK for health checks without checking host
            return HttpResponse('OK', content_type='text/plain')
        
        try:
            host = request.get_host().split(':')[0].lower()  # Remove port if present
        except DisallowedHost:
            # For requests with disallowed hosts, just pass through
            # Django will handle the error appropriately
            return self.get_response(request)
        
        # Redirect mason.build (apex) to the landing page
        if host == 'mason.build' or host == 'www.mason.build':
            # Preserve the path in case someone bookmarked a deep link
            # But redirect to landing page root since paths won't match
            return HttpResponsePermanentRedirect(self.LANDING_PAGE_URL)
        
        # Redirect www.app.mason.build to app.mason.build (canonical)
        if host == 'www.app.mason.build':
            new_url = f'https://{self.CANONICAL_HOST}{request.get_full_path()}'
            return HttpResponsePermanentRedirect(new_url)
        
        return self.get_response(request)
