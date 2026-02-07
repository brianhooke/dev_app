"""
HC Variations-related views.

Template Rendering:
1. hc_variations_view - Render HC variations section template (supports project_pk query param)
"""

import json
import logging

from django.db import models
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from ..models import Categories, Costing, Hc_variation, Hc_variation_allocations, Projects, Units

logger = logging.getLogger(__name__)


def hc_variations_view(request):
    """Render the HC variations section template.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/hc_variations/?project_pk=123
    
    Returns construction-specific columns when project_type == 'construction'.
    """
    project_pk = request.GET.get('project_pk')
    is_construction = False
    project_status = 1  # Default to tender
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            # Use rates_based flag from ProjectTypes instead of hardcoded project type names
            is_construction = (project.project_type and project.project_type.rates_based == 1)
            project_status = project.project_status if project.project_status in [1, 2] else 1
        except Projects.DoesNotExist:
            pass
    
    # Main table columns - HC Variations list
    main_table_columns = [
        {'header': 'Date', 'width': '30%', 'sortable': True},
        {'header': '$ Amount', 'width': '25%', 'sortable': True},
        {'header': 'Update', 'width': '15%', 'class': 'col-action-first'},
        {'header': 'Delete', 'width': '10%', 'class': 'col-action'},
    ]
    
    # Allocations columns differ by project type
    if is_construction:
        allocations_columns = [
            {'header': 'Item', 'width': '25%'},
            {'header': 'Unit', 'width': '8%'},
            {'header': 'Qty', 'width': '7%'},
            {'header': 'Rate', 'width': '9%'},
            {'header': '$ Amount', 'width': '11%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '35%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    else:
        allocations_columns = [
            {'header': 'Item', 'width': '40%'},
            {'header': '$ Amount', 'width': '25%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '30%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    
    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
        'project_status': project_status,
        'main_table_columns': main_table_columns,
        'allocations_columns': allocations_columns,
    }
    return render(request, 'core/hc_variations.html', context)


@csrf_exempt
def get_hc_variations(request, project_pk):
    """Get all HC variations for a project."""
    if not project_pk:
        return JsonResponse({'error': 'project_pk required'}, status=400)
    
    try:
        # Get all costing items for this project
        costing_items = Costing.objects.filter(project_id=project_pk)
        costing_pks = list(costing_items.values_list('costing_pk', flat=True))
        
        # Get all variation allocations for these costing items
        allocations = Hc_variation_allocations.objects.filter(
            costing__in=costing_pks
        ).select_related('hc_variation', 'costing')
        
        # Group by variation - use amount from Hc_variation model
        variations_dict = {}
        for alloc in allocations:
            var_pk = alloc.hc_variation.hc_variation_pk
            if var_pk not in variations_dict:
                variations_dict[var_pk] = {
                    'hc_variation_pk': var_pk,
                    'date': alloc.hc_variation.date.isoformat() if alloc.hc_variation.date else None,
                    'total_amount': float(alloc.hc_variation.amount) if alloc.hc_variation.amount else 0,
                    'allocations': []
                }
            
            alloc_data = {
                'hc_variation_allocation_pk': alloc.hc_variation_allocation_pk,
                'costing_pk': alloc.costing.costing_pk,
                'item': alloc.costing.item,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': alloc.unit,
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes or '',
            }
            variations_dict[var_pk]['allocations'].append(alloc_data)
        
        variations_list = list(variations_dict.values())
        return JsonResponse({'status': 'success', 'variations': variations_list})
    
    except Exception as e:
        logger.error(f"Error getting HC variations: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_hc_variation_allocations(request, variation_pk):
    """Get allocations for a specific HC variation."""
    try:
        allocations = Hc_variation_allocations.objects.filter(
            hc_variation_id=variation_pk
        ).select_related('costing', 'costing__unit')
        
        allocations_list = []
        for alloc in allocations:
            allocations_list.append({
                'hc_variation_allocation_pk': alloc.hc_variation_allocation_pk,
                'costing_pk': alloc.costing.costing_pk,
                'item': alloc.costing.item,
                'item_pk': alloc.costing.costing_pk,
                'item_name': alloc.costing.item,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': alloc.unit or (alloc.costing.unit.unit_name if alloc.costing.unit else None),
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes or '',
            })
        
        return JsonResponse({'status': 'success', 'allocations': allocations_list})
    
    except Exception as e:
        logger.error(f"Error getting HC variation allocations: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def _create_new_item_for_variation(project, alloc_data):
    """
    Helper function to create a new category/unit/costing item from variation allocation data.
    
    Args:
        project: The Project object
        alloc_data: Dict containing:
            - new_category_name: str (optional) - Create new category with this name
            - category_name: str (optional) - Use existing category with this name
            - new_item_name: str - The new item name
            - new_unit_name: str (optional) - Create new unit with this name
            - unit: str (optional) - Use existing unit with this name
            - xero_account_code: str - Xero account code
    
    Returns:
        Costing object if created successfully, None otherwise
    """
    try:
        # 1. Get or create category
        new_category_name = alloc_data.get('new_category_name')
        category_name = alloc_data.get('category_name')
        
        if new_category_name:
            # Create new category
            # Get max order_in_list for this project
            max_order = Categories.objects.filter(project=project).aggregate(
                max_order=models.Max('order_in_list')
            )['max_order'] or 0
            
            category = Categories.objects.create(
                project=project,
                category=new_category_name,
                invoice_category=new_category_name,
                order_in_list=max_order + 1,
                division=0
            )
            logger.info(f"Created new category '{new_category_name}' for project {project.projects_pk}")
        elif category_name:
            # Find existing category by name
            category = Categories.objects.filter(
                project=project,
                category__iexact=category_name
            ).first()
            if not category:
                logger.error(f"Category '{category_name}' not found for project {project.projects_pk}")
                return None
        else:
            logger.error("No category specified for new item")
            return None
        
        # 2. Get or create unit (if provided)
        unit_obj = None
        new_unit_name = alloc_data.get('new_unit_name')
        unit_name = alloc_data.get('unit')
        
        if new_unit_name:
            # Create new unit for project
            max_unit_order = Units.objects.filter(project=project).aggregate(
                max_order=models.Max('order_in_list')
            )['max_order'] or 0
            
            unit_obj = Units.objects.create(
                project=project,
                unit_name=new_unit_name,
                order_in_list=max_unit_order + 1
            )
            logger.info(f"Created new unit '{new_unit_name}' for project {project.projects_pk}")
        elif unit_name:
            # Find existing unit by name
            unit_obj = Units.objects.filter(
                project=project,
                unit_name__iexact=unit_name
            ).first()
            # If not found at project level, try project_type level
            if not unit_obj and project.project_type:
                unit_obj = Units.objects.filter(
                    project__isnull=True,
                    project_type=project.project_type,
                    unit_name__iexact=unit_name
                ).first()
        
        # 3. Create the costing item
        item_name = alloc_data.get('new_item_name', '').strip()
        xero_account_code = alloc_data.get('xero_account_code', '')
        
        if not item_name:
            logger.error("No item name provided for new item")
            return None
        
        # Get max order_in_list for items in this category
        max_item_order = Costing.objects.filter(
            project=project,
            category=category
        ).aggregate(max_order=models.Max('order_in_list'))['max_order'] or 0
        
        # Set tender_or_execution based on project_status (1=tender, 2=execution)
        tender_or_execution = project.project_status if project.project_status in [1, 2] else 1
        
        costing = Costing.objects.create(
            project=project,
            category=category,
            item=item_name,
            unit=unit_obj,
            order_in_list=max_item_order + 1,
            xero_account_code=xero_account_code,
            contract_budget=0,
            uncommitted_amount=0,
            fixed_on_site=0,
            sc_invoiced=0,
            sc_paid=0,
            tender_or_execution=tender_or_execution
        )
        
        logger.info(f"Created new item '{item_name}' in category '{category.category}' for project {project.projects_pk}")
        return costing
        
    except Exception as e:
        logger.error(f"Error creating new item for variation: {e}", exc_info=True)
        return None


@csrf_exempt
def save_hc_variation(request):
    """Save a new HC variation with allocations, or update allocations for existing variation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        variation_pk = data.get('pk')  # If provided, this is an update
        allocations_data = data.get('allocations', [])
        
        if variation_pk:
            # UPDATE existing variation's allocations
            try:
                variation = Hc_variation.objects.get(hc_variation_pk=variation_pk)
            except Hc_variation.DoesNotExist:
                return JsonResponse({'error': 'Variation not found'}, status=404)
            
            # Delete existing allocations and recreate
            Hc_variation_allocations.objects.filter(hc_variation=variation).delete()
            
            # Create new allocations
            for alloc_data in allocations_data:
                costing_pk = alloc_data.get('item_pk')
                if not costing_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(costing_pk=costing_pk)
                    
                    # Handle construction mode (qty/rate) vs simple mode (amount)
                    qty = alloc_data.get('qty')
                    rate = alloc_data.get('rate')
                    if qty is not None and rate is not None:
                        amount = float(qty) * float(rate)
                    else:
                        amount = alloc_data.get('amount', 0)
                    
                    Hc_variation_allocations.objects.create(
                        hc_variation=variation,
                        costing=costing,
                        amount=amount,
                        qty=qty,
                        unit=alloc_data.get('unit', ''),
                        rate=rate,
                        notes=alloc_data.get('notes', '')
                    )
                except Costing.DoesNotExist:
                    logger.warning(f"Costing {costing_pk} not found for variation allocation")
            
            logger.info(f"Updated HC variation {variation_pk} with {len(allocations_data)} allocations")
            return JsonResponse({
                'status': 'success',
                'hc_variation_pk': variation.hc_variation_pk
            })
        
        else:
            # CREATE new variation
            project_pk = data.get('project_pk')
            date = data.get('date')
            total_amount = data.get('total_amount', 0)
            
            if not project_pk or not date:
                return JsonResponse({'error': 'project_pk and date required'}, status=400)
            
            # Get the project
            try:
                project = Projects.objects.get(projects_pk=project_pk)
            except Projects.DoesNotExist:
                return JsonResponse({'error': 'Project not found'}, status=404)
            
            # Create the variation with amount
            from datetime import datetime
            variation_date = datetime.strptime(date, '%Y-%m-%d').date()
            variation = Hc_variation.objects.create(date=variation_date, amount=total_amount)
            
            created_items = []
            
            # Create allocations
            for alloc_data in allocations_data:
                is_new_item = alloc_data.get('is_new_item', False)
                
                if is_new_item:
                    # Handle new item creation
                    costing = _create_new_item_for_variation(project, alloc_data)
                    if costing:
                        created_items.append({
                            'costing_pk': costing.costing_pk,
                            'item': costing.item,
                            'category': costing.category.category
                        })
                else:
                    # Existing item
                    costing_pk = alloc_data.get('item_pk')
                    if not costing_pk:
                        continue
                    try:
                        costing = Costing.objects.get(costing_pk=costing_pk)
                    except Costing.DoesNotExist:
                        logger.warning(f"Costing {costing_pk} not found for variation allocation")
                        continue
                
                if costing:
                    # Handle construction mode (qty/rate) vs simple mode (amount)
                    qty = alloc_data.get('qty')
                    rate = alloc_data.get('rate')
                    if qty is not None and rate is not None:
                        amount = float(qty) * float(rate)
                    else:
                        amount = alloc_data.get('amount', 0)
                    
                    Hc_variation_allocations.objects.create(
                        hc_variation=variation,
                        costing=costing,
                        amount=amount,
                        qty=qty,
                        unit=alloc_data.get('unit', ''),
                        rate=rate,
                        notes=alloc_data.get('notes', '')
                    )
            
            logger.info(f"Created HC variation {variation.hc_variation_pk} with {len(allocations_data)} allocations, {len(created_items)} new items")
            return JsonResponse({
                'status': 'success',
                'hc_variation_pk': variation.hc_variation_pk,
                'created_items': created_items
            })
    
    except Exception as e:
        logger.error(f"Error saving HC variation: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_hc_variation(request):
    """Delete an HC variation and its allocations."""
    if request.method != 'DELETE' and request.method != 'POST':
        return JsonResponse({'error': 'DELETE or POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Support pk or hc_variation_pk for consistency with quotes pattern
        variation_pk = data.get('pk') or data.get('hc_variation_pk')
        
        if not variation_pk:
            return JsonResponse({'status': 'error', 'message': 'Variation PK is required'}, status=400)
        
        variation = Hc_variation.objects.get(hc_variation_pk=variation_pk)
        variation.delete()  # Cascades to allocations
        
        logger.info(f"Deleted HC variation {variation_pk}")
        return JsonResponse({'status': 'success', 'message': f'Variation deleted successfully'})
    
    except Hc_variation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Variation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC variation: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_hc_variation_allocation(request, allocation_pk):
    """Update an HC variation allocation."""
    if request.method != 'POST' and request.method != 'PUT':
        return JsonResponse({'error': 'POST or PUT required'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation = Hc_variation_allocations.objects.get(hc_variation_allocation_pk=allocation_pk)
        
        if 'amount' in data:
            allocation.amount = data['amount']
        if 'qty' in data:
            allocation.qty = data['qty']
        if 'rate' in data:
            allocation.rate = data['rate']
        if 'notes' in data:
            allocation.notes = data['notes']
        if 'item_pk' in data:
            allocation.costing_id = data['item_pk']
        
        allocation.save()
        return JsonResponse({'status': 'success'})
    
    except Hc_variation_allocations.DoesNotExist:
        return JsonResponse({'error': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error updating HC variation allocation: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def delete_hc_variation_allocation(request, allocation_pk):
    """Delete an HC variation allocation."""
    if request.method != 'DELETE' and request.method != 'POST':
        return JsonResponse({'error': 'DELETE or POST required'}, status=405)
    
    try:
        allocation = Hc_variation_allocations.objects.get(hc_variation_allocation_pk=allocation_pk)
        allocation.delete()
        return JsonResponse({'status': 'success'})
    
    except Hc_variation_allocations.DoesNotExist:
        return JsonResponse({'error': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting HC variation allocation: {e}")
        return JsonResponse({'error': str(e)}, status=500)
