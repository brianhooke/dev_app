"""
Xero management views.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from ..models import XeroInstances
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
        
        if not client_secret:
            return False, "Client secret not found"
        
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
        
        response = requests.post('https://identity.xero.com/connect/token', headers=headers, data=data, timeout=10)
        response_data = response.json()
        
        if response.status_code != 200:
            error_msg = response_data.get('error_description', response_data.get('error', 'Unknown error'))
            return False, f"Token request failed: {error_msg}"
        
        if 'access_token' not in response_data:
            return False, "No access token in response"
        
        return True, response_data['access_token']
        
    except requests.exceptions.Timeout:
        return False, "Request timed out - Xero API not responding"
    except requests.exceptions.ConnectionError:
        return False, "Connection error - Cannot reach Xero API"
    except Exception as e:
        logger.error(f"Error getting Xero token: {str(e)}")
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
                return JsonResponse({
                    'status': 'success',
                    'message': f'Connection successful! Found {len(connections)} Xero organisation(s)',
                    'details': {
                        'xero_name': xero_instance.xero_name,
                        'connections_count': len(connections)
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
