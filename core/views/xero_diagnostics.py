"""
Xero OAuth diagnostics to help troubleshoot configuration issues.
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import XeroInstances


@csrf_exempt
def xero_oauth_diagnostics(request, instance_pk):
    """
    Show OAuth configuration details for troubleshooting.
    """
    try:
        xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
        
        # Build the redirect URI that will be sent to Xero
        redirect_uri = request.build_absolute_uri('/core/xero_oauth_callback/')
        
        # Get auth URL that would be generated
        from urllib.parse import urlencode
        params = {
            'response_type': 'code',
            'client_id': xero_instance.xero_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'offline_access accounting.contacts accounting.transactions',
            'state': 'diagnostic-test'
        }
        auth_url = f'https://login.xero.com/identity/connect/authorize?{urlencode(params)}'
        
        return JsonResponse({
            'status': 'success',
            'diagnostics': {
                'instance_name': xero_instance.xero_name,
                'client_id': xero_instance.xero_client_id,
                'client_id_length': len(xero_instance.xero_client_id),
                'redirect_uri': redirect_uri,
                'redirect_uri_length': len(redirect_uri),
                'has_client_secret': bool(xero_instance.xero_client_secret_encrypted),
                'scopes': 'offline_access accounting.contacts accounting.transactions',
                'expected_auth_url': auth_url
            },
            'instructions': {
                'step_1': 'Go to https://developer.xero.com/app/manage',
                'step_2': 'Select your Xero app',
                'step_3': 'Go to Configuration tab',
                'step_4': f'Verify OAuth 2.0 redirect URI matches EXACTLY: {redirect_uri}',
                'step_5': f'Verify Client Id matches EXACTLY: {xero_instance.xero_client_id}'
            }
        }, json_dumps_params={'indent': 2})
        
    except XeroInstances.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Xero instance not found'
        }, status=404)
