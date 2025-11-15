"""
Diagnostic endpoint to check API configuration
"""
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def api_diagnostics(request):
    """Show API configuration for debugging"""
    # Get the configured API key (first 10 chars only for security)
    api_key = getattr(settings, 'EMAIL_API_SECRET_KEY', 'NOT_SET')
    api_key_preview = api_key[:15] + "..." if len(api_key) > 15 else api_key
    
    # Get the key from request header
    request_key = request.headers.get('X-API-Secret', 'NOT_PROVIDED')
    request_key_preview = request_key[:15] + "..." if len(request_key) > 15 else request_key
    
    return JsonResponse({
        'configured_key_preview': api_key_preview,
        'configured_key_length': len(api_key),
        'request_key_preview': request_key_preview,
        'request_key_length': len(request_key),
        'keys_match': api_key == request_key,
        'environment_test': settings.DEBUG
    })
