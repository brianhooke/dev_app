"""
Settings View Functions

Endpoints for managing project type to Xero instance mappings.

Data Retrieval:
1. get_project_types - Get all project types with their Xero instance assignments

Data Updates:
2. update_project_type_xero_instance - Update a project type's Xero instance
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404

from ..models import ProjectTypes, XeroInstances

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def get_project_types(request):
    """
    Get all project types with their Xero instance assignments.
    Filters by archived status (default: 0 = active).
    """
    try:
        archived = request.GET.get('archived', '0')
        archived_filter = 1 if archived == '1' else 0
        
        project_types = ProjectTypes.objects.select_related('xero_instance').filter(archived=archived_filter)
        
        data = []
        for pt in project_types:
            data.append({
                'project_type_pk': pt.project_type_pk,
                'project_type': pt.project_type,
                'xero_instance_pk': pt.xero_instance.xero_instance_pk if pt.xero_instance else None,
                'xero_instance_name': pt.xero_instance.xero_name if pt.xero_instance else None,
                'rates_based': pt.rates_based,
                'archived': pt.archived,
                'stocktake': pt.stocktake or 0,
            })
        
        return JsonResponse({
            'status': 'success',
            'project_types': data
        })
        
    except Exception as e:
        logger.error(f"Error getting project types: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting project types: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_xero_instances_list(request):
    """
    Get all Xero instances for dropdown selection.
    """
    try:
        instances = XeroInstances.objects.all().values('xero_instance_pk', 'xero_name', 'stocktake')
        
        return JsonResponse({
            'status': 'success',
            'xero_instances': list(instances)
        })
        
    except Exception as e:
        logger.error(f"Error getting Xero instances: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting Xero instances: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_project_type(request):
    """
    Create a new project type with optional Xero instance assignment.
    """
    try:
        data = json.loads(request.body)
        project_type_name = data.get('project_type', '').strip()
        xero_instance_pk = data.get('xero_instance_pk')
        rates_based = data.get('rates_based', 0)
        
        if not project_type_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Project type name is required'
            }, status=400)
        
        if len(project_type_name) > 50:
            return JsonResponse({
                'status': 'error',
                'message': 'Project type name must be 50 characters or less'
            }, status=400)
        
        # Check for uniqueness
        if ProjectTypes.objects.filter(project_type=project_type_name).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'Project type "{project_type_name}" already exists'
            }, status=400)
        
        # Get Xero instance if provided
        xero_instance = None
        if xero_instance_pk:
            xero_instance = get_object_or_404(XeroInstances, pk=xero_instance_pk)
        
        # Create the project type
        project_type = ProjectTypes.objects.create(
            project_type=project_type_name,
            xero_instance=xero_instance,
            rates_based=rates_based
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Project type created successfully',
            'project_type': {
                'project_type_pk': project_type.project_type_pk,
                'project_type': project_type.project_type,
                'xero_instance_pk': project_type.xero_instance.xero_instance_pk if project_type.xero_instance else None,
                'xero_instance_name': project_type.xero_instance.xero_name if project_type.xero_instance else None,
                'rates_based': project_type.rates_based,
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating project type: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating project type: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_project_type_name(request, project_type_pk):
    """
    Update the name of a project type.
    """
    try:
        data = json.loads(request.body)
        new_name = data.get('project_type', '').strip()
        
        if not new_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Project type name cannot be empty'
            }, status=400)
        
        if len(new_name) > 50:
            return JsonResponse({
                'status': 'error',
                'message': 'Project type name must be 50 characters or less'
            }, status=400)
        
        project_type = get_object_or_404(ProjectTypes, pk=project_type_pk)
        
        # Check for uniqueness (excluding current record)
        if ProjectTypes.objects.filter(project_type=new_name).exclude(pk=project_type_pk).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'Project type "{new_name}" already exists'
            }, status=400)
        
        project_type.project_type = new_name
        project_type.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Project type name updated successfully',
            'project_type': project_type.project_type,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating project type name: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating project type name: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_project_type_xero_instance(request, project_type_pk):
    """
    Update the Xero instance assignment for a project type.
    """
    try:
        data = json.loads(request.body)
        xero_instance_pk = data.get('xero_instance_pk')
        
        project_type = get_object_or_404(ProjectTypes, pk=project_type_pk)
        
        if xero_instance_pk:
            xero_instance = get_object_or_404(XeroInstances, pk=xero_instance_pk)
            project_type.xero_instance = xero_instance
        else:
            project_type.xero_instance = None
        
        project_type.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Xero instance updated successfully',
            'xero_instance_pk': project_type.xero_instance.xero_instance_pk if project_type.xero_instance else None,
            'xero_instance_name': project_type.xero_instance.xero_name if project_type.xero_instance else None,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating project type Xero instance: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating Xero instance: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_project_type_rates_based(request, project_type_pk):
    """
    Update the rates_based setting for a project type.
    """
    try:
        data = json.loads(request.body)
        rates_based = data.get('rates_based')
        
        if rates_based not in [0, 1]:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid rates_based value. Must be 0 or 1.'
            }, status=400)
        
        project_type = get_object_or_404(ProjectTypes, pk=project_type_pk)
        project_type.rates_based = rates_based
        project_type.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Rates based updated successfully',
            'rates_based': project_type.rates_based,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error updating project type rates_based: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating rates based: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_project_type_archive(request, project_type_pk):
    """
    Toggle the archived status of a project type.
    """
    try:
        data = json.loads(request.body)
        archived = data.get('archived')
        
        if archived not in [0, 1]:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid archived value. Must be 0 or 1.'
            }, status=400)
        
        project_type = get_object_or_404(ProjectTypes, pk=project_type_pk)
        project_type.archived = archived
        project_type.save()
        
        action = 'archived' if archived == 1 else 'restored'
        return JsonResponse({
            'status': 'success',
            'message': f'Project type {action} successfully',
            'archived': project_type.archived,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error toggling project type archive: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error toggling archive status: {str(e)}'
        }, status=500)
