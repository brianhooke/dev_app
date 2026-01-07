"""
Rates views for managing rates by project type.
"""

import json
import logging
import traceback
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt

from core.models import Categories, Costing, Units, Projects

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET"])
def get_rates_data(request):
    """
    Get all rates data (categories, items, units) filtered by project_type.
    Returns data for populating the List dropdowns and the RHS table.
    
    Note: Temporarily removed @login_required to debug session issue.
    The page itself (dashboard) requires login, so this data is still protected.
    """
    logger.info("[get_rates_data] Endpoint called")
    logger.info(f"[get_rates_data] User authenticated: {request.user.is_authenticated}")
    project_type = request.GET.get('project_type', '')
    logger.info(f"[get_rates_data] project_type parameter: '{project_type}'")
    
    if not project_type:
        logger.warning("[get_rates_data] Missing project_type parameter")
        return JsonResponse({
            'status': 'error',
            'message': 'project_type is required'
        }, status=400)
    
    # Validate project_type
    valid_types = [choice[0] for choice in Projects.PROJECT_TYPE_CHOICES]
    logger.info(f"[get_rates_data] Valid project types: {valid_types}")
    if project_type not in valid_types:
        logger.warning(f"[get_rates_data] Invalid project_type: {project_type}")
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid project_type. Must be one of: {", ".join(valid_types)}'
        }, status=400)
    
    try:
        logger.info(f"[get_rates_data] Querying categories for project_type={project_type}, project__isnull=True")
        # Get template categories for this project type (project=null means template data)
        categories = Categories.objects.filter(
            project__isnull=True,
            project_type=project_type
        ).order_by('order_in_list').values(
            'categories_pk', 'category', 'order_in_list'
        )
        categories_count = categories.count()
        logger.info(f"[get_rates_data] Found {categories_count} categories")
        
        logger.info(f"[get_rates_data] Querying items for project_type={project_type}, project__isnull=True")
        # Get template items (costings) for this project type (project=null means template data)
        items = Costing.objects.filter(
            project__isnull=True,
            project_type=project_type
        ).select_related('category', 'unit').order_by(
            'category__order_in_list', 'order_in_list'
        ).values(
            'costing_pk', 'item', 'order_in_list',
            'category__categories_pk', 'category__category',
            'unit__unit_name', 'operator', 'operator_value'
        )
        items_count = items.count()
        logger.info(f"[get_rates_data] Found {items_count} items")
        
        logger.info(f"[get_rates_data] Querying units for project_type={project_type}, project__isnull=True")
        # Get template units for this project type (project=null means template data)
        units = Units.objects.filter(
            project__isnull=True,
            project_type=project_type
        ).order_by('order_in_list').values(
            'unit_pk', 'unit_name', 'order_in_list'
        )
        units_count = units.count()
        logger.info(f"[get_rates_data] Found {units_count} units")
        
        logger.info("[get_rates_data] Formatting categories list")
        # Format categories for response
        categories_list = [
            {
                'categories_pk': c['categories_pk'],
                'category': c['category'],
                'order_in_list': int(c['order_in_list']) if c['order_in_list'] else 0
            }
            for c in categories
        ]
        logger.info(f"[get_rates_data] Formatted {len(categories_list)} categories")
        
        logger.info("[get_rates_data] Formatting items list")
        # Format items for response
        items_list = [
            {
                'costing_pk': i['costing_pk'],
                'item': i['item'],
                'order_in_list': int(i['order_in_list']) if i['order_in_list'] else 0,
                'category_pk': i['category__categories_pk'],
                'category': i['category__category'],
                'unit': i['unit__unit_name'] or '',
                'operator': i['operator'],
                'operator_value': float(i['operator_value']) if i['operator_value'] is not None else None
            }
            for i in items
        ]
        logger.info(f"[get_rates_data] Formatted {len(items_list)} items")
        
        logger.info("[get_rates_data] Formatting units list")
        # Format units for response
        units_list = [
            {
                'unit_pk': u['unit_pk'],
                'unit_name': u['unit_name'],
                'order_in_list': u['order_in_list']
            }
            for u in units
        ]
        logger.info(f"[get_rates_data] Formatted {len(units_list)} units")
        
        logger.info("[get_rates_data] Returning success response")
        return JsonResponse({
            'status': 'success',
            'project_type': project_type,
            'categories': categories_list,
            'items': items_list,
            'units': units_list
        })
        
    except Exception as e:
        logger.error(f"[get_rates_data] Exception occurred: {str(e)}")
        logger.error(f"[get_rates_data] Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_new_category_costing_unit_quantity(request):
    """
    Create a new Category, Costing (Item), or Unit entry.
    Handles order_in_list reordering - if inserting at a position that exists,
    bump existing entries at that position and above up by 1.
    
    Supports two modes:
    - project_type mode: Creates template data (project=null, project_type=value)
    - project mode: Creates project-specific data (project=value, project_type=null)
    
    Note: Temporarily removed @login_required to debug session issue.
    The page itself (dashboard) requires login, so this data is still protected.
    
    Expected JSON payload:
    {
        "model_type": "category" | "item" | "unit",
        "project_type": "general" | ... (for template mode),
        "project_pk": 123 (for project mode),
        "name": "the name/value",
        "order_in_list": 1,
        "category_pk": 123  // only for items
    }
    """
    logger.info("[create_new_category_costing_unit_quantity] Endpoint called")
    try:
        data = json.loads(request.body)
        
        model_type = data.get('model_type', '').lower()
        project_type = data.get('project_type', '')
        project_pk = data.get('project_pk')
        name = data.get('name', '').strip()
        order_in_list = int(data.get('order_in_list', 1))
        category_pk = data.get('category_pk')  # Only for items
        
        # Validate required fields
        if not model_type:
            return JsonResponse({'status': 'error', 'message': 'model_type is required'}, status=400)
        if not project_type and not project_pk:
            return JsonResponse({'status': 'error', 'message': 'Either project_type or project_pk is required'}, status=400)
        if not name:
            return JsonResponse({'status': 'error', 'message': 'name is required'}, status=400)
        
        # Validate model_type
        valid_model_types = ['category', 'item', 'unit']
        if model_type not in valid_model_types:
            return JsonResponse({
                'status': 'error',
                'message': f'Invalid model_type. Must be one of: {", ".join(valid_model_types)}'
            }, status=400)
        
        # Determine mode and get project if needed
        project = None
        if project_pk:
            # Project mode - creating project-specific data
            try:
                project = Projects.objects.get(projects_pk=project_pk)
            except Projects.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
            project_type = None  # Clear project_type for project-specific data
        else:
            # Template mode - validate project_type
            valid_project_types = [choice[0] for choice in Projects.PROJECT_TYPE_CHOICES]
            if project_type not in valid_project_types:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Invalid project_type. Must be one of: {", ".join(valid_project_types)}'
                }, status=400)
        
        # Item requires category_pk
        if model_type == 'item' and not category_pk:
            return JsonResponse({'status': 'error', 'message': 'category_pk is required for items'}, status=400)
        
        with transaction.atomic():
            if model_type == 'category':
                # Build filter for reordering
                if project:
                    reorder_filter = {'project': project, 'order_in_list__gte': order_in_list}
                else:
                    reorder_filter = {'project__isnull': True, 'project_type': project_type, 'order_in_list__gte': order_in_list}
                
                Categories.objects.filter(**reorder_filter).update(order_in_list=F('order_in_list') + 1)
                
                # Create new category
                new_entry = Categories.objects.create(
                    category=name,
                    project=project,
                    project_type=project_type,
                    order_in_list=order_in_list,
                    division=0,
                    invoice_category=name
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Category created successfully',
                    'pk': new_entry.categories_pk,
                    'model_type': model_type
                })
            
            elif model_type == 'item':
                # Get the category
                try:
                    category = Categories.objects.get(categories_pk=category_pk)
                except Categories.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Category not found'}, status=404)
                
                # Build filter for reordering
                if project:
                    reorder_filter = {'project': project, 'category': category, 'order_in_list__gte': order_in_list}
                else:
                    reorder_filter = {'project__isnull': True, 'project_type': project_type, 'category': category, 'order_in_list__gte': order_in_list}
                
                Costing.objects.filter(**reorder_filter).update(order_in_list=F('order_in_list') + 1)
                
                # Create new item (costing)
                new_entry = Costing.objects.create(
                    item=name,
                    project=project,
                    project_type=project_type,
                    category=category,
                    order_in_list=order_in_list,
                    xero_account_code='',
                    contract_budget=0,
                    uncommitted_amount=0,
                    fixed_on_site=0,
                    sc_invoiced=0,
                    sc_paid=0
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Item created successfully',
                    'pk': new_entry.costing_pk,
                    'model_type': model_type
                })
            
            elif model_type == 'unit':
                # Build filter for reordering
                if project:
                    reorder_filter = {'project': project, 'order_in_list__gte': order_in_list}
                else:
                    reorder_filter = {'project__isnull': True, 'project_type': project_type, 'order_in_list__gte': order_in_list}
                
                Units.objects.filter(**reorder_filter).update(order_in_list=F('order_in_list') + 1)
                
                # Create new unit
                new_entry = Units.objects.create(
                    unit_name=name,
                    project=project,
                    project_type=project_type,
                    order_in_list=order_in_list
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Unit created successfully',
                    'pk': new_entry.unit_pk,
                    'model_type': model_type
                })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid value: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_category_costing_order_in_list(request):
    """
    Update order_in_list for a Category or Costing (Item) after drag/drop.
    Handles reordering - shifts other entries as needed.
    
    For items, also handles moving between categories.
    
    Expected JSON payload:
    {
        "type": "category" | "item",
        "project_type": "general" | "development" | "construction" | "precast" | "pods",
        "pk": 123,  // categories_pk or costing_pk
        "new_order": 2,
        "new_category_pk": 456  // only for items, required if moving between categories
    }
    """
    try:
        data = json.loads(request.body)
        
        entry_type = data.get('type', '').lower()
        project_type = data.get('project_type', '')
        pk = data.get('pk')
        new_order = int(data.get('new_order', 1))
        new_category_pk = data.get('new_category_pk')  # Only for items
        
        # Validate required fields
        if entry_type not in ['category', 'item']:
            return JsonResponse({'status': 'error', 'message': 'type must be "category" or "item"'}, status=400)
        if not project_type:
            return JsonResponse({'status': 'error', 'message': 'project_type is required'}, status=400)
        if not pk:
            return JsonResponse({'status': 'error', 'message': 'pk is required'}, status=400)
        
        with transaction.atomic():
            if entry_type == 'category':
                # Get the category being moved
                try:
                    category = Categories.objects.get(categories_pk=pk, project_type=project_type)
                except Categories.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Category not found'}, status=404)
                
                old_order = int(category.order_in_list)
                
                if old_order == new_order:
                    return JsonResponse({'status': 'success', 'message': 'No change needed'})
                
                # Reorder other categories
                if old_order < new_order:
                    # Moving down: shift entries between old+1 and new up (decrement)
                    Categories.objects.filter(
                        project_type=project_type,
                        order_in_list__gt=old_order,
                        order_in_list__lte=new_order
                    ).update(order_in_list=F('order_in_list') - 1)
                else:
                    # Moving up: shift entries between new and old-1 down (increment)
                    Categories.objects.filter(
                        project_type=project_type,
                        order_in_list__gte=new_order,
                        order_in_list__lt=old_order
                    ).update(order_in_list=F('order_in_list') + 1)
                
                # Update the moved category
                category.order_in_list = new_order
                category.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Category order updated'
                })
            
            elif entry_type == 'item':
                # Get the item being moved
                try:
                    item = Costing.objects.get(costing_pk=pk, project_type=project_type)
                except Costing.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
                
                old_order = int(item.order_in_list)
                old_category_pk = item.category_id
                
                # Determine if moving within same category or to a new one
                moving_categories = new_category_pk and int(new_category_pk) != old_category_pk
                
                if moving_categories:
                    # Get new category
                    try:
                        new_category = Categories.objects.get(categories_pk=new_category_pk)
                    except Categories.DoesNotExist:
                        return JsonResponse({'status': 'error', 'message': 'Target category not found'}, status=404)
                    
                    # Close the gap in the old category (decrement items after old position)
                    Costing.objects.filter(
                        project_type=project_type,
                        category_id=old_category_pk,
                        order_in_list__gt=old_order
                    ).update(order_in_list=F('order_in_list') - 1)
                    
                    # Make room in new category (increment items at and after new position)
                    Costing.objects.filter(
                        project_type=project_type,
                        category_id=new_category_pk,
                        order_in_list__gte=new_order
                    ).update(order_in_list=F('order_in_list') + 1)
                    
                    # Update the item
                    item.category = new_category
                    item.order_in_list = new_order
                    item.save()
                else:
                    # Moving within same category
                    if old_order == new_order:
                        return JsonResponse({'status': 'success', 'message': 'No change needed'})
                    
                    # Log all items in this category for debugging
                    all_items = list(Costing.objects.filter(
                        project_type=project_type,
                        category_id=old_category_pk
                    ).values('costing_pk', 'item', 'order_in_list').order_by('order_in_list'))
                    print(f"[Reorder] BEFORE - Items in category {old_category_pk}: {all_items}")
                    print(f"[Reorder] Moving item pk={pk} from order={old_order} to order={new_order}")
                    
                    if old_order < new_order:
                        # Moving down: shift entries between old+1 and new up (decrement)
                        affected = Costing.objects.filter(
                            project_type=project_type,
                            category_id=old_category_pk,
                            order_in_list__gt=old_order,
                            order_in_list__lte=new_order
                        )
                        affected_list = list(affected.values('costing_pk', 'order_in_list'))
                        print(f"[Reorder] Moving DOWN - will shift these items by -1: {affected_list}")
                        affected.update(order_in_list=F('order_in_list') - 1)
                    else:
                        # Moving up: shift entries between new and old-1 down (increment)
                        affected = Costing.objects.filter(
                            project_type=project_type,
                            category_id=old_category_pk,
                            order_in_list__gte=new_order,
                            order_in_list__lt=old_order
                        )
                        affected_list = list(affected.values('costing_pk', 'order_in_list'))
                        print(f"[Reorder] Moving UP - will shift these items by +1: {affected_list}")
                        affected.update(order_in_list=F('order_in_list') + 1)
                    
                    # Update the item
                    item.order_in_list = new_order
                    item.save()
                    
                    # Log final state
                    all_items_after = list(Costing.objects.filter(
                        project_type=project_type,
                        category_id=old_category_pk
                    ).values('costing_pk', 'item', 'order_in_list').order_by('order_in_list'))
                    print(f"[Reorder] AFTER - Items in category {old_category_pk}: {all_items_after}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Item order updated'
                })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid value: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_item_unit(request):
    """
    Update the unit for a Costing (Item).
    
    Expected JSON payload:
    {
        "item_pk": 123,
        "unit_pk": 456 (or null to clear),
        "project_type": "construction"
    }
    """
    try:
        data = json.loads(request.body)
        
        item_pk = data.get('item_pk')
        unit_pk = data.get('unit_pk')
        
        if not item_pk:
            return JsonResponse({'status': 'error', 'message': 'item_pk is required'}, status=400)
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk)
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
        
        # Get the unit if specified
        if unit_pk:
            try:
                unit = Units.objects.get(unit_pk=unit_pk)
                item.unit = unit
            except Units.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Unit not found'}, status=404)
        else:
            item.unit = None
        
        item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_item_operator(request):
    """
    Update the operator for a Costing (Item).
    
    Expected JSON payload:
    {
        "item_pk": 123,
        "operator": 1 (multiply) or 2 (divide) or null
    }
    """
    try:
        data = json.loads(request.body)
        
        item_pk = data.get('item_pk')
        operator = data.get('operator')
        
        if not item_pk:
            return JsonResponse({'status': 'error', 'message': 'item_pk is required'}, status=400)
        
        # Validate operator value
        if operator is not None and operator not in [1, 2]:
            return JsonResponse({'status': 'error', 'message': 'operator must be 1 (multiply) or 2 (divide)'}, status=400)
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk)
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
        
        item.operator = operator
        item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Operator updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_item_operator_value(request):
    """
    Update the operator_value for a Costing (Item).
    
    Expected JSON payload:
    {
        "item_pk": 123,
        "operator_value": 1.23456 (up to 5dp) or null
    }
    """
    try:
        data = json.loads(request.body)
        
        item_pk = data.get('item_pk')
        operator_value = data.get('operator_value')
        
        if not item_pk:
            return JsonResponse({'status': 'error', 'message': 'item_pk is required'}, status=400)
        
        # Get the item
        try:
            item = Costing.objects.get(costing_pk=item_pk)
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
        
        # Convert to Decimal if provided
        if operator_value is not None:
            from decimal import Decimal, ROUND_HALF_UP
            operator_value = Decimal(str(operator_value)).quantize(Decimal('0.00001'), rounding=ROUND_HALF_UP)
        
        item.operator_value = operator_value
        item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Operator value updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_category_name(request):
    """
    Update the name of a Category.
    
    Expected JSON payload:
    {
        "pk": 123,
        "name": "New Category Name"
    }
    """
    try:
        data = json.loads(request.body)
        
        pk = data.get('pk')
        name = data.get('name', '').strip()
        
        if not pk:
            return JsonResponse({'status': 'error', 'message': 'pk is required'}, status=400)
        if not name:
            return JsonResponse({'status': 'error', 'message': 'name is required'}, status=400)
        
        try:
            category = Categories.objects.get(categories_pk=pk)
        except Categories.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Category not found'}, status=404)
        
        category.category = name
        category.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Category name updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def update_item_name(request):
    """
    Update the name of a Costing (Item).
    
    Expected JSON payload:
    {
        "pk": 123,
        "name": "New Item Name"
    }
    """
    try:
        data = json.loads(request.body)
        
        pk = data.get('pk')
        name = data.get('name', '').strip()
        
        if not pk:
            return JsonResponse({'status': 'error', 'message': 'pk is required'}, status=400)
        if not name:
            return JsonResponse({'status': 'error', 'message': 'name is required'}, status=400)
        
        try:
            item = Costing.objects.get(costing_pk=pk)
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
        
        item.item = name
        item.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item name updated successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
