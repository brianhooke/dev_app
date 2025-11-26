"""
Quotes-related views.
"""

import csv
from decimal import Decimal, InvalidOperation
from django.template import loader
from ..forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from ..models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Invoices, Invoice_allocations, HC_claims, HC_claim_allocations, Projects, Hc_variation, Hc_variation_allocations
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch, Max
from ..services import bills as bill_service
from ..services import quotes as quote_service
from ..services import pos as pos_service
from ..services import invoices as invoice_service
from ..services import costings as costing_service
from ..services import contacts as contact_service
from ..services import aggregations as aggregation_service
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
import uuid
from django.core.files.base import ContentFile
import base64
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter
import os
import logging
from io import BytesIO
from django.core.files.storage import default_storage
from datetime import datetime, date, timedelta
import re
from django.core.mail import send_mail
from django.db import connection
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO
from django.core.mail import EmailMessage
from urllib.parse import urljoin
import textwrap
from django.core import serializers
from reportlab.lib import colors
import requests
from decimal import Decimal
from ratelimit import limits, sleep_and_retry
from urllib.request import urlretrieve
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.forms.models import model_to_dict
from django.db.models import Sum
from ..models import Invoices, Contacts, Costing, Categories, Quote_allocations, Quotes, Po_globals, Po_orders, SPVData
import json
from django.db.models import Q, Sum
import ssl
import urllib.request
from django.core.exceptions import ValidationError
from ..formulas import Committed
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  

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
            item.uncommitted = uncommitted
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
            
            for line_item in line_items:
                item_pk = line_item.get('item')
                amount = line_item.get('amount', 0)
                notes = line_item.get('notes', '')
                
                if not item_pk:
                    continue
                
                try:
                    costing = Costing.objects.get(pk=item_pk)
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
    if request.method == 'DELETE':
        data = json.loads(request.body)
        supplier_quote_number = data.get('supplier_quote_number')
        if not supplier_quote_number:
            return JsonResponse({'status': 'fail', 'message': 'Supplier quote number is required'}, status=400)
        try:
            quote = Quotes.objects.get(supplier_quote_number=supplier_quote_number)
        except Quotes.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Quote not found'}, status=404)
        quote.delete()
        return JsonResponse({'status': 'success', 'message': 'Quote deleted successfully'})
    else:
        return JsonResponse({'status': 'fail', 'message': 'Invalid request method'}, status=405)
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
@csrf_exempt
def update_uncommitted(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        uncommitted = data.get('uncommitted')
        notes = data.get('notes')  
        try:
            costing = Costing.objects.get(costing_pk=costing_pk)
            costing.uncommitted = uncommitted
            costing.uncommitted_notes = notes  
            costing.save()
            return JsonResponse({'status': 'success'})
        except Costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Costing not found'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
logger = logging.getLogger(__name__)

def get_quotes_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')
    contact = Contacts.objects.filter(contact_name=supplier_name).first()
    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)
    quotes = Quotes.objects.filter(contact_pk=contact).prefetch_related(
        Prefetch('quote_allocations_set', queryset=Quote_allocations.objects.all(), to_attr='fetched_allocations')  
    )
    quotes_data = []
    for quote in quotes:
        quote_info = {
            "quotes_pk": quote.quotes_pk,
            "supplier_quote_number": quote.supplier_quote_number,
            "total_cost": str(quote.total_cost),  
            "quote_allocations": [
                {
                    "quote_allocations_pk": allocation.quote_allocations_pk,
                    "item": allocation.item.item,  
                    "amount": str(allocation.amount),
                    "notes": allocation.notes or ""
                } for allocation in quote.fetched_allocations  
            ]
        }
        quotes_data.append(quote_info)
    return JsonResponse(quotes_data, safe=False)

@require_http_methods(["GET"])
def get_project_contacts(request, project_pk):
    """
    Get all contacts for a project's Xero instance
    
    Returns contacts filtered by the project's xero_instance
    """
    try:
        # Get the project
        try:
            project = Projects.objects.select_related('xero_instance').get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Check if project has a Xero instance
        if not project.xero_instance:
            return JsonResponse({
                'status': 'success',
                'contacts': [],
                'message': 'Project has no Xero instance assigned'
            })
        
        # Get contacts for this Xero instance
        contacts = Contacts.objects.filter(
            xero_instance=project.xero_instance
        ).order_by('name').values('contact_pk', 'name')
        
        contacts_list = list(contacts)
        
        logger.info(f"Retrieved {len(contacts_list)} contacts for project {project.project} (Xero instance: {project.xero_instance.xero_name})")
        
        return JsonResponse({
            'status': 'success',
            'contacts': contacts_list,
            'xero_instance_name': project.xero_instance.xero_name
        })
        
    except Exception as e:
        logger.error(f"Error getting project contacts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting contacts: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_project_quote(request):
    """
    Save a quote for a project
    
    Expected POST data:
    {
        "project_pk": int,
        "supplier": int (contact_pk),
        "total_cost": decimal,
        "quote_number": string,
        "line_items": [
            {"item": int (costing_pk), "amount": decimal, "notes": string}
        ],
        "pdf_data_url": string (base64 encoded PDF)
    }
    """
    try:
        data = json.loads(request.body)
        
        # Extract data
        project_pk = data.get('project_pk')
        supplier_pk = data.get('supplier')
        total_cost = data.get('total_cost')
        quote_number = data.get('quote_number')
        line_items = data.get('line_items', [])
        pdf_data_url = data.get('pdf_data_url')
        
        # Validate required fields
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
        
        # Process PDF
        try:
            # Extract base64 data from data URL
            format_part, imgstr = pdf_data_url.split(';base64,')
            ext = format_part.split('/')[-1]
            
            # Generate unique filename
            supplier_name = contact.name.replace(' ', '_')
            unique_filename = f"{supplier_name}_{quote_number}_{uuid.uuid4()}.{ext}"
            
            # Decode and create file
            pdf_content = ContentFile(base64.b64decode(imgstr), name=unique_filename)
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing PDF: {str(e)}'
            }, status=400)
        
        # Create Quote using transaction
        with transaction.atomic():
            # Create the quote
            quote = Quotes.objects.create(
                supplier_quote_number=quote_number,
                total_cost=total_cost,
                pdf=pdf_content,
                contact_pk=contact,
                project=project
            )
            
            # Create quote allocations
            for item_data in line_items:
                item_pk = item_data.get('item')
                amount = item_data.get('amount')
                notes = item_data.get('notes', '')
                
                try:
                    item = Costing.objects.get(costing_pk=item_pk)
                except Costing.DoesNotExist:
                    raise Exception(f'Costing item with pk {item_pk} not found')
                
                Quote_allocations.objects.create(
                    quotes_pk=quote,
                    item=item,
                    amount=amount,
                    notes=notes
                )
            
            logger.info(f"Quote {quote.quotes_pk} created for project {project.project} with {len(line_items)} allocations")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Quote saved successfully',
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
                allocations.append({
                    'quote_allocations_pk': allocation.quote_allocations_pk,
                    'item_pk': allocation.item.costing_pk,
                    'item_name': allocation.item.item,
                    'category': allocation.item.category.category if allocation.item.category else None,
                    'amount': str(allocation.amount),
                    'notes': allocation.notes or ''
                })
            
            quote_info = {
                'quotes_pk': quote.quotes_pk,
                'supplier_quote_number': quote.supplier_quote_number,
                'total_cost': str(quote.total_cost),
                'supplier_name': quote.contact_pk.name if quote.contact_pk else 'Unknown',
                'supplier_pk': quote.contact_pk.contact_pk if quote.contact_pk else None,
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


@require_http_methods(["GET"])
def get_project_committed_amounts(request, project_pk):
    """
    Get committed amounts (sum of quote allocations) per item for a project.
    For Internal category items, use contract_budget as committed amount.
    Returns a dictionary of {costing_pk: total_committed_amount}
    """
    try:
        project = get_object_or_404(Projects, pk=project_pk)
        
        # Get all quotes for this project
        project_quotes = Quotes.objects.filter(project=project)
        
        # Get all quote allocations for these quotes and aggregate by item
        committed_amounts = Quote_allocations.objects.filter(
            quotes_pk__in=project_quotes
        ).values('item__costing_pk').annotate(
            total_committed=Sum('amount')
        )
        
        # Convert to dictionary {costing_pk: amount}
        committed_dict = {
            item['item__costing_pk']: float(item['total_committed'])
            for item in committed_amounts
        }
        
        # For Internal category items, use contract_budget as committed amount
        # (since they don't use uncommitted or quote allocations)
        internal_items = Costing.objects.filter(
            project=project,
            category__category='Internal'
        )
        
        for item in internal_items:
            committed_dict[item.costing_pk] = float(item.contract_budget or 0)
        
        return JsonResponse({
            'status': 'success',
            'committed_amounts': committed_dict
        })
        
    except Exception as e:
        logger.error(f"Error getting committed amounts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting committed amounts: {str(e)}'
        }, status=500)