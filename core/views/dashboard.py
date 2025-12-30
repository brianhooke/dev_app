"""
Dashboard app views.

Response Helpers:
- error_response(message, status) - Standardized error JSON response
- success_response(message, data) - Standardized success JSON response

Dashboard View:
1. dashboard_view - Main dashboard homepage

Contacts Views:
2. verify_contact_details - Save verified contact details to separate verified fields
   Uses validators from core.validators for email, BSB, account, ABN validation
3. pull_xero_contacts - Pull contacts from Xero API, insert/update locally
   Uses loop-based field comparison for efficient updates
4. get_contacts_by_instance - Get ACTIVE contacts with verified status (0/1/2)
   Uses Contact.verified_status model property
5. create_contact - Create contact in Xero + local DB
6. update_contact_details - Update bank details, email, ABN in Xero
7. update_contact_status - Archive/unarchive contact in Xero

Bills Views:
8. send_bill - Send invoice to Xero (Direct mode) or move to Direct (Inbox mode)

Dependencies:
- Validators: core.validators (validate_email, validate_bsb, validate_account_number, validate_abn)
- Xero helpers: core.views.xero (get_xero_auth, format_bank_details, parse_xero_validation_errors)
- Decorator: @handle_xero_request_errors for Xero API exception handling
- Model property: Contact.verified_status for verification status calculation
"""

import json
import logging
import requests
import csv
import uuid
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from core.models import Contacts, SPVData, XeroInstances, Bills, Projects, Bill_allocations, Categories, Costing, Quotes, Quote_allocations, Po_orders, Po_order_detail, Units
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.utils import timezone
from io import StringIO, BytesIO
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from xhtml2pdf import pisa
try:
    from PyPDF2 import PdfMerger, PdfReader
except ImportError:
    from pypdf import PdfMerger, PdfReader
# Import helpers from core.views.xero
from core.views.xero import get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors, get_xero_config
# Import validators
from core.validators import validate_email, validate_bsb, validate_account_number, validate_abn, validate_required_field
# Import contacts config
from core.views.contacts import get_contacts_config

logger = logging.getLogger(__name__)


# Response helper functions
def error_response(message, status=400):
    """Return a standardized error JSON response."""
    return JsonResponse({'status': 'error', 'message': message}, status=status)


def success_response(message, data=None):
    """Return a standardized success JSON response."""
    response = {'status': 'success', 'message': message}
    if data:
        response.update(data)
    return JsonResponse(response)


def dashboard_view(request):
    """
    Main dashboard view - serves as the application homepage.
    """
    spv_data = SPVData.objects.first()
    
    # Navigation items for navbar
    nav_items = [
        {'label': 'Dashboard', 'url': '/', 'id': 'dashboardLink', 'page_id': 'dashboard'},
        {'divider': True},
        {'label': 'Bills', 'url': '#', 'id': 'billsLink', 'page_id': 'bills'},
        {'label': 'Projects', 'url': '#', 'id': 'projectsLink', 'page_id': 'projects'},
        {'label': 'Stocktake', 'url': '#', 'id': 'stocktakeLink', 'page_id': 'stocktake', 'disabled': True},
        {'label': 'Staff Hours', 'url': '#', 'id': 'staffHoursLink', 'page_id': 'staff_hours', 'disabled': True},
        {'label': 'Contacts', 'url': '#', 'id': 'contactsLink', 'page_id': 'contacts'},
        {'label': 'Xero', 'url': '#', 'id': 'xeroLink', 'page_id': 'xero'},
        {'divider': True},
        {'label': 'Settings', 'url': '#', 'id': 'settingsLink', 'page_id': 'settings'},
    ]
    
    # Contacts table configuration - uses allocations_layout.html with full config
    contacts_config = get_contacts_config()
    
    # Xero table configuration - uses allocations_layout.html with full config
    xero_config = get_xero_config()
    
    # Get XeroInstances for dropdown
    xero_instances = XeroInstances.objects.all()
    
    # Serialize xero_instances for JavaScript
    import json
    xero_instances_json = json.dumps([
        {
            'xero_instance_pk': instance.xero_instance_pk,
            'xero_name': instance.xero_name
        }
        for instance in xero_instances
    ])
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
        "nav_items": nav_items,
        "contacts_config": contacts_config,
        "xero_config": xero_config,
        "xero_instances": xero_instances,
        "xero_instances_json": xero_instances_json,
        "settings": settings,  # Add settings to context for environment indicator
    }
    
    return render(request, "core/dashboard.html", context)


# Contact functions moved to contacts.py:
# - verify_contact_details
# - pull_xero_contacts
# - get_contacts_by_instance
# - create_contact
# - update_contact_details
# - update_contact_status


@csrf_exempt
@require_http_methods(["POST"])
@handle_xero_request_errors
def send_bill(request):
    """
    Send invoice and its allocations to Xero, then update status to 2 if successful.
    Expected POST data:
    - bill_pk: int
    - xero_instance_or_project: str (format: 'xero_123' or 'project_456')
    - supplier_pk: int
    - bill_number: str
    - total_net: decimal
    - total_gst: decimal
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        bill_pk = data.get('bill_pk')
        xero_instance_or_project = data.get('xero_instance_or_project')
        supplier_pk = data.get('supplier_pk')
        bill_number = data.get('bill_number')
        total_net = data.get('total_net')
        total_gst = data.get('total_gst')
        
        # Check all required fields
        if not all([bill_pk, xero_instance_or_project, supplier_pk, bill_number, total_net is not None, total_gst is not None]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            }, status=400)
        
        # Get the invoice
        try:
            invoice = Bills.objects.get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invoice not found'
            }, status=404)
        
        # Get supplier
        try:
            supplier = Contacts.objects.get(contact_pk=supplier_pk)
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier not found'
            }, status=404)
        
        # Parse xero_instance_or_project
        xero_instance = None
        project = None
        instance_pk = None
        
        if xero_instance_or_project.startswith('xero_'):
            xero_instance_id = int(xero_instance_or_project.replace('xero_', ''))
            try:
                xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_id)
                instance_pk = xero_instance.xero_instance_pk
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Xero Instance not found'
                }, status=404)
        elif xero_instance_or_project.startswith('project_'):
            project_id = int(xero_instance_or_project.replace('project_', ''))
            try:
                project = Projects.objects.get(projects_pk=project_id)
                if not project.xero_instance:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Project does not have a Xero Instance assigned'
                    }, status=400)
                xero_instance = project.xero_instance
                instance_pk = xero_instance.xero_instance_pk
            except Projects.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Project not found'
                }, status=404)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid xero_instance_or_project format'
            }, status=400)
        
        # Get allocations for this invoice
        allocations = Bill_allocations.objects.filter(bill=invoice).select_related('xero_account')
        
        # Check if allocations exist - this determines the workflow
        if allocations.exists():
            # Bills - Direct workflow: Validate allocations and send to Xero
            logger.info(f"Bills - Direct: Validating allocations and sending to Xero for invoice {bill_pk}")
            
            # Check supplier has Xero contact ID (required for Xero API)
            if not supplier.xero_contact_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Supplier does not have a Xero Contact ID. Please sync contacts first.'
                }, status=400)
            
            # Check all allocations have Xero accounts
            for allocation in allocations:
                if not allocation.xero_account:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'All allocations must have a Xero Account selected'
                    }, status=400)
            
            # Get Xero authentication
            xero_inst, access_token, tenant_id = get_xero_auth(instance_pk)
            if not xero_inst:
                return access_token  # This is the error response
            
            logger.info(f"Sending bill {bill_pk} to Xero for instance: {xero_instance.xero_name}")
            
            # Build line items from allocations
            line_items = []
            for allocation in allocations:
                line_item = {
                    "Description": allocation.notes or "No description",
                    "Quantity": 1,
                    "UnitAmount": float(allocation.amount),
                    "AccountCode": allocation.xero_account.account_code,
                    "TaxType": "INPUT" if allocation.gst_amount and allocation.gst_amount > 0 else "NONE",
                    "TaxAmount": float(allocation.gst_amount) if allocation.gst_amount else 0
                }
                line_items.append(line_item)
            
            # Build invoice payload for Xero
            invoice_payload = {
                "Type": "ACCPAY",  # Bill (purchase invoice)
                "Contact": {
                    "ContactID": supplier.xero_contact_id
                },
                "Date": date.today().strftime('%Y-%m-%d'),
                "DueDate": date.today().strftime('%Y-%m-%d'),  # Set to today for now
                "InvoiceNumber": bill_number,
                "LineItems": line_items,
                "Status": "DRAFT"  # Send as draft for review
            }
            
            # Send to Xero API
            logger.info(f"Sending invoice to Xero: {json.dumps(invoice_payload, indent=2)}")
            
            response = requests.post(
                'https://api.xero.com/api.xro/2.0/Invoices',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json',
                    'Xero-tenant-id': tenant_id
                },
                json={"Invoices": [invoice_payload]},
                timeout=30
            )
            
            # Check response
            if response.status_code != 200:
                error_msg = parse_xero_validation_errors(response)
                if not error_msg:
                    error_msg = f'Xero API error: {response.status_code} - {response.text}'
                logger.error(f"Xero API error: {error_msg}")
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=response.status_code)
            
            # Success\! Parse response
            xero_response = response.json()
            logger.info(f"Xero response: {json.dumps(xero_response, indent=2)}")
            
            # Extract Xero Invoice ID from response
            xero_invoice_id = None
            if 'Invoices' in xero_response and len(xero_response['Invoices']) > 0:
                xero_invoice_id = xero_response['Invoices'][0].get('InvoiceID')
            
            # Update invoice in database - only now that Xero succeeded
            invoice.xero_instance = xero_instance
            invoice.project = project
            invoice.contact_pk = supplier
            invoice.supplier_bill_number = bill_number
            invoice.total_net = Decimal(str(total_net))
            invoice.total_gst = Decimal(str(total_gst))
            invoice.bill_status = 2  # Set status to 2 (sent to Xero)
            
            invoice.save()
            
            logger.info(f"Successfully sent invoice {bill_pk} to Xero (InvoiceID: {xero_invoice_id})")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Invoice sent to Xero successfully',
                'bill_pk': invoice.bill_pk,
                'xero_invoice_id': xero_invoice_id
            })
        else:
            # Bills - Inbox workflow: Just update invoice and set status to 0 (ready for allocation)
            logger.info(f"Bills - Inbox: Moving invoice {bill_pk} to Bills - Direct (status 0)")
            
            # Update invoice in database
            invoice.xero_instance = xero_instance
            invoice.project = project
            invoice.contact_pk = supplier
            invoice.supplier_bill_number = bill_number
            invoice.total_net = Decimal(str(total_net))
            invoice.total_gst = Decimal(str(total_gst))
            invoice.bill_status = 0  # Set status to 0 (created, ready for allocation in Bills - Direct)
            
            invoice.save()
            
            logger.info(f"Successfully moved invoice {bill_pk} to Bills - Direct")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Invoice moved to Bills - Direct successfully',
                'bill_pk': invoice.bill_pk
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_bill: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# ============================================================================
# ITEMS (CATEGORIES & COSTINGS) VIEWS
# ============================================================================

@require_http_methods(["GET"])
def get_project_categories(request, project_pk):
    """
    Get all categories for a specific project, ordered by order_in_list.
    """
    try:
        from core.models import Categories
        
        categories = Categories.objects.filter(
            project_id=project_pk
        ).order_by('order_in_list').values('categories_pk', 'category', 'order_in_list')
        
        categories_list = list(categories)
        
        logger.info(f"Retrieved {len(categories_list)} categories for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'categories': categories_list
        })
        
    except Exception as e:
        logger.error(f"Error getting project categories: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting categories: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_project_items(request, project_pk):
    """
    Get all items (costings) for a specific project, grouped by category.
    """
    try:
        from core.models import Costing
        
        items = Costing.objects.filter(
            project_id=project_pk
        ).select_related('category', 'unit').order_by('category__order_in_list', 'order_in_list')
        
        items_list = []
        for item in items:
            items_list.append({
                'costing_pk': item.costing_pk,
                'item': item.item,
                'unit': item.unit.unit_name if item.unit else None,
                'unit_pk': item.unit.unit_pk if item.unit else None,
                'order_in_list': int(item.order_in_list),
                'category__category': item.category.category,
                'category__order_in_list': int(item.category.order_in_list),
                'uncommitted_amount': float(item.uncommitted_amount) if item.uncommitted_amount else 0,
                'uncommitted_qty': float(item.uncommitted_qty) if item.uncommitted_qty else None,
                'uncommitted_rate': float(item.uncommitted_rate) if item.uncommitted_rate else None,
                'uncommitted_notes': item.uncommitted_notes or '',
            })
        
        logger.info(f"Retrieved {len(items_list)} items for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'items': items_list
        })
        
    except Exception as e:
        logger.error(f"Error getting project items: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting items: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_category(request, project_pk):
    """
    Create a new category for a project.
    
    Expected POST data:
    - category: str (max 20 chars)
    - order_in_list: int
    """
    try:
        from core.models import Categories, Projects
        
        data = json.loads(request.body)
        
        # Validate required fields
        category_name = data.get('category', '').strip()
        order_in_list = data.get('order_in_list')
        
        if not category_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Category name is required'
            }, status=400)
        
        if len(category_name) > 20:
            return JsonResponse({
                'status': 'error',
                'message': 'Category name must be 20 characters or less'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Check for duplicate category name (case-insensitive)
        existing_category = Categories.objects.filter(
            project=project,
            category__iexact=category_name
        ).first()
        
        if existing_category:
            return JsonResponse({
                'status': 'error',
                'message': f'A category named "{existing_category.category}" already exists for this project'
            }, status=400)
        
        # Reorder existing categories if needed
        # If inserting at position N and there are already items at N or higher, increment them
        categories_to_reorder = Categories.objects.filter(
            project=project,
            order_in_list__gte=order_in_list
        ).order_by('-order_in_list')  # Order descending to avoid conflicts
        
        for cat in categories_to_reorder:
            cat.order_in_list += 1
            cat.save()
        
        logger.info(f"Reordered {categories_to_reorder.count()} categories to make space at position {order_in_list}")
        
        # Create the category
        category = Categories.objects.create(
            project=project,
            category=category_name,
            invoice_category=category_name,  # Default to same as category
            order_in_list=order_in_list,
            division=0  # Default division
        )
        
        logger.info(f"Created category '{category_name}' for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Category created successfully',
            'category': {
                'categories_pk': category.categories_pk,
                'category': category.category,
                'order_in_list': int(category.order_in_list)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating category: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_item(request, project_pk):
    """
    Create a new item (costing) for a project.
    
    Expected POST data:
    - item: str (max 20 chars)
    - unit: int (unit_pk, optional)
    - category_pk: int
    - order_in_list: int
    """
    try:
        from core.models import Costing, Categories, Projects, Units
        
        data = json.loads(request.body)
        
        # Validate required fields
        item_name = data.get('item', '').strip()
        unit_pk = data.get('unit')  # Now expecting unit_pk instead of unit name
        category_pk = data.get('category_pk')
        order_in_list = data.get('order_in_list')
        
        if not item_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Item name is required'
            }, status=400)
        
        # Validate unit if provided
        unit_obj = None
        if unit_pk:
            try:
                unit_obj = Units.objects.get(unit_pk=unit_pk)
            except Units.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid unit selected'
                }, status=400)
        
        if len(item_name) > 20:
            return JsonResponse({
                'status': 'error',
                'message': 'Item name must be 20 characters or less'
            }, status=400)
        
        if not category_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Category is required'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
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
                'message': 'Category not found for this project'
            }, status=404)
        
        # Reorder existing items in this category if needed
        # If inserting at position N and there are already items at N or higher, increment them
        items_to_reorder = Costing.objects.filter(
            project=project,
            category=category,
            order_in_list__gte=order_in_list
        ).order_by('-order_in_list')  # Order descending to avoid conflicts
        
        for item_obj in items_to_reorder:
            item_obj.order_in_list += 1
            item_obj.save()
        
        logger.info(f"Reordered {items_to_reorder.count()} items in category '{category.category}' to make space at position {order_in_list}")
        
        # Create the item
        item = Costing.objects.create(
            project=project,
            category=category,
            item=item_name,
            unit=unit_obj,  # Now using the Units ForeignKey object
            order_in_list=order_in_list,
            xero_account_code='',  # Default empty
            contract_budget=0,
            uncommitted_amount=0,
            fixed_on_site=0,
            sc_invoiced=0,
            sc_paid=0
        )
        
        logger.info(f"Created item '{item_name}' in category '{category.category}' for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item created successfully',
            'item': {
                'costing_pk': item.costing_pk,
                'item': item.item,
                'category': category.category,
                'category_pk': category.categories_pk
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating item: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_category(request, project_pk, category_pk):
    """
    Reorder a category to a new position.
    All items in the category move with it.
    
    Expected POST data:
    - new_order: int (new position in list)
    """
    try:
        from core.models import Categories, Projects
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order position is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the category to move
        try:
            category = Categories.objects.get(categories_pk=category_pk, project=project)
        except Categories.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Category not found'
            }, status=404)
        
        old_order = int(category.order_in_list)
        new_order = int(new_order)
        
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'No change in position'
            })
        
        # Get all categories for this project
        categories = Categories.objects.filter(project=project).exclude(categories_pk=category_pk).order_by('order_in_list')
        
        # Update order_in_list for all affected categories
        if new_order < old_order:
            # Moving up: increment categories between new_order and old_order
            for cat in categories:
                if new_order <= int(cat.order_in_list) < old_order:
                    cat.order_in_list += 1
                    cat.save()
        else:
            # Moving down: decrement categories between old_order and new_order
            for cat in categories:
                if old_order < int(cat.order_in_list) <= new_order:
                    cat.order_in_list -= 1
                    cat.save()
        
        # Update the moved category
        category.order_in_list = new_order
        category.save()
        
        logger.info(f"Reordered category '{category.category}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Category reordered successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error reordering category: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering category: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_item(request, project_pk, item_pk):
    """
    Reorder an item to a new position within its category.
    Items can only be reordered within their own category.
    
    Expected POST data:
    - new_order: int (new position in list within the category)
    """
    try:
        from core.models import Costing, Projects
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order position is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the item to move
        try:
            item = Costing.objects.get(costing_pk=item_pk, project=project)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found'
            }, status=404)
        
        old_order = int(item.order_in_list)
        new_order = int(new_order)
        
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'No change in position'
            })
        
        # Get all items in the same category
        items = Costing.objects.filter(
            project=project,
            category=item.category
        ).exclude(costing_pk=item_pk).order_by('order_in_list')
        
        # Update order_in_list for all affected items in this category
        if new_order < old_order:
            # Moving up: increment items between new_order and old_order
            for itm in items:
                if new_order <= int(itm.order_in_list) < old_order:
                    itm.order_in_list += 1
                    itm.save()
        else:
            # Moving down: decrement items between old_order and new_order
            for itm in items:
                if old_order < int(itm.order_in_list) <= new_order:
                    itm.order_in_list -= 1
                    itm.save()
        
        # Update the moved item
        item.order_in_list = new_order
        item.save()
        
        logger.info(f"Reordered item '{item.item}' in category '{item.category.category}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item reordered successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error reordering item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering item: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def download_items_csv_template(request):
    """
    Download an example CSV template for bulk category and item upload.
    
    Format:
    Category,Item,Unit,Category Order,Item Order
    Preliminaries,Site Establishment,item,1,1
    Preliminaries,Temp Fencing,m,1,2
    Excavation,Bulk Excavation,m3,2,1
    
    Valid units: item, each, m, m2, m3, ton
    """
    try:
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="items_upload_template.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(['Category', 'Item', 'Unit', 'Category Order', 'Item Order'])
        
        # Write example data with various units
        writer.writerow(['Preliminaries', 'Site Establishment', 'item', '1', '1'])
        writer.writerow(['Preliminaries', 'Temp Fencing', 'm', '1', '2'])
        writer.writerow(['Preliminaries', 'Site Signage', 'each', '1', '3'])
        writer.writerow(['Excavation', 'Bulk Excavation', 'm3', '2', '1'])
        writer.writerow(['Excavation', 'Trench Excavation', 'm3', '2', '2'])
        writer.writerow(['Concrete', 'Footings', 'm3', '3', '1'])
        writer.writerow(['Concrete', 'Slab', 'm2', '3', '2'])
        writer.writerow(['Concrete', 'Walls', 'm2', '3', '3'])
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating CSV template: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error generating template: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_items_csv(request, project_pk):
    """
    Upload and process CSV file to create categories and items in bulk.
    
    Expected CSV format:
    Category,Item,Unit,Category Order,Item Order
    Preliminaries,Site Establishment,item,1,1
    
    - Adds to existing categories/items (does not replace)
    - Creates categories if they don't exist
    - Handles duplicate category names within same project
    - Validates order numbers
    - Validates units: item, each, m, m2, m3, ton
    """
    try:
        # Get project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get CSV file from request
        if 'csv_file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No CSV file provided'
            }, status=400)
        
        csv_file = request.FILES['csv_file']
        
        # Validate file type
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'File must be a CSV'
            }, status=400)
        
        # Read and parse CSV with robust encoding handling
        try:
            # Try to decode with multiple encodings (handles Excel, Google Sheets, etc.)
            file_bytes = csv_file.read()
            file_data = None
            
            # Try UTF-8 with BOM first (Excel on Windows)
            try:
                file_data = file_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                pass
            
            # Try UTF-8 without BOM
            if file_data is None:
                try:
                    file_data = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    pass
            
            # Try Latin-1 / ISO-8859-1 (fallback, rarely fails)
            if file_data is None:
                try:
                    file_data = file_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Unable to decode CSV file. Please ensure it is saved as UTF-8.'
                    }, status=400)
            
            # Normalize line endings (handles Windows, Mac, Unix)
            file_data = file_data.replace('\r\n', '\n').replace('\r', '\n')
            
            # Parse CSV
            csv_reader = csv.DictReader(StringIO(file_data))
            
            # Validate headers exist
            if not csv_reader.fieldnames:
                return JsonResponse({
                    'status': 'error',
                    'message': 'CSV file appears to be empty or has no headers'
                }, status=400)
            
            # Normalize header names (strip whitespace, case-insensitive)
            # Map common variations to expected names
            header_map = {}
            for field in csv_reader.fieldnames:
                field_lower = field.strip().lower()
                if field_lower in ['category', 'category name']:
                    header_map[field] = 'Category'
                elif field_lower in ['item', 'item name']:
                    header_map[field] = 'Item'
                elif field_lower in ['unit', 'units']:
                    header_map[field] = 'Unit'
                elif field_lower in ['category order', 'categoryorder', 'cat order']:
                    header_map[field] = 'Category Order'
                elif field_lower in ['item order', 'itemorder']:
                    header_map[field] = 'Item Order'
            
            # Check if we have all required headers (Unit is optional for backward compatibility)
            required = {'Category', 'Item', 'Category Order', 'Item Order'}
            if not required.issubset(set(header_map.values())):
                missing = required - set(header_map.values())
                return JsonResponse({
                    'status': 'error',
                    'message': f'CSV missing required columns: {", ".join(missing)}'
                }, status=400)
            
            # Track created items
            categories_created = 0
            items_created = 0
            category_cache = {}  # Cache created/existing categories {name: category_obj}
            errors = []
            
            # Create reverse map for easy lookup
            reverse_map = {v: k for k, v in header_map.items()}
            
            # Process each row
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                try:
                    # Skip completely empty rows
                    if not any(row.values()):
                        continue
                    
                    # Validate required fields using mapped headers
                    category_name = row.get(reverse_map['Category'], '').strip()
                    item_name = row.get(reverse_map['Item'], '').strip()
                    item_unit = row.get(reverse_map.get('Unit', ''), '').strip() if 'Unit' in reverse_map else ''
                    category_order = row.get(reverse_map['Category Order'], '').strip()
                    item_order = row.get(reverse_map['Item Order'], '').strip()
                    
                    if not category_name:
                        errors.append(f"Row {row_num}: Missing category name")
                        continue
                    
                    if not item_name:
                        errors.append(f"Row {row_num}: Missing item name")
                        continue
                    
                    # Validate and look up unit if provided
                    unit_obj = None
                    if item_unit:
                        # Look up the Units object by unit_name
                        unit_obj = Units.objects.filter(unit_name__iexact=item_unit).first()
                        if not unit_obj:
                            # List valid units from database
                            valid_units = list(Units.objects.values_list('unit_name', flat=True))
                            errors.append(f"Row {row_num}: Invalid unit '{item_unit}'. Must be one of: {', '.join(valid_units)}")
                            continue
                    
                    if not category_order or not category_order.isdigit():
                        errors.append(f"Row {row_num}: Invalid category order")
                        continue
                    
                    if not item_order or not item_order.isdigit():
                        errors.append(f"Row {row_num}: Invalid item order")
                        continue
                    
                    category_order_int = int(category_order)
                    item_order_int = int(item_order)
                    
                    # Get or create category
                    if category_name in category_cache:
                        category = category_cache[category_name]
                    else:
                        # Check if category already exists for this project
                        existing_category = Categories.objects.filter(
                            project=project,
                            category=category_name
                        ).first()
                        
                        if existing_category:
                            category = existing_category
                        else:
                            # Create new category (division is required, set to 0 as default)
                            category = Categories.objects.create(
                                project=project,
                                category=category_name,
                                division=0,
                                invoice_category='',
                                order_in_list=category_order_int
                            )
                            categories_created += 1
                        
                        category_cache[category_name] = category
                    
                    # Check if item already exists
                    existing_item = Costing.objects.filter(
                        project=project,
                        category=category,
                        item=item_name
                    ).first()
                    
                    if existing_item:
                        # Skip if item already exists
                        errors.append(f"Row {row_num}: Item '{item_name}' already exists in category '{category_name}'")
                        continue
                    
                    # Create item with required fields set to defaults
                    Costing.objects.create(
                        project=project,
                        category=category,
                        item=item_name,
                        unit=unit_obj,  # ForeignKey to Units model
                        order_in_list=item_order_int,
                        xero_account_code='',
                        contract_budget=0,
                        uncommitted_amount=0,
                        fixed_on_site=0,
                        sc_invoiced=0,
                        sc_paid=0
                    )
                    items_created += 1
                    
                except Exception as row_error:
                    errors.append(f"Row {row_num}: {str(row_error)}")
                    continue
            
            # Prepare response
            response_data = {
                'status': 'success',
                'categories_created': categories_created,
                'items_created': items_created
            }
            
            if errors:
                response_data['warnings'] = errors
                response_data['message'] = f"Processed with {len(errors)} warning(s)"
            
            return JsonResponse(response_data)
            
        except csv.Error as e:
            return JsonResponse({
                'status': 'error',
                'message': f'CSV parsing error: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing CSV: {str(e)}'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error uploading CSV: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error uploading CSV: {str(e)}'
        }, status=500)


def generate_po_html(project, supplier, items, total_amount, po_url=None, is_construction=False):
    """
    Generate HTML for PO PDF with professional formatting.
    Shared between email and download endpoints.
    Dynamically scales row height based on number of items.
    For construction projects, shows: Description | Units | Qty | Rate | Amount | Quote #
    For non-construction projects, shows: Description | Amount | Quote #
    """
    # Dynamic scaling based on number of items to fit on one A4 page
    # 1-10 items: Full padding (12px), large font (12px) - comfortable spacing
    # 11-20 items: Medium padding (8px), medium font (11px) - balanced
    # 21-30 items: Tight padding (6px), small font (10px) - maximum density
    num_items = len(items)
    if num_items <= 10:
        td_padding = "12px"
        font_size = "12px"
        header_padding = "14px 12px"
    elif num_items <= 20:
        td_padding = "8px"
        font_size = "11px"
        header_padding = "10px 12px"
    else:  # 21-30 items
        td_padding = "6px"
        font_size = "10px"
        header_padding = "8px 12px"
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                margin: 0;
                padding: 30px 40px;
                color: #333;
                position: relative;
                background-color: #fff;
                box-sizing: border-box;
            }}
            .header {{
                text-align: center;
                margin-bottom: {f'15px' if num_items > 20 else '20px'};
                position: relative;
            }}
            h1 {{
                color: #2c3e50;
                font-size: {f'24px' if num_items > 20 else '28px'};
                margin: 0 0 8px 0;
                font-weight: bold;
            }}
            h2 {{
                color: #7f8c8d;
                font-size: {f'16px' if num_items > 20 else '18px'};
                margin: 0;
                font-weight: normal;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: {f'10px' if num_items > 20 else '15px'};
                border: 1px solid #ddd;
            }}
            thead th {{
                background-color: #34495e;
                color: white;
                padding: {f'8px 6px' if num_items > 20 else '10px 8px'};
                text-align: left;
                font-weight: bold;
                font-size: {f'13px' if num_items > 20 else '14px'};
                border-bottom: 2px solid #2c3e50;
            }}
            thead th.amount {{
                text-align: right;
            }}
            tbody td {{
                padding: {f'6px' if num_items > 20 else '8px'};
                border-bottom: 1px solid #ecf0f1;
                font-size: {f'12px' if num_items > 20 else '13px'};
                vertical-align: top;
            }}
            tbody td.amount {{
                text-align: right;
                font-weight: 500;
            }}
            tfoot td {{
                background-color: #ecf0f1;
                font-weight: bold;
                padding: {f'8px 6px' if num_items > 20 else '10px 8px'};
                border-top: 2px solid #34495e;
                border-bottom: none;
                font-size: {f'13px' if num_items > 20 else '14px'};
            }}
            tfoot td.amount {{
                text-align: right;
            }}
            .footer {{
                margin-top: {f'12px' if num_items > 20 else '18px'};
                text-align: left;
            }}
            .po-url {{
                margin-top: {f'10px' if num_items > 20 else '15px'};
                margin-bottom: {f'10px' if num_items > 20 else '15px'};
                padding: {f'12px' if num_items > 20 else '15px'};
                background-color: #fff3cd;
                border: 2px solid #ffc107;
                border-radius: 8px;
            }}
            .po-url-title {{
                color: #2c3e50;
                font-weight: bold;
                font-size: {f'13px' if num_items > 20 else '15px'};
                margin-bottom: 10px;
            }}
            .po-url a {{
                color: #0066cc;
                text-decoration: underline;
                font-weight: 600;
                font-size: {f'12px' if num_items > 20 else '14px'};
                word-break: break-all;
            }}
            .claims-process {{
                margin-top: {f'10px' if num_items > 20 else '15px'};
                padding: {f'10px' if num_items > 20 else '12px'};
                background-color: #f8f9fa;
                border-left: 4px solid #34495e;
            }}
            .claims-heading {{
                color: #2c3e50;
                font-size: {f'12px' if num_items > 20 else '13px'};
                font-weight: bold;
                margin-bottom: {f'6px' if num_items > 20 else '8px'};
            }}
            .claims-text {{
                color: #555;
                font-size: {f'10px' if num_items > 20 else '11px'};
                line-height: 1.5;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Purchase Order</h1>
            <h2>{project.project} - {supplier.name}</h2>
        </div>
        
        <table>
            <thead>
                <tr>
    '''
    
    if is_construction:
        # Construction: Description | Units | Qty | Rate | Amount | Quote #
        html_content += '''
                    <th style="width: 28%;">Description</th>
                    <th style="width: 10%;">Units</th>
                    <th class="amount" style="width: 12%;">Qty</th>
                    <th class="amount" style="width: 14%;">Rate</th>
                    <th class="amount" style="width: 16%;">Amount</th>
                    <th style="width: 20%;">Quote #</th>
        '''
    else:
        # Non-construction: Description | Amount | Quote #
        html_content += '''
                    <th style="width: 50%;">Description</th>
                    <th class="amount" style="width: 25%;">Amount</th>
                    <th style="width: 25%;">Quote #</th>
        '''
    
    html_content += '''
                </tr>
            </thead>
            <tbody>
    '''
    
    for item in items:
        if is_construction:
            qty_str = f"{item['qty']:,.2f}" if item.get('qty') else ''
            rate_str = f"${item['rate']:,.2f}" if item.get('rate') else ''
            html_content += f'''
                <tr>
                    <td style="width: 28%;">{item['description']}</td>
                    <td style="width: 10%;">{item.get('unit', '')}</td>
                    <td class="amount" style="width: 12%;">{qty_str}</td>
                    <td class="amount" style="width: 14%;">{rate_str}</td>
                    <td class="amount" style="width: 16%;">${item['amount']:,.2f}</td>
                    <td style="width: 20%;">{item.get('quote_number', '')}</td>
                </tr>
            '''
        else:
            html_content += f'''
                <tr>
                    <td style="width: 50%;">{item['description']}</td>
                    <td class="amount" style="width: 25%;">${item['amount']:,.2f}</td>
                    <td style="width: 25%;">{item['quote_numbers']}</td>
                </tr>
            '''
    
    if is_construction:
        html_content += f'''
            </tbody>
            <tfoot>
                <tr>
                    <td style="width: 28%;">TOTAL</td>
                    <td style="width: 10%;"></td>
                    <td style="width: 12%;"></td>
                    <td style="width: 14%;"></td>
                    <td class="amount" style="width: 16%;">${total_amount:,.2f}</td>
                    <td style="width: 20%;"></td>
                </tr>
            </tfoot>
        </table>'''
    else:
        html_content += f'''
            </tbody>
            <tfoot>
                <tr>
                    <td style="width: 50%;">TOTAL</td>
                    <td class="amount" style="width: 25%;">${total_amount:,.2f}</td>
                    <td style="width: 25%;"></td>
                </tr>
            </tfoot>
        </table>'''
    
    html_content += '''
        <div class="footer">
    '''
    
    if po_url:
        html_content += f'''
            <div class="po-url">
                <div class="po-url-title">Your Unique Payment Processing Link For All Claims:</div>
                <a href="{po_url}">{po_url}</a>
            </div>
            
            <div class="claims-process">
                <div class="claims-heading">Claims Process</div>
                <p class="claims-text">
                    1) Click your unique url above to submit your claim for approval by the 25th of the month.<br><br>
                    2) You will receive an email when your claim is approved or rejected by the end of the month.<br><br>
                    3) Once approved, click your unique url and upload your invoice matching the approved claim amount.
                </p>
            </div>
        '''
    
    html_content += '''
        </div>
    </body>
    </html>
    '''
    
    return html_content


def get_po_status(request, project_pk):
    """
    Get PO sent status for all suppliers in a project.
    Returns dict mapping supplier_pk to {sent: bool, pdf_url: str|null, po_order_pk: int|null}
    """
    try:
        project = Projects.objects.get(projects_pk=project_pk)
        
        # Get all Po_orders for this project
        po_orders = Po_orders.objects.filter(project=project, po_sent=True).select_related('po_supplier')
        
        # Build status map
        status_map = {}
        for po in po_orders:
            supplier_pk = po.po_supplier.contact_pk
            pdf_url = po.pdf.url if po.pdf else None
            status_map[supplier_pk] = {
                'sent': True,
                'pdf_url': pdf_url,
                'po_order_pk': po.po_order_pk
            }
        
        return JsonResponse({
            'status': 'success',
            'po_status': status_map
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting PO status: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def preview_po(request, project_pk, supplier_pk):
    """
    Generate PO HTML preview for display in iframe.
    Returns the same HTML that would be used for the PDF email.
    """
    try:
        from collections import defaultdict
        
        # Get project and supplier details
        project = Projects.objects.get(projects_pk=project_pk)
        supplier = Contacts.objects.get(contact_pk=supplier_pk)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if not quotes.exists():
            return HttpResponse('<html><body style="font-family: Arial; padding: 20px; color: #666; text-align: center;"><p>No quotes found for this supplier</p></body></html>')
        
        # Check if construction project - needs different formatting
        is_construction = project.project_type == 'construction'
        
        if is_construction:
            # Construction: Keep individual allocations with qty/unit/rate
            items = []
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    # Get unit name from costing item
                    unit_name = ''
                    if allocation.item and allocation.item.unit:
                        unit_name = allocation.item.unit.unit_name if hasattr(allocation.item.unit, 'unit_name') else str(allocation.item.unit)
                    
                    items.append({
                        'description': allocation.item.item,
                        'unit': unit_name,
                        'qty': float(allocation.qty) if allocation.qty else None,
                        'rate': float(allocation.rate) if allocation.rate else None,
                        'amount': float(allocation.amount),
                        'quote_number': quote.supplier_quote_number or ''
                    })
        else:
            # Non-construction: Group allocations by item
            items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': []})
            
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    item_name = allocation.item.item
                    items_map[item_name]['amount'] += allocation.amount
                    if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
            
            # Convert to list
            items = [
                {
                    'description': item_name,
                    'amount': float(data['amount']),
                    'quote_numbers': ', '.join(data['quote_numbers'])
                }
                for item_name, data in items_map.items()
            ]
        
        # Calculate total
        total_amount = sum(item['amount'] for item in items)
        
        # Check if PO has been sent - if so, use the actual URL
        po_url = "[URL will be generated when email is sent]"
        existing_po = Po_orders.objects.filter(project=project, po_supplier=supplier, po_sent=True).first()
        if existing_po and existing_po.unique_id:
            scheme = 'https' if request.is_secure() else 'http'
            host = request.get_host()
            if 'mason.build' in host or 'elasticbeanstalk.com' in host:
                scheme = 'https'
            po_url = f"{scheme}://{host}/po/{existing_po.unique_id}/"
        
        html_content = generate_po_html(project, supplier, items, total_amount, po_url=po_url, is_construction=is_construction)
        
        return HttpResponse(html_content)
        
    except Projects.DoesNotExist:
        return HttpResponse('<html><body style="font-family: Arial; padding: 20px; color: red; text-align: center;"><p>Project not found</p></body></html>', status=404)
    except Contacts.DoesNotExist:
        return HttpResponse('<html><body style="font-family: Arial; padding: 20px; color: red; text-align: center;"><p>Supplier not found</p></body></html>', status=404)
    except Exception as e:
        logger.error(f"Error generating PO preview: {e}")
        return HttpResponse(f'<html><body style="font-family: Arial; padding: 20px; color: red; text-align: center;"><p>Error: {str(e)}</p></body></html>', status=500)


@csrf_exempt
def send_po_email(request, project_pk, supplier_pk):
    """
    Generate PO PDF and send email to supplier.
    Reuses existing email configuration (invoices@mason.build).
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get project and supplier details
        project = Projects.objects.get(projects_pk=project_pk)
        supplier = Contacts.objects.get(contact_pk=supplier_pk)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if not quotes.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No quotes found for this supplier'
            }, status=404)
        
        # Check if construction project - needs different formatting
        is_construction = project.project_type == 'construction'
        
        if is_construction:
            # Construction: Keep individual allocations with qty/unit/rate
            items = []
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    # Get unit name from costing item
                    unit_name = ''
                    if allocation.item and allocation.item.unit:
                        unit_name = allocation.item.unit.unit_name if hasattr(allocation.item.unit, 'unit_name') else str(allocation.item.unit)
                    
                    items.append({
                        'description': allocation.item.item,
                        'unit': unit_name,
                        'qty': float(allocation.qty) if allocation.qty else None,
                        'rate': float(allocation.rate) if allocation.rate else None,
                        'amount': float(allocation.amount),
                        'quote_number': quote.supplier_quote_number or ''
                    })
        else:
            # Non-construction: Group allocations by item
            from collections import defaultdict
            items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': []})
            
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    item_name = allocation.item.item
                    items_map[item_name]['amount'] += allocation.amount
                    if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
            
            # Convert to list
            items = [
                {
                    'description': item_name,
                    'amount': float(data['amount']),
                    'quote_numbers': ', '.join(data['quote_numbers'])
                }
                for item_name, data in items_map.items()
            ]
        
        # Calculate total
        total_amount = sum(item['amount'] for item in items)
        
        # Create Po_orders entry with unique URL (before PDF generation)
        unique_id = str(uuid.uuid4())
        po_order = Po_orders.objects.create(
            po_supplier=supplier,
            project=project,
            unique_id=unique_id,
            po_sent=True
        )
        
        # Create Po_order_detail records for each quote allocation
        from datetime import date
        for quote in quotes:
            for allocation in quote.quote_allocations.all():
                Po_order_detail.objects.create(
                    po_order_pk=po_order,
                    date=date.today(),
                    costing=allocation.item,
                    quote=quote,
                    amount=allocation.amount,
                    qty=allocation.qty if hasattr(allocation, 'qty') and allocation.qty else None,
                    unit=allocation.item.unit if hasattr(allocation.item, 'unit') else None,
                    rate=allocation.rate if hasattr(allocation, 'rate') and allocation.rate else None,
                    variation_note=None
                )
        
        logger.info(f"Created Po_order with {Po_order_detail.objects.filter(po_order_pk=po_order).count()} detail records")
        
        # Generate URL dynamically from the request
        # This ensures the URL matches the environment (local/AWS) automatically
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        
        # Force HTTPS for production domains (AWS load balancer may terminate SSL)
        if 'mason.build' in host or 'elasticbeanstalk.com' in host:
            scheme = 'https'
        
        po_url = f"{scheme}://{host}/po/{unique_id}/"
        
        # Generate HTML for PDF using shared function with clickable URL
        html_content = generate_po_html(project, supplier, items, total_amount, po_url, is_construction)
        
        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate PDF'
            }, status=500)
        
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()
        
        # Collect unique quote numbers from items (in order of appearance)
        quote_numbers_in_order = []
        for item in items:
            # Construction uses 'quote_number' (singular), non-construction uses 'quote_numbers' (plural)
            qn_value = item.get('quote_number', '') if is_construction else item.get('quote_numbers', '')
            for qn in qn_value.split(', '):
                qn = qn.strip()
                if qn and qn not in quote_numbers_in_order:
                    quote_numbers_in_order.append(qn)
        
        # Fetch quote PDFs in order of appearance
        quote_pdfs_to_attach = []
        for quote_num in quote_numbers_in_order:
            try:
                quote = Quotes.objects.get(
                    supplier_quote_number=quote_num,
                    project=project,
                    contact_pk=supplier
                )
                if quote.pdf:
                    quote_pdfs_to_attach.append(quote.pdf)
            except Quotes.DoesNotExist:
                logger.warning(f"Quote {quote_num} not found for supplier {supplier.name}")
                continue
        
        # Merge PO PDF with quote PDFs
        if quote_pdfs_to_attach:
            try:
                merger = PdfMerger()
                
                # Add the PO PDF first
                po_pdf_buffer = BytesIO(pdf_content)
                merger.append(po_pdf_buffer)
                
                # Add each quote PDF in order
                for quote_pdf in quote_pdfs_to_attach:
                    quote_pdf.open('rb')
                    merger.append(quote_pdf)
                    quote_pdf.close()
                
                # Write merged PDF to buffer
                merged_buffer = BytesIO()
                merger.write(merged_buffer)
                merger.close()
                
                # Use merged PDF as the final content
                merged_buffer.seek(0)
                final_pdf_content = merged_buffer.read()
                logger.info(f"Merged PO PDF with {len(quote_pdfs_to_attach)} quote PDFs")
            except Exception as e:
                logger.error(f"Error merging PDFs: {e}", exc_info=True)
                # Fall back to PO PDF only if merge fails
                final_pdf_content = pdf_content
        else:
            # No quote PDFs to attach, use PO PDF only
            final_pdf_content = pdf_content
        
        # Save combined PDF to Po_orders model for record keeping
        pdf_filename = f'PO_{project.project}_{supplier.name}_{unique_id[:8]}.pdf'
        po_order.pdf.save(pdf_filename, ContentFile(final_pdf_content), save=True)
        
        # Prepare email
        supplier_name = supplier.first_name or supplier.name.split()[0] if supplier.name else 'there'
        supplier_last_name = supplier.last_name or ''
        full_name = f"{supplier_name} {supplier_last_name}".strip()
        
        subject = 'Purchase Order'
        
        # Plain text version (fallback)
        text_message = f'''Dear {full_name},

Please see attached purchase order with payment claim instructions.

Please read the payment claim instructions carefully to ensure your claim is processed and paid on time.

View payment claim instructions: {po_url}

Regards,
Mason'''
        
        # HTML version with hyperlink
        html_message = f'''
        <html>
        <body>
            <p>Dear {full_name},</p>
            
            <p>Please see attached purchase order with <a href="{po_url}">payment claim instructions</a>.</p>
            
            <p>Please read the payment claim instructions carefully to ensure your claim is processed and paid on time.</p>
            
            <p>Regards,<br>
            Mason</p>
        </body>
        </html>
        '''
        
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [supplier.email] if supplier.email else []
        
        if not recipient_list:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier has no email address'
            }, status=400)
        
        # Create email with attachment (combined PO + Quotes PDF)
        email = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
        email.attach_alternative(html_message, "text/html")
        email.attach(f'PO_{project.project}.pdf', final_pdf_content, 'application/pdf')
        
        # Add CC if configured
        if hasattr(settings, 'EMAIL_CC') and settings.EMAIL_CC:
            cc_addresses = settings.EMAIL_CC.split(';')
            email.cc = cc_addresses
        
        # Send email
        email.send()
        
        logger.info(f"PO email sent to {supplier.email} for project {project.project}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Purchase order sent to {supplier.email}',
            'pdf_url': po_order.pdf.url if po_order.pdf else None
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Project not found'
        }, status=404)
    except Contacts.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Supplier not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error sending PO email: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to send email: {str(e)}'
        }, status=500)


@csrf_exempt
def download_po_pdf(request, project_pk, supplier_pk):
    """
    Generate PO PDF and return as download.
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get project and supplier details
        project = Projects.objects.get(projects_pk=project_pk)
        supplier = Contacts.objects.get(contact_pk=supplier_pk)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if not quotes.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No quotes found for this supplier'
            }, status=404)
        
        # Group allocations by item
        from collections import defaultdict
        items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': []})
        
        for quote in quotes:
            for allocation in quote.quote_allocations.all():
                item_name = allocation.item.item
                items_map[item_name]['amount'] += allocation.amount
                if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                    items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
        
        # Convert to list
        items = [
            {
                'description': item_name,
                'amount': float(data['amount']),
                'quote_numbers': ', '.join(data['quote_numbers'])
            }
            for item_name, data in items_map.items()
        ]
        
        # Calculate total
        total_amount = sum(item['amount'] for item in items)
        
        # Generate HTML for PDF using shared function
        html_content = generate_po_html(project, supplier, items, total_amount)
        
        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate PDF'
            }, status=500)
        
        pdf_buffer.seek(0)
        
        # Return PDF as download
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO_{project.project}_{supplier.name}.pdf"'
        
        logger.info(f"PO PDF downloaded for project {project.project}, supplier {supplier.name}")
        
        return response
        
    except Projects.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Project not found'
        }, status=404)
    except Contacts.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Supplier not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error generating PO PDF: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to generate PDF: {str(e)}'
        }, status=500)


@csrf_exempt
def get_units(request):
    """
    Get all units ordered by order_in_list
    """
    try:
        from core.models import Units
        
        units = Units.objects.all().order_by('order_in_list')
        
        units_data = [{
            'unit_pk': unit.unit_pk,
            'unit_name': unit.unit_name,
            'order_in_list': unit.order_in_list
        } for unit in units]
        
        return JsonResponse({
            'status': 'success',
            'units': units_data
        })
        
    except Exception as e:
        logger.error(f"Error getting units: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting units: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_unit(request):
    """
    Add a new unit
    
    Expected POST data:
    {
        "unit_name": string,
        "order_in_list": int
    }
    """
    try:
        from core.models import Units
        
        data = json.loads(request.body)
        
        unit_name = data.get('unit_name', '').strip()
        order_in_list = data.get('order_in_list')
        
        if not unit_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit name is required'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
        # Check if unit name already exists
        if Units.objects.filter(unit_name=unit_name).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'Unit "{unit_name}" already exists'
            }, status=400)
        
        # Get all units and adjust their order if needed
        existing_units = Units.objects.filter(order_in_list__gte=order_in_list).order_by('-order_in_list')
        
        # Shift existing units down
        for unit in existing_units:
            unit.order_in_list += 1
            unit.save()
        
        # Create new unit
        new_unit = Units.objects.create(
            unit_name=unit_name,
            order_in_list=order_in_list
        )
        
        logger.info(f"Added new unit: {unit_name} at position {order_in_list}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit added successfully',
            'unit': {
                'unit_pk': new_unit.unit_pk,
                'unit_name': new_unit.unit_name,
                'order_in_list': new_unit.order_in_list
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error adding unit: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_unit(request, unit_pk):
    """
    Reorder a unit by updating its order_in_list
    
    Expected POST data:
    {
        "new_order": int
    }
    """
    try:
        from core.models import Units
        from django.db import transaction
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order is required'
            }, status=400)
        
        # Get the unit to reorder
        try:
            unit = Units.objects.get(unit_pk=unit_pk)
        except Units.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit not found'
            }, status=404)
        
        old_order = unit.order_in_list
        
        # If order hasn't changed, no need to do anything
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'Unit order unchanged'
            })
        
        # Use transaction to ensure all updates happen together
        with transaction.atomic():
            # First, move the dragged unit to a temporary position (9999) to free up its current position
            unit.order_in_list = 9999
            unit.save()
            
            if new_order < old_order:
                # Moving up: shift items down between new_order and old_order
                units_to_shift = Units.objects.filter(
                    order_in_list__gte=new_order,
                    order_in_list__lt=old_order
                ).order_by('-order_in_list')  # Update in reverse order to avoid conflicts
                
                for u in units_to_shift:
                    u.order_in_list += 1
                    u.save()
                
            else:
                # Moving down: shift items up between old_order and new_order
                units_to_shift = Units.objects.filter(
                    order_in_list__gt=old_order,
                    order_in_list__lte=new_order
                ).order_by('order_in_list')  # Update in forward order to avoid conflicts
                
                for u in units_to_shift:
                    u.order_in_list -= 1
                    u.save()
            
            # Finally, update the dragged unit to its final position
            unit.order_in_list = new_order
            unit.save()
        
        logger.info(f"Reordered unit '{unit.unit_name}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit reordered successfully'
        })
        
    except Exception as e:
        logger.error(f"Error reordering unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering unit: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_unit(request):
    """
    Delete a unit
    
    Expected POST data:
    {
        "unit_pk": int
    }
    """
    try:
        from core.models import Units
        
        data = json.loads(request.body)
        
        unit_pk = data.get('unit_pk')
        
        if not unit_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit PK is required'
            }, status=400)
        
        # Get the unit
        try:
            unit = Units.objects.get(unit_pk=unit_pk)
        except Units.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit not found'
            }, status=404)
        
        unit_name = unit.unit_name
        order = unit.order_in_list
        
        # Delete the unit
        unit.delete()
        
        # Adjust order of remaining units
        remaining_units = Units.objects.filter(order_in_list__gt=order).order_by('order_in_list')
        for remaining_unit in remaining_units:
            remaining_unit.order_in_list -= 1
            remaining_unit.save()
        
        logger.info(f"Deleted unit: {unit_name}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting unit: {str(e)}'
        }, status=500)


def get_recent_activities(request):
    """
    Get recent activities for the dashboard.
    'Recent' = within 24 workday hours (last 24 hours for now).
    
    Activities tracked:
    1. Invoices moved from Inbox (email invoices that were processed - have email_attachment and status > -2)
    2. New projects created
    3. Invoices allocated (status changed to 1)
    """
    try:
        # Calculate 24 hours ago
        now = timezone.now()
        cutoff = now - timedelta(hours=24)
        
        activities = []
        
        # 1. Invoices moved from Inbox
        # These are invoices that came from email (have email_attachment or received_email)
        # and have been moved out of inbox (status > -2, meaning they were processed)
        # We look at updated_at to see when they were moved
        inbox_moved = Bills.objects.filter(
            updated_at__gte=cutoff,
            bill_status__gt=-2,  # Not in unprocessed state
        ).filter(
            # Has email origin (came from inbox)
            models.Q(email_attachment__isnull=False) | models.Q(received_email__isnull=False)
        ).exclude(
            # Exclude if created_at == updated_at (meaning just created, not moved)
            created_at=models.F('updated_at')
        ).select_related('project', 'contact_pk').order_by('-updated_at')[:20]
        
        for invoice in inbox_moved:
            supplier_name = invoice.contact_pk.name if invoice.contact_pk else 'Unknown'
            project_name = invoice.project.project if invoice.project else 'Unassigned'
            activities.append({
                'type': 'inbox_moved',
                'icon': 'fas fa-inbox',
                'color': '#17a2b8',  # info blue
                'message': f'Invoice from {supplier_name} moved from Inbox',
                'detail': f'Project: {project_name}',
                'timestamp': invoice.updated_at.isoformat() if invoice.updated_at else None,
                'link': None,
                'project_pk': invoice.project.projects_pk if invoice.project else None,
            })
        
        # 2. New projects created
        new_projects = Projects.objects.filter(
            created_at__gte=cutoff
        ).order_by('-created_at')[:10]
        
        for project in new_projects:
            activities.append({
                'type': 'project_created',
                'icon': 'fas fa-folder-plus',
                'color': '#28a745',  # success green
                'message': f'New project created: {project.project}',
                'detail': f'Type: {project.project_type or "Not set"}',
                'timestamp': project.created_at.isoformat() if project.created_at else None,
                'link': None,
                'project_pk': project.projects_pk,
            })
        
        # 3. Invoices allocated (status = 1, recently updated)
        # These are invoices that were allocated to a project
        allocated_invoices = Bills.objects.filter(
            updated_at__gte=cutoff,
            bill_status=1,  # Allocated status
        ).select_related('project', 'contact_pk').order_by('-updated_at')[:20]
        
        for invoice in allocated_invoices:
            supplier_name = invoice.contact_pk.name if invoice.contact_pk else 'Unknown'
            project_name = invoice.project.project if invoice.project else 'Unassigned'
            activities.append({
                'type': 'invoice_allocated',
                'icon': 'fas fa-check-circle',
                'color': '#6f42c1',  # purple
                'message': f'Invoice allocated: {supplier_name}',
                'detail': f'Project: {project_name}',
                'timestamp': invoice.updated_at.isoformat() if invoice.updated_at else None,
                'link': None,
                'project_pk': invoice.project.projects_pk if invoice.project else None,
            })
        
        # Sort all activities by timestamp (most recent first)
        activities.sort(key=lambda x: x['timestamp'] or '', reverse=True)
        
        # Limit to 50 most recent
        activities = activities[:50]
        
        return JsonResponse({
            'status': 'success',
            'activities': activities,
            'count': len(activities)
        })
        
    except Exception as e:
        logger.error(f"Error getting recent activities: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def get_action_items(request):
    """
    Get action items for the dashboard.
    
    Action items:
    1. Bills in Inbox (bill_status = -2)
    2. Bills to be Allocated in {project} (bill_status = 0, grouped by project)
    3. Bills to be Approved in {project} (bill_status = 1 or 102, grouped by project)
    4. Approved Bills ready to send to Xero (bill_status = 2 or 103)
    5. Supplier Progress Claims awaiting Approval (bill_status = 100)
    """
    try:
        action_items = []
        
        # 1. Bills in Inbox (status -2) - exclude archived projects
        inbox_count = Bills.objects.filter(
            bill_status=-2
        ).exclude(
            project__archived=1
        ).count()
        if inbox_count > 0:
            action_items.append({
                'type': 'inbox',
                'icon': 'fas fa-inbox',
                'color': '#dc3545',  # red - urgent
                'priority': 1,
                'title': 'Bills in Inbox',
                'count': inbox_count,
                'message': f'{inbox_count} bill{"s" if inbox_count > 1 else ""} waiting to be processed',
                'action': 'Go to Inbox',
                'action_type': 'bills_inbox',
            })
        
        # 2. Bills to be Allocated (status 0, grouped by project) - exclude archived projects
        unallocated = Bills.objects.filter(bill_status=0).exclude(project__archived=1).select_related('project')
        unallocated_by_project = {}
        for inv in unallocated:
            project_name = inv.project.project if inv.project else 'Unassigned'
            project_pk = inv.project.projects_pk if inv.project else None
            key = (project_pk, project_name)
            if key not in unallocated_by_project:
                unallocated_by_project[key] = 0
            unallocated_by_project[key] += 1
        
        for (project_pk, project_name), count in unallocated_by_project.items():
            action_items.append({
                'type': 'allocate',
                'icon': 'fas fa-file-invoice-dollar',
                'color': '#fd7e14',  # orange
                'priority': 2,
                'title': f'Bills to be Allocated',
                'subtitle': project_name,
                'count': count,
                'message': f'{count} bill{"s" if count > 1 else ""} need allocation',
                'action': 'Allocate',
                'action_type': 'project_invoices',
                'project_pk': project_pk,
            })
        
        # 3. Bills to be Approved (status 1 or 102, grouped by project) - exclude archived projects
        to_approve = Bills.objects.filter(bill_status__in=[1, 102]).exclude(project__archived=1).select_related('project')
        approve_by_project = {}
        for inv in to_approve:
            project_name = inv.project.project if inv.project else 'Unassigned'
            project_pk = inv.project.projects_pk if inv.project else None
            key = (project_pk, project_name)
            if key not in approve_by_project:
                approve_by_project[key] = 0
            approve_by_project[key] += 1
        
        for (project_pk, project_name), count in approve_by_project.items():
            action_items.append({
                'type': 'approve',
                'icon': 'fas fa-check-circle',
                'color': '#ffc107',  # yellow
                'priority': 3,
                'title': f'Bills to be Approved',
                'subtitle': project_name,
                'count': count,
                'message': f'{count} bill{"s" if count > 1 else ""} awaiting approval',
                'action': 'Review',
                'action_type': 'project_allocated',
                'project_pk': project_pk,
            })
        
        # 4. Approved Bills ready to send to Xero (status 2 or 103) - exclude archived projects
        ready_for_xero = Bills.objects.filter(bill_status__in=[2, 103]).exclude(project__archived=1).count()
        if ready_for_xero > 0:
            action_items.append({
                'type': 'xero',
                'icon': 'fas fa-paper-plane',
                'color': '#28a745',  # green
                'priority': 4,
                'title': 'Approved Bills ready to send to Xero',
                'count': ready_for_xero,
                'message': f'{ready_for_xero} bill{"s" if ready_for_xero > 1 else ""} ready to send',
                'action': 'Send to Xero',
                'action_type': 'bills_approvals',
            })
        
        # 5. Supplier Progress Claims awaiting Approval (status 100) - exclude archived projects
        pending_claims = Bills.objects.filter(bill_status=100).exclude(project__archived=1).select_related('project', 'contact_pk')
        claims_by_supplier = {}
        for inv in pending_claims:
            supplier_name = inv.contact_pk.name if inv.contact_pk else 'Unknown Supplier'
            project_name = inv.project.project if inv.project else 'Unknown Project'
            project_pk = inv.project.projects_pk if inv.project else None
            key = (supplier_name, project_pk, project_name)
            if key not in claims_by_supplier:
                claims_by_supplier[key] = 0
            claims_by_supplier[key] += 1
        
        for (supplier_name, project_pk, project_name), count in claims_by_supplier.items():
            action_items.append({
                'type': 'progress_claim',
                'icon': 'fas fa-file-contract',
                'color': '#6f42c1',  # purple
                'priority': 2,  # High priority - supplier waiting
                'title': 'Supplier Progress Claim awaiting Approval',
                'subtitle': f'{supplier_name} - {project_name}',
                'count': count,
                'message': f'{count} claim{"s" if count > 1 else ""} pending approval',
                'action': 'Review',
                'action_type': 'po_claims',
                'project_pk': project_pk,
            })
        
        # Sort by priority
        action_items.sort(key=lambda x: x['priority'])
        
        # Calculate summary counts
        total_count = len(action_items)
        pending_count = sum(1 for item in action_items if item['type'] in ['inbox', 'allocate', 'approve', 'progress_claim'])
        
        return JsonResponse({
            'status': 'success',
            'action_items': action_items,
            'summary': {
                'total': total_count,
                'pending': pending_count,
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting action items: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
