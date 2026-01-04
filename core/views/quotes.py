"""
Quotes-related views.

Template Rendering:
1. quotes_view - Render quotes section template (supports project_pk query param)

Quote CRUD:
2. commit_data - Commit quote data (create new quote with allocations)
3. update_quote - Update existing quote with new data
4. delete_quote - Delete quote and its allocations
5. save_project_quote - Save or update a project quote (with PDF upload)

Quote Retrieval:
6. get_project_quotes - Get all quotes for a project with allocations
7. get_project_contacts - Get contacts for project's Xero instance

Allocation Management:
8. get_quote_allocations - Get allocations by supplier
9. get_quote_allocations_for_quote - Get allocations for specific quote
10. get_quote_allocations_by_quotes - Get allocations for given quote IDs
11. create_quote_allocation - Create new quote allocation
12. update_quote_allocation - Update existing quote allocation
13. delete_quote_allocation - Delete quote allocation
"""

import base64
import json
import logging
import ssl
import uuid
from collections import defaultdict
from decimal import Decimal

from django.core.files.base import ContentFile
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Prefetch
from django.forms.models import model_to_dict
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..models import Contacts, Costing, Projects, Quote_allocations, Quotes

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)  


def quotes_view(request):
    """Render the quotes section template.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/quotes/?project_pk=123
    
    Returns construction-specific columns when project_type == 'construction'.
    """
    project_pk = request.GET.get('project_pk')
    is_construction = False
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            is_construction = (project.project_type == 'construction')
        except Projects.DoesNotExist:
            pass
    
    # Main table columns (same for both project types)
    main_table_columns = [
        {'header': 'Supplier', 'width': '50%', 'sortable': True},
        {'header': '$ Net', 'width': '15%', 'sortable': True},
        {'header': 'Quote #', 'width': '15%', 'sortable': True},
        {'header': 'Update', 'width': '12%', 'class': 'col-action-first'},
        {'header': 'Delete', 'width': '8%', 'class': 'col-action'},
    ]
    
    # Allocations columns differ by project type
    if is_construction:
        allocations_columns = [
            {'header': 'Item', 'width': '22%'},
            {'header': 'Unit', 'width': '8%'},
            {'header': 'Qty', 'width': '10%'},
            {'header': 'Rate', 'width': '12%'},
            {'header': '$ Amount', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '30%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    else:
        allocations_columns = [
            {'header': 'Item', 'width': '40%'},
            {'header': '$ Net', 'width': '20%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '35%'},
            {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
        ]
    
    context = {
        'project_pk': project_pk,
        'is_construction': is_construction,
        'main_table_columns': main_table_columns,
        'allocations_columns': allocations_columns,
    }
    return render(request, 'core/quotes.html', context)


@csrf_exempt
def commit_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        total_cost = data['total_cost']
        supplier_quote_number = data['supplier_quote_number']  
        pdf_data = data['pdf']
        contact_pk = data['contact_pk']
        allocations = data.get('allocations')
        format, imgstr = pdf_data.split(';base64,')
        ext = format.split('/')[-1]
        contact = get_object_or_404(Contacts, pk=contact_pk)
        supplier = contact.contact_name
        unique_filename = supplier + " " + str(uuid.uuid4()) + '.' + ext
        data = ContentFile(base64.b64decode(imgstr), name=unique_filename)
        quote = Quotes.objects.create(total_cost=total_cost, supplier_quote_number=supplier_quote_number, pdf=data, contact_pk=contact)
        for allocation in allocations:
            amount = allocation['amount']
            item_pk = allocation['item']
            item = Costing.objects.get(pk=item_pk)
            notes = allocation.get('notes', '')  
            if amount == '':
                amount = '0'
            Quote_allocations.objects.create(quotes_pk=quote, item=item, amount=amount, notes=notes)  
            uncommitted = allocation['uncommitted']
            item.uncommitted_amount = uncommitted
            item.save()
        return JsonResponse({'status': 'success'})
@csrf_exempt
def update_quote(request):
    """
    Update an existing quote with new data
    Expects: quote_id, total_cost, quote_number, supplier, line_items
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.info(f"Update quote request data: {data}")
            
            quote_id = data.get('quote_id')
            total_cost = data.get('total_cost')
            quote_number = data.get('quote_number')
            supplier_id = data.get('supplier')
            line_items = data.get('line_items', [])
            
            # Validate required fields
            if not quote_id:
                return JsonResponse({'status': 'error', 'message': 'Quote ID is required'}, status=400)
            
            # Get the quote
            try:
                quote = Quotes.objects.get(pk=quote_id)
            except Quotes.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Quote not found'}, status=404)
            
            # Update quote fields
            quote.total_cost = total_cost
            quote.supplier_quote_number = quote_number
            
            # Update supplier if provided
            if supplier_id:
                try:
                    contact = Contacts.objects.get(pk=supplier_id)
                    quote.contact_pk = contact
                except Contacts.DoesNotExist:
                    logger.warning(f"Contact {supplier_id} not found, keeping existing supplier")
            
            quote.save()
            logger.info(f"Updated quote {quote_id} - Total: {total_cost}, Number: {quote_number}")
            
            # Delete existing allocations and create new ones
            Quote_allocations.objects.filter(quotes_pk=quote).delete()
            
            # Check if construction project
            is_construction = (quote.project and quote.project.project_type == 'construction')
            
            for line_item in line_items:
                item_pk = line_item.get('item')
                notes = line_item.get('notes', '')
                
                if not item_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(pk=item_pk)
                    
                    # Handle construction vs non-construction
                    if is_construction:
                        # Construction: save qty, unit, rate and calculate amount
                        qty = Decimal(str(line_item.get('qty', 0)))
                        unit = line_item.get('unit', '')
                        rate = Decimal(str(line_item.get('rate', 0)))
                        amount = qty * rate
                        
                        Quote_allocations.objects.create(
                            quotes_pk=quote,
                            item=costing,
                            qty=qty,
                            unit=unit,
                            rate=rate,
                            amount=amount,
                            notes=notes
                        )
                        logger.info(f"Created construction allocation: Item {item_pk}, Qty {qty}, Rate {rate}, Amount {amount}")
                    else:
                        # Non-construction: use provided amount
                        amount = line_item.get('amount', 0)
                        
                        Quote_allocations.objects.create(
                            quotes_pk=quote,
                            item=costing,
                            amount=amount,
                            notes=notes
                        )
                        logger.info(f"Created allocation: Item {item_pk}, Amount {amount}")
                        
                except Costing.DoesNotExist:
                    logger.error(f"Costing {item_pk} not found, skipping allocation")
                    continue
            
            return JsonResponse({
                'status': 'success',
                'message': 'Quote updated successfully',
                'quote_id': quote_id
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in update_quote: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            logger.error(f"Error updating quote: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f'Error updating quote: {str(e)}'}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
@csrf_exempt
def delete_quote(request):
    if request.method in ['DELETE', 'POST']:
        data = json.loads(request.body)
        
        # Support pk, quote_pk, and supplier_quote_number for backwards compatibility
        quote_pk = data.get('pk') or data.get('quote_pk')
        supplier_quote_number = data.get('supplier_quote_number')
        
        if not quote_pk and not supplier_quote_number:
            return JsonResponse({'status': 'error', 'message': 'Quote PK or supplier quote number is required'}, status=400)
        
        try:
            if quote_pk:
                quote = Quotes.objects.get(quotes_pk=quote_pk)
            else:
                quote = Quotes.objects.get(supplier_quote_number=supplier_quote_number)
        except Quotes.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Quote not found'}, status=404)
        
        quote_number = quote.supplier_quote_number
        quote.delete()
        
        logger.info(f"Deleted quote {quote_number} (pk={quote_pk})")
        
        return JsonResponse({'status': 'success', 'message': f'Quote {quote_number} deleted successfully'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
def get_quote_allocations(request, supplier_id):
    quote_allocations = Quote_allocations.objects.filter(
        quotes_pk__contact_pk_id=supplier_id
    ).select_related('item', 'quotes_pk').values('item__item', 'item__pk', 'quotes_pk_id', 'quotes_pk__supplier_quote_number', 'amount')
    costings = Costing.objects.all().order_by('category__order_in_list', 'category__category', 'item')
    costings = [model_to_dict(costing) for costing in costings]
    data = defaultdict(list)
    for qa in quote_allocations:
        data[qa['item__item']].append({
            'item_pk': qa['item__pk'],
            'quote_pk': qa['quotes_pk_id'],
            'quote_number': qa['quotes_pk__supplier_quote_number'],
            'amount': qa['amount']
        })
    data['costings'] = costings
    return JsonResponse(data, safe=False)


def get_quote_allocations_for_quote(request, quote_pk):
    """Get all allocations for a specific quote."""
    try:
        quote = Quotes.objects.get(quotes_pk=quote_pk)
        allocations = Quote_allocations.objects.filter(quotes_pk=quote).select_related('item', 'item__unit')
        
        allocations_data = []
        for alloc in allocations:
            # Get unit from Costing item's linked Units object if available
            unit = ''
            if alloc.item and alloc.item.unit:
                unit = alloc.item.unit.unit_name  # unit is FK to Units model
            elif alloc.unit:
                unit = alloc.unit
            
            allocations_data.append({
                'quote_allocations_pk': alloc.quote_allocations_pk,
                'item_pk': alloc.item.costing_pk if alloc.item else None,
                'item_name': alloc.item.item if alloc.item else None,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': unit,
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes,
            })
        
        return JsonResponse({
            'status': 'success',
            'quote': {
                'quotes_pk': quote.quotes_pk,
                'supplier_quote_number': quote.supplier_quote_number,
                'total_cost': float(quote.total_cost) if quote.total_cost else 0,
            },
            'allocations': allocations_data
        })
    except Quotes.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Quote not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def create_quote_allocation(request):
    """Create a new quote allocation."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        quote_pk = request.POST.get('quote_pk')
        item_pk = request.POST.get('item_pk')
        amount = request.POST.get('amount', 0)
        notes = request.POST.get('notes', '')
        
        # Construction-specific fields
        qty = request.POST.get('qty')
        rate = request.POST.get('rate')
        unit = request.POST.get('unit', '')
        
        quote = Quotes.objects.get(quotes_pk=quote_pk)
        item = Costing.objects.get(costing_pk=item_pk) if item_pk else None
        
        # Handle construction mode (qty/rate provided)
        if qty is not None and rate is not None and qty != '' and rate != '':
            qty_decimal = Decimal(str(qty))
            rate_decimal = Decimal(str(rate))
            calc_amount = qty_decimal * rate_decimal
            
            allocation = Quote_allocations.objects.create(
                quotes_pk=quote,
                item=item,
                qty=qty_decimal,
                rate=rate_decimal,
                unit=unit,
                amount=calc_amount,
                notes=notes
            )
        else:
            allocation = Quote_allocations.objects.create(
                quotes_pk=quote,
                item=item,
                amount=Decimal(amount) if amount else Decimal('0'),
                notes=notes
            )
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.quote_allocations_pk
        })
    except Quotes.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Quote not found'}, status=404)
    except Costing.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_quote_allocation(request, allocation_pk):
    """Update an existing quote allocation."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        allocation = Quote_allocations.objects.get(quote_allocations_pk=allocation_pk)
        
        item_pk = request.POST.get('item_pk')
        amount = request.POST.get('amount', 0)
        notes = request.POST.get('notes', '')
        
        # Construction-specific fields
        qty = request.POST.get('qty')
        rate = request.POST.get('rate')
        unit = request.POST.get('unit', '')
        
        if item_pk:
            allocation.item = Costing.objects.get(costing_pk=item_pk)
        
        # Handle construction mode (qty/rate provided)
        if qty is not None and rate is not None and qty != '' and rate != '':
            allocation.qty = Decimal(str(qty))
            allocation.rate = Decimal(str(rate))
            allocation.unit = unit
            allocation.amount = allocation.qty * allocation.rate
        else:
            allocation.amount = Decimal(amount) if amount else Decimal('0')
            
        allocation.notes = notes
        allocation.save()
        
        return JsonResponse({'status': 'success'})
    except Quote_allocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Costing.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_quote_allocation(request, allocation_pk):
    """Delete a quote allocation."""
    try:
        allocation = Quote_allocations.objects.get(quote_allocations_pk=allocation_pk)
        allocation.delete()
        return JsonResponse({'status': 'success'})
    except Quote_allocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_http_methods(["GET"])
def get_project_contacts(request, project_pk):
    """
    Get all contacts for a project's Xero instance
    
    Returns contacts filtered by the project's xero_instance
    """
    logger.info(f"🔍 [QUOTE DEBUG] Backend: get_project_contacts called with project_pk={project_pk}")
    
    try:
        # Get the project
        try:
            project = Projects.objects.select_related('xero_instance').get(projects_pk=project_pk)
            logger.info(f"🔍 [QUOTE DEBUG] Backend: Found project '{project.project}' (pk={project.projects_pk})")
            logger.info(f"🔍 [QUOTE DEBUG] Backend: Xero instance: {project.xero_instance.xero_name if project.xero_instance else 'None'}")
        except Projects.DoesNotExist:
            logger.warning(f"🔍 [QUOTE DEBUG] Backend: Project {project_pk} not found")
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Check if project has a Xero instance
        if not project.xero_instance:
            logger.warning(f"🔍 [QUOTE DEBUG] Backend: Project {project.project} has no Xero instance assigned")
            return JsonResponse({
                'status': 'success',
                'contacts': [],
                'message': 'Project has no Xero instance assigned'
            })
        
        # Check Xero instance details
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Xero instance details:")
        logger.info(f"🔍 [QUOTE DEBUG] Backend:   - PK: {project.xero_instance.xero_instance_pk}")
        logger.info(f"🔍 [QUOTE DEBUG] Backend:   - Name: {project.xero_instance.xero_name}")
        logger.info(f"🔍 [QUOTE DEBUG] Backend:   - Client ID: {project.xero_instance.xero_client_id}")
        logger.info(f"🔍 [QUOTE DEBUG] Backend:   - Has encrypted access token: {bool(project.xero_instance.oauth_access_token_encrypted)}")
        logger.info(f"🔍 [QUOTE DEBUG] Backend:   - Has tenant ID: {bool(project.xero_instance.oauth_tenant_id)}")
        
        # Get contacts for this Xero instance
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Querying Contacts for xero_instance_id={project.xero_instance.xero_instance_pk}")
        
        # First, let's check if there are ANY contacts in the database
        total_contacts = Contacts.objects.count()
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Total contacts in database: {total_contacts}")
        
        # Check contacts for this specific Xero instance
        instance_contacts = Contacts.objects.filter(xero_instance=project.xero_instance)
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Contacts for this Xero instance (raw count): {instance_contacts.count()}")
        
        # Log some sample contacts from this instance
        if instance_contacts.exists():
            sample_contacts = instance_contacts.values('contact_pk', 'name', 'xero_instance_id')[:3]
            logger.info(f"🔍 [QUOTE DEBUG] Backend: Sample contacts for this instance: {list(sample_contacts)}")
        
        # Check if there are contacts for other instances
        other_instances = Contacts.objects.exclude(xero_instance=project.xero_instance).values('xero_instance__xero_name').distinct()
        if other_instances.exists():
            logger.info(f"🔍 [QUOTE DEBUG] Backend: Other Xero instances with contacts: {list(other_instances)}")
        
        contacts = Contacts.objects.filter(
            xero_instance=project.xero_instance
        ).order_by('name').values('contact_pk', 'name')
        
        contacts_list = list(contacts)
        
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Retrieved {len(contacts_list)} contacts for project {project.project}")
        logger.info(f"🔍 [QUOTE DEBUG] Backend: Xero instance: {project.xero_instance.xero_name}")
        
        # Log first few contacts for debugging
        if contacts_list:
            logger.info(f"🔍 [QUOTE DEBUG] Backend: First 3 contacts: {contacts_list[:3]}")
        else:
            logger.warning(f"🔍 [QUOTE DEBUG] Backend: No contacts found for Xero instance {project.xero_instance.xero_name}")
        
        return JsonResponse({
            'status': 'success',
            'contacts': contacts_list,
            'xero_instance_name': project.xero_instance.xero_name
        })
        
    except Exception as e:
        logger.error(f"🔍 [QUOTE DEBUG] Backend: Error getting project contacts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting contacts: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_project_quote(request):
    """
    Save or update a quote for a project
    
    Expected POST data:
    {
        "project_pk": int,
        "supplier": int (contact_pk),
        "total_cost": decimal,
        "quote_number": string,
        "line_items": [
            {"item": int (costing_pk), "amount": decimal, "notes": string}
        ],
        "pdf_data_url": string (base64 encoded PDF) - required for new quotes only
        "quote_pk": int (optional - if provided, updates existing quote)
    }
    """
    try:
        # LOGGING: Basic debug info
        logger.info(f"=== QUOTE SAVE DEBUG ===")
        logger.info(f"DJANGO_SETTINGS_MODULE: {getattr(settings, 'DJANGO_SETTINGS_MODULE', 'NOT SET')}")
        logger.info(f"DEBUG: {getattr(settings, 'DEBUG', 'NOT SET')}")
        logger.info(f"MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'NOT SET')}")
        logger.info(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'NOT SET')}")
        
        data = json.loads(request.body)
        
        # Extract data
        project_pk = data.get('project_pk')
        supplier_pk = data.get('supplier')
        total_cost = data.get('total_cost')
        quote_number = data.get('quote_number')
        line_items = data.get('line_items', [])
        pdf_data_url = data.get('pdf_data_url')
        quote_pk = data.get('quote_pk')  # For updates
        
        is_update = quote_pk is not None
        
        # Validate required fields (pdf_data_url only required for new quotes)
        if is_update:
            if not all([project_pk, supplier_pk, total_cost, quote_number]):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing required fields'
                }, status=400)
        else:
            if not all([project_pk, supplier_pk, total_cost, quote_number, pdf_data_url]):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing required fields'
                }, status=400)
        
        if not line_items:
            return JsonResponse({
                'status': 'error',
                'message': 'At least one line item is required'
            }, status=400)
        
        # Get related objects
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        try:
            contact = Contacts.objects.get(contact_pk=supplier_pk)
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Contact/Supplier not found'
            }, status=404)
        
        # Process PDF only for new quotes
        pdf_content = None
        if pdf_data_url:
            try:
                # LOGGING: PDF processing details
                logger.info(f"Processing PDF upload...")
                logger.info(f"PDF data URL length: {len(pdf_data_url)}")
                
                # Extract base64 data from data URL
                format_part, imgstr = pdf_data_url.split(';base64,')
                ext = format_part.split('/')[-1]
                logger.info(f"PDF extension: {ext}")
                
                # Generate unique filename
                supplier_name = contact.name.replace(' ', '_')
                unique_filename = f"{supplier_name}_{quote_number}_{uuid.uuid4()}.{ext}"
                logger.info(f"Generated filename: {unique_filename}")
                
                # Decode and create file
                pdf_content = ContentFile(base64.b64decode(imgstr), name=unique_filename)
                logger.info(f"PDF ContentFile created, size: {len(pdf_content)} bytes")
                
            except Exception as e:
                logger.error(f"Error processing PDF: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error processing PDF: {str(e)}'
                }, status=400)
        
        # Create or Update Quote using transaction
        with transaction.atomic():
            if is_update:
                # Update existing quote
                try:
                    quote = Quotes.objects.get(quotes_pk=quote_pk)
                except Quotes.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Quote not found'
                    }, status=404)
                
                # Update quote fields
                quote.supplier_quote_number = quote_number
                quote.total_cost = total_cost
                quote.contact_pk = contact
                if pdf_content:
                    quote.pdf = pdf_content
                quote.save()
                
                # Delete existing allocations and recreate
                Quote_allocations.objects.filter(quotes_pk=quote).delete()
                
                logger.info(f"Updating quote {quote_pk}")
                
                # LOGGING: Check PDF update
                if pdf_content:
                    logger.info(f"Updating PDF for quote {quote_pk}")
                    quote.pdf = pdf_content
                    logger.info(f"New PDF assigned, saving quote...")
                quote.save()
                
                # Log PDF details after save
                if quote.pdf:
                    logger.info(f"After save - Quote.pdf.name: {quote.pdf.name}")
                    logger.info(f"After save - Quote.pdf.url: {quote.pdf.url}")
            else:
                # Create new quote
                logger.info(f"Creating new quote with PDF...")
                quote = Quotes.objects.create(
                    supplier_quote_number=quote_number,
                    total_cost=total_cost,
                    pdf=pdf_content,
                    contact_pk=contact,
                    project=project
                )
                
                # LOGGING: Check where the file was saved
                if quote.pdf:
                    logger.info(f"Quote.pdf.name: {quote.pdf.name}")
                    logger.info(f"Quote.pdf.url: {quote.pdf.url}")
                else:
                    logger.error("Quote.pdf is None after save!")
            
            # Create quote allocations
            is_construction = (project.project_type == 'construction')
            
            for item_data in line_items:
                item_pk = item_data.get('item')
                notes = item_data.get('notes', '')
                
                try:
                    item = Costing.objects.get(costing_pk=item_pk)
                except Costing.DoesNotExist:
                    raise Exception(f'Costing item with pk {item_pk} not found')
                
                # Handle construction vs non-construction projects
                if is_construction:
                    # Construction: check if qty/rate provided, otherwise use direct amount
                    qty_val = item_data.get('qty')
                    rate_val = item_data.get('rate')
                    unit = item_data.get('unit', '') or ''
                    
                    if qty_val is not None and rate_val is not None:
                        # Use qty * rate calculation
                        qty = Decimal(str(qty_val))
                        rate = Decimal(str(rate_val))
                        amount = qty * rate
                    else:
                        # Use direct amount (for simplified quote entry)
                        qty = None
                        rate = None
                        amount = Decimal(str(item_data.get('amount', 0)))
                    
                    Quote_allocations.objects.create(
                        quotes_pk=quote,
                        item=item,
                        qty=qty,
                        unit=unit,
                        rate=rate,
                        amount=amount,
                        notes=notes
                    )
                else:
                    # Non-construction: use provided amount
                    amount = item_data.get('amount')
                    
                    Quote_allocations.objects.create(
                        quotes_pk=quote,
                        item=item,
                        amount=amount,
                        notes=notes
                    )
            
            action = 'updated' if is_update else 'created'
            logger.info(f"Quote {quote.quotes_pk} {action} for project {project.project} with {len(line_items)} allocations")
            
            # LOGGING: Final PDF check
            if quote.pdf and not is_update:
                logger.info(f"Final PDF name: {quote.pdf.name}")
                logger.info(f"Final PDF URL: {quote.pdf.url}")
                logger.info(f"=== QUOTE SAVE DEBUG END ===")
            
            return JsonResponse({
                'status': 'success',
                'message': f'Quote {action} successfully',
                'quote_pk': quote.quotes_pk,
                'quote_number': quote.supplier_quote_number
            })
    
    except Exception as e:
        logger.error(f"Error saving quote: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error saving quote: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_project_quotes(request, project_pk):
    """
    Get all quotes for a project with their allocations
    
    Returns quotes with related allocations and supplier info
    """
    try:
        # Verify project exists
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get all quotes for this project with related data
        quotes = Quotes.objects.filter(
            project_id=project_pk
        ).select_related('contact_pk').prefetch_related(
            Prefetch(
                'quote_allocations',
                queryset=Quote_allocations.objects.select_related('item', 'item__category')
            )
        ).order_by('-quotes_pk')
        
        # Format data
        quotes_data = []
        for quote in quotes:
            # Get allocations
            allocations = []
            for allocation in quote.quote_allocations.all():
                alloc_data = {
                    'quote_allocations_pk': allocation.quote_allocations_pk,
                    'item_pk': allocation.item.costing_pk,
                    'costing_pk': allocation.item.costing_pk,
                    'item_name': allocation.item.item,
                    'category': allocation.item.category.category if allocation.item.category else None,
                    'amount': str(allocation.amount),
                    'notes': allocation.notes or ''
                }
                
                # Add construction-specific fields if they exist
                if hasattr(allocation, 'qty') and allocation.qty is not None:
                    alloc_data['qty'] = str(allocation.qty)
                if hasattr(allocation, 'unit') and allocation.unit:
                    alloc_data['unit'] = allocation.unit
                if hasattr(allocation, 'rate') and allocation.rate is not None:
                    alloc_data['rate'] = str(allocation.rate)
                    
                allocations.append(alloc_data)
            
            quote_info = {
                'quotes_pk': quote.quotes_pk,
                'supplier_quote_number': quote.supplier_quote_number,
                'total_cost': str(quote.total_cost),
                'supplier_name': quote.contact_pk.name if quote.contact_pk else 'Unknown',
                'supplier_pk': quote.contact_pk.contact_pk if quote.contact_pk else None,
                'supplier_email': quote.contact_pk.email if quote.contact_pk else '',
                'supplier_first_name': quote.contact_pk.first_name if quote.contact_pk else '',
                'supplier_last_name': quote.contact_pk.last_name if quote.contact_pk else '',
                'supplier_contact_person': quote.contact_pk.contact_person if quote.contact_pk else '',
                'pdf_url': quote.pdf.url if quote.pdf else None,
                'allocations': allocations
            }
            quotes_data.append(quote_info)
        
        logger.info(f"Retrieved {len(quotes_data)} quotes for project {project.project}")
        
        return JsonResponse({
            'status': 'success',
            'quotes': quotes_data,
            'project_name': project.project
        })
        
    except Exception as e:
        logger.error(f"Error getting project quotes: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting quotes: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_quote_allocations_by_quotes(request):
    """
    Get all allocations for given quote IDs
    
    Expected POST data:
    {
        "quote_ids": [1, 2, 3, ...]
    }
    
    Returns:
    {
        "status": "success",
        "allocations": [
            {
                "quote_pk": int,
                "item_pk": int,
                "item_name": string,
                "amount": decimal,
                "notes": string
            }
        ]
    }
    """
    try:
        data = json.loads(request.body)
        quote_ids = data.get('quote_ids', [])
        
        if not quote_ids:
            return JsonResponse({
                'status': 'error',
                'message': 'No quote IDs provided'
            }, status=400)
        
        # Fetch allocations for these quotes with nested unit relationship
        allocations = Quote_allocations.objects.filter(
            quotes_pk_id__in=quote_ids
        ).select_related('item', 'item__unit', 'quotes_pk')
        
        # Format response
        allocations_list = []
        for alloc in allocations:
            # Get unit from Costing item's linked Units object if available
            unit = ''
            if alloc.item and alloc.item.unit:
                unit = alloc.item.unit.unit_name  # unit is FK to Units model
            elif alloc.unit:
                unit = alloc.unit
            
            allocations_list.append({
                'quote_allocation_pk': alloc.quote_allocations_pk,
                'quote_pk': alloc.quotes_pk_id,
                'item_pk': alloc.item.costing_pk if alloc.item else None,
                'item_name': alloc.item.item if alloc.item else None,
                'amount': str(alloc.amount) if alloc.amount else '0',
                'qty': str(alloc.qty) if alloc.qty else '0',
                'unit': unit,
                'rate': str(alloc.rate) if alloc.rate else '0',
                'notes': alloc.notes or ''
            })
        
        logger.info(f"Retrieved {len(allocations_list)} allocations for {len(quote_ids)} quotes")
        
        return JsonResponse({
            'status': 'success',
            'allocations': allocations_list
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in get_quote_allocations_by_quotes: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting quote allocations: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting allocations: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_quote_allocations(request):
    """
    Save allocations for an existing quote (update mode).
    
    Expected POST data:
    {
        "pk": int (quote_pk),
        "allocations": [
            {"item_pk": int, "amount": decimal, "qty": decimal, "rate": decimal, "unit": str, "notes": str}
        ]
    }
    """
    try:
        data = json.loads(request.body)
        quote_pk = data.get('pk')
        allocations_data = data.get('allocations', [])
        
        if not quote_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Quote PK is required'
            }, status=400)
        
        # Get the quote
        try:
            quote = Quotes.objects.get(quotes_pk=quote_pk)
        except Quotes.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Quote not found'
            }, status=404)
        
        # Check if construction project
        is_construction = (quote.project and quote.project.project_type == 'construction')
        
        with transaction.atomic():
            # Delete existing allocations and recreate
            Quote_allocations.objects.filter(quotes_pk=quote).delete()
            
            # Create new allocations
            for alloc_data in allocations_data:
                item_pk = alloc_data.get('item_pk')
                if not item_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(costing_pk=item_pk)
                    
                    # Handle construction mode (qty/rate) vs simple mode (amount)
                    qty = alloc_data.get('qty')
                    rate = alloc_data.get('rate')
                    if qty is not None and rate is not None:
                        amount = Decimal(str(qty)) * Decimal(str(rate))
                        qty_val = Decimal(str(qty))
                        rate_val = Decimal(str(rate))
                    else:
                        amount = Decimal(str(alloc_data.get('amount', 0)))
                        qty_val = None
                        rate_val = None
                    
                    Quote_allocations.objects.create(
                        quotes_pk=quote,
                        item=costing,
                        amount=amount,
                        qty=qty_val,
                        unit=alloc_data.get('unit', ''),
                        rate=rate_val,
                        notes=alloc_data.get('notes', '')
                    )
                except Costing.DoesNotExist:
                    logger.warning(f"Costing {item_pk} not found for quote allocation")
            
            logger.info(f"Updated quote {quote_pk} with {len(allocations_data)} allocations")
            return JsonResponse({
                'status': 'success',
                'quote_pk': quote_pk
            })
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in save_quote_allocations: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error saving quote allocations: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error saving allocations: {str(e)}'
        }, status=500)