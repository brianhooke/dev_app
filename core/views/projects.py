"""
Project management views
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from core.models import Projects, XeroInstances, XeroAccounts, Categories, Costing

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
        manager = request.POST.get('manager', '').strip() or None
        manager_email = request.POST.get('manager_email', '').strip() or None
        contracts_admin_emails = request.POST.get('contracts_admin_emails', '').strip() or None
        
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
            xero_sales_account=xero_sales_account,
            manager=manager,
            manager_email=manager_email,
            contracts_admin_emails=contracts_admin_emails
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
        
        # Auto-create "Internal" category with order_in_list=0
        internal_category = Categories.objects.create(
            project=project,
            category='Internal',
            invoice_category='Internal',
            order_in_list=0,
            division=0
        )
        logger.info(f"Created Internal category for project {project.projects_pk}")
        
        # Auto-create "Margin" item within Internal category with order_in_list=1
        margin_item = Costing.objects.create(
            project=project,
            category=internal_category,
            item='Margin',
            order_in_list=1,
            xero_account_code='',
            contract_budget=0,
            uncommitted_amount=0,
            fixed_on_site=0,
            sc_invoiced=0,
            sc_paid=0
        )
        logger.info(f"Created Margin item in Internal category for project {project.projects_pk}")
        
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
                'background_url': background_url,
                'project_status': project.project_status
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
                'manager': project.manager or '',
                'manager_email': project.manager_email or '',
                'contracts_admin_emails': project.contracts_admin_emails or '',
                'background_url': background_url,
                'project_status': project.project_status
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
    - manager: str (optional)
    - manager_email: str (optional)
    - contracts_admin_emails: str (optional)
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
        
        # Update Xero instance if provided
        xero_instance_pk = request.POST.get('xero_instance_pk', '').strip()
        if xero_instance_pk:
            try:
                xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_pk)
                project.xero_instance = xero_instance
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid Xero instance'
                }, status=400)
        
        # Update sales account if provided
        xero_sales_account = request.POST.get('xero_sales_account', '').strip()
        if xero_sales_account:
            project.xero_sales_account = xero_sales_account
        elif 'xero_sales_account' in request.POST:
            # Empty string provided, clear the field
            project.xero_sales_account = None
        
        # Update manager fields if provided
        manager = request.POST.get('manager', '').strip()
        if manager:
            project.manager = manager
        elif 'manager' in request.POST:
            project.manager = None
        
        manager_email = request.POST.get('manager_email', '').strip()
        if manager_email:
            project.manager_email = manager_email
        elif 'manager_email' in request.POST:
            project.manager_email = None
        
        contracts_admin_emails = request.POST.get('contracts_admin_emails', '').strip()
        if contracts_admin_emails:
            project.contracts_admin_emails = contracts_admin_emails
        elif 'contracts_admin_emails' in request.POST:
            project.contracts_admin_emails = None
        
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
                'manager': project.manager or '',
                'manager_email': project.manager_email or '',
                'contracts_admin_emails': project.contracts_admin_emails or '',
                'background_url': background_url,
                'project_status': project.project_status
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


@csrf_exempt
@require_http_methods(["POST"])
def delete_category(request, project_pk, category_pk):
    """
    Delete a category and all its items (cascade delete).
    Cannot delete the "Internal" category.
    
    Returns:
    - status: success/error
    - message: description
    - items_deleted: count of items deleted with the category
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
        
        # Get the category
        try:
            category = Categories.objects.get(categories_pk=category_pk, project=project)
        except Categories.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Category not found'
            }, status=404)
        
        # Prevent deletion of "Internal" category
        if category.category == 'Internal':
            return JsonResponse({
                'status': 'error',
                'message': 'The Internal category cannot be deleted'
            }, status=400)
        
        # Count items to be deleted
        items_count = Costing.objects.filter(category=category).count()
        
        # Delete the category (Django will cascade delete related items)
        category_name = category.category
        category.delete()
        
        logger.info(f"Deleted category '{category_name}' and {items_count} items for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Category "{category_name}" and {items_count} item(s) deleted successfully',
            'items_deleted': items_count
        })
        
    except Exception as e:
        logger.error(f"Error deleting category: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting category: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_item(request, project_pk, item_pk):
    """
    Delete an item (costing).
    Items within "Internal" category can be deleted.
    
    Returns:
    - status: success/error
    - message: description
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
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk, project=project)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found'
            }, status=404)
        
        # Delete the item
        item_name = item.item
        category_name = item.category.category
        item.delete()
        
        logger.info(f"Deleted item '{item_name}' from category '{category_name}' for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Item "{item_name}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting item: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def update_internal_committed(request):
    """
    Update the committed amount for Internal category items.
    This is a special case where Internal items update committed directly,
    not uncommitted like regular items.
    
    Expected POST data:
    - project_pk: Project primary key
    - item_pk: Costing item primary key
    - committed_amount: New committed amount
    
    Returns:
    - status: success/error
    - message: description
    """
    try:
        # Get POST data
        project_pk = request.POST.get('project_pk')
        item_pk = request.POST.get('item_pk')
        committed_amount = request.POST.get('committed_amount', '0')
        
        # Validate inputs
        if not project_pk or not item_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required parameters'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk, project=project)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found'
            }, status=404)
        
        # Verify this is an Internal category item
        if item.category.category != 'Internal':
            return JsonResponse({
                'status': 'error',
                'message': 'This endpoint is only for Internal category items'
            }, status=400)
        
        # Parse and update committed amount
        try:
            committed_value = float(committed_amount)
        except ValueError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid committed amount'
            }, status=400)
        
        # For Internal items, we store the committed amount in contract_budget
        # since they don't use uncommitted
        item.contract_budget = committed_value
        item.save()
        
        logger.info(f"Updated Internal item '{item.item}' committed amount to {committed_value} for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Committed amount updated successfully',
            'item_pk': item.costing_pk,
            'committed_amount': committed_value
        })
        
    except Exception as e:
        logger.error(f"Error updating internal committed: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error updating committed amount: {str(e)}'
        }, status=500)
