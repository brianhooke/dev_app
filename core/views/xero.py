"""
Xero management views.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import XeroInstances
import json


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
