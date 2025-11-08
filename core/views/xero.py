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
    Create a new Xero instance.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            xero_name = data.get('xero_name')
            xero_client_id = data.get('xero_client_id')
            
            if not xero_name or not xero_client_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Both xero_name and xero_client_id are required'
                }, status=400)
            
            xero_instance = XeroInstances.objects.create(
                xero_name=xero_name,
                xero_client_id=xero_client_id
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Xero instance created successfully',
                'xero_instance': {
                    'xero_instance_pk': xero_instance.xero_instance_pk,
                    'xero_name': xero_instance.xero_name,
                    'xero_client_id': xero_instance.xero_client_id
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
