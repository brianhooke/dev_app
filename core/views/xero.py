"""
Xero management views.

Xero Table Configuration:
- get_xero_config() - Returns column definitions for allocations_layout.html

Helper Functions:
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

Xero Contact Endpoints:
10. pull_xero_contacts - Pull contacts from Xero API
11. pull_xero_tracking_categories - Pull tracking categories from Xero API
12. create_contact - Create contact in Xero + local DB
13. create_supplier - Create supplier (minimal contact) in Xero + local DB
14. update_contact_details - Update contact details in Xero
15. update_contact_status - Archive/unarchive contact in Xero
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import XeroInstances, Contacts, XeroTrackingCategories
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
            {'header': 'Xero Instance', 'width': '28%', 'sortable': True},
            {'header': 'Test', 'width': '8%', 'class': 'col-action-first'},
            {'header': 'Authorise', 'width': '8%', 'class': 'col-action'},
            {'header': 'Pull Contacts', 'width': '8%', 'class': 'col-action'},
            {'header': 'Pull Accounts', 'width': '8%', 'class': 'col-action'},
            {'header': 'Pull Tracking', 'width': '8%', 'class': 'col-action'},
            {'header': 'Edit', 'width': '8%', 'class': 'col-action'},
            {'header': 'Delete', 'width': '8%', 'class': 'col-action'},
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
    tenant_id = xero_instance.get_oauth_tenant_id()
    
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
                # Clear OAuth tokens since credentials changed (clears both SSM and DB)
                xero_instance.clear_oauth_tokens()
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
            # Delete SSM parameters before deleting instance
            xero_instance.delete_ssm_params()
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


@csrf_exempt
def migrate_xero_to_ssm(request):
    """
    Migrate all XeroInstances credentials from database to AWS SSM Parameter Store.
    This is a one-time migration tool to preserve credentials before a database wipe.
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        from ..utils.ssm import is_ssm_available, set_xero_param
        
        if not is_ssm_available():
            return JsonResponse({
                'status': 'error',
                'message': 'AWS SSM Parameter Store is not available. Check AWS credentials.'
            }, status=500)
        
        instances = XeroInstances.objects.all()
        
        if not instances.exists():
            return JsonResponse({
                'status': 'success',
                'message': 'No XeroInstances found to migrate.'
            })
        
        migrated = 0
        errors = []
        
        for instance in instances:
            try:
                instance_pk = instance.xero_instance_pk
                
                # Get values from DB (using the encrypted fields directly)
                client_id = instance.xero_client_id
                
                # Get decrypted values from DB
                client_secret = None
                if instance.xero_client_secret_encrypted:
                    try:
                        cipher = instance._get_cipher()
                        client_secret = cipher.decrypt(bytes(instance.xero_client_secret_encrypted)).decode()
                    except Exception:
                        pass
                
                access_token = None
                if instance.oauth_access_token_encrypted:
                    try:
                        cipher = instance._get_cipher()
                        access_token = cipher.decrypt(bytes(instance.oauth_access_token_encrypted)).decode()
                    except Exception:
                        pass
                
                refresh_token = None
                if instance.oauth_refresh_token_encrypted:
                    try:
                        cipher = instance._get_cipher()
                        refresh_token = cipher.decrypt(bytes(instance.oauth_refresh_token_encrypted)).decode()
                    except Exception:
                        pass
                
                tenant_id = instance.oauth_tenant_id
                token_expires_at = instance.oauth_token_expires_at.isoformat() if instance.oauth_token_expires_at else None
                
                # Store in SSM
                if client_id:
                    set_xero_param(instance_pk, 'client_id', client_id)
                if client_secret:
                    set_xero_param(instance_pk, 'client_secret', client_secret)
                if access_token:
                    set_xero_param(instance_pk, 'access_token', access_token)
                if refresh_token:
                    set_xero_param(instance_pk, 'refresh_token', refresh_token)
                if tenant_id:
                    set_xero_param(instance_pk, 'tenant_id', tenant_id)
                if token_expires_at:
                    set_xero_param(instance_pk, 'token_expires_at', token_expires_at)
                
                migrated += 1
                logger.info(f"Migrated XeroInstance {instance_pk} ({instance.xero_name}) to SSM")
                
            except Exception as e:
                errors.append(f"{instance.xero_name}: {str(e)}")
                logger.error(f"Error migrating instance {instance.xero_name}: {str(e)}")
        
        if errors:
            return JsonResponse({
                'status': 'partial',
                'message': f'Migrated {migrated} instance(s) with {len(errors)} error(s):\n' + '\n'.join(errors)
            })
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully migrated {migrated} XeroInstance(s) to SSM Parameter Store.'
        })
        
    except Exception as e:
        logger.error(f"Error in migrate_xero_to_ssm: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)


# ============================================
# XERO CONTACT ENDPOINTS (moved from contacts.py)
# ============================================

@csrf_exempt
@handle_xero_request_errors
def pull_xero_contacts(request, instance_pk):
    """
    Pull contacts from Xero API for a specific instance.
    Only inserts new contacts, does not update existing ones.
    """
    if request.method == 'POST':
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        logger.info(f"Using tenant_id: {tenant_id} for instance: {xero_instance.xero_name}")
        
        # Fetch contacts from Xero API (includes archived contacts)
        # IMPORTANT: Using paging ensures ContactPersons field is populated
        xero_contacts = []
        page = 1
        
        while True:
            logger.info(f"Fetching page {page} of contacts...")
            contacts_response = requests.get(
                f'https://api.xero.com/api.xro/2.0/Contacts?includeArchived=true&page={page}',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json',
                    'Xero-tenant-id': tenant_id
                },
                timeout=30
            )
            
            if contacts_response.status_code != 200:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Failed to fetch contacts from Xero: {contacts_response.status_code}'
                }, status=400)
            
            contacts_data = contacts_response.json()
            page_contacts = contacts_data.get('Contacts', [])
            
            if not page_contacts:
                break  # No more contacts
            
            xero_contacts.extend(page_contacts)
            logger.info(f"Fetched {len(page_contacts)} contacts from page {page}. Total so far: {len(xero_contacts)}")
            page += 1
        
        logger.info(f"Received {len(xero_contacts)} contacts from Xero API")
        
        # Process contacts - insert new ones and update existing ones
        new_contacts_count = 0
        updated_contacts_count = 0
        unchanged_contacts_count = 0
        contact_person_updates = 0
        
        for xero_contact in xero_contacts:
            contact_id = xero_contact.get('ContactID')
            
            # Extract contact data from Xero
            name = xero_contact.get('Name', '')
            email = xero_contact.get('EmailAddress', '')
            status = xero_contact.get('ContactStatus', '')
            first_name = xero_contact.get('FirstName', '')
            last_name = xero_contact.get('LastName', '')
            
            # Parse bank account details
            bank_account_details = xero_contact.get('BankAccountDetails', '')
            bank_bsb = ''
            bank_account_number = ''
            
            if bank_account_details:
                cleaned = bank_account_details.replace(' ', '').replace('-', '')
                if len(cleaned) >= 6:
                    bank_bsb = cleaned[:6]
                    bank_account_number = cleaned[6:]
                else:
                    bank_account_number = cleaned
            
            bank_details = bank_account_details
            tax_number = xero_contact.get('TaxNumber', '')
            
            # Check if contact already exists for this Xero instance
            try:
                existing_contact = Contacts.objects.get(xero_contact_id=contact_id, xero_instance=xero_instance)
                
                # Compare and update if any field has changed
                fields_to_update = {
                    'name': name,
                    'email': email,
                    'status': status,
                    'first_name': first_name,
                    'last_name': last_name,
                    'bank_details': bank_details,
                    'bank_bsb': bank_bsb,
                    'bank_account_number': bank_account_number,
                    'tax_number': tax_number
                }
                
                updated = False
                for field, value in fields_to_update.items():
                    current_value = getattr(existing_contact, field)
                    if current_value != value:
                        setattr(existing_contact, field, value)
                        updated = True
                        if field in ['first_name', 'last_name']:
                            contact_person_updates += 1
                
                if updated:
                    existing_contact.save()
                    updated_contacts_count += 1
                else:
                    unchanged_contacts_count += 1
                    
            except Contacts.DoesNotExist:
                # Create new contact
                Contacts.objects.create(
                    xero_instance=xero_instance,
                    xero_contact_id=contact_id,
                    name=name,
                    email=email,
                    status=status,
                    first_name=first_name,
                    last_name=last_name,
                    bank_details=bank_details,
                    bank_bsb=bank_bsb,
                    bank_account_number=bank_account_number,
                    bank_details_verified=0,
                    tax_number=tax_number
                )
                new_contacts_count += 1
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully pulled contacts from Xero',
            'details': {
                'total_xero_contacts': len(xero_contacts),
                'new_contacts_added': new_contacts_count,
                'contacts_updated': updated_contacts_count,
                'contacts_unchanged': unchanged_contacts_count,
                'contact_person_updates': contact_person_updates
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def pull_xero_tracking_categories(request, instance_pk):
    """
    Pull tracking categories from Xero API for a specific instance.
    Inserts new tracking categories and options, updates existing ones.
    """
    if request.method == 'POST':
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        logger.info(f"Pulling tracking categories for instance: {xero_instance.xero_name}")
        
        # Fetch tracking categories from Xero API
        response = requests.get(
            'https://api.xero.com/api.xro/2.0/TrackingCategories',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            timeout=30
        )
        
        if response.status_code != 200:
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to fetch tracking categories from Xero: {response.status_code}'
            }, status=400)
        
        tracking_data = response.json()
        xero_categories = tracking_data.get('TrackingCategories', [])
        
        logger.info(f"Received {len(xero_categories)} tracking categories from Xero API")
        
        # Process tracking categories and their options
        new_count = 0
        updated_count = 0
        unchanged_count = 0
        
        for xero_category in xero_categories:
            tracking_category_id = xero_category.get('TrackingCategoryID')
            category_name = xero_category.get('Name', '')
            category_status = xero_category.get('Status', '')
            options = xero_category.get('Options', [])
            
            # Process each option within the category
            for option in options:
                option_id = option.get('TrackingOptionID')
                option_name = option.get('Name', '')
                
                try:
                    # Check if this category+option already exists
                    existing = XeroTrackingCategories.objects.get(
                        xero_instance=xero_instance,
                        tracking_category_id=tracking_category_id,
                        option_id=option_id
                    )
                    
                    # Check if any fields need updating
                    updated = False
                    if existing.name != category_name:
                        existing.name = category_name
                        updated = True
                    if existing.status != category_status:
                        existing.status = category_status
                        updated = True
                    if existing.option_name != option_name:
                        existing.option_name = option_name
                        updated = True
                    
                    if updated:
                        existing.save()
                        updated_count += 1
                    else:
                        unchanged_count += 1
                        
                except XeroTrackingCategories.DoesNotExist:
                    # Create new tracking category option
                    XeroTrackingCategories.objects.create(
                        xero_instance=xero_instance,
                        tracking_category_id=tracking_category_id,
                        name=category_name,
                        status=category_status,
                        option_id=option_id,
                        option_name=option_name
                    )
                    new_count += 1
        
        logger.info(f"Tracking categories sync complete: {new_count} new, {updated_count} updated, {unchanged_count} unchanged")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Successfully pulled tracking categories from Xero',
            'details': {
                'total_categories': len(xero_categories),
                'new_added': new_count,
                'updated': updated_count,
                'unchanged': unchanged_count
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def create_contact(request, instance_pk):
    """
    Create a new contact in Xero and local database using OAuth2 tokens.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        bsb = data.get('bsb', '')
        account_number = data.get('account_number', '')
        tax_number = data.get('tax_number', '')
        
        # Validation: Name and Email are required
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Name is required'
            }, status=400)
        
        if not email:
            return JsonResponse({
                'status': 'error',
                'message': 'Email is required'
            }, status=400)
            
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare contact data for Xero
        bank_account_details = format_bank_details(bsb, account_number)
        
        contact_data = {
            'Contacts': [{
                'Name': name,
                'FirstName': first_name if first_name else '',
                'LastName': last_name if last_name else '',
                'EmailAddress': email,
                'BankAccountDetails': bank_account_details,
                'TaxNumber': tax_number.replace(' ', '') if tax_number else ''
            }]
        }
        
        logger.info(f"Creating contact - Name: {name}, Email: {email}")
        
        create_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=contact_data,
            timeout=30
        )
        
        if create_response.status_code != 200:
            error_message = parse_xero_validation_errors(create_response) or f'Failed to create contact in Xero: {create_response.status_code}'
            return JsonResponse({
                'status': 'error',
                'message': error_message
            }, status=400)
        
        # Extract the created contact from Xero response
        response_data = create_response.json()
        xero_contact = response_data['Contacts'][0]
        xero_contact_id = xero_contact['ContactID']
        contact_status = xero_contact.get('ContactStatus', 'ACTIVE')
        
        # Save to local database
        new_contact = Contacts(
            xero_instance=xero_instance,
            xero_contact_id=xero_contact_id,
            name=name,
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            email=email,
            status=contact_status,
            bank_bsb=bsb.replace('-', '') if bsb else '',
            bank_account_number=account_number,
            tax_number=tax_number.replace(' ', '') if tax_number else '',
            bank_details=bank_account_details,
            checked=0
        )
        new_contact.save()
        
        logger.info(f"Successfully created contact {name} with ID {new_contact.contact_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contact created successfully',
            'contact': {
                'contact_pk': new_contact.contact_pk,
                'name': new_contact.name,
                'first_name': new_contact.first_name,
                'last_name': new_contact.last_name,
                'email': new_contact.email,
                'bank_bsb': new_contact.bank_bsb,
                'bank_account_number': new_contact.bank_account_number,
                'tax_number': new_contact.tax_number
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def create_supplier(request):
    """
    Create a new supplier (contact with IsSupplier=true) in Xero and local database.
    Simplified version of create_contact - only requires name.
    Used by Bills Inbox for quick supplier creation.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        xero_instance_id = data.get('xero_instance_id')
        
        # Validation: Name is required
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier name is required'
            }, status=400)
        
        if not xero_instance_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance ID is required'
            }, status=400)
            
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(xero_instance_id)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare contact data for Xero - minimal supplier
        contact_data = {
            'Contacts': [{
                'Name': name,
                'IsSupplier': True
            }]
        }
        
        logger.info(f"Creating supplier - Name: {name} for Xero instance: {xero_instance.xero_name}")
        
        create_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=contact_data,
            timeout=30
        )
        
        if create_response.status_code != 200:
            error_message = parse_xero_validation_errors(create_response) or f'Failed to create supplier in Xero: {create_response.status_code}'
            return JsonResponse({
                'status': 'error',
                'message': error_message
            }, status=400)
        
        # Extract the created contact from Xero response
        response_data = create_response.json()
        xero_contact = response_data['Contacts'][0]
        xero_contact_id = xero_contact['ContactID']
        contact_status = xero_contact.get('ContactStatus', 'ACTIVE')
        
        # Save to local database
        new_contact = Contacts(
            xero_instance=xero_instance,
            xero_contact_id=xero_contact_id,
            name=name,
            status=contact_status,
            checked=0
        )
        new_contact.save()
        
        logger.info(f"Successfully created supplier {name} with ID {new_contact.contact_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Supplier created successfully',
            'supplier': {
                'contact_pk': new_contact.contact_pk,
                'name': new_contact.name,
                'xero_instance_id': xero_instance_id
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def update_contact_details(request, instance_pk, contact_pk):
    """
    Update a contact's details in Xero using OAuth2 tokens.
    Accepts flexible data - can update just name/first_name/last_name/email (from PO table)
    or full contact details including bank info (from Contacts modal).
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        email = data.get('email', '')
        bsb = data.get('bsb', '')
        account_number = data.get('account_number', '')
        tax_number = data.get('tax_number', '')
        
        # Get the contact
        contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare update data for Xero - only include provided fields
        xero_contact_data = {
            'ContactID': contact.xero_contact_id
        }
        
        if name:
            xero_contact_data['Name'] = name
        if first_name:
            xero_contact_data['FirstName'] = first_name
        if last_name:
            xero_contact_data['LastName'] = last_name
        if email:
            xero_contact_data['EmailAddress'] = email
        
        bank_account_details = None
        if bsb or account_number:
            bank_account_details = format_bank_details(bsb, account_number)
            xero_contact_data['BankAccountDetails'] = bank_account_details
        
        if tax_number:
            xero_contact_data['TaxNumber'] = tax_number.replace(' ', '')
        
        update_data = {
            'Contacts': [xero_contact_data]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id}")
        
        update_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=update_data,
            timeout=30
        )
        
        if update_response.status_code != 200:
            error_message = parse_xero_validation_errors(update_response) or f'Failed to update contact in Xero: {update_response.status_code}'
            return JsonResponse({
                'status': 'error',
                'message': error_message
            }, status=400)
        
        # Update local database - only update provided fields
        if name:
            contact.name = name
        if first_name:
            contact.first_name = first_name
        if last_name:
            contact.last_name = last_name
        if email:
            contact.email = email
        if bsb:
            contact.bank_bsb = bsb.replace('-', '')
        if account_number:
            contact.bank_account_number = account_number
        if tax_number:
            contact.tax_number = tax_number.replace(' ', '')
        if bank_account_details:
            contact.bank_details = bank_account_details
        
        contact.save()
        
        logger.info(f"Successfully updated contact {contact.name}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contact updated successfully',
            'contact': {
                'name': contact.name,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'email': contact.email,
                'bank_bsb': contact.bank_bsb,
                'bank_account_number': contact.bank_account_number,
                'tax_number': contact.tax_number
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def update_contact_status(request, instance_pk, contact_pk):
    """
    Update a contact's status in Xero using OAuth2 tokens.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        archive = data.get('archive', False)
        
        # Get the contact
        contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Update contact status in Xero
        new_status = 'ARCHIVED' if archive else 'ACTIVE'
        
        update_data = {
            'Contacts': [{
                'ContactID': contact.xero_contact_id,
                'ContactStatus': new_status
            }]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id} to status {new_status}")
        
        update_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=update_data,
            timeout=10
        )
        
        if update_response.status_code not in [200, 201]:
            logger.error(f"Xero API error: {update_response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to update contact in Xero: {update_response.status_code}'
            }, status=400)
        
        # Update local database
        contact.status = new_status
        contact.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Contact {"archived" if archive else "unarchived"} successfully',
            'new_status': new_status
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)
