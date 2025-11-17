"""
Bills-related views.
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
import requests
from .xero import handle_xero_request_errors, get_xero_auth
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
def archive_bill(request):
    """
    Archive a bill by setting invoice_status to 4
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invoice_pk = data.get('invoice_pk')
            
            if not invoice_pk:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice PK is required'
                }, status=400)
            
            # Get the invoice
            try:
                invoice = Invoices.objects.get(invoice_pk=invoice_pk)
            except Invoices.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice not found'
                }, status=404)
            
            # Update status to -1 (archived)
            invoice.invoice_status = -1
            invoice.save()
            
            logger.info(f"Archived invoice #{invoice_pk}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Bill archived successfully',
                'invoice_pk': invoice_pk
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error archiving bill: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)

@csrf_exempt
def return_to_inbox(request):
    """
    Return a bill to inbox by clearing fields and setting status to -2
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            invoice_pk = data.get('invoice_pk')
            
            if not invoice_pk:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice PK is required'
                }, status=400)
            
            # Get the invoice
            try:
                invoice = Invoices.objects.get(invoice_pk=invoice_pk)
            except Invoices.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice not found'
                }, status=404)
            
            # Clear fields and set status to -2
            invoice.xero_instance = None
            invoice.project = None
            invoice.total_net = None
            invoice.total_gst = None
            invoice.supplier_invoice_number = None
            invoice.contact_pk = None
            invoice.invoice_status = -2
            
            invoice.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Bill returned to inbox successfully',
                'invoice_pk': invoice.invoice_pk
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)

def get_bills_list(request):
    """
    Get list of all invoices for Bills modals (Inbox and Direct)
    Frontend will filter by invoice_status as needed
    Also provides dropdown data for Xero instances, suppliers, and projects
    """
    from core.models import XeroInstances, Projects
    
    # Get all invoices (frontend will filter by status)
    invoices = Invoices.objects.select_related(
        'contact_pk', 'project', 'xero_instance', 'received_email', 'email_attachment'
    ).prefetch_related('invoice_allocations').order_by('-created_at')
    
    # Get dropdown options
    xero_instances = XeroInstances.objects.all().values('xero_instance_pk', 'xero_name')
    suppliers = Contacts.objects.filter(status='ACTIVE').order_by('name').values('contact_pk', 'name', 'xero_instance_id')
    projects = Projects.objects.all().order_by('project').values('projects_pk', 'project', 'xero_instance_id')
    
    # Prepare bills data
    bills_data = []
    for invoice in invoices:
        try:
            # Get presigned S3 URL for attachment if it exists
            attachment_url = ''
            if invoice.email_attachment:
                try:
                    # Generate presigned URL (valid for 1 hour)
                    attachment_url = invoice.email_attachment.get_download_url()
                except Exception as e:
                    # If S3 URL generation fails, use empty string
                    print(f"Error getting download URL for attachment {invoice.email_attachment.id}: {str(e)}")
                    attachment_url = ''
            
            # Get email URL (link to received email in admin)
            email_url = ''
            if invoice.received_email:
                email_url = f"/admin/core/receivedemail/{invoice.received_email.id}/change/"
            
            # Determine xero_instance_id from either direct xero_instance or project
            xero_instance_id = None
            if invoice.xero_instance_id:
                xero_instance_id = invoice.xero_instance_id
            elif invoice.project and invoice.project.xero_instance_id:
                xero_instance_id = invoice.project.xero_instance_id
            
            # Get existing allocations for this invoice
            allocations = []
            for allocation in invoice.invoice_allocations.all():
                allocations.append({
                    'allocation_pk': allocation.invoice_allocations_pk,
                    'amount': float(allocation.amount) if allocation.amount else None,
                    'gst_amount': float(allocation.gst_amount) if allocation.gst_amount else None,
                    'notes': allocation.notes or '',
                    'xero_account_pk': allocation.xero_account_id if allocation.xero_account else None,
                })
            
            bill = {
                'invoice_pk': invoice.invoice_pk,
                'invoice_status': invoice.invoice_status,
                'xero_instance_id': xero_instance_id,
                'xero_instance_pk': xero_instance_id,  # Add this for frontend compatibility
                'contact_pk': invoice.contact_pk.contact_pk if invoice.contact_pk else None,
                'project_pk': invoice.project.projects_pk if invoice.project else None,
                'supplier_invoice_number': invoice.supplier_invoice_number or '',
                'total_net': float(invoice.total_net) if invoice.total_net else None,
                'total_gst': float(invoice.total_gst) if invoice.total_gst else None,
                'email_subject': invoice.received_email.subject if invoice.received_email else 'N/A',
                'email_from': invoice.received_email.from_address if invoice.received_email else 'N/A',
                'email_body_html': invoice.received_email.body_html if invoice.received_email else '',
                'email_body_text': invoice.received_email.body_text if invoice.received_email else '',
                'attachment_filename': invoice.email_attachment.filename if invoice.email_attachment else 'N/A',
                'attachment_url': attachment_url,
                'email_url': email_url,
                'allocations': allocations,
            }
            bills_data.append(bill)
        except Exception as e:
            # Log error but continue processing other invoices
            print(f"Error processing invoice {invoice.invoice_pk}: {str(e)}")
            continue
    
    return JsonResponse({
        'bills': bills_data,
        'xero_instances': list(xero_instances),
        'suppliers': list(suppliers),
        'projects': list(projects),
        'count': len(bills_data)
    })  

def delete_invoice(request):
    if request.method == 'DELETE':
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        try:
            invoice = Invoices.objects.get(pk=invoice_id)
        except Invoices.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Invoice not found'}, status=404)
        invoice.delete()
        return JsonResponse({'status': 'success', 'message': 'Invoice deleted successfully'})
    else:
        return JsonResponse({'status': 'fail', 'message': 'Invalid request method'}, status=405)
@csrf_exempt
def upload_invoice(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        invoice_number = request.POST.get('invoice_number')
        invoice_total = request.POST.get('invoice_total')
        invoice_total_gst = request.POST.get('invoice_total_gst') 
        invoice_date = request.POST.get('invoice_date')
        invoice_due_date = request.POST.get('invoice_due_date')
        invoice_division = request.POST.get('invoiceDivision') 
        pdf_file = request.FILES.get('pdf')
        try:
            contact = Contacts.objects.get(pk=supplier_id)
            invoice = Invoices(
                supplier_invoice_number=invoice_number,
                total_net=invoice_total,
                total_gst=invoice_total_gst, 
                invoice_status=0, 
                invoice_date=invoice_date,
                invoice_due_date=invoice_due_date,
                invoice_division=invoice_division, 
                pdf=pdf_file,
                contact_pk=contact
            )
            invoice.save()
            return JsonResponse({'success': True})
        except Contacts.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Supplier not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
@csrf_exempt
def upload_invoice_allocations(request):
    if request.method == 'POST':
        invoice_pk = request.POST.get('invoice_pk')
        allocations = json.loads(request.POST.get('allocations'))
        try:
            invoice = Invoices.objects.get(pk=invoice_pk)
            for allocation in allocations:
                item_id = allocation.get('item')
                if item_id:
                    item = Costing.objects.get(pk=item_id)
                    amount = Decimal(str(allocation.get('thisInvoice', 0)))  
                    gst_amount = Decimal(str(allocation.get('gst_amount', 0)))  
                    uncommitted = Decimal(str(allocation.get('uncommitted', 0)))  
                    notes = allocation.get('notes', '')
                    Invoice_allocations.objects.create(
                        invoice_pk=invoice,
                        item=item,
                        amount=amount,
                        gst_amount=gst_amount,  
                        notes=notes
                    )
                    item.uncommitted = uncommitted  
                    item.save()
            invoice.invoice_status = 1
            invoice.save()
            return JsonResponse({'success': True})
        except Invoices.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invoice not found'})
        except Costing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Costing item not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
@csrf_exempt
def post_invoice(request):
    logger.info('Starting post_invoice function')
    body = json.loads(request.body)
    invoice_pk = body.get('invoice_pk')
    division = int(body.get('division', 0))  
    logger.info(f'Division: {division}')
    logger.info(f'Invoice PK: {invoice_pk}')
    invoice = Invoices.objects.get(pk=invoice_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    invoice_allocations = Invoice_allocations.objects.filter(invoice_pk_id=invoice_pk)
    line_items = []
    for invoice_allocation in invoice_allocations:
        costing = Costing.objects.get(pk=invoice_allocation.item_id)
        line_item = {
            "Description": invoice_allocation.notes,
            "Quantity": 1,
            "UnitAmount": str(invoice_allocation.amount),
            "AccountCode": costing.xero_account_code,
            "TaxType": "INPUT",
            "TaxAmount": str(invoice_allocation.gst_amount),
        }
        line_items.append(line_item)
    
    # DEPRECATED: Old custom connection - needs OAuth2 implementation
    # TODO: Replace with OAuth2 flow using XeroInstances
    raise NotImplementedError("This endpoint needs to be updated to use OAuth2. Use contacts.html and xero.py endpoints instead.")
    
    # get_xero_token(request, division)
    # access_token = request.session.get('access_token')
    # logger.info(f'Access Token: {access_token}')
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "Type": "ACCPAY",
        "Contact": {"ContactID": contact.xero_contact_id},
        "Date": invoice.invoice_date.isoformat(),
        "DueDate": invoice.invoice_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_invoice_number,
        "Url": request.build_absolute_uri(invoice.pdf.url),  
        "LineItems": line_items
    }
    logger.info('Sending request to Xero API')
    logger.info('Data: %s', json.dumps(data))  
    response = requests.post('https://api.xero.com/api.xro/2.0/Invoices', headers=headers, data=json.dumps(data))
    try:
        response_data = response.json()
    except json.JSONDecodeError:
        logger.error('Empty response from Xero API')
        return JsonResponse({'status': 'error', 'message': 'Empty response from Xero API'})
    if 'Status' in response_data and response_data['Status'] == 'OK':
        invoice_id = response_data['Invoices'][0]['InvoiceID']
        logger.info(f'Invoice created with ID: {invoice_id}')
        invoice.invoice_status = 2
        invoice.invoice_xero_id = invoice_id
        invoice.save()
        file_url = invoice.pdf.url
        file_name = file_url.split('/')[-1]
        urlretrieve(file_url, file_name)
        with open(file_name, 'rb') as f:
            file_data = f.read()
        headers['Content-Type'] = 'application/octet-stream'
        logger.info('Sending request to attach file to invoice')
        response = requests.post(f'https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}', headers=headers, data=file_data)
        if response.status_code == 200:
            logger.info('File attached successfully')
            return JsonResponse({'status': 'success', 'message': 'Invoice and attachment created successfully.'})
        else:
            logger.error('Failed to attach file to invoice')
            return JsonResponse({'status': 'error', 'message': 'Invoice created but attachment failed to upload.'})
    else:
        logger.error('Unexpected response from Xero API: %s', response_data)
        return JsonResponse({'status': 'error', 'message': 'Unexpected response from Xero API', 'response_data': response_data})
@csrf_exempt
def test_xero_invoice(request):
    logger.info('Starting post_invoice function')
    body = json.loads(request.body)
    invoice_pk = body.get('invoice_pk')
    logger.info(f'Invoice PK: {invoice_pk}')
    invoice = Invoices.objects.get(pk=invoice_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    invoice_allocations = Invoice_allocations.objects.filter(invoice_pk_id=invoice_pk)
    line_items = []
    for invoice_allocation in invoice_allocations:
        costing = Costing.objects.get(pk=invoice_allocation.item_id)
        line_item = {
            "Description": invoice_allocation.notes,
            "Quantity": 1,
            "UnitAmount": str(invoice_allocation.amount),
            "AccountCode": costing.xero_account_code,
            "TaxType": "INPUT",
            "TaxAmount": str(invoice_allocation.gst_amount),
        }
        line_items.append(line_item)
    
    # DEPRECATED: Old custom connection - needs OAuth2 implementation
    # TODO: Replace with OAuth2 flow using XeroInstances
    raise NotImplementedError("This endpoint needs to be updated to use OAuth2. Use contacts.html and xero.py endpoints instead.")
    
    # get_xero_token(request)
    # access_token = request.session.get('access_token')
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "Type": "ACCPAY",
        "Contact": {"ContactID": Contacts.objects.first().xero_contact_id},
        "Date": invoice.invoice_date.isoformat(),
        "DueDate": invoice.invoice_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_invoice_number,
        "Url": "https://precastappbucket.s3.amazonaws.com/drawings/P071.pdf",
        "LineItems": line_items
    }
    logger.info('Sending request to Xero API')
    logger.info('Data: %s', json.dumps(data))  
    response = requests.post('https://api.xero.com/api.xro/2.0/Invoices', headers=headers, data=json.dumps(data))
    response_data = response.json()
    if 'Status' in response_data and response_data['Status'] == 'OK':
        invoice_id = response_data['Invoices'][0]['InvoiceID']
        logger.info(f'Invoice created with ID: {invoice_id}')
        file_url = 'https://precastappbucket.s3.amazonaws.com/drawings/P071.pdf'
        file_name = file_url.split('/')[-1]
        urlretrieve(file_url, file_name)
        with open(file_name, 'rb') as f:
            file_data = f.read()
        headers['Content-Type'] = 'application/octet-stream'
        logger.info('Sending request to attach file to invoice')
        response = requests.post(f'https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}', headers=headers, data=file_data)
        if response.status_code == 200:
            logger.info('File attached successfully')
            return JsonResponse({'status': 'success', 'message': 'Invoice and attachment created successfully.'})
        else:
            logger.error('Failed to attach file to invoice')
            return JsonResponse({'status': 'error', 'message': 'Invoice created but attachment failed to upload.'})
    else:
        logger.error('Unexpected response from Xero API: %s', response_data)
        return JsonResponse({'status': 'error', 'message': 'Unexpected response from Xero API', 'response_data': response_data})
def get_invoices_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')
    contact = Contacts.objects.filter(contact_name=supplier_name).first()
    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)
    invoices = Invoices.objects.filter(contact_pk=contact, invoice_status=2).prefetch_related(
        Prefetch('invoice_allocations_set', queryset=Invoice_allocations.objects.all(), to_attr='fetched_allocations')
    )
    if not invoices.exists():  
        return JsonResponse({"message": "No invoices found for this supplier with status=2"}, safe=False)
    invoices_data = []
    for invoice in invoices:
        invoice_info = {
            "invoice_pk": invoice.invoice_pk,
            "supplier_invoice_number": invoice.supplier_invoice_number,  
            "total_net": str(invoice.total_net),  
            "total_gst": str(invoice.total_gst),  
            "invoice_date": invoice.invoice_date.strftime("%Y-%m-%d"),  
            "invoice_due_date": invoice.invoice_due_date.strftime("%Y-%m-%d"),  
            "invoice_allocations": [
                {
                    "invoice_allocations_pk": allocation.invoice_allocations_pk,
                    "item": allocation.item.item,  
                    "amount": str(allocation.amount),
                    "gst_amount": str(allocation.gst_amount),
                    "notes": allocation.notes or ""
                } for allocation in invoice.fetched_allocations  
            ]
        }
        invoices_data.append(invoice_info)
    return JsonResponse(invoices_data, safe=False)
@csrf_exempt
def get_invoice_allocations(request, invoice_id):
    """Fetch existing allocations for an invoice to enable updating them"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests are allowed'}, status=405)
    try:
        print(f"DEBUG: Starting get_invoice_allocations for invoice_id: {invoice_id}")
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_id)
            print(f"DEBUG: Found invoice with pk={invoice_id}, type={invoice.invoice_type}")
        except Invoices.DoesNotExist:
            print(f"ERROR: Invoice with pk={invoice_id} does not exist")
            return JsonResponse({'error': f'Invoice with id {invoice_id} not found'}, status=404)
        try:
            allocations = Invoice_allocations.objects.filter(invoice_pk=invoice)
            print(f"DEBUG: Found {allocations.count()} allocations for invoice {invoice_id}")
        except Exception as e:
            print(f"ERROR: Failed to query allocations: {str(e)}")
            return JsonResponse({'error': f'Failed to query allocations: {str(e)}'}, status=500)
        formatted_allocations = []
        for alloc in allocations:
            try:
                item = alloc.item  
                if not item:
                    print(f"WARNING: Allocation {alloc.invoice_allocations_pk} has no item relationship")
                    continue
                print(f"DEBUG: Processing allocation {alloc.invoice_allocations_pk} for item {item.item}")
                print(f"DEBUG: Allocation {item.item} - allocation_type: {alloc.allocation_type} (type: {type(alloc.allocation_type)})")
                print(f"DEBUG: Raw DB values - amount: {alloc.amount}, gst_amount: {alloc.gst_amount}")
                formatted_allocations.append({
                    'allocation_id': alloc.invoice_allocations_pk,  
                    'item_pk': item.costing_pk,  
                    'item': item.item,  
                    'amount': float(alloc.amount),  
                    'gst_amount': float(alloc.gst_amount),
                    'notes': alloc.notes or "",  
                    'allocation_type': alloc.allocation_type
                })
            except Exception as e:
                print(f"ERROR: Failed to process allocation {alloc.invoice_allocations_pk}: {str(e)}")
                continue
        try:
            contact_pk = invoice.contact_pk_id if invoice.contact_pk else None
            print(f"DEBUG: Contact PK for invoice {invoice_id}: {contact_pk}")
        except Exception as e:
            print(f"ERROR: Failed to get contact_pk: {str(e)}")
            contact_pk = None
        other_invoices = []
        if invoice.invoice_type == 2 and contact_pk:  
            try:
                print(f"DEBUG: Querying ALL invoices for contact_pk={contact_pk}")
                all_invoices = list(Invoices.objects.filter(contact_pk_id=contact_pk))
                print(f"DEBUG: ALL invoices for contact {contact_pk}: {[(i.invoice_pk, i.invoice_type) for i in all_invoices]}")
                invoice_id_for_query = invoice_id
                if isinstance(invoice_id, str) and invoice_id.isdigit():
                    invoice_id_for_query = int(invoice_id)
                print(f"DEBUG: Using invoice_id_for_query={invoice_id_for_query} (type: {type(invoice_id_for_query)}) for exclude")
                print(f"DEBUG: Running query: Invoices.objects.filter(contact_pk_id={contact_pk}, invoice_type=2).exclude(invoice_pk={invoice_id_for_query})")
                other_invoice_objects = Invoices.objects.filter(
                    contact_pk_id=contact_pk,
                    invoice_type=2  
                ).exclude(invoice_pk=invoice_id_for_query)
                print(f"DEBUG: Found {other_invoice_objects.count()} other invoices for contact {contact_pk}: {[i.invoice_pk for i in other_invoice_objects]}")
                for other_inv in other_invoice_objects:
                    try:
                        print(f"DEBUG: Processing other invoice {other_inv.invoice_pk}")
                        other_allocations = Invoice_allocations.objects.filter(invoice_pk=other_inv)
                        formatted_other_allocations = []
                        for alloc in other_allocations:
                            try:
                                item = alloc.item
                                if not item:
                                    print(f"WARNING: Other allocation {alloc.invoice_allocations_pk} has no item relationship")
                                    continue
                                formatted_other_allocations.append({
                                    'item_pk': item.costing_pk,
                                    'item_name': item.item,
                                    'amount': float(alloc.amount),
                                    'gst_amount': float(alloc.gst_amount),
                                    'allocation_type': alloc.allocation_type,
                                    'invoice_allocation_type': 'progress_claim'  
                                })
                            except Exception as e:
                                print(f"ERROR: Failed to process other allocation: {str(e)}")
                                continue
                        print(f"DEBUG: Other invoice details - PK: {other_inv.invoice_pk}, Number: {other_inv.supplier_invoice_number}")
                        print(f"DEBUG: Other invoice has {len(formatted_other_allocations)} allocations")
                        other_invoice_obj = {
                            'invoice_pk': other_inv.invoice_pk,
                            'invoice_number': other_inv.supplier_invoice_number,
                            'invoice_allocations': formatted_other_allocations
                        }
                        print(f"DEBUG: Adding other invoice to response: {other_invoice_obj['invoice_pk']} / {other_invoice_obj['invoice_number']}")
                        other_invoices.append(other_invoice_obj)
                    except Exception as e:
                        print(f"ERROR: Failed to process other invoice {other_inv.invoice_pk}: {str(e)}")
                        continue
            except Exception as e:
                print(f"ERROR: Failed to query other invoices: {str(e)}")
        if not formatted_allocations:
            print(f"WARNING: No valid allocations found for invoice {invoice_id}")
        response_data = {
            'allocations': formatted_allocations,
            'contact_pk': contact_pk,
            'invoice_type': invoice.invoice_type,
            'other_invoices': other_invoices  
        }
        print(f"DEBUG: Successfully prepared response for invoice {invoice_id} with {len(formatted_allocations)} allocations")
        return JsonResponse(response_data)
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR in get_invoice_allocations: {str(e)}")
        print(traceback.format_exc())  
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


def _pull_xero_accounts_for_instance(instance_pk):
    """
    Helper function to pull accounts and tracking categories for a single Xero instance.
    Returns a dict with results for this instance.
    Note: Does not use @handle_xero_request_errors decorator since it returns a dict, not a JsonResponse.
    """
    from .xero import get_xero_auth
    from core.models import XeroInstances, XeroAccounts
    
    xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
    logger.info(f"Processing Xero instance: {xero_instance.xero_name} (PK: {instance_pk})")
    
    # Get Xero authentication
    xero_inst, access_token, tenant_id = get_xero_auth(instance_pk)
    if not xero_inst:
        # access_token is actually a JsonResponse error when auth fails
        logger.error(f"Authentication failed for {xero_instance.xero_name}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'error',
            'message': 'Authentication failed - please re-authorize this Xero instance',
            'accounts_added': 0,
            'accounts_updated': 0,
            'accounts_unchanged': 0,
            'divisions_added': 0,
            'divisions_updated': 0,
            'divisions_unchanged': 0
        }
    
    logger.info(f"Successfully authenticated for {xero_instance.xero_name}, tenant_id: {tenant_id}")
    
    accounts_added = 0
    accounts_updated = 0
    accounts_unchanged = 0
    
    # Fetch Chart of Accounts from Xero
    accounts_response = requests.get(
        'https://api.xero.com/api.xro/2.0/Accounts',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Xero-tenant-id': tenant_id
        },
        timeout=30
    )
    
    if accounts_response.status_code != 200:
        error_msg = f'Failed to fetch accounts: {accounts_response.status_code}'
        logger.error(f"{xero_instance.xero_name}: {error_msg}")
        logger.error(f"Response body: {accounts_response.text[:500]}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'error',
            'message': error_msg,
            'accounts_added': 0,
            'accounts_updated': 0,
            'accounts_unchanged': 0
        }
    
    accounts_data = accounts_response.json()
    xero_accounts = accounts_data.get('Accounts', [])
    
    logger.info(f"Fetched {len(xero_accounts)} accounts from Xero for {xero_instance.xero_name} (PK: {xero_instance.xero_instance_pk})")
    
    # Process each account
    for xero_account in xero_accounts:
        account_id = xero_account.get('AccountID')
        account_code = xero_account.get('Code', '')
        account_name = xero_account.get('Name', '')
        account_status = xero_account.get('Status', '')
        account_type = xero_account.get('Type', '')
        
        # Check if account already exists (using xero_instance + account_id as unique identifier)
        try:
            account, created = XeroAccounts.objects.update_or_create(
                xero_instance=xero_instance,
                account_id=account_id,
                defaults={
                    'account_name': account_name,
                    'account_code': account_code,
                    'account_status': account_status,
                    'account_type': account_type
                }
            )
            
            # Debug log for first few accounts
            if xero_accounts.index(xero_account) < 3:
                logger.info(f"  Account {account_code} ({account_name}) -> Instance PK: {account.xero_instance_id}, Created: {created}")
            
            if created:
                accounts_added += 1
            else:
                # Check if anything actually changed
                if (account.account_name == account_name and 
                    account.account_code == account_code and 
                    account.account_status == account_status and 
                    account.account_type == account_type):
                    accounts_unchanged += 1
                else:
                    accounts_updated += 1
        except Exception as e:
            # Handle duplicate account_code within same instance (shouldn't happen but Xero data might be inconsistent)
            logger.warning(f"Skipping duplicate account {account_code} ({account_name}) for {xero_instance.xero_name}: {str(e)}")
            continue
    
    logger.info(f"Processed {len(xero_accounts)} accounts for {xero_instance.xero_name}")
    
    # Fetch Tracking Categories (Divisions) from Xero
    tracking_response = requests.get(
        'https://api.xero.com/api.xro/2.0/TrackingCategories',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Xero-tenant-id': tenant_id
        },
        timeout=30
    )
    
    if tracking_response.status_code != 200:
        logger.warning(f"Failed to fetch tracking categories for {xero_instance.xero_name}: {tracking_response.status_code}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'partial',
            'message': f'Accounts synced but tracking categories failed: {tracking_response.status_code}',
            'accounts_added': accounts_added,
            'accounts_updated': accounts_updated,
            'tracking_categories_found': 0
        }
    
    return {
        'instance_name': xero_instance.xero_name,
        'status': 'success',
        'accounts_added': accounts_added,
        'accounts_updated': accounts_updated,
        'accounts_unchanged': accounts_unchanged
    }


@csrf_exempt
def pull_xero_accounts_and_divisions(request):
    """
    Pull accounts from Xero API for all instances.
    Inserts new records and updates existing ones.
    
    Uses helper functions from xero.py:
    - get_xero_auth() for OAuth authentication
    - @handle_xero_request_errors decorator for exception handling
    """
    from core.models import XeroInstances
    
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get all Xero instances
        xero_instances = XeroInstances.objects.all()
        
        if not xero_instances.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No Xero instances found'
            }, status=404)
        
        total_accounts_added = 0
        total_accounts_updated = 0
        total_accounts_unchanged = 0
        instance_results = []
        
        # Process each Xero instance using the helper function
        for xero_instance in xero_instances:
            instance_pk = xero_instance.xero_instance_pk
            
            try:
                # Call helper function
                result = _pull_xero_accounts_for_instance(instance_pk)
                instance_results.append(result)
                
                # Aggregate totals
                total_accounts_added += result.get('accounts_added', 0)
                total_accounts_updated += result.get('accounts_updated', 0)
                total_accounts_unchanged += result.get('accounts_unchanged', 0)
                
            except Exception as e:
                logger.error(f"Error processing instance {xero_instance.xero_name}: {str(e)}", exc_info=True)
                instance_results.append({
                    'instance_name': xero_instance.xero_name,
                    'status': 'error',
                    'message': f'Error: {str(e)}',
                    'accounts_added': 0,
                    'accounts_updated': 0,
                    'accounts_unchanged': 0
                })
        
        return JsonResponse({
            'status': 'success',
            'message': f'Processed {len(xero_instances)} Xero instance(s)',
            'summary': {
                'total_accounts_added': total_accounts_added,
                'total_accounts_updated': total_accounts_updated,
                'total_accounts_unchanged': total_accounts_unchanged
            },
            'instances': instance_results
        })
        
    except Exception as e:
        logger.error(f"Error in pull_xero_accounts_and_divisions: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
def get_xero_accounts_by_instance(request, instance_pk):
    """
    Get all Xero accounts for a specific Xero instance.
    Used to populate the Xero Account dropdown in bill allocations.
    """
    try:
        from core.models import XeroAccounts
        
        accounts = XeroAccounts.objects.filter(
            xero_instance_id=instance_pk,
            account_status='ACTIVE'
        ).order_by('account_code').values(
            'xero_account_pk',
            'account_code',
            'account_name',
            'account_type'
        )
        
        return JsonResponse({
            'status': 'success',
            'accounts': list(accounts)
        })
        
    except Exception as e:
        logger.error(f"Error fetching Xero accounts for instance {instance_pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)



@csrf_exempt
def create_invoice_allocation(request):
    """
    Create a new invoice allocation entry.
    Called when a bill row is clicked or when user adds a new allocation row.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        amount = data.get('amount')
        gst_amount = data.get('gst_amount')
        
        if not invoice_pk:
            return JsonResponse({'status': 'error', 'message': 'invoice_pk is required'}, status=400)
        
        # Create allocation
        allocation = Invoice_allocations.objects.create(
            invoice_pk_id=invoice_pk,
            amount=amount or 0,
            gst_amount=gst_amount or 0,
            allocation_type=0
        )
        
        logger.info(f"Created invoice allocation {allocation.invoice_allocations_pk} for invoice {invoice_pk}")
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.invoice_allocations_pk
        })
        
    except Exception as e:
        logger.error(f"Error creating invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_invoice_allocation(request):
    """
    Update an existing invoice allocation entry.
    Called when user changes Xero Account, Division, amounts, or description.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation_pk = data.get('allocation_pk')
        
        if not allocation_pk:
            return JsonResponse({'status': 'error', 'message': 'allocation_pk is required'}, status=400)
        
        try:
            allocation = Invoice_allocations.objects.get(invoice_allocations_pk=allocation_pk)
        except Invoice_allocations.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
        
        # Update fields if provided
        if 'amount' in data:
            allocation.amount = data['amount']
        if 'gst_amount' in data:
            allocation.gst_amount = data['gst_amount']
        if 'notes' in data:
            allocation.notes = data['notes']
        if 'xero_account_pk' in data:
            allocation.xero_account_id = data['xero_account_pk'] if data['xero_account_pk'] else None
        
        allocation.save()
        
        logger.info(f"Updated invoice allocation {allocation_pk}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error updating invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_invoice_allocation(request):
    """
    Delete an invoice allocation entry.
    Called when user clicks the X button on an allocation row.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation_pk = data.get('allocation_pk')
        
        if not allocation_pk:
            return JsonResponse({'status': 'error', 'message': 'allocation_pk is required'}, status=400)
        
        try:
            allocation = Invoice_allocations.objects.get(invoice_allocations_pk=allocation_pk)
            allocation.delete()
            logger.info(f"Deleted invoice allocation {allocation_pk}")
            return JsonResponse({'status': 'success'})
        except Invoice_allocations.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
        
    except Exception as e:
        logger.error(f"Error deleting invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_invoice(request):
    """
    Update an invoice's fields from the LHS table.
    Called when user changes Xero Instance, Supplier, Invoice #, Net, or GST.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        
        if not invoice_pk:
            return JsonResponse({'status': 'error', 'message': 'invoice_pk is required'}, status=400)
        
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        except Invoices.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
        
        # Update fields if provided
        if 'xero_instance_id' in data:
            invoice.xero_instance_id = data['xero_instance_id'] if data['xero_instance_id'] else None
        if 'contact_pk' in data:
            invoice.contact_pk_id = data['contact_pk'] if data['contact_pk'] else None
        if 'supplier_invoice_number' in data:
            invoice.supplier_invoice_number = data['supplier_invoice_number']
        if 'total_net' in data:
            invoice.total_net = data['total_net']
        if 'total_gst' in data:
            invoice.total_gst = data['total_gst']
        if 'project_pk' in data:
            invoice.project_id = data['project_pk'] if data['project_pk'] else None
        
        invoice.save()
        
        logger.info(f"Updated invoice {invoice_pk}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error updating invoice: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def null_allocation_xero_fields(request):
    """
    Null out xero_account for all allocations of an invoice.
    Called when user changes the Xero Instance in the LHS table.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        
        if not invoice_pk:
            return JsonResponse({'status': 'error', 'message': 'invoice_pk is required'}, status=400)
        
        # Null out xero_account for all allocations
        updated_count = Invoice_allocations.objects.filter(
            invoice_pk_id=invoice_pk
        ).update(
            xero_account=None
        )
        
        logger.info(f"Nulled Xero account for {updated_count} allocations of invoice {invoice_pk}")
        
        return JsonResponse({'status': 'success', 'updated_count': updated_count})
        
    except Exception as e:
        logger.error(f"Error nulling allocation Xero fields: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)