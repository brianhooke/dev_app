"""
Xero management views.

Xero Table Configuration:
- get_xero_config() - Returns column definitions for allocations_layout.html

Helper Functions (exported to contacts.py):
1. get_xero_auth - Centralized OAuth authentication + tenant ID retrieval
2. build_xero_headers - Build standard Xero API request headers
3. format_bank_details - Combines BSB + account number for Xero format
4. parse_xero_validation_errors - Extracts validation errors from Xero API responses
5. @handle_xero_request_errors - Decorator handling timeout/connection/generic errors

Xero Instance Management:
6. get_xero_instances - Fetch all Xero instances (PK, name, client ID)
7. create_xero_instance - Create new Xero instance with encrypted credentials
8. delete_xero_instance - Delete a Xero instance by PK
9. test_xero_connection - Test Xero API connection via Contacts endpoint

Note: Contact-related functions (pull_xero_contacts, get_contacts_by_instance, 
create_contact, update_contact_details, update_contact_status) have been moved 
to contacts.py but still use the helper functions from this module.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import XeroInstances, Contacts
import json
import base64
import requests
import logging
import secrets
from urllib.parse import urlencode
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_xero_config():
    """
    Get the configuration for the Xero instances section.
    Returns a dict with all context variables needed for allocations_layout.html.
    """
    return {
        'section_id': 'xero',
        'main_table_columns': [
            {'header': 'Xero Instance', 'width': '37%', 'sortable': True},
            {'header': 'Test', 'width': '9%', 'class': 'col-action-first'},
            {'header': 'Authorise', 'width': '9%', 'class': 'col-action'},
            {'header': 'Pull Contacts', 'width': '9%', 'class': 'col-action'},
            {'header': 'Pull Accounts', 'width': '9%', 'class': 'col-action'},
            {'header': 'Edit', 'width': '9%', 'class': 'col-action'},
            {'header': 'Delete', 'width': '9%', 'class': 'col-action'},
        ],
        'hide_viewer': True,
        'hide_allocations': True,
    }


def get_xero_auth(instance_pk):
    """
    Helper function to get Xero authentication credentials.
    Returns (xero_instance, access_token, tenant_id) or (None, error_response, None).
    
    Usage:
        xero_instance, result, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return result  # This is the error JsonResponse
    """
    try:
        xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
    except XeroInstances.DoesNotExist:
        return None, JsonResponse({
            'status': 'error',
            'message': 'Xero instance not found'
        }, status=404), None
    
    # Get OAuth token
    from .xero_oauth import get_oauth_token
    success, token_or_error = get_oauth_token(xero_instance)
    
    if not success:
        logger.error(f"OAuth token failed for instance {instance_pk}: {token_or_error}")
        return None, JsonResponse({
            'status': 'error',
            'message': f'OAuth authentication failed: {token_or_error}',
            'needs_auth': True
        }, status=401), None
    
    access_token = token_or_error
    tenant_id = xero_instance.oauth_tenant_id
    
    if not tenant_id:
        return None, JsonResponse({
            'status': 'error',
            'message': 'No tenant ID found. Please re-authorize this Xero instance.',
            'needs_auth': True
        }, status=401), None
    
    return xero_instance, access_token, tenant_id


def build_xero_headers(access_token, tenant_id, include_content_type=True):
    """
    Build standard Xero API request headers.
    
    Args:
        access_token: OAuth2 access token
        tenant_id: Xero tenant ID
        include_content_type: If True, includes 'Content-Type: application/json' (for POST/PUT)
                             If False, omits it (for GET requests)
    
    Returns:
        Dictionary of headers ready for requests
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Xero-tenant-id': tenant_id
    }
    if include_content_type:
        headers['Content-Type'] = 'application/json'
    return headers


def format_bank_details(bsb, account_number):
    """
    Combine BSB and account number for Xero BankAccountDetails field.
    Returns empty string if either field is missing.
    """
    if bsb and account_number:
        return bsb.replace('-', '') + account_number
    return ''


def parse_xero_validation_errors(response):
    """
    Extract validation error messages from Xero API error response.
    Returns formatted error message or None.
    """
    try:
        error_data = response.json()
        if 'Elements' in error_data and len(error_data['Elements']) > 0:
            element = error_data['Elements'][0]
            if 'ValidationErrors' in element and len(element['ValidationErrors']) > 0:
                validation_errors = [err['Message'] for err in element['ValidationErrors']]
                return 'Xero validation error: ' + '; '.join(validation_errors)
    except (ValueError, KeyError, TypeError, IndexError):
        pass
    return None


def handle_xero_request_errors(func):
    """
    Decorator to handle common Xero API request exceptions.
    Wraps timeout, connection, and generic errors with appropriate JSON responses.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.Timeout:
            return JsonResponse({
                'status': 'error',
                'message': 'Request timed out - Xero API not responding'
            }, status=408)
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                'status': 'error',
                'message': 'Connection error - Cannot reach Xero API'
            }, status=503)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    return wrapper


def get_xero_instances(request):
    """
    Fetch all Xero instances.
    """
    xero_instances = XeroInstances.objects.all().values(
        'xero_instance_pk',
        'xero_name',
        'xero_client_id'
    )
    return JsonResponse(list(xero_instances), safe=False)


@csrf_exempt
def create_xero_instance(request):
    """
    Create a new Xero instance with encrypted client secret.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            xero_name = data.get('xero_name')
            xero_client_id = data.get('xero_client_id')
            xero_client_secret = data.get('xero_client_secret')
            
            if not xero_name or not xero_client_id or not xero_client_secret:
                return JsonResponse({
                    'status': 'error',
                    'message': 'xero_name, xero_client_id, and xero_client_secret are all required'
                }, status=400)
            
            # Create instance
            xero_instance = XeroInstances(
                xero_name=xero_name,
                xero_client_id=xero_client_id
            )
            
            # Encrypt and set the secret
            xero_instance.set_client_secret(xero_client_secret)
            xero_instance.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Xero instance created successfully',
                'xero_instance': {
                    'xero_instance_pk': xero_instance.xero_instance_pk,
                    'xero_name': xero_instance.xero_name,
                    'xero_client_id': xero_instance.xero_client_id,
                    'has_secret': bool(xero_instance.xero_client_secret_encrypted)
                }
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
def update_xero_instance(request, instance_pk):
    """
    Update an existing Xero instance.
    Client secret is optional - only updates if provided.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            xero_name = data.get('xero_name')
            xero_client_id = data.get('xero_client_id')
            xero_client_secret = data.get('xero_client_secret')  # Optional
            
            # Get the instance
            try:
                xero_instance = XeroInstances.objects.get(pk=instance_pk)
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Xero instance not found'
                }, status=404)
            
            # Update fields
            if xero_name:
                xero_instance.xero_name = xero_name
            
            if xero_client_id:
                xero_instance.xero_client_id = xero_client_id
            
            # Only update secret if provided
            if xero_client_secret:
                xero_instance.set_client_secret(xero_client_secret)
                # Clear OAuth tokens since credentials changed
                xero_instance.oauth_access_token_encrypted = None
                xero_instance.oauth_refresh_token_encrypted = None
                xero_instance.oauth_token_expires_at = None
                xero_instance.oauth_tenant_id = None
                logger.info(f"Credentials updated for instance {instance_pk}. OAuth tokens cleared.")
            
            xero_instance.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Xero instance updated successfully',
                'xero_instance': {
                    'xero_instance_pk': xero_instance.xero_instance_pk,
                    'xero_name': xero_instance.xero_name,
                    'xero_client_id': xero_instance.xero_client_id,
                    'has_secret': bool(xero_instance.xero_client_secret_encrypted),
                    'needs_reauth': bool(xero_client_secret)  # True if credentials changed
                }
            })
        except Exception as e:
            logger.error(f"Error updating Xero instance {instance_pk}: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
def delete_xero_instance(request, instance_pk):
    """
    Delete a Xero instance.
    """
    if request.method == 'DELETE':
        try:
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            xero_name = xero_instance.xero_name
            xero_instance.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Xero instance "{xero_name}" deleted successfully'
            })
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only DELETE method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def test_xero_connection(request, instance_pk):
    """
    Test Xero API connection for a specific instance.
    Performs a health check by getting a token and fetching organisation info.
    """
    if request.method == 'GET':
        # Get Xero authentication
        xero_instance, result, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return result
        
        access_token = result
        
        # Step 2: First, get the list of authorized tenants for this token
        connections_response = requests.get(
            'https://api.xero.com/connections',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            },
            timeout=10
        )
        
        if connections_response.status_code != 200:
            logger.error(f"Failed to get connections for instance {instance_pk}: {connections_response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to verify authorized tenants: {connections_response.status_code}',
                'needs_auth': True
            }, status=401)
        
        connections = connections_response.json()
        logger.info(f"Authorized connections for instance {instance_pk}: {connections}")
        
        # tenant_id already retrieved from get_xero_auth helper
        stored_tenant_id = tenant_id
        
        if not connections:
            return JsonResponse({
                'status': 'error',
                'message': 'No Xero organizations are authorized for this token. Please re-authorize.',
                'needs_auth': True
            }, status=401)
        
        # Use the first authorized tenant (or match stored one if it exists)
        tenant_id = None
        for conn in connections:
            if stored_tenant_id and conn.get('tenantId') == stored_tenant_id:
                tenant_id = stored_tenant_id
                break
        
        # If stored tenant not found in authorized list, use the first one
        if not tenant_id:
            tenant_id = connections[0].get('tenantId')
            logger.warning(f"Stored tenant_id {stored_tenant_id} not in authorized list. Using {tenant_id} instead.")
            # Update the stored tenant_id
            xero_instance.oauth_tenant_id = tenant_id
            xero_instance.save()
        
        logger.info(f"Testing connection for instance {instance_pk} with tenant_id: {tenant_id}")
        
        # Step 3: Test API with a simple contacts call (we have accounting.contacts scope)
        # Using contacts instead of Organisation because Organisation requires accounting.settings scope
        test_response = requests.get(
            'https://api.xero.com/api.xro/2.0/Contacts?page=1&pageSize=1',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            timeout=10
        )
        
        if test_response.status_code == 200:
            # API is working! Get the org name from the connection info
            org_name = None
            for conn in connections:
                if conn.get('tenantId') == tenant_id:
                    org_name = conn.get('tenantName')
                    break
            
            logger.info(f"API test successful for instance {instance_pk}, org: {org_name}")
            
            return JsonResponse({
                'status': 'success',
                'message': f'✓ API Connection Working',
                'details': {
                    'xero_org_name': org_name,
                    'xero_instance_name': xero_instance.xero_name,
                    'tenant_id': tenant_id
                }
            })
        elif test_response.status_code == 401:
            # Token is invalid or expired
            logger.error(f"Xero API returned 401 for instance {instance_pk}. Response: {test_response.text}")
            return JsonResponse({
                'status': 'error',
                'message': 'OAuth token is invalid or expired. Please re-authorize.',
                'needs_auth': True  # Prompt for re-auth
            }, status=401)
        else:
            logger.error(f"Xero API returned {test_response.status_code} for instance {instance_pk}. Response: {test_response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'API call failed with status {test_response.status_code}: {test_response.text[:100]}'
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only GET method is allowed'
    }, status=405)
