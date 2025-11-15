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

def get_bills_list(request):
    """
    Get list of invoices with invoice_status = -2 for the Bills modal
    Also provides dropdown data for Xero instances, suppliers, and projects
    """
    from core.models import XeroInstances, Projects
    
    # Get all invoices with status -2 (bills to be processed)
    invoices = Invoices.objects.filter(invoice_status=-2).select_related(
        'contact_pk', 'project', 'received_email', 'email_attachment'
    ).order_by('-created_at')
    
    # Get dropdown options
    xero_instances = XeroInstances.objects.all().values('xero_instance_pk', 'xero_name')
    suppliers = Contacts.objects.filter(status='ACTIVE').order_by('name').values('contact_pk', 'name')
    projects = Projects.objects.all().order_by('project').values('projects_pk', 'project')
    
    # Prepare bills data
    bills_data = []
    for invoice in invoices:
        # Get presigned S3 URL for attachment if it exists
        attachment_url = ''
        if invoice.email_attachment:
            # Generate presigned URL (valid for 1 hour)
            attachment_url = invoice.email_attachment.get_download_url()
        
        # Get email URL (link to received email in admin)
        email_url = ''
        if invoice.received_email:
            email_url = f"/admin/core/receivedemail/{invoice.received_email.id}/change/"
        
        bill = {
            'invoice_pk': invoice.invoice_pk,
            'xero_instance_id': invoice.project.xero_instance_id if invoice.project and invoice.project.xero_instance else None,
            'contact_pk': invoice.contact_pk.contact_pk if invoice.contact_pk else None,
            'project_pk': invoice.project.projects_pk if invoice.project else None,
            'total_net': float(invoice.total_net) if invoice.total_net else None,
            'total_gst': float(invoice.total_gst) if invoice.total_gst else None,
            'email_subject': invoice.received_email.subject if invoice.received_email else 'N/A',
            'email_from': invoice.received_email.from_address if invoice.received_email else 'N/A',
            'attachment_filename': invoice.email_attachment.filename if invoice.email_attachment else 'N/A',
            'attachment_url': attachment_url,
            'email_url': email_url,
        }
        bills_data.append(bill)
    
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