"""
Xero management views.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import XeroInstances, Contacts
import json
import base64
import requests
import logging

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


def get_xero_token(xero_instance):
    """
    Get Xero access token using client credentials from XeroInstance.
    Returns tuple: (success: bool, token_or_error: str)
    """
    try:
        client_id = xero_instance.xero_client_id
        client_secret = xero_instance.get_client_secret()
        
        logger.info(f"Getting Xero token for instance: {xero_instance.xero_name}")
        logger.info(f"Client ID: {client_id[:10]}... (truncated)")
        
        if not client_secret:
            logger.error("Client secret not found or could not be decrypted")
            return False, "Client secret not found or could not be decrypted"
        
        logger.info(f"Client secret retrieved successfully (length: {len(client_secret)})")
        
        scopes_list = [
            "accounting.transactions.read",
            "accounting.contacts.read",
            "accounting.settings.read"
        ]
        scopes = ' '.join(scopes_list)
        
        credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'client_credentials',
            'scope': scopes
        }
        
        logger.info("Sending token request to Xero...")
        response = requests.post('https://identity.xero.com/connect/token', headers=headers, data=data, timeout=10)
        response_data = response.json()
        
        logger.info(f"Xero token response status: {response.status_code}")
        logger.info(f"Xero token response: {response_data}")
        
        if response.status_code != 200:
            error_msg = response_data.get('error_description', response_data.get('error', 'Unknown error'))
            logger.error(f"Token request failed: {error_msg}")
            return False, f"Token request failed: {error_msg}"
        
        if 'access_token' not in response_data:
            logger.error("No access token in response")
            return False, "No access token in response"
        
        logger.info("Token retrieved successfully")
        return True, response_data['access_token']
        
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return False, "Request timed out - Xero API not responding"
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return False, "Connection error - Cannot reach Xero API"
    except Exception as e:
        logger.error(f"Unexpected error getting Xero token: {str(e)}", exc_info=True)
        return False, f"Error: {str(e)}"


@csrf_exempt
def test_xero_connection(request, instance_pk):
    """
    Test Xero API connection for a specific instance.
    Performs a health check by getting a token and fetching organisation info.
    """
    if request.method == 'GET':
        try:
            xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
            
            # Step 1: Get token
            success, token_or_error = get_xero_token(xero_instance)
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Authentication failed: {token_or_error}'
                }, status=400)
            
            access_token = token_or_error
            
            # Step 2: Test API with a simple call to get connections
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            response = requests.get('https://api.xero.com/connections', headers=headers, timeout=10)
            
            if response.status_code == 200:
                connections = response.json()
                
                # Get the organisation name from the first connection if available
                org_name = None
                if connections and len(connections) > 0:
                    tenant_id = connections[0].get('tenantId')
                    if tenant_id:
                        # Fetch organisation details
                        org_response = requests.get(
                            f'https://api.xero.com/api.xro/2.0/Organisation',
                            headers={
                                'Authorization': f'Bearer {access_token}',
                                'Accept': 'application/json',
                                'Xero-tenant-id': tenant_id
                            },
                            timeout=10
                        )
                        if org_response.status_code == 200:
                            org_data = org_response.json()
                            if 'Organisations' in org_data and len(org_data['Organisations']) > 0:
                                org_name = org_data['Organisations'][0].get('Name')
                                
                                # Update the instance name if we got a name from Xero
                                if org_name and org_name != xero_instance.xero_name:
                                    logger.info(f"Updating instance name from '{xero_instance.xero_name}' to '{org_name}'")
                                    xero_instance.xero_name = org_name
                                    xero_instance.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Connection successful! Found {len(connections)} Xero organisation(s)',
                    'details': {
                        'xero_name': org_name or xero_instance.xero_name,
                        'connections_count': len(connections),
                        'name_updated': org_name is not None and org_name != xero_instance.xero_name
                    }
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': f'API call failed with status {response.status_code}'
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
            
            # Step 1: Get token
            success, token_or_error = get_xero_token(xero_instance)
            if not success:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Authentication failed: {token_or_error}'
                }, status=400)
            
            access_token = token_or_error
            
            # Step 2: Get tenant ID from connections
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            connections_response = requests.get('https://api.xero.com/connections', headers=headers, timeout=10)
            
            if connections_response.status_code != 200:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Failed to get Xero connections'
                }, status=400)
            
            connections = connections_response.json()
            if not connections or len(connections) == 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No Xero organisations connected'
                }, status=400)
            
            tenant_id = connections[0].get('tenantId')
            
            # Step 3: Fetch contacts from Xero API
            contacts_response = requests.get(
                'https://api.xero.com/api.xro/2.0/Contacts',
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
            
            # Step 4: Process contacts - only insert new ones
            new_contacts_count = 0
            skipped_contacts_count = 0
            
            for xero_contact in xero_contacts:
                contact_id = xero_contact.get('ContactID')
                
                # Check if contact already exists
                if Contacts.objects.filter(xero_contact_id=contact_id).exists():
                    skipped_contacts_count += 1
                    continue
                
                # Extract contact data
                name = xero_contact.get('Name', '')
                email = xero_contact.get('EmailAddress', '')
                status = xero_contact.get('ContactStatus', '')
                bank_details = xero_contact.get('BankAccountDetails', '')
                
                # Create new contact
                Contacts.objects.create(
                    xero_instance=xero_instance,
                    xero_contact_id=contact_id,
                    name=name,
                    email=email,
                    status=status,
                    bank_details=bank_details,
                    bank_details_verified=0
                )
                new_contacts_count += 1
            
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully pulled contacts from Xero',
                'details': {
                    'total_xero_contacts': len(xero_contacts),
                    'new_contacts_added': new_contacts_count,
                    'existing_contacts_skipped': skipped_contacts_count
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
