"""
Main dashboard views.

Contains the primary dashboard views (main, homepage_view, build_view)
and utility functions.
"""

import csv
from decimal import Decimal, InvalidOperation
from django.template import loader
from ..forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Invoices, Invoice_allocations, HC_claims, HC_claim_allocations, Projects, Hc_variation, Hc_variation_allocations
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch, Max
from ..services import quotes as quote_service
from ..services import pos as pos_service
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import uuid
from django.core.files.base import ContentFile
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
from django.core.mail import EmailMessage
from urllib.parse import urljoin
import textwrap
from django.core import serializers
from reportlab.lib import colors
import requests
from decimal import Decimal
from ratelimit import limits, sleep_and_retry
from urllib.request import urlretrieve
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models import Sum
from ..models import Invoices, Contacts, Costing, Categories, Quote_allocations, Quotes, Po_globals, Po_orders, SPVData
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
def create_contacts(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        contacts = data.get('contacts')
        division = data.get('division')
        if contacts:
            for contact in contacts:
                if contact['name']:
                    Contacts.objects.create(contact_name=contact['name'], contact_email=contact['email'], division=division)
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'No contacts provided'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'})
def send_test_email():
    subject = 'Test Email - Developer App'
    message = 'If you are reading this, the Developer App is sending emails successfully.'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = ['brian.hooke@mason.build']
    try:
        send_mail(subject, message, from_email, recipient_list)
        logger.info('Test email sent successfully.')
    except Exception as e:
        logger.error(f'Failed to send test email: {e}')
        raise
def send_test_email_view(request):
    try:
        send_test_email()
        return JsonResponse({'status': 'Email sent'})
    except Exception as e:
        logger.error(f'Error in send_test_email_view: {e}')
        return JsonResponse({'status': 'Error', 'message': str(e)}, status=500)
from django.core.files.storage import default_storage

@csrf_exempt
def upload_categories(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            logger.info('CSV file decoded and reader created')
            first_row = next(reader)
            logger.info('First row of CSV: %s', first_row)
            reader = csv.DictReader(decoded_file)
            Categories.objects.all().delete()
            logger.info('All existing Categories objects deleted')
            for row in reader:
                Categories.objects.create(
                    category=row['category'],
                    division=row['division'],
                    order_in_list=row['order_in_list']
                )
                logger.info('Created new Categories object: %s', row)
            return JsonResponse({"message": "CSV file uploaded successfully"}, status=200)
        else:
            logger.error('Form is not valid: %s', form.errors)
            return JsonResponse({"message": str(form.errors)}, status=400)
    else:
        form = CSVUploadForm()
        logger.info('GET request received, CSVUploadForm created')
@csrf_exempt
def upload_costings(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        csv_reader = csv.DictReader(csv_file.read().decode('utf-8').splitlines())
        try:
            for row in csv_reader:
                logger.debug(f"Processing row: {row}")
                category_name = row['category']
                category, created = Categories.objects.get_or_create(category=category_name)
                logger.debug(f"Category: {category}, Created: {created}")
                Costing.objects.update_or_create(
                    category=category,
                    item=row['item'],
                    defaults={
                        'xero_account_code': row.get('xero_account_code', ''),
                        'contract_budget': Decimal(row.get('contract_budget', '0.00')),
                        'uncommitted': Decimal(row.get('uncommitted', '0.00')),
                        'sc_invoiced': Decimal(row.get('sc_invoiced', '0.00')),
                        'sc_paid': Decimal(row.get('sc_paid', '0.00')),
                        'fixed_on_site': Decimal(row.get('fixed_on_site', '0.00')),
                    }
                )
                logger.debug(f"Updated or created Costing for item: {row['item']}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})
@csrf_exempt
def update_contract_budget_amounts(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        skipped_rows = []
        updated_rows = []
        try:
            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
            csv_reader = csv.DictReader(decoded_file)
            logger.info("Starting to process CSV file for contract budget updates")
            logger.info(f"CSV Headers: {csv_reader.fieldnames}")
            row_count = 0
            for row in csv_reader:
                row_count += 1
                try:
                    if row.get('contract_budget'):
                        row['contract_budget'] = row['contract_budget'].strip()
                    logger.info(f"Processing row {row_count}: {row}")
                    category = Categories.objects.get(category=row['category'])
                    logger.info(f"Found category: {category.category} (pk={category.categories_pk})")
                    try:
                        costing = Costing.objects.get(
                            category=category,
                            item=row['item']
                        )
                        logger.info(f"Found costing: {costing.item} (pk={costing.costing_pk})")
                        old_budget = costing.contract_budget
                        try:
                            budget_str = row['contract_budget'].replace('$', '').replace(',', '')
                            new_budget = Decimal(budget_str)
                            if new_budget != old_budget:
                                costing.contract_budget = new_budget
                                costing.save()
                                logger.info(f"Updated contract_budget for {row['category']} - {row['item']} from {old_budget} to {new_budget}")
                                updated_rows.append({
                                    'category': row['category'],
                                    'item': row['item'],
                                    'old_budget': str(old_budget),
                                    'new_budget': str(new_budget)
                                })
                            else:
                                logger.info(f"Skipping update for {row['category']} - {row['item']} as budget hasn't changed ({old_budget})")
                        except (ValueError, InvalidOperation) as e:
                            logger.error(f"Invalid budget value '{row['contract_budget']}' for {row['category']} - {row['item']}: {str(e)}")
                            skipped_rows.append({
                                'category': row['category'],
                                'item': row['item'],
                                'reason': f'Invalid budget value: {row["contract_budget"]}'
                            })
                            continue
                    except Costing.DoesNotExist:
                        logger.warning(f"No costing found for category: {row['category']}, item: {row['item']}")
                        skipped_rows.append({
                            'category': row['category'],
                            'item': row['item'],
                            'reason': 'No matching costing entry found'
                        })
                        continue
                except Categories.DoesNotExist:
                    logger.warning(f"Category not found: {row['category']}")
                    skipped_rows.append({
                        'category': row['category'],
                        'item': row['item'],
                        'reason': f'Category not found: {row["category"]}'
                    })
                    continue
                except Exception as e:
                    logger.error(f"Error processing row: {row}. Error: {str(e)}")
                    skipped_rows.append({
                        'category': row['category'],
                        'item': row['item'],
                        'reason': f'Error: {str(e)}'
                    })
                    continue
            response_data = {
                'message': 'File processed successfully',
                'updated': len(updated_rows),
                'skipped': len(skipped_rows),
                'updated_rows': updated_rows,
                'skipped_rows': skipped_rows
            }
            logger.info(f"Completed processing CSV file. Updated: {len(updated_rows)}, Skipped: {len(skipped_rows)}")
            if updated_rows:
                logger.info("Updated rows:")
                for row in updated_rows:
                    logger.info(f"  {row['category']} - {row['item']}: {row['old_budget']} -> {row['new_budget']}")
            if skipped_rows:
                logger.info("Skipped rows:")
                for row in skipped_rows:
                    logger.info(f"  {row['category']} - {row['item']}: {row['reason']}")
            status_code = 206 if skipped_rows else 200
            return JsonResponse(response_data, status=status_code)
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return JsonResponse({
                'error': f'Error processing file: {str(e)}',
                'updated_rows': updated_rows,
                'skipped_rows': skipped_rows
            }, status=400)
    return JsonResponse({'error': 'No file uploaded'}, status=400)
@csrf_exempt
def upload_letterhead(request):
    if request.method == 'POST':
        file = request.FILES['letterhead_path']
        file.name = 'letterhead.pdf'
        file_path = default_storage.save(file.name, file)
        letterhead = Letterhead(letterhead_path=file_path)
        letterhead.save()
        Letterhead.objects.exclude(id=letterhead.id).delete()
        return JsonResponse({'message': 'File uploaded successfully'})
    else:
        return JsonResponse({'error': 'Invalid request method'})
@csrf_exempt
def update_contacts(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        for contact in data:
            try:
                contact_obj = Contacts.objects.get(contact_pk=contact['contact_pk'])
                contact_obj.checked = contact['checked']
                contact_obj.contact_email = contact['contact_email']
                contact_obj.save()
            except Contacts.DoesNotExist:
                return JsonResponse({'error': 'Contact with pk {} does not exist'.format(contact['contact_pk'])}, status=400)
        return JsonResponse({'message': 'Contacts updated successfully'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)
@csrf_exempt
def upload_margin_category_and_lines(request):
    if request.method == 'POST':
        try:
            logger.info('Received margin category upload request')
            data = json.loads(request.body)
            logger.info(f'Parsed request body: {data}')
            rows = data['rows']
            division = data['division']
            logger.info(f'Processing {len(rows)} rows for division {division}')
            with transaction.atomic():
                if not rows:
                    raise ValueError('No data rows found in CSV')
                try:
                    category_name = rows[0]['category']
                    invoice_category = rows[0].get('invoice_category', category_name)
                    logger.info(f'Processing category: {category_name}, invoice_category: {invoice_category}')
                except (KeyError, IndexError) as e:
                    raise ValueError(f'Missing required field in CSV: {str(e)}')
                Categories.objects.update_or_create(
                    division=division,
                    order_in_list=-1,
                    defaults={
                        'category': category_name,
                        'invoice_category': invoice_category
                    }
                )
                total_cost = sum(Decimal(row['contract_budget']) for row in rows)
                quote, created = Quotes.objects.update_or_create(
                    supplier_quote_number='Internal_Margin_Quote',
                    defaults={
                        'total_cost': total_cost
                    }
                )
                Quote_allocations.objects.filter(quotes_pk=quote).delete()
                category = Categories.objects.get(division=division, order_in_list=-1)
                for row in rows:
                    costing, created = Costing.objects.update_or_create(
                        category=category,
                        item=row['item'],
                        defaults={
                            'xero_account_code': row['xero_code'],
                            'contract_budget': row['contract_budget'],
                            'uncommitted': 0,
                            'fixed_on_site': 0,
                            'sc_invoiced': 0,
                            'sc_paid': 0
                        }
                    )
                    Quote_allocations.objects.create(
                        quotes_pk=quote,
                        item=costing,
                        amount=row['contract_budget']
                    )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f'Error in upload_margin_category_and_lines: {str(e)}')
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def invoices_view(request):
    """Render the invoices section template."""
    template_type = request.GET.get('template', 'unallocated')
    
    if template_type == 'approvals':
        # Approvals - invoices approved and ready to send to Xero (status 2 or 103)
        context = {
            'template_type': 'approvals',
            'main_table_title': 'Approved Invoices',
            'main_table_columns': [
                {'header': 'Project', 'width': '15%'},
                {'header': 'Xero Instance', 'width': '12%'},
                {'header': 'Xero Account', 'width': '12%'},
                {'header': 'Supplier', 'width': '13%'},
                {'header': '$ Gross', 'width': '9%'},
                {'header': '$ Net', 'width': '9%'},
                {'header': '$ GST', 'width': '9%'},
                {'header': 'Send to Xero', 'width': '12%'},
                {'header': 'Return to Project', 'width': '12%'},
            ],
            'allocations_columns': [
                {'header': 'Item', 'width': '25%'},
                {'header': '$ Net', 'width': '15%', 'still_to_allocate_id': 'TotalNet'},
                {'header': '$ GST', 'width': '15%', 'still_to_allocate_id': 'TotalGst'},
                {'header': 'Notes', 'width': '45%'},
            ],
            'readonly': True,
        }
        return render(request, 'core/invoices.html', context)
    
    if template_type == 'allocated':
        # Allocated invoices - read-only display with Unallocate/Approve buttons
        context = {
            'template_type': 'allocated',
            'main_table_title': 'Invoices',
            'main_table_columns': [
                {'header': 'Supplier', 'width': '15%'},
                {'header': 'Invoice #', 'width': '12%'},
                {'header': '$ Net', 'width': '10%'},
                {'header': '$ GST', 'width': '10%'},
                {'header': 'Progress Claim', 'width': '10%'},
                {'header': 'Unallocate', 'width': '13%'},
                {'header': 'Approve', 'width': '13%'},
                {'header': 'Save', 'width': '10%'},
            ],
            'allocations_columns': [
                {'header': 'Item', 'width': '20%'},
                {'header': '$ Net', 'width': '12%', 'still_to_allocate_id': 'TotalNet'},
                {'header': '$ GST', 'width': '12%', 'still_to_allocate_id': 'TotalGst'},
                {'header': 'Notes', 'width': '56%'},
            ],
            'readonly': True,
        }
        return render(request, 'core/invoices.html', context)
    
    # Unallocated invoices - editable with Allocate/Delete buttons
    context = {
        'template_type': 'unallocated',
        'main_table_title': 'Invoices',
        'main_table_columns': [
            {'header': 'Supplier', 'width': '25%'},
            {'header': 'Invoice #', 'width': '20%'},
            {'header': '$ Net', 'width': '17%'},
            {'header': '$ GST', 'width': '17%'},
            {'header': 'Allocate', 'width': '13%'},
            {'header': 'Del', 'width': '8%'},
        ],
        'allocations_columns': [
            {'header': 'Item', 'width': '35%'},
            {'header': '$ Net', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': '$ GST', 'width': '15%', 'still_to_allocate_id': 'RemainingGst'},
            {'header': 'Notes', 'width': '30%'},
            {'header': '', 'width': '5%', 'align': 'center'},
        ],
    }
    return render(request, 'core/invoices.html', context)


@csrf_exempt
def update_allocated_invoice(request, invoice_pk):
    """Update invoice number and GST for an allocated invoice."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)
    
    try:
        import json
        data = json.loads(request.body)
        invoice_number = data.get('invoice_number', '')
        total_gst = data.get('total_gst', '0.00')
        
        invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        invoice.supplier_invoice_number = invoice_number
        invoice.total_gst = float(total_gst)
        invoice.save()
        
        return JsonResponse({'status': 'success'})
    except Invoices.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error updating allocated invoice {invoice_pk}: {e}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def quotes_view(request):
    """Render the quotes section template."""
    # Define column configurations for the reusable template
    context = {
        'main_table_title': 'Quotes',
        'main_table_columns': [
            {'header': 'Supplier', 'width': '50%'},
            {'header': '$ Net', 'width': '15%'},
            {'header': 'Quote #', 'width': '15%'},
            {'header': 'Save', 'width': '10%'},
            {'header': 'Del', 'width': '10%'},
        ],
        'allocations_columns': [
            {'header': 'Item', 'width': '40%'},
            {'header': '$ Net', 'width': '20%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Notes', 'width': '35%'},
            {'header': '', 'width': '5%', 'align': 'center'},
        ],
    }
    return render(request, 'core/quotes.html', context)


def get_project_invoices(request, project_pk):
    """
    Get invoices for a project filtered by status.
    Query params:
    - status: invoice_status to filter by (default: 0 for unallocated)
             status=1 also includes status=102 (PO claim invoices)
    """
    try:
        status = int(request.GET.get('status', 0))
        
        # Get invoices for this project with the specified status
        # For allocated invoices (status=1), also include PO claim invoices (status=102)
        if status == 1:
            invoices = Invoices.objects.filter(
                project_id=project_pk,
                invoice_status__in=[1, 102]
            ).select_related('contact_pk', 'email_attachment').order_by('-invoice_pk')
        else:
            invoices = Invoices.objects.filter(
                project_id=project_pk,
                invoice_status=status
            ).select_related('contact_pk', 'email_attachment').order_by('-invoice_pk')
        
        # Get suppliers (contacts) for this project's xero instance
        project = Projects.objects.get(projects_pk=project_pk)
        suppliers = []
        if project.xero_instance:
            suppliers = list(Contacts.objects.filter(
                xero_instance=project.xero_instance
            ).values('contact_pk', 'name').order_by('name'))
        
        # Build response data
        invoices_data = []
        for inv in invoices:
            # Get PDF URL from invoice.pdf field
            pdf_url = None
            if inv.pdf:
                try:
                    pdf_url = inv.pdf.url
                except Exception as e:
                    logger.error(f'Error getting PDF URL for invoice {inv.invoice_pk}: {str(e)}')
            
            # Get attachment URL from email_attachment (fallback)
            attachment_url = None
            if inv.email_attachment:
                try:
                    attachment_url = inv.email_attachment.get_download_url()
                except Exception as e:
                    logger.error(f'Error getting attachment URL for invoice {inv.invoice_pk}: {str(e)}')
            
            logger.info(f'Invoice {inv.invoice_pk}: pdf_url={pdf_url}, attachment_url={attachment_url}')
            
            invoices_data.append({
                'invoice_pk': inv.invoice_pk,
                'supplier_pk': inv.contact_pk.contact_pk if inv.contact_pk else None,
                'supplier_name': inv.contact_pk.name if inv.contact_pk else None,
                'invoice_number': inv.supplier_invoice_number or '',
                'total_net': float(inv.total_net) if inv.total_net else None,
                'total_gst': float(inv.total_gst) if inv.total_gst else None,
                'pdf_url': pdf_url,
                'attachment_url': attachment_url,
                'invoice_status': inv.invoice_status,
            })
        
        # Get costing items for this project (include unit_name for construction mode)
        costing_items = list(Costing.objects.filter(
            project_id=project_pk
        ).select_related('category', 'unit').values(
            'costing_pk', 'item', 'unit__unit_name', 'category__category'
        ).order_by('category__order_in_list', 'order_in_list'))
        
        return JsonResponse({
            'status': 'success',
            'invoices': invoices_data,
            'suppliers': suppliers,
            'costing_items': costing_items,
            'project_pk': project_pk,
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    except Exception as e:
        logger.error(f'Error in get_project_invoices: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_allocated_invoices(request, project_pk):
    """
    Get allocated invoices (status != 0) for a project.
    """
    try:
        # Get invoices with status != 0 (allocated)
        # Include status=1 (allocated) and status=102 (PO claim invoices)
        invoices = Invoices.objects.filter(
            project_id=project_pk,
            invoice_status__in=[1, 102]
        ).select_related('contact_pk', 'email_attachment').order_by('-invoice_pk')
        
        # Build response data
        invoices_data = []
        for inv in invoices:
            pdf_url = None
            if inv.pdf:
                try:
                    pdf_url = inv.pdf.url
                except Exception as e:
                    logger.error(f'Error getting PDF URL for invoice {inv.invoice_pk}: {str(e)}')
            
            attachment_url = None
            if inv.email_attachment:
                try:
                    attachment_url = inv.email_attachment.get_download_url()
                except Exception as e:
                    logger.error(f'Error getting attachment URL for invoice {inv.invoice_pk}: {str(e)}')
            
            invoices_data.append({
                'invoice_pk': inv.invoice_pk,
                'supplier_pk': inv.contact_pk.contact_pk if inv.contact_pk else None,
                'supplier_name': inv.contact_pk.name if inv.contact_pk else None,
                'invoice_number': inv.supplier_invoice_number or '',
                'total_net': float(inv.total_net) if inv.total_net else None,
                'total_gst': float(inv.total_gst) if inv.total_gst else None,
                'pdf_url': pdf_url,
                'attachment_url': attachment_url,
                'invoice_status': inv.invoice_status,
            })
        
        return JsonResponse({
            'status': 'success',
            'invoices': invoices_data,
            'project_pk': project_pk,
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Project not found'}, status=404)
    except Exception as e:
        logger.error(f'Error in get_allocated_invoices: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def get_unallocated_invoice_allocations(request, invoice_pk):
    """
    Get all allocations for a specific invoice (for unallocated invoices section).
    """
    try:
        allocations = Invoice_allocations.objects.filter(
            invoice_pk_id=invoice_pk
        ).select_related('item', 'item__unit').order_by('invoice_allocations_pk')
        
        allocations_data = []
        for alloc in allocations:
            # Get unit from Costing item's linked Units object if available
            unit = ''
            if alloc.item and alloc.item.unit:
                unit = alloc.item.unit.unit_name  # unit is FK to Units model
            elif alloc.unit:
                unit = alloc.unit
            
            allocations_data.append({
                'allocation_pk': alloc.invoice_allocations_pk,
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
        invoice_pk = data.get('invoice_pk')
        
        if not invoice_pk:
            return JsonResponse({'status': 'error', 'message': 'invoice_pk required'}, status=400)
        
        # Create new allocation with defaults (including construction fields)
        allocation = Invoice_allocations.objects.create(
            invoice_pk_id=invoice_pk,
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
            'allocation_pk': allocation.invoice_allocations_pk
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
        
        allocation = Invoice_allocations.objects.get(invoice_allocations_pk=allocation_pk)
        
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
        
    except Invoice_allocations.DoesNotExist:
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
        allocation = Invoice_allocations.objects.get(invoice_allocations_pk=allocation_pk)
        allocation.delete()
        
        return JsonResponse({'status': 'success'})
        
    except Invoice_allocations.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
    except Exception as e:
        logger.error(f'Error deleting invoice allocation: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def allocate_invoice(request, invoice_pk):
    """
    Mark an invoice as allocated (invoice_status = 1).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        invoice.invoice_status = 1
        invoice.save()
        
        return JsonResponse({'status': 'success'})
        
    except Invoices.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error allocating invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def unallocate_invoice(request, invoice_pk):
    """
    Return an invoice to unallocated status (invoice_status = 0).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        invoice.invoice_status = 0
        invoice.save()
        
        return JsonResponse({'status': 'success'})
        
    except Invoices.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error unallocating invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def approve_invoice(request, invoice_pk):
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
        
        invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        
        # Use current_status from request or fall back to invoice's actual status
        status_to_check = current_status if current_status is not None else invoice.invoice_status
        
        # PO claim invoices (102) go to 103, others go to 2
        if status_to_check == 102:
            invoice.invoice_status = 103
        else:
            invoice.invoice_status = 2
        invoice.save()
        
        return JsonResponse({'status': 'success', 'new_status': invoice.invoice_status})
        
    except Invoices.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error approving invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)