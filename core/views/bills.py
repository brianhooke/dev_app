"""
Bills-related views for PROJECT BILLS (bills within a project context).

NOTE: Global Bills functions (for bills_global_inbox/direct/approvals templates) 
have been moved to bills_global.py:
- archive_bill, return_to_inbox, get_bills_list
- pull_xero_accounts_and_divisions, pull_xero_accounts, get_xero_accounts_by_instance
- create_bill_allocation, update_bill_allocation, delete_bill_allocation
- _pull_xero_accounts_for_instance

Template Rendering:
1. bills_view - Render bills section template (supports project_pk, template_type query params)

Bill Status Management:
2. allocate_bill - Mark invoice as allocated (bill_status = 1)
3. unallocate_bill - Return invoice to unallocated (bill_status = 0)
4. approve_bill - Mark invoice as approved (status 2 or 103 for PO claims)

Bill Retrieval:
5. get_bills_by_supplier - Get invoices filtered by supplier
6. get_bill_allocations - Fetch existing allocations for an invoice (update mode)
7. get_approved_bills - Get approved invoices ready to send to Xero (status 2/103)
8. get_project_bills - Get invoices for a project filtered by status
9. get_allocated_bills - Get allocated invoices for a project

Bill CRUD:
10. delete_bill - Delete an invoice by ID
11. upload_bill - Create invoice from file upload
12. update_bill - Update invoice fields (Xero Instance, Supplier, Invoice #, Net, GST)
13. update_allocated_bill - Update invoice number and GST for allocated invoice

Allocation Management (Dashboard):
14. upload_bill_allocations - Bulk upload allocations from file
15. null_allocation_xero_fields - Clear xero_account for all allocations

Allocation Management (Project Bills):
16. get_unallocated_bill_allocations - Get allocations for unallocated invoice
17. create_unallocated_invoice_allocation - Create allocation for unallocated invoice
18. update_unallocated_invoice_allocation - Update allocation for unallocated invoice
19. delete_unallocated_invoice_allocation - Delete allocation for unallocated invoice

Xero Integration (Legacy):
20. post_bill - Post invoice to Xero (legacy - deprecated)
21. test_xero_bill - Test Xero invoice creation (legacy - deprecated)

Note: Uses helper functions from xero.py:
- get_xero_auth() - OAuth authentication + tenant ID retrieval
- @handle_xero_request_errors - Decorator handling timeout/connection/generic errors
"""

import csv
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, JsonResponse
from ..models import Contacts, Costing, Bills, Bill_allocations, Projects
import json
from django.shortcuts import render
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch, Max
from django.views.decorators.csrf import csrf_exempt
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
from django.db import connection
from collections import defaultdict
import requests
from .xero import handle_xero_request_errors, get_xero_auth
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.core.mail import EmailMessage
from urllib.parse import urljoin
import textwrap
from django.core import serializers
from reportlab.lib import colors
from ratelimit import limits, sleep_and_retry
import ssl
from django.core.exceptions import ValidationError
from ..formulas import Committed
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# NOTE: archive_bill, return_to_inbox, get_bills_list moved to bills_global.py


def delete_bill(request):
    if request.method == 'DELETE':
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        try:
            invoice = Bills.objects.get(pk=invoice_id)
        except Bills.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Invoice not found'}, status=404)
        invoice.delete()
        return JsonResponse({'status': 'success', 'message': 'Invoice deleted successfully'})
    else:
        return JsonResponse({'status': 'fail', 'message': 'Invalid request method'}, status=405)
@csrf_exempt
def upload_bill(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        bill_number = request.POST.get('bill_number')
        invoice_total = request.POST.get('invoice_total')
        invoice_total_gst = request.POST.get('invoice_total_gst') 
        bill_date = request.POST.get('bill_date')
        bill_due_date = request.POST.get('bill_due_date')
        invoice_division = request.POST.get('invoiceDivision') 
        pdf_file = request.FILES.get('pdf')
        try:
            contact = Contacts.objects.get(pk=supplier_id)
            invoice = Bills(
                supplier_bill_number=bill_number,
                total_net=invoice_total,
                total_gst=invoice_total_gst, 
                bill_status=0, 
                bill_date=bill_date,
                bill_due_date=bill_due_date,
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
def upload_bill_allocations(request):
    if request.method == 'POST':
        bill_pk = request.POST.get('bill_pk')
        allocations = json.loads(request.POST.get('allocations'))
        try:
            invoice = Bills.objects.get(pk=bill_pk)
            for allocation in allocations:
                item_id = allocation.get('item')
                if item_id:
                    item = Costing.objects.get(pk=item_id)
                    amount = Decimal(str(allocation.get('thisInvoice', 0)))  
                    gst_amount = Decimal(str(allocation.get('gst_amount', 0)))  
                    uncommitted = Decimal(str(allocation.get('uncommitted', 0)))  
                    notes = allocation.get('notes', '')
                    Bill_allocations.objects.create(
                        bill_pk=invoice,
                        item=item,
                        amount=amount,
                        gst_amount=gst_amount,  
                        notes=notes
                    )
                    item.uncommitted_amount = uncommitted  
                    item.save()
            invoice.bill_status = 1
            invoice.save()
            return JsonResponse({'success': True})
        except Bills.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invoice not found'})
        except Costing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Costing item not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
@csrf_exempt
def post_bill(request):
    logger.info('Starting post_bill function')
    body = json.loads(request.body)
    bill_pk = body.get('bill_pk')
    division = int(body.get('division', 0))  
    logger.info(f'Division: {division}')
    logger.info(f'Invoice PK: {bill_pk}')
    invoice = Bills.objects.get(pk=bill_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    bill_allocations = Bill_allocations.objects.filter(bill_pk_id=bill_pk)
    line_items = []
    for invoice_allocation in bill_allocations:
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
        "Date": invoice.bill_date.isoformat(),
        "DueDate": invoice.bill_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_bill_number,
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
        invoice.bill_status = 2
        invoice.bill_xero_id = invoice_id
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
def test_xero_bill(request):
    logger.info('Starting post_bill function')
    body = json.loads(request.body)
    bill_pk = body.get('bill_pk')
    logger.info(f'Invoice PK: {bill_pk}')
    invoice = Bills.objects.get(pk=bill_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    bill_allocations = Bill_allocations.objects.filter(bill_pk_id=bill_pk)
    line_items = []
    for invoice_allocation in bill_allocations:
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
        "Date": invoice.bill_date.isoformat(),
        "DueDate": invoice.bill_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_bill_number,
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
def get_bills_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')
    contact = Contacts.objects.filter(contact_name=supplier_name).first()
    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)
    invoices = Bills.objects.filter(contact_pk=contact, bill_status=2).prefetch_related(
        Prefetch('bill_allocations_set', queryset=Bill_allocations.objects.all(), to_attr='fetched_allocations')
    )
    if not invoices.exists():  
        return JsonResponse({"message": "No invoices found for this supplier with status=2"}, safe=False)
    invoices_data = []
    for invoice in invoices:
        invoice_info = {
            "bill_pk": invoice.bill_pk,
            "supplier_bill_number": invoice.supplier_bill_number,  
            "total_net": str(invoice.total_net),  
            "total_gst": str(invoice.total_gst),  
            "bill_date": invoice.bill_date.strftime("%Y-%m-%d"),  
            "bill_due_date": invoice.bill_due_date.strftime("%Y-%m-%d"),  
            "bill_allocations": [
                {
                    "bill_allocations_pk": allocation.bill_allocations_pk,
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
def get_bill_allocations(request, invoice_id):
    """Fetch existing allocations for an invoice to enable updating them"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests are allowed'}, status=405)
    try:
        logger.debug(f"Starting get_bill_allocations for invoice_id: {invoice_id}")
        try:
            invoice = Bills.objects.select_related('contact_pk').get(bill_pk=invoice_id)
            logger.debug(f"Found invoice with pk={invoice_id}, type={invoice.bill_type}")
        except Bills.DoesNotExist:
            logger.warning(f"Invoice with pk={invoice_id} does not exist")
            return JsonResponse({'error': f'Invoice with id {invoice_id} not found'}, status=404)
        try:
            # OPTIMIZED: Added select_related to avoid N+1 on item
            allocations = Bill_allocations.objects.filter(
                bill_pk=invoice
            ).select_related('item')
            logger.debug(f"Found {allocations.count()} allocations for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to query allocations: {str(e)}")
            return JsonResponse({'error': f'Failed to query allocations: {str(e)}'}, status=500)
        formatted_allocations = []
        for alloc in allocations:
            try:
                item = alloc.item  
                if not item:
                    logger.warning(f"Allocation {alloc.bill_allocations_pk} has no item relationship")
                    continue
                formatted_allocations.append({
                    'allocation_id': alloc.bill_allocations_pk,  
                    'item_pk': item.costing_pk,  
                    'item': item.item,  
                    'amount': float(alloc.amount),  
                    'gst_amount': float(alloc.gst_amount),
                    'notes': alloc.notes or "",  
                    'allocation_type': alloc.allocation_type
                })
            except Exception as e:
                logger.error(f"Failed to process allocation {alloc.bill_allocations_pk}: {str(e)}")
                continue
        contact_pk = invoice.contact_pk_id if invoice.contact_pk else None
        other_invoices = []
        if invoice.bill_type == 2 and contact_pk:  
            try:
                invoice_id_for_query = int(invoice_id) if isinstance(invoice_id, str) and invoice_id.isdigit() else invoice_id
                # OPTIMIZED: Prefetch allocations with items to avoid N+1
                other_invoice_objects = Bills.objects.filter(
                    contact_pk_id=contact_pk,
                    bill_type=2  
                ).exclude(bill_pk=invoice_id_for_query).prefetch_related(
                    'bill_allocations__item'
                )
                logger.debug(f"Found {other_invoice_objects.count()} other invoices for contact {contact_pk}")
                for other_inv in other_invoice_objects:
                    formatted_other_allocations = []
                    for alloc in other_inv.bill_allocations.all():
                        item = alloc.item
                        if not item:
                            logger.warning(f"Other allocation {alloc.bill_allocations_pk} has no item relationship")
                            continue
                        formatted_other_allocations.append({
                            'item_pk': item.costing_pk,
                            'item_name': item.item,
                            'amount': float(alloc.amount),
                            'gst_amount': float(alloc.gst_amount),
                            'allocation_type': alloc.allocation_type,
                            'invoice_allocation_type': 'progress_claim'  
                        })
                    other_invoices.append({
                        'bill_pk': other_inv.bill_pk,
                        'bill_number': other_inv.supplier_bill_number,
                        'bill_allocations': formatted_other_allocations
                    })
            except Exception as e:
                logger.error(f"Failed to query other invoices: {str(e)}")
        
        response_data = {
            'allocations': formatted_allocations,
            'contact_pk': contact_pk,
            'bill_type': invoice.bill_type,
            'other_invoices': other_invoices  
        }
        logger.debug(f"Prepared response for invoice {invoice_id} with {len(formatted_allocations)} allocations")
        return JsonResponse(response_data)
    except Exception as e:
        logger.exception(f"Critical error in get_bill_allocations: {str(e)}")
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


# NOTE: _pull_xero_accounts_for_instance, pull_xero_accounts_and_divisions, pull_xero_accounts,
# get_xero_accounts_by_instance, create_bill_allocation, update_bill_allocation, delete_bill_allocation
# have been moved to bills_global.py


@csrf_exempt
def update_bill(request):
    """
    Update an invoice's fields from the LHS table.
    Called when user changes Xero Instance, Supplier, Invoice #, Net, or GST.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({'status': 'error', 'message': 'bill_pk is required'}, status=400)
        
        try:
            invoice = Bills.objects.get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
        
        # Update fields if provided
        if 'xero_instance_id' in data:
            invoice.xero_instance_id = data['xero_instance_id'] if data['xero_instance_id'] else None
        if 'contact_pk' in data:
            invoice.contact_pk_id = data['contact_pk'] if data['contact_pk'] else None
        if 'supplier_bill_number' in data:
            invoice.supplier_bill_number = data['supplier_bill_number']
        if 'total_net' in data:
            invoice.total_net = data['total_net']
        if 'total_gst' in data:
            invoice.total_gst = data['total_gst']
        if 'project_pk' in data:
            invoice.project_id = data['project_pk'] if data['project_pk'] else None
        
        invoice.save()
        
        logger.info(f"Updated invoice {bill_pk}")
        
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
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({'status': 'error', 'message': 'bill_pk is required'}, status=400)
        
        # Null out xero_account for all allocations
        updated_count = Bill_allocations.objects.filter(
            bill_pk_id=bill_pk
        ).update(
            xero_account=None
        )
        
        logger.info(f"Nulled Xero account for {updated_count} allocations of invoice {bill_pk}")
        
        return JsonResponse({'status': 'success', 'updated_count': updated_count})
        
    except Exception as e:
        logger.error(f"Error nulling allocation Xero fields: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_approved_bills(request):
    """
    Get list of approved invoices ready to send to Xero (status 2 or 103).
    Used by the Approvals section in Bills.
    """
    from core.models import XeroInstances, Projects, XeroAccounts
    
    # Get invoices with status 2 (approved) or 103 (PO approved, invoice uploaded & approved)
    invoices = Bills.objects.filter(
        bill_status__in=[2, 103]
    ).select_related(
        'contact_pk', 'project', 'xero_instance', 'project__xero_instance', 'email_attachment'
    ).prefetch_related('bill_allocations__xero_account', 'bill_allocations__item').order_by('-created_at')
    
    # Prepare invoices data
    invoices_data = []
    for invoice in invoices:
        try:
            # Get project name
            project_name = invoice.project.project if invoice.project else '-'
            
            # Get xero instance name (from invoice or project)
            xero_instance_name = '-'
            xero_instance_id = None
            if invoice.xero_instance:
                xero_instance_name = invoice.xero_instance.xero_name
                xero_instance_id = invoice.xero_instance.xero_instance_pk
            elif invoice.project and invoice.project.xero_instance:
                xero_instance_name = invoice.project.xero_instance.xero_name
                xero_instance_id = invoice.project.xero_instance.xero_instance_pk
            
            # Get supplier name
            supplier_name = invoice.contact_pk.name if invoice.contact_pk else '-'
            
            # Get Xero account from first allocation (if exists)
            xero_account_name = '-'
            first_allocation = invoice.bill_allocations.first()
            if first_allocation and first_allocation.xero_account:
                xero_account_name = first_allocation.xero_account.name
            
            # Calculate gross
            total_net = float(invoice.total_net) if invoice.total_net else 0
            total_gst = float(invoice.total_gst) if invoice.total_gst else 0
            total_gross = total_net + total_gst
            
            # Get PDF URL - check invoice.pdf first, then email_attachment
            pdf_url = ''
            if invoice.pdf:
                pdf_url = invoice.pdf.url
            elif invoice.email_attachment:
                pdf_url = invoice.email_attachment.get_download_url() or ''
            
            # Get allocations
            allocations = []
            for allocation in invoice.bill_allocations.all():
                allocations.append({
                    'allocation_pk': allocation.bill_allocation_pk,
                    'costing_name': allocation.item.item if allocation.item else '-',
                    'amount': float(allocation.amount) if allocation.amount else 0,
                    'gst_amount': float(allocation.gst_amount) if allocation.gst_amount else 0,
                    'notes': allocation.notes or '',
                })
            
            invoice_data = {
                'bill_pk': invoice.bill_pk,
                'bill_status': invoice.bill_status,
                'project_name': project_name,
                'project_pk': invoice.project.projects_pk if invoice.project else None,
                'xero_instance_name': xero_instance_name,
                'xero_instance_id': xero_instance_id,
                'xero_account_name': xero_account_name,
                'supplier_name': supplier_name,
                'supplier_bill_number': invoice.supplier_bill_number or '',
                'total_gross': total_gross,
                'total_net': total_net,
                'total_gst': total_gst,
                'pdf_url': pdf_url,
                'allocations': allocations,
            }
            invoices_data.append(invoice_data)
        except Exception as e:
            logger.error(f"Error processing approved invoice {invoice.bill_pk}: {str(e)}")
            continue
    
    return JsonResponse({
        'bills': invoices_data,
        'count': len(invoices_data)
    })


# ============================================================================
# Bill views moved from main.py for consolidation
# ============================================================================

def bills_view(request):
    """Render the invoices section template.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/bills/?project_pk=123&template=unallocated
    
    Returns construction-specific columns when project_type == 'construction'.
    """
    template_type = request.GET.get('template', 'unallocated')
    source = request.GET.get('source', '')  # 'project' for Projects view
    project_pk = request.GET.get('project_pk')
    xero_instance_pk = None
    is_construction = False
    
    # Get project info if provided
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            xero_instance_pk = project.xero_instance_id if project.xero_instance else None
            is_construction = (project.project_type in ['construction', 'pods', 'precast'])
        except Projects.DoesNotExist:
            pass
    
    # For Projects view, use the simpler bills_project.html template
    if source == 'project' or template_type in ['unallocated', 'allocated']:
        is_allocated = (template_type == 'allocated')
        
        # Main table columns (same for both project types)
        if is_allocated:
            main_table_columns = [
                {'header': 'Supplier', 'width': '15%', 'sortable': True},
                {'header': 'Bill #', 'width': '12%', 'sortable': True},
                {'header': '$ Net', 'width': '10%', 'sortable': True},
                {'header': '$ GST', 'width': '10%', 'sortable': True},
                {'header': 'Progress Claim', 'width': '10%', 'class': 'col-action-first'},
                {'header': 'Unallocate', 'width': '13%', 'class': 'col-action'},
                {'header': 'Approve', 'width': '13%', 'class': 'col-action'},
                {'header': 'Save', 'width': '10%', 'class': 'col-action'},
            ]
        else:
            main_table_columns = [
                {'header': 'Supplier', 'width': '25%', 'sortable': True},
                {'header': 'Bill #', 'width': '20%', 'sortable': True},
                {'header': '$ Net', 'width': '17%', 'sortable': True},
                {'header': '$ GST', 'width': '17%', 'sortable': True},
                {'header': 'Allocate', 'width': '13%', 'class': 'col-action-first'},
                {'header': 'Del', 'width': '8%', 'class': 'col-action'},
            ]
        
        # Allocations columns differ by project type AND allocated status
        if is_construction:
            if is_allocated:
                # Construction + Allocated (read-only, no delete column)
                allocations_columns = [
                    {'header': 'Item', 'width': '25%'},
                    {'header': 'Unit', 'width': '8%'},
                    {'header': 'Qty', 'width': '12%'},
                    {'header': 'Rate', 'width': '12%'},
                    {'header': '$ Amount', 'width': '15%', 'still_to_allocate_id': 'TotalNet'},
                    {'header': 'Notes', 'width': '28%'},
                ]
            else:
                # Construction + Unallocated (editable, has delete column)
                allocations_columns = [
                    {'header': 'Item', 'width': '22%'},
                    {'header': 'Unit', 'width': '8%'},
                    {'header': 'Qty', 'width': '10%'},
                    {'header': 'Rate', 'width': '10%'},
                    {'header': '$ Amount', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
                    {'header': 'Notes', 'width': '30%'},
                    {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
                ]
        else:
            if is_allocated:
                # Non-construction + Allocated (read-only, no delete column)
                allocations_columns = [
                    {'header': 'Item', 'width': '20%'},
                    {'header': '$ Net', 'width': '12%', 'still_to_allocate_id': 'TotalNet'},
                    {'header': '$ GST', 'width': '12%', 'still_to_allocate_id': 'TotalGst'},
                    {'header': 'Notes', 'width': '56%'},
                ]
            else:
                # Non-construction + Unallocated (editable, has delete column)
                allocations_columns = [
                    {'header': 'Item', 'width': '35%'},
                    {'header': '$ Net', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
                    {'header': '$ GST', 'width': '15%', 'still_to_allocate_id': 'RemainingGst'},
                    {'header': 'Notes', 'width': '30%'},
                    {'header': 'Delete', 'width': '5%', 'class': 'col-action-first', 'edit_only': True},
                ]
        
        context = {
            'template_type': template_type,
            'project_pk': project_pk,
            'xero_instance_pk': xero_instance_pk,
            'is_construction': is_construction,
            'main_table_columns': main_table_columns,
            'allocations_columns': allocations_columns,
            'readonly': is_allocated,
        }
        return render(request, 'core/bills_project.html', context)
    
    if template_type == 'approvals':
        # Approvals - invoices approved and ready to send to Xero (status 2 or 103)
        # Returns the approvals template which is loaded via AJAX into the approvals section
        return render(request, 'core/bills_global_approvals.html')
    
    # Fallback - should not reach here
    return render(request, 'core/bills_global_approvals.html')


@csrf_exempt
def update_allocated_bill(request, bill_pk):
    """Update invoice number and GST for an allocated invoice."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_number = data.get('bill_number', '')
        total_gst = data.get('total_gst', '0.00')
        
        invoice = Bills.objects.get(bill_pk=bill_pk)
        invoice.supplier_bill_number = bill_number
        invoice.total_gst = float(total_gst)
        invoice.save()
        
        return JsonResponse({'status': 'success'})
    except Bills.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error updating allocated invoice {bill_pk}: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_project_bills(request, project_pk):
    """
    Get invoices for a project filtered by status.
    Query params:
    - status: bill_status to filter by (default: 0 for unallocated)
             status=1 also includes status=102 (PO claim invoices)
    """
    try:
        status = int(request.GET.get('status', 0))
        
        # Get invoices for this project with the specified status
        # For allocated invoices (status=1), also include PO claim invoices (status=102)
        if status == 1:
            invoices = Bills.objects.filter(
                project_id=project_pk,
                bill_status__in=[1, 102]
            ).select_related('contact_pk', 'email_attachment').order_by('-bill_pk')
        else:
            invoices = Bills.objects.filter(
                project_id=project_pk,
                bill_status=status
            ).select_related('contact_pk', 'email_attachment').order_by('-bill_pk')
        
        # Get suppliers (contacts) for this project's xero instance
        project = Projects.objects.get(projects_pk=project_pk)
        suppliers = list(Contacts.objects.filter(
            xero_instance_id=project.xero_instance_id
        ).values('contact_pk', 'name'))
        
        # Build response data
        invoices_data = []
        for inv in invoices:
            pdf_url = None
            if inv.pdf:
                try:
                    pdf_url = inv.pdf.url
                except Exception as e:
                    logger.error(f'Error getting PDF URL for invoice {inv.bill_pk}: {str(e)}')
            
            # Get attachment URL from email_attachment (fallback)
            attachment_url = None
            if inv.email_attachment:
                try:
                    attachment_url = inv.email_attachment.get_download_url()
                except Exception as e:
                    logger.error(f'Error getting attachment URL for invoice {inv.bill_pk}: {str(e)}')
            
            logger.info(f'Invoice {inv.bill_pk}: pdf_url={pdf_url}, attachment_url={attachment_url}')
            
            invoices_data.append({
                'bill_pk': inv.bill_pk,
                'supplier_pk': inv.contact_pk.contact_pk if inv.contact_pk else None,
                'supplier_name': inv.contact_pk.name if inv.contact_pk else None,
                'bill_number': inv.supplier_bill_number or '',
                'total_net': float(inv.total_net) if inv.total_net else None,
                'total_gst': float(inv.total_gst) if inv.total_gst else None,
                'pdf_url': pdf_url,
                'attachment_url': attachment_url,
                'bill_status': inv.bill_status,
            })
        
        # Get costing items for this project (include unit_name for construction mode)
        costing_items = list(Costing.objects.filter(
            project_id=project_pk
        ).select_related('unit').values('costing_pk', 'item', 'unit__unit_name'))
        
        return JsonResponse({
            'status': 'success',
            'bills': invoices_data,
            'suppliers': suppliers,
            'costing_items': costing_items,
            'project_pk': project_pk,
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    except Exception as e:
        logger.error(f'Error in get_project_bills: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_allocated_bills(request, project_pk):
    """
    Get allocated invoices (status != 0) for a project.
    """
    try:
        # Get invoices with status != 0 (allocated)
        # Include status=1 (allocated) and status=102 (PO claim invoices)
        invoices = Bills.objects.filter(
            project_id=project_pk,
            bill_status__in=[1, 102]
        ).select_related('contact_pk', 'email_attachment').order_by('-bill_pk')
        
        # Build response data
        invoices_data = []
        for inv in invoices:
            pdf_url = None
            if inv.pdf:
                try:
                    pdf_url = inv.pdf.url
                except Exception as e:
                    logger.error(f'Error getting PDF URL for invoice {inv.bill_pk}: {str(e)}')
            
            attachment_url = None
            if inv.email_attachment:
                try:
                    attachment_url = inv.email_attachment.get_download_url()
                except Exception as e:
                    logger.error(f'Error getting attachment URL for invoice {inv.bill_pk}: {str(e)}')
            
            invoices_data.append({
                'bill_pk': inv.bill_pk,
                'supplier_pk': inv.contact_pk.contact_pk if inv.contact_pk else None,
                'supplier_name': inv.contact_pk.name if inv.contact_pk else None,
                'bill_number': inv.supplier_bill_number or '',
                'total_net': float(inv.total_net) if inv.total_net else None,
                'total_gst': float(inv.total_gst) if inv.total_gst else None,
                'pdf_url': pdf_url,
                'attachment_url': attachment_url,
                'bill_status': inv.bill_status,
            })
        
        return JsonResponse({
            'status': 'success',
            'bills': invoices_data,
            'project_pk': project_pk,
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    except Exception as e:
        logger.error(f'Error in get_allocated_bills: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def get_unallocated_bill_allocations(request, bill_pk):
    """
    Get all allocations for a specific invoice (for unallocated invoices section).
    """
    try:
        allocations = Bill_allocations.objects.filter(
            bill_id=bill_pk
        ).select_related('item', 'item__unit').order_by('bill_allocation_pk')
        
        allocations_data = []
        for alloc in allocations:
            # Get unit from Costing item's linked Units object if available
            unit = ''
            if alloc.item and alloc.item.unit:
                unit = alloc.item.unit.unit_name  # unit is FK to Units model
            elif alloc.unit:
                unit = alloc.unit
            
            allocations_data.append({
                'allocation_pk': alloc.bill_allocation_pk,
                'item_pk': alloc.item_id,
                'item_name': alloc.item.item if alloc.item else None,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'gst_amount': float(alloc.gst_amount) if alloc.gst_amount else 0,
                'qty': float(alloc.qty) if alloc.qty else None,
                'unit': unit,
                'rate': float(alloc.rate) if alloc.rate else None,
                'notes': alloc.notes or '',
            })
        
        return JsonResponse({
            'status': 'success',
            'allocations': allocations_data
        })
        
    except Exception as e:
        logger.error(f'Error getting invoice allocations: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def create_unallocated_invoice_allocation(request):
    """
    Create a new allocation for an unallocated invoice.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({'status': 'error', 'message': 'bill_pk required'}, status=400)
        
        # Create new allocation with defaults (including construction fields)
        allocation = Bill_allocations.objects.create(
            bill_id=bill_pk,
            item_id=data.get('item_pk') or None,
            amount=data.get('amount', 0),
            gst_amount=data.get('gst_amount', 0),
            qty=data.get('qty') or None,
            unit=data.get('unit', ''),
            rate=data.get('rate') or None,
            notes=data.get('notes', ''),
        )
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.bill_allocation_pk
        })
        
    except Exception as e:
        logger.error(f'Error creating invoice allocation: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_unallocated_invoice_allocation(request, allocation_pk):
    """
    Update an existing allocation for an unallocated invoice.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        allocation = Bill_allocations.objects.get(bill_allocation_pk=allocation_pk)
        
        # Update fields if provided
        if 'item_pk' in data:
            allocation.item_id = data['item_pk'] if data['item_pk'] else None
        if 'amount' in data:
            allocation.amount = data['amount'] or 0
        if 'gst_amount' in data:
            allocation.gst_amount = data['gst_amount'] or 0
        if 'qty' in data:
            allocation.qty = data['qty'] if data['qty'] else None
        if 'unit' in data:
            allocation.unit = data['unit'] or ''
        if 'rate' in data:
            allocation.rate = data['rate'] if data['rate'] else None
        if 'notes' in data:
            allocation.notes = data['notes'] or ''
        
        allocation.save()
        
        return JsonResponse({'status': 'success'})
        
    except Bill_allocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f'Error updating invoice allocation: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_unallocated_invoice_allocation(request, allocation_pk):
    """
    Delete an allocation for an unallocated invoice.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        allocation = Bill_allocations.objects.get(bill_allocation_pk=allocation_pk)
        allocation.delete()
        
        return JsonResponse({'status': 'success'})
        
    except Bill_allocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f'Error deleting invoice allocation: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def allocate_bill(request, bill_pk):
    """
    Mark an invoice as allocated (bill_status = 1).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Bills.objects.get(bill_pk=bill_pk)
        invoice.bill_status = 1
        invoice.save()
        
        return JsonResponse({'status': 'success'})
        
    except Bills.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error allocating invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def unallocate_bill(request, bill_pk):
    """
    Return an invoice to unallocated status (bill_status = 0).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Bills.objects.get(bill_pk=bill_pk)
        invoice.bill_status = 0
        invoice.save()
        
        return JsonResponse({'status': 'success'})
        
    except Bills.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error unallocating invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def approve_bill(request, bill_pk):
    """
    Mark an invoice as approved.
    - PO claim invoices (status 102) -> status 103
    - Other invoices -> status 2
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        # Get current status from request body if provided
        current_status = None
        if request.body:
            data = json.loads(request.body)
            current_status = data.get('current_status')
        
        invoice = Bills.objects.get(bill_pk=bill_pk)
        
        # Use current_status from request or fall back to invoice's actual status
        status_to_check = current_status if current_status is not None else invoice.bill_status
        
        # PO claim invoices (102) go to 103, others go to 2
        if status_to_check == 102:
            invoice.bill_status = 103
        else:
            invoice.bill_status = 2
        invoice.save()
        
        return JsonResponse({'status': 'success', 'new_status': invoice.bill_status})
        
    except Bills.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error approving invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)