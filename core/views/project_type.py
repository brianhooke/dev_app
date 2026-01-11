"""
Views for PROJECT_TYPE management.

Handles switching between project types and project selection.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import Projects, ProjectTypes
from ..utils.project_type import set_project_type, set_active_project, get_project_type
import json


@csrf_exempt
def switch_project_type(request):
    """
    Switch the active project_type.
    
    POST data:
        project_type: The project type to switch to
        
    Returns:
        JSON response with status
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_type = data.get('project_type')
        
        if project_type in dict(ProjectTypes.PROJECT_TYPE_CHOICES):
            set_project_type(request, project_type)
            return JsonResponse({
                'status': 'success',
                'project_type': project_type,
                'message': f'Switched to {project_type} mode'
            })
        
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid project type'
        }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


@csrf_exempt
def switch_project(request):
    """
    Switch the active project.
    
    POST data:
        project_pk: The project primary key to switch to
        
    Returns:
        JSON response with status
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        project_pk = data.get('project_pk')
        
        try:
            set_active_project(request, project_pk)
            project = Projects.objects.get(projects_pk=project_pk)
            
            return JsonResponse({
                'status': 'success',
                'project_pk': project_pk,
                'project_name': project.project,
                'project_type': project.project_type.project_type if project.project_type else None,
                'message': f'Switched to project: {project.project}'
            })
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


def get_current_project_info(request):
    """
    Get information about the current project and project_type.
    
    Returns:
        JSON response with current project info
    """
    project = getattr(request, 'project', None)
    project_type = get_project_type(request)
    
    response_data = {
        'project_type': project_type,
        'available_types': ProjectTypes.PROJECT_TYPE_CHOICES,
    }
    
    if project:
        response_data['project'] = {
            'pk': project.projects_pk,
            'name': project.project,
            'type': project.project_type.project_type if project.project_type else None,
        }
    
    return JsonResponse(response_data)


def project_selector_view(request):
    """
    Render the project selector page.
    
    Shows available projects and allows switching between them.
    """
    projects = Projects.objects.all()
    current_project = getattr(request, 'project', None)
    current_project_type = get_project_type(request)
    
    context = {
        'projects': projects,
        'current_project': current_project,
        'current_project_type': current_project_type,
        'project_type_choices': ProjectTypes.PROJECT_TYPE_CHOICES,
    }
    
    return render(request, 'core/project_selector.html', context)
