"""
Xero management views.
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


# ============================================================================
# DEPRECATED: Custom Connection (Client Credentials) - DO NOT USE
# Use OAuth2 via xero_oauth.py instead
# ============================================================================

# def get_xero_token(xero_instance):
#     """DEPRECATED: Use get_oauth_token from xero_oauth.py instead"""
#     try:
#         client_id = xero_instance.xero_client_id
#         client_secret = xero_instance.get_client_secret()
#         
#         logger.info(f"Getting Xero token for instance: {xero_instance.xero_name}")
#         logger.info(f"Client ID: {client_id[:10]}... (truncated)")
#         
#         if not client_secret:
#             logger.error("Client secret not found or could not be decrypted")
#             return False, "Client secret not found or could not be decrypted"
#         
#         logger.info(f"Client secret retrieved successfully (length: {len(client_secret)})")
#         
#         scopes_list = [
#             "accounting.transactions.read",
#             "accounting.contacts.read",
#             "accounting.settings.read"
#         ]
#         scopes = ' '.join(scopes_list)
#         
#         credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
#         headers = {
#             'Authorization': f'Basic {credentials}',
#             'Content-Type': 'application/x-www-form-urlencoded'
#         }
#         data = {
#             'grant_type': 'client_credentials',
#             'scope': scopes
#         }
#         
#         logger.info("Sending token request to Xero...")
#         response = requests.post('https://identity.xero.com/connect/token', headers=headers, data=data, timeout=10)
#         response_data = response.json()
#         
#         logger.info(f"Xero token response status: {response.status_code}")
#         logger.info(f"Xero token response: {response_data}")
#         
#         if response.status_code != 200:
#             error_msg = response_data.get('error_description', response_data.get('error', 'Unknown error'))
#             logger.error(f"Token request failed: {error_msg}")
#             return False, f"Token request failed: {error_msg}"
#         
#         if 'access_token' not in response_data:
#             logger.error("No access token in response")
#             return False, "No access token in response"
#         
#         logger.info("Token retrieved successfully")
#         return True, response_data['access_token']
#         
#     except requests.exceptions.Timeout:
#         logger.error("Request timed out")
#         return False, "Request timed out - Xero API not responding"
#     except requests.exceptions.ConnectionError as e:
#         logger.error(f"Connection error: {str(e)}")
#         return False, "Connection error - Cannot reach Xero API"
#     except Exception as e:
#         logger.error(f"Unexpected error getting Xero token: {str(e)}", exc_info=True)
#         return False, f"Error: {str(e)}"


@csrf_exempt
def test_xero_connection(request, instance_pk):
    """
    Test Xero API connection for a specific instance.
    Performs a health check by getting a token and fetching organisation info.
    """
    if request.method == 'GET':
        try:
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            
            # Step 1: Get OAuth token
            from .xero_oauth import get_oauth_token
            success, token_or_error = get_oauth_token(xero_instance)
            if not success:
                logger.error(f"get_oauth_token failed for instance {instance_pk}: {token_or_error}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Authentication failed: {token_or_error}',
                    'needs_auth': True
                }, status=401)
            
            access_token = token_or_error
            
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
            
            # Get the stored tenant_id
            stored_tenant_id = xero_instance.oauth_tenant_id
            
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
                    'message': 'OAuth token is invalid or expired. Token refresh may have failed.',
                    'needs_auth': False  # Don't prompt for re-auth since token exists
                }, status=401)
            else:
                logger.error(f"Xero API returned {test_response.status_code} for instance {instance_pk}. Response: {test_response.text}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'API call failed with status {test_response.status_code}: {test_response.text[:100]}'
                }, status=400)
                
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance not found'
            }, status=404)
        except requests.exceptions.Timeout:
            return JsonResponse({
                'status': 'error',
                'message': 'Request timed out - Xero API not responding'
            }, status=408)
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                'status': 'error',
                'message': 'Connection error - Cannot reach Xero API. Check your internet connection.'
            }, status=503)
        except Exception as e:
            logger.error(f"Error testing Xero connection: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only GET method is allowed'
    }, status=405)


@csrf_exempt
def pull_xero_contacts(request, instance_pk):
    """
    Pull contacts from Xero API for a specific instance.
    Only inserts new contacts, does not update existing ones.
    """
    if request.method == 'POST':
        try:
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            
            # Get OAuth token (OAuth2 only - no fallback to custom connection)
            from .xero_oauth import get_oauth_token
            success, token_or_error = get_oauth_token(xero_instance)
            
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'message': f'OAuth authentication failed: {token_or_error}. Please authorize the app first.',
                    'needs_auth': True
                }, status=401)
            
            access_token = token_or_error
            
            # Step 2: Get tenant ID from stored XeroInstance
            tenant_id = xero_instance.oauth_tenant_id
            
            if not tenant_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No tenant ID found. Please re-authorize this Xero instance.',
                    'needs_auth': True
                }, status=401)
            
            logger.info(f"Using tenant_id: {tenant_id} for instance: {xero_instance.xero_name}")
            
            # Step 3: Fetch contacts from Xero API (includes archived contacts)
            contacts_response = requests.get(
                'https://api.xero.com/api.xro/2.0/Contacts?includeArchived=true',
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
            xero_contacts = contacts_data.get('Contacts', [])
            
            # Step 4: Process contacts - insert new ones and update existing ones
            new_contacts_count = 0
            updated_contacts_count = 0
            unchanged_contacts_count = 0
            
            for xero_contact in xero_contacts:
                contact_id = xero_contact.get('ContactID')
                
                # Extract contact data from Xero
                name = xero_contact.get('Name', '')
                email = xero_contact.get('EmailAddress', '')
                status = xero_contact.get('ContactStatus', '')
                
                # Parse bank account details
                bank_account_details = xero_contact.get('BankAccountDetails', '')
                bank_bsb = ''
                bank_account_number = ''
                
                if bank_account_details:
                    # Remove spaces and dashes for parsing
                    cleaned = bank_account_details.replace(' ', '').replace('-', '')
                    
                    # BSB is first 6 digits, rest is account number
                    if len(cleaned) >= 6:
                        bank_bsb = cleaned[:6]
                        bank_account_number = cleaned[6:]
                    else:
                        # If less than 6 digits, store as-is in account number
                        bank_account_number = cleaned
                
                # Keep original for reference
                bank_details = bank_account_details
                tax_number = xero_contact.get('TaxNumber', '')
                
                # Check if contact already exists
                try:
                    existing_contact = Contacts.objects.get(xero_contact_id=contact_id)
                    
                    # Compare and update if any field has changed
                    updated = False
                    if existing_contact.name != name:
                        existing_contact.name = name
                        updated = True
                    if existing_contact.email != email:
                        existing_contact.email = email
                        updated = True
                    if existing_contact.status != status:
                        existing_contact.status = status
                        updated = True
                    if existing_contact.bank_details != bank_details:
                        existing_contact.bank_details = bank_details
                        updated = True
                    if existing_contact.bank_bsb != bank_bsb:
                        existing_contact.bank_bsb = bank_bsb
                        updated = True
                    if existing_contact.bank_account_number != bank_account_number:
                        existing_contact.bank_account_number = bank_account_number
                        updated = True
                    if existing_contact.tax_number != tax_number:
                        existing_contact.tax_number = tax_number
                        updated = True
                    
                    if updated:
                        existing_contact.save()
                        updated_contacts_count += 1
                        logger.info(f"Updated contact: {name} (ID: {contact_id})")
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
                        bank_details=bank_details,
                        bank_bsb=bank_bsb,
                        bank_account_number=bank_account_number,
                        bank_details_verified=0,
                        tax_number=tax_number
                    )
                    new_contacts_count += 1
                    logger.info(f"Created new contact: {name} (ID: {contact_id})")
            
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully pulled contacts from Xero',
                'details': {
                    'total_xero_contacts': len(xero_contacts),
                    'new_contacts_added': new_contacts_count,
                    'contacts_updated': updated_contacts_count,
                    'contacts_unchanged': unchanged_contacts_count
                }
            })
            
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance not found'
            }, status=404)
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
            logger.error(f"Error pulling Xero contacts: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


def get_contacts_by_instance(request, instance_pk):
    """
    Get all ACTIVE contacts for a specific Xero instance, sorted alphabetically by name.
    Archived contacts are stored in the database but not displayed in the UI.
    """
    if request.method == 'GET':
        try:
            contacts = Contacts.objects.filter(
                xero_instance_id=instance_pk,
                status='ACTIVE'
            ).order_by('name').values(
                'contact_pk',
                'xero_instance_id',
                'xero_contact_id',
                'name',
                'email',
                'status',
                'bank_bsb',
                'bank_account_number',
                'tax_number'
            )
            return JsonResponse(list(contacts), safe=False)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only GET method is allowed'
    }, status=405)


@csrf_exempt
def update_contact_details(request, instance_pk, contact_pk):
    """
    Update a contact's bank details and tax number in Xero using OAuth2 tokens.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '')
            bsb = data.get('bsb', '')
            account_number = data.get('account_number', '')
            tax_number = data.get('tax_number', '')
            
            # Get the contact and xero instance
            contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            
            # Import OAuth token function
            from .xero_oauth import get_oauth_token
            
            # Get OAuth access token
            success, token_or_error = get_oauth_token(xero_instance)
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'message': token_or_error,
                    'needs_auth': True
                }, status=401)
            
            access_token = token_or_error
            tenant_id = xero_instance.oauth_tenant_id
            
            if not tenant_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No tenant ID found. Please re-authorize this Xero instance.',
                    'needs_auth': True
                }, status=401)
            
            # Prepare update data for Xero
            # Combine BSB and account number for BankAccountDetails
            bank_account_details = ''
            if bsb and account_number:
                bank_account_details = bsb.replace('-', '') + account_number
            
            update_data = {
                'Contacts': [{
                    'ContactID': contact.xero_contact_id,
                    'EmailAddress': email,
                    'BankAccountDetails': bank_account_details,
                    'TaxNumber': tax_number.replace(' ', '') if tax_number else ''
                }]
            }
            
            logger.info(f"Updating contact {contact.xero_contact_id} - Email: {email}, BSB: {bsb}, Account: {account_number}, Tax: {tax_number}")
            
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
            
            logger.info(f"Xero API response status: {update_response.status_code}")
            logger.info(f"Xero API response: {update_response.text}")
            
            if update_response.status_code != 200:
                # Try to parse Xero validation errors
                error_message = f'Failed to update contact in Xero: {update_response.status_code}'
                try:
                    error_data = update_response.json()
                    if 'Elements' in error_data and len(error_data['Elements']) > 0:
                        element = error_data['Elements'][0]
                        if 'ValidationErrors' in element and len(element['ValidationErrors']) > 0:
                            validation_errors = [err['Message'] for err in element['ValidationErrors']]
                            error_message = 'Xero validation error: ' + '; '.join(validation_errors)
                except:
                    pass
                
                return JsonResponse({
                    'status': 'error',
                    'message': error_message
                }, status=400)
            
            # Update local database
            contact.email = email
            contact.bank_bsb = bsb.replace('-', '')
            contact.bank_account_number = account_number
            contact.tax_number = tax_number.replace(' ', '')
            contact.bank_details = bank_account_details
            contact.save()
            
            logger.info(f"Successfully updated contact {contact.name} in database")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Contact updated successfully',
                'contact': {
                    'email': contact.email,
                    'bank_bsb': contact.bank_bsb,
                    'bank_account_number': contact.bank_account_number,
                    'tax_number': contact.tax_number
                }
            })
            
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Contact not found'
            }, status=404)
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance not found'
            }, status=404)
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
            logger.error(f"Error updating contact: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
def update_contact_status(request, instance_pk, contact_pk):
    """
    Update a contact's status in Xero using OAuth2 tokens.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            archive = data.get('archive', False)  # True to archive, False to unarchive
            
            # Get the contact and xero instance
            contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            
            # Import OAuth token function
            from .xero_oauth import get_oauth_token
            
            # Get OAuth access token
            success, token_or_error = get_oauth_token(xero_instance)
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'message': token_or_error,
                    'needs_auth': True
                }, status=401)
            
            access_token = token_or_error
            
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
                    'Xero-tenant-id': xero_instance.oauth_tenant_id
                },
                json=update_data,
                timeout=10
            )
            
            logger.info(f"Xero API response status: {update_response.status_code}")
            logger.info(f"Xero API response: {update_response.text}")
            
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
            
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Contact not found'
            }, status=404)
        except XeroInstances.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Xero instance not found'
            }, status=404)
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
            logger.error(f"Error updating contact status: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)
