"""
Xero OAuth2 authorization flow implementation.
"""

from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import XeroInstances
import requests
import secrets
import logging
import base64
from urllib.parse import urlencode
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def xero_oauth_authorize(request, instance_pk):
    """
    Initiate OAuth2 authorization flow for a Xero instance.
    Redirects user to Xero authorization page.
    """
    try:
        xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in session (works across workers and restarts)
        request.session[f'xero_oauth_state_{state}'] = {
            'instance_pk': instance_pk,
            'timestamp': timezone.now().isoformat()
        }
        request.session.modified = True
        
        # Build authorization URL - dynamically detect domain
        redirect_uri = request.build_absolute_uri('/core/xero_oauth_callback/')
        
        params = {
            'response_type': 'code',
            'client_id': xero_instance.xero_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'offline_access accounting.contacts accounting.transactions accounting.settings accounting.settings.read',
            'state': state
        }
        
        auth_url = f'https://login.xero.com/identity/connect/authorize?{urlencode(params)}'
        
        logger.info(f"Redirecting to Xero OAuth for instance {instance_pk}")
        logger.info(f"Redirect URI being sent: {redirect_uri}")
        logger.info(f"Full auth URL: {auth_url}")
        return redirect(auth_url)
        
    except XeroInstances.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Xero instance not found'
        }, status=404)


@csrf_exempt
def xero_oauth_callback(request):
    """
    Handle OAuth2 callback from Xero.
    Exchange authorization code for access and refresh tokens.
    """
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        logger.error(f"OAuth error: {error}")
        return JsonResponse({
            'status': 'error',
            'message': f'Authorization failed: {error}'
        }, status=400)
    
    if not code or not state:
        return JsonResponse({
            'status': 'error',
            'message': 'Missing code or state parameter'
        }, status=400)
    
    # Verify state token from session
    session_key = f'xero_oauth_state_{state}'
    if session_key not in request.session:
        logger.error(f"State token not found in session: {state}")
        logger.error(f"Available session keys: {list(request.session.keys())}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid state token'
        }, status=400)
    
    state_data = request.session.pop(session_key)
    request.session.modified = True
    instance_pk = state_data['instance_pk']
    
    try:
        xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
        
        # Exchange code for tokens - dynamically detect domain
        redirect_uri = request.build_absolute_uri('/core/xero_oauth_callback/')
        
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        # Prepare Basic Auth header
        client_secret = xero_instance.get_client_secret()
        credentials = f"{xero_instance.xero_client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(
            'https://identity.xero.com/connect/token',
            data=token_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Token exchange failed: {response.status_code}'
            }, status=400)
        
        token_response = response.json()
        
        # Get tenant/connection info
        access_token = token_response['access_token']
        connections_response = requests.get(
            'https://api.xero.com/connections',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if connections_response.status_code == 200:
            connections = connections_response.json()
            if connections:
                # Sort by createdDateUtc to get the most recently authorized connection
                # This ensures we get the organization the user just selected
                sorted_connections = sorted(connections, key=lambda x: x.get('createdDateUtc', ''), reverse=True)
                tenant_id = sorted_connections[0].get('tenantId')
                tenant_name = sorted_connections[0].get('tenantName', 'Unknown')
                
                logger.info(f"Storing tenant_id: {tenant_id} ({tenant_name}) for instance {instance_pk}")
                logger.info(f"All connections: {[(c.get('tenantName'), c.get('tenantId')) for c in connections]}")
                
                xero_instance.set_oauth_tenant_id(tenant_id)
        
        # Store tokens (uses SSM when available, DB fallback otherwise)
        xero_instance.set_oauth_access_token(token_response['access_token'])
        xero_instance.set_oauth_refresh_token(token_response['refresh_token'])
        
        # Calculate and store expiry time
        expires_in = token_response.get('expires_in', 1800)  # Default 30 minutes
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        xero_instance.set_oauth_token_expires_at(expires_at)
        
        xero_instance.save()
        
        logger.info(f"OAuth tokens stored for instance {instance_pk}")
        
        # Redirect back to dashboard with success message
        return redirect('/?oauth_success=true')
        
    except XeroInstances.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Xero instance not found'
        }, status=404)
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        }, status=500)


def get_oauth_token(xero_instance):
    """
    Get valid OAuth access token, refreshing if necessary.
    Returns (success, token_or_error_message)
    """
    try:
        # Check if we have OAuth tokens
        access_token = xero_instance.get_oauth_access_token()
        refresh_token = xero_instance.get_oauth_refresh_token()
        
        if not access_token or not refresh_token:
            return False, "No OAuth tokens found. Please authorize the app first."
        
        # Check if token is expired (use getter for SSM support)
        token_expires_at = xero_instance.get_oauth_token_expires_at()
        if token_expires_at and timezone.now() >= token_expires_at:
            # Refresh the token
            logger.info(f"Refreshing OAuth token for instance {xero_instance.xero_instance_pk}")
            
            client_secret = xero_instance.get_client_secret()
            credentials = f"{xero_instance.xero_client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
            
            response = requests.post(
                'https://identity.xero.com/connect/token',
                data=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                return False, f"Token refresh failed: {response.status_code}"
            
            token_response = response.json()
            
            # Update tokens (uses SSM when available)
            xero_instance.set_oauth_access_token(token_response['access_token'])
            xero_instance.set_oauth_refresh_token(token_response['refresh_token'])
            
            expires_in = token_response.get('expires_in', 1800)
            expires_at = timezone.now() + timedelta(seconds=expires_in)
            xero_instance.set_oauth_token_expires_at(expires_at)
            
            xero_instance.save()
            
            access_token = token_response['access_token']
        
        return True, access_token
        
    except Exception as e:
        logger.error(f"Error getting OAuth token: {str(e)}", exc_info=True)
        return False, str(e)
