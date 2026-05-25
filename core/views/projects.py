"""
Project management views.

These endpoints all mutate first-class business state (projects, costings,
items). They require an authenticated user. See core/views/_helpers.py for
the decorator definitions and BEST_PRACTICE_AUDIT.md (P-3) for the broader
auth migration plan.
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.models import (
    Projects, ProjectTypes, XeroInstances, XeroAccounts, Categories,
    Costing, Units, HC_claim_allocations,
)
from ._helpers import api_login_required

logger = logging.getLogger(__name__)


@api_login_required
@require_http_methods(["POST"])
def create_project(request):
    """
    Create a new project
    
    Expected POST data:
    - project_name: str (required)
    - project_type: str (required)
    - xero_sales_account: str (optional)
    
    xero_instance is set from ProjectTypes.xero_instance for the selected project_type.
    Xero account for BOM lines are copied from template Costings.
    """
    try:
        # Get form data
        project_name = request.POST.get('project_name', '').strip()
        project_type = request.POST.get('project_type', '')
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
        
        if not project_type:
            return JsonResponse({
                'status': 'error',
                'message': 'Project type is required'
            }, status=400)
        
        # Validate project type and get ProjectTypes object
        project_type_obj = ProjectTypes.objects.filter(project_type=project_type).first()
        if not project_type_obj:
            valid_types = list(ProjectTypes.objects.values_list('project_type', flat=True))
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid project type. Must be one of: {", ".join(valid_types)}'
            }, status=400)
        
        # Get xero_instance from the project type
        xero_instance = project_type_obj.xero_instance
        
        # Create project (always starts in tender mode)
        project = Projects(
            project=project_name,
            project_type=project_type_obj,
            xero_instance=xero_instance,
            xero_sales_account=xero_sales_account,
            manager=manager,
            manager_email=manager_email,
            contracts_admin_emails=contracts_admin_emails,
            project_status=1  # 1=tender, 2=execution
        )
        
        project.save()
        
        logger.info(f"Created project: {project.project} (pk={project.projects_pk})")
        
        # Copy template data from rates tables based on project_type
        # Find template categories (where project is null and project_type matches)
        # Use case-insensitive match since CharField may have different casing
        template_categories = Categories.objects.filter(
            project__isnull=True,
            project_type__iexact=project_type
        ).order_by('order_in_list')
        
        logger.info(f"Found {template_categories.count()} template categories for project_type '{project_type}'")
        
        # Map old category pks to new category objects for item duplication
        category_pk_map = {}
        
        for template_cat in template_categories:
            new_category = Categories.objects.create(
                project=project,
                project_type=None,  # Clear project_type for project-specific data
                division=getattr(template_cat, 'division', 0),
                category=template_cat.category,
                invoice_category=template_cat.invoice_category,
                order_in_list=template_cat.order_in_list
            )
            category_pk_map[template_cat.categories_pk] = new_category
            logger.info(f"Copied category '{template_cat.category}' to project {project.projects_pk}")
        
        # Find template items (where project is null and project_type matches)
        # Use case-insensitive match since CharField may have different casing
        template_items = Costing.objects.filter(
            project__isnull=True,
            project_type__iexact=project_type
        ).order_by('category__order_in_list', 'order_in_list')
        
        logger.info(f"Found {template_items.count()} template items for project_type '{project_type}'")
        
        for template_item in template_items:
            # Get the new category for this item
            new_category = category_pk_map.get(template_item.category_id)
            if new_category:
                Costing.objects.create(
                    project=project,
                    project_type=None,  # Clear project_type for project-specific data
                    category=new_category,
                    item=template_item.item,
                    order_in_list=template_item.order_in_list,
                    unit=template_item.unit,
                    rate=template_item.rate,
                    operator=template_item.operator,
                    operator_value=template_item.operator_value,
                    xero_account_code=template_item.xero_account_code or '',
                    contract_budget=0,
                    uncommitted_amount=0,
                    fixed_on_site=0,
                    sc_invoiced=0,
                    sc_paid=0
                )
                logger.info(f"Copied item '{template_item.item}' to project {project.projects_pk}")
        
        # Find template units (where project is null and project_type matches)
        # Use case-insensitive match since CharField may have different casing
        template_units = Units.objects.filter(
            project__isnull=True,
            project_type__iexact=project_type
        ).order_by('order_in_list')
        
        logger.info(f"Found {template_units.count()} template units for project_type '{project_type}'")
        
        for template_unit in template_units:
            Units.objects.create(
                project=project,
                project_type=None,  # Clear project_type for project-specific data
                unit_name=template_unit.unit_name,
                order_in_list=template_unit.order_in_list
            )
            logger.info(f"Copied unit '{template_unit.unit_name}' to project {project.projects_pk}")
        
        # Always create Internal/Margin category for all new projects
        internal_category = Categories.objects.create(
            project=project,
            division=-10,
            category='Internal',
            invoice_category='Internal',
            order_in_list=-2
        )
        logger.info(f"Created Internal category for project {project.projects_pk}")
        
        Costing.objects.create(
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
        logger.info(f"Created Margin item for project {project.projects_pk}")
        
        # Create Labour category for staff hours allocation (only if not already copied from template)
        existing_labour = Categories.objects.filter(project=project, category__iexact='Labour').first()
        if not existing_labour:
            labour_category = Categories.objects.create(
                project=project,
                division=-5,
                category='Labour',
                invoice_category='Labour',
                order_in_list=-1
            )
            logger.info(f"Created Labour category for project {project.projects_pk}")
        else:
            logger.info(f"Labour category already exists from template for project {project.projects_pk} (pk={existing_labour.categories_pk})")

        # Always create Unexpected Line Items category + matching costing
        # (added 2026-05-25). This is a special division (-15) like
        # Internal/Labour: auto-seeded on every project, undeletable,
        # locked to its single same-named costing. Exposed to staff
        # hours and stocktake snaps for execution-mode projects, and
        # the "Committed" dropdown in contract_budget aggregates
        # bills + snaps + staff wages on this single costing PK.
        # Idempotent: skip if a ULI category already exists (e.g. from
        # a partially-completed prior creation or a backfill migration).
        existing_uli = Categories.objects.filter(
            project=project, division=Categories.DIVISION_ULI
        ).first()
        if not existing_uli:
            uli_category = Categories.objects.create(
                project=project,
                division=Categories.DIVISION_ULI,
                category='Unexpected Line Items',
                invoice_category='Unexpected Line Items',
                order_in_list=-3,  # sorts above Internal (-2) and Labour (-1)
            )
            Costing.objects.create(
                project=project,
                category=uli_category,
                item='Unexpected Line Items',
                order_in_list=1,
                xero_account_code='',
                contract_budget=0,
                uncommitted_amount=0,
                fixed_on_site=0,
                sc_invoiced=0,
                sc_paid=0,
                tender_or_execution=1,  # tender; execution copy is created
                                        # by fix_contract_budget like every
                                        # other costing.
            )
            logger.info(
                f"Created Unexpected Line Items category + costing for project {project.projects_pk}"
            )
        else:
            logger.info(
                f"ULI category already exists for project {project.projects_pk} (pk={existing_uli.categories_pk})"
            )

        # Return project data
        return JsonResponse({
            'status': 'success',
            'message': 'Project created successfully',
            'project': {
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type.project_type if project.project_type else None,
                'project_type_display': project.project_type.project_type if project.project_type else '',
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'project_status': project.project_status
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Error creating project'
        }, status=500)


@api_login_required
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
            
            projects_data.append({
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type.project_type if project.project_type else None,
                'project_type_display': project.project_type.project_type if project.project_type else '',
                'rates_based': project.project_type.rates_based if project.project_type else 0,
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'xero_sales_account_display': sales_account_display,
                'manager': project.manager or '',
                'manager_email': project.manager_email or '',
                'contracts_admin_emails': project.contracts_admin_emails or '',
                'project_status': project.project_status,
                'is_revenue_project': bool(project.is_revenue_project),
            })
        
        return JsonResponse({
            'status': 'success',
            'projects': projects_data
        })
        
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Error getting projects'
        }, status=500)


@api_login_required
@require_http_methods(["POST"])
def update_project(request, project_pk):
    """
    Update an existing project
    
    Expected POST data:
    - project_name: str (optional)
    - project_type: str (optional) - if changed, xero_instance is updated from ProjectTypes
    - xero_sales_account: str (optional)
    - manager: str (optional)
    - manager_email: str (optional)
    - contracts_admin_emails: str (optional)
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
        
        # Update project type if provided - also updates xero_instance
        project_type = request.POST.get('project_type', '').strip()
        if project_type:
            project_type_obj = ProjectTypes.objects.filter(project_type=project_type).first()
            if project_type_obj:
                project.project_type = project_type_obj
                project.xero_instance = project_type_obj.xero_instance
        
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

        # Revenue Project flag — guard the True->False transition.
        # Allowed transitions:
        #   True  -> True   no-op
        #   True  -> False  ONLY if no HC_claim_allocations point at any
        #                   Costing belonging to this project. Existing
        #                   Hc_variation rows are *not* a blocker — they
        #                   simply get relabelled "Scope Variation" in the UI.
        #   False -> True   always allowed
        #   False -> False  no-op
        if 'is_revenue_project' in request.POST:
            raw = request.POST.get('is_revenue_project', '').strip().lower()
            new_value = raw in ('1', 'true', 'yes', 'on')
            if project.is_revenue_project and not new_value:
                has_claims = HC_claim_allocations.objects.filter(
                    item__project=project
                ).exists()
                if has_claims:
                    return JsonResponse({
                        'status': 'error',
                        'message': (
                            "Cannot set this project to non-revenue: at least "
                            "one HC claim has already been raised against it. "
                            "Delete the HC claim(s) first if you really need "
                            "to flip this flag."
                        ),
                    }, status=400)
            project.is_revenue_project = new_value

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
        
        # Return updated project data
        return JsonResponse({
            'status': 'success',
            'message': 'Project updated successfully',
            'project': {
                'projects_pk': project.projects_pk,
                'project': project.project,
                'project_type': project.project_type.project_type if project.project_type else None,
                'project_type_display': project.project_type.project_type if project.project_type else '',
                'xero_instance_pk': project.xero_instance.xero_instance_pk if project.xero_instance else None,
                'xero_instance_name': project.xero_instance.xero_name if project.xero_instance else '',
                'xero_sales_account': project.xero_sales_account or '',
                'xero_sales_account_display': sales_account_display,
                'manager': project.manager or '',
                'manager_email': project.manager_email or '',
                'contracts_admin_emails': project.contracts_admin_emails or '',
                'project_status': project.project_status,
                'is_revenue_project': bool(project.is_revenue_project),
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating project: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Error updating project'
        }, status=500)


@api_login_required
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
        logger.info(f"Archive request for project {project_pk}: received archived={archived}")
        
        project.archived = 1 if archived == '1' else 0
        project.save()
        
        logger.info(f"Project {project.project} archived status updated to: {project.archived}")
        
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
            'message': 'Error toggling archive status'
        }, status=500)


@api_login_required
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

        # Prevent deletion of "Unexpected Line Items" — the auto-seeded
        # contingency category is fixed for every project (added 2026-05-25).
        if category.division == Categories.DIVISION_ULI:
            return JsonResponse({
                'status': 'error',
                'message': 'The Unexpected Line Items category cannot be deleted'
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
            'message': 'Error deleting category'
        }, status=500)


@api_login_required
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

        # Prevent deletion of the auto-seeded ULI costing (added 2026-05-25).
        # The ULI category is locked to its single same-named costing.
        if item.category and item.category.division == Categories.DIVISION_ULI:
            return JsonResponse({
                'status': 'error',
                'message': 'The Unexpected Line Items costing cannot be deleted',
            }, status=400)

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
            'message': 'Error deleting item'
        }, status=500)


@api_login_required
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
            'message': 'Error updating committed amount'
        }, status=500)
