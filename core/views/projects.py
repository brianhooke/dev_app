"""
Project management views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.models import Projects, XeroInstances, XeroAccounts

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def create_project(request):
    """
    Create a new project
    
    Expected POST data:
    - project_name: str (required)
    - project_type: str (optional, default='general')
    - xero_instance_pk: int (optional)
    - xero_sales_account: str (optional)
    - background: file (optional)
    """
    try:
        # Get form data
        project_name = request.POST.get('project_name', '').strip()
        project_type = request.POST.get('project_type', 'general')
        xero_instance_pk = request.POST.get('xero_instance_pk')
        xero_sales_account = request.POST.get('xero_sales_account')
        
        # Validate required fields
        if not project_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Project name is required'
            }, status=400)
        
        # Validate project type
        valid_types = [choice[0] for choice in Projects.PROJECT_TYPE_CHOICES]
        if project_type not in valid_types:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid project type. Must be one of: {", ".join(valid_types)}'
            }, status=400)
        
        # Get xero instance if provided
        xero_instance = None
        if xero_instance_pk:
            try:
                xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_pk)
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid Xero instance'
                }, status=400)
        
        # Create project
        project = Projects(
            project=project_name,
            project_type=project_type,
            xero_instance=xero_instance,
            xero_sales_account=xero_sales_account
        )
        
        # Handle background image upload
        if 'background' in request.FILES:
            background_file = request.FILES['background']
            
            # Validate file type
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            file_ext = background_file.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'
                }, status=400)
            
            project.background = background_file
        
        project.save()
        
        logger.info(f"Created project: {project.project} (pk={project.projects_pk})")
        
        # Generate background URL - use relative URL for media files
        background_url = ''
        if project.background:
            # Use just the path, not absolute URI - browser will resolve relative to current host
            background_url = project.background.url
        
        # Return project data
        return JsonResponse({
            'status': 'success',
            'message': 'Project created successfully',
            'project': {
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type,
                'project_type_display': project.get_project_type_display(),
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'background_url': background_url
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating project: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_projects(request):
    """
    Get all projects, optionally filtered by archived status
    
    Query params:
    - archived: 0 (active) or 1 (archived). Default is 0.
    """
    try:
        # Get archived filter from query params (default to 0 = active)
        archived_filter = request.GET.get('archived', '0')
        archived_value = 1 if archived_filter == '1' else 0
        
        projects = Projects.objects.filter(archived=archived_value).select_related('xero_instance')
        
        projects_data = []
        for project in projects:
            # Get sales account display name (code - name)
            sales_account_display = ''
            if project.xero_sales_account and project.xero_instance:
                try:
                    account = XeroAccounts.objects.get(
                        xero_instance=project.xero_instance,
                        account_code=project.xero_sales_account
                    )
                    sales_account_display = f"{account.account_code} - {account.account_name}"
                except XeroAccounts.DoesNotExist:
                    # If account not found, just show the code
                    sales_account_display = project.xero_sales_account
            
            # Generate background URL - use relative URL for media files
            background_url = ''
            if project.background:
                # Use just the path, not absolute URI - browser will resolve relative to current host
                background_url = project.background.url
                logger.info(f"Project '{project.project}' background URL: {background_url}")
            else:
                logger.info(f"Project '{project.project}' has no background image")
            
            projects_data.append({
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type,
                'project_type_display': project.get_project_type_display(),
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'xero_sales_account_display': sales_account_display,
                'background_url': background_url
            })
        
        return JsonResponse({
            'status': 'success',
            'projects': projects_data
        })
        
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting projects: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_project(request, project_pk):
    """
    Update an existing project
    
    Expected POST data:
    - project_name: str (optional)
    - xero_sales_account: str (optional)
    - background: file (optional)
    """
    try:
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Update project name if provided
        project_name = request.POST.get('project_name', '').strip()
        if project_name:
            project.project = project_name
        
        # Update sales account if provided
        xero_sales_account = request.POST.get('xero_sales_account', '').strip()
        if xero_sales_account:
            project.xero_sales_account = xero_sales_account
        elif 'xero_sales_account' in request.POST:
            # Empty string provided, clear the field
            project.xero_sales_account = None
        
        # Handle background image upload if provided
        if 'background' in request.FILES:
            background_file = request.FILES['background']
            
            # Validate file type
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            file_ext = background_file.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'
                }, status=400)
            
            # Delete old background if exists
            if project.background:
                project.background.delete(save=False)
            
            project.background = background_file
        
        project.save()
        
        logger.info(f"Updated project: {project.project} (pk={project.projects_pk})")
        
        # Get sales account display name (code - name)
        sales_account_display = ''
        if project.xero_sales_account and project.xero_instance:
            try:
                account = XeroAccounts.objects.get(
                    xero_instance=project.xero_instance,
                    account_code=project.xero_sales_account
                )
                sales_account_display = f"{account.account_code} - {account.account_name}"
            except XeroAccounts.DoesNotExist:
                # If account not found, just show the code
                sales_account_display = project.xero_sales_account
        
        # Generate background URL - use relative URL for media files
        background_url = ''
        if project.background:
            # Use just the path, not absolute URI - browser will resolve relative to current host
            background_url = project.background.url
        
        # Return updated project data
        return JsonResponse({
            'status': 'success',
            'message': 'Project updated successfully',
            'project': {
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type,
                'project_type_display': project.get_project_type_display(),
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'xero_sales_account_display': sales_account_display,
                'background_url': background_url
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating project: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def toggle_project_archive(request, project_pk):
    """
    Toggle the archived status of a project
    
    Expected POST data:
    - archived: 0 or 1
    """
    try:
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get new archived status
        archived = request.POST.get('archived', '0')
        project.archived = 1 if archived == '1' else 0
        project.save()
        
        action = 'archived' if project.archived == 1 else 'unarchived'
        logger.info(f"Project {action}: {project.project} (pk={project.projects_pk})")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Project {action} successfully',
            'archived': project.archived
        })
        
    except Exception as e:
        logger.error(f"Error toggling project archive: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error toggling archive status: {str(e)}'
        }, status=500)
