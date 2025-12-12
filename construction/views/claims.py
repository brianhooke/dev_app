"""
Construction-specific claims views.

Contains HC claims, variations, progress claims, and direct costs functionality
that is specific to the construction project type.
"""

import csv
from decimal import Decimal, InvalidOperation
from django.template import loader
from core.forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from core.models import (
    Categories, Contacts, Quotes, Costing, Quote_allocations,
    DesignCategories, PlanPdfs, ReportPdfs, ReportCategories,
    Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead,
    Invoices, Invoice_allocations, HC_claims, HC_claim_allocations,
    Projects, Hc_variation, Hc_variation_allocations
)
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch, Max
from core.services import bills as bill_service
from core.services import quotes as quote_service
from core.services import pos as pos_service
from core.services import invoices as invoice_service
from core.services import costings as costing_service
from core.services import contacts as contact_service
from core.services import aggregations as aggregation_service
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
from django.core.mail import EmailMessage
from urllib.parse import urljoin
import textwrap
from django.core import serializers
from reportlab.lib import colors
import requests
from ratelimit import limits, sleep_and_retry
from urllib.request import urlretrieve
from django.http import HttpResponseBadRequest
import ssl
import urllib.request
from django.core.exceptions import ValidationError
from core.formulas import Committed
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@csrf_exempt
def associate_sc_claims_with_hc_claim(request):
    """Associate selected SC invoices with a new HC claim."""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)
        logger.info('Processing associate_sc_claims_with_hc_claim request')
        data = json.loads(request.body)
        logger.info(f'Request data: {data}')
        selected_invoices = data.get('selectedInvoices', [])
        logger.info(f'Selected invoices: {selected_invoices}')
        if not selected_invoices:
            logger.warning('No invoices selected')
            return JsonResponse({'error': 'No invoices selected'}, status=400)
        if HC_claims.objects.exists():
            latest_hc_claim = HC_claims.objects.latest('hc_claim_pk')
            logger.info(f'Latest HC claim status: {latest_hc_claim.status}')
            if latest_hc_claim.status == 0:
                logger.warning('Found existing HC claim in progress')
                return JsonResponse({
                    'error': 'There is a HC claim in progress. Complete this claim before starting another.'
                }, status=400)
        new_hc_claim = HC_claims.objects.create(date=datetime.now(), status=0)
        logger.info(f'Created new HC claim with pk: {new_hc_claim.hc_claim_pk}')
        update_result = Invoices.objects.filter(invoice_pk__in=selected_invoices).update(associated_hc_claim=new_hc_claim)
        logger.info(f'Updated {update_result} invoices with new HC claim')
        return JsonResponse({
            'latest_hc_claim_pk': new_hc_claim.hc_claim_pk,
            'invoices_updated': update_result
        })
    except Exception as e:
        logger.error(f'Error in associate_sc_claims_with_hc_claim: {str(e)}', exc_info=True)
        return JsonResponse({'error': 'Internal server error occurred'}, status=500)


@csrf_exempt
def update_fixedonsite(request):
    """Update fixed on site value for a costing item."""
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        fixed_on_site = data.get('fixed_on_site')
        costing = Costing.objects.get(pk=costing_pk)
        costing.fixed_on_site = fixed_on_site
        costing.save()
        return JsonResponse({'status': 'success'})


@csrf_exempt
def update_hc_claim_data(request):
    """Update HC claim data with allocations."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_hc_claim_display_id = data.get('current_hc_claim_display_id', '0')
            save_or_final = data.get('save_or_final', 0)
            hc_claim = HC_claims.objects.get(status=0)
            for entry in data.get('hc_claim_data', []):
                category = Categories.objects.get(category=entry['category'])
                item = Costing.objects.get(costing_pk=entry['item_id'])
                obj, created = HC_claim_allocations.objects.update_or_create(
                    hc_claim_pk=hc_claim,
                    category=category,
                    item=item,
                    defaults={
                        'contract_budget': entry['contract_budget'],
                        'working_budget': entry['working_budget'],
                        'uncommitted': entry['uncommitted'],
                        'committed': entry['committed'],
                        'fixed_on_site': entry['fixed_on_site_current'],
                        'fixed_on_site_previous': entry['fixed_on_site_previous'],
                        'fixed_on_site_this': entry['fixed_on_site_this'],
                        'sc_invoiced': entry['sc_invoiced'],
                        'sc_invoiced_previous': entry['sc_invoiced_previous'],
                        'adjustment': entry['adjustment'],
                        'hc_claimed': entry['hc_claimed'],
                        'hc_claimed_previous': entry['hc_claimed_previous'],
                        'qs_claimed': entry['qs_claimed'],
                        'qs_claimed_previous': entry['qs_claimed_previous'],
                    }
                )
            if current_hc_claim_display_id != '0':
                hc_claim_to_update = HC_claims.objects.get(display_id=current_hc_claim_display_id)
                if save_or_final == 1:
                    hc_claim_to_update.status = 1
                    hc_claim_to_update.save()
            return JsonResponse({'status': 'success', 'message': 'Data saved successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"Unexpected error: {str(e)}"}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


def get_claim_table(request, claim_id):
    """Get claim table data by claim ID."""
    claim_id = request.GET.get('claim_id')
    if not claim_id:
        return HttpResponseBadRequest("Missing claim_id")


@csrf_exempt
def send_hc_claim_to_xero(request):
    """Send HC claim to Xero as an invoice."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    try:
        data = json.loads(request.body)
        hc_claim_pk = data.get('hc_claim_pk')
        xero_contact_id = data.get('xero_contact_id')
        contact_name = data.get('contact_name')
        categories = data.get('categories', [])
        logger.info("Received Xero API parameters:")
        logger.info(f"hc_claim_pk: {hc_claim_pk}")
        logger.info(f"xero_contact_id: {xero_contact_id}")
        logger.info(f"contact_name: {contact_name}")
        logger.info(f"categories: {categories}")
        if not all([hc_claim_pk, xero_contact_id, contact_name]):
            logger.error("Missing required fields for Xero API")
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        hc_claim = HC_claims.objects.get(pk=hc_claim_pk)

        # DEPRECATED: Old custom connection - needs OAuth2 implementation
        # TODO: Replace with OAuth2 flow using XeroInstances
        raise NotImplementedError("This endpoint needs to be updated to use OAuth2. Use contacts.html and xero.py endpoints instead.")

        url = 'https://api.xero.com/api.xro/2.0/Invoices'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        project_id = settings.XERO_PROJECT_ID
        logger.info(f"Retrieving project with XERO_PROJECT_ID: {project_id}")
        try:
            project = Projects.objects.get(xero_project_id=project_id)
            logger.info(f"Retrieved project: {project.__dict__}")
        except Projects.DoesNotExist:
            logger.error(f"No project found with xero_project_id: {project_id}")
            return JsonResponse({"error": "Project not found"}, status=404)
        except Exception as e:
            logger.error(f"Error retrieving project: {str(e)}")
            return JsonResponse({"error": f"Error retrieving project: {str(e)}"}, status=500)
        sales_account = project.xero_sales_account
        if not sales_account:
            return JsonResponse({'success': False, 'error': 'Sales account not configured'})
        line_items = []
        for cat_data in categories:
            try:
                logger.info(f"Looking for category with PK: {cat_data['categories_pk']}")
                if cat_data['categories_pk'] is None:
                    logger.info("Using default category description for null categories_pk")
                    description = "HC Claim"
                else:
                    cat_obj = Categories.objects.get(categories_pk=cat_data['categories_pk'])
                    description = cat_obj.category
                    logger.info(f"Found category: {description}")
                amount = Decimal(str(cat_data['amount']))
                line_items.append({
                    "Description": description,
                    "Quantity": "1.0",
                    "UnitAmount": str(amount),
                    "AccountCode": sales_account,
                    "TaxType": "OUTPUT",
                    "TaxAmount": str(amount * Decimal('0.1')),
                    "Tracking": [
                        {
                            "Name": "Project",
                            "Option": project.project
                        }
                    ]
                })
            except Categories.DoesNotExist:
                logger.error(f"Category not found with PK: {cat_data['categories_pk']}")
                return JsonResponse({"error": f"Category not found with ID: {cat_data['categories_pk']}"}, status=404)
            except Exception as e:
                logger.error(f"Error processing category: {str(e)}")
                return JsonResponse({"error": f"Error processing category: {str(e)}"}, status=500)
        invoice_data = {
            "Type": "ACCREC",
            "Contact": {"ContactID": xero_contact_id},
            "LineItems": line_items,
            "Date": hc_claim.date.strftime("%Y-%m-%d"),
            "DueDate": (hc_claim.date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "Status": "DRAFT"
        }
        response = requests.post(url, headers=headers, json=invoice_data)
        response_data = response.json()
        logger.info(f"Xero response code: {response.status_code}")
        logger.info(f"Xero response JSON: {response_data}")
        if response.status_code == 200 and response_data.get('Status') == 'OK':
            invoice_id = response_data['Invoices'][0]['InvoiceID']
            hc_claim.status = 2
            hc_claim.invoicee = contact_name
            hc_claim.save()
            return JsonResponse({'success': True, 'invoice_id': invoice_id})
        else:
            return JsonResponse({
                'success': False,
                'error': f"Xero API error: {response_data.get('ErrorNumber', 'Unknown error')} - {response_data}"
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def delete_variation(request):
    """Delete a HC variation and its allocations."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method is allowed'}, status=405)
    try:
        variation_pk = request.POST.get('variation_pk')
        if not variation_pk:
            return JsonResponse({'success': False, 'error': 'Variation PK is required'}, status=400)
        try:
            variation = Hc_variation.objects.get(hc_variation_pk=variation_pk)
        except Hc_variation.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Variation not found'}, status=404)
        max_approved_claim_date = HC_claims.objects.filter(status__gt=0).aggregate(Max('date'))['date__max']
        if max_approved_claim_date and variation.date <= max_approved_claim_date:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete a variation that is already part of an HC claim'
            }, status=400)
        variation.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def create_variation(request):
    """Create a new HC variation and its allocation entries."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    try:
        data = json.loads(request.body)
        variation_date = data.get('variation_date')
        items = data.get('items', [])
        if not variation_date:
            return JsonResponse({'status': 'error', 'message': 'Variation date is required'}, status=400)
        if not items or len(items) == 0:
            return JsonResponse({'status': 'error', 'message': 'At least one item is required'}, status=400)
        variation_date_obj = datetime.strptime(variation_date, '%Y-%m-%d').date()
        with transaction.atomic():
            variation = Hc_variation.objects.create(
                date=variation_date
            )
            for item_data in items:
                costing_pk = item_data.get('costing_pk')
                amount = item_data.get('amount')
                notes = item_data.get('notes', '')
                if not costing_pk or not amount:
                    transaction.set_rollback(True)
                    return JsonResponse({'status': 'error', 'message': 'Costing and amount are required for each item'}, status=400)
                try:
                    costing = Costing.objects.get(costing_pk=costing_pk)
                except Costing.DoesNotExist:
                    transaction.set_rollback(True)
                    return JsonResponse({'status': 'error', 'message': f'Costing item with id {costing_pk} does not exist'}, status=404)
                Hc_variation_allocations.objects.create(
                    hc_variation=variation,
                    costing=costing,
                    amount=amount,
                    notes=notes
                )
        return JsonResponse({
            'status': 'success',
            'message': 'Variation created successfully',
            'variation_id': variation.hc_variation_pk
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error creating HC variation: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Error creating variation: {str(e)}'}, status=500)


@csrf_exempt
def post_progress_claim_data(request):
    """Post progress claim data and create invoice allocations."""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        invoice_id = data.get("invoice_id")
        allocations = data.get("allocations", [])
        updating = data.get("updating", False)
        if not invoice_id:
            return JsonResponse({"error": "No invoice_id provided"}, status=400)
        if not allocations:
            return JsonResponse({"error": "No allocations provided"}, status=400)
        new_allocations = []
        with transaction.atomic():
            invoice = Invoices.objects.get(pk=invoice_id)
            invoice.invoice_status = 1
            invoice.invoice_type = 2
            invoice.save()
            if updating:
                existing_count = Invoice_allocations.objects.filter(invoice_pk=invoice).count()
                Invoice_allocations.objects.filter(invoice_pk=invoice).delete()
                print(f"Deleted {existing_count} existing allocations for invoice {invoice_id}")
            for alloc in allocations:
                item_pk = alloc.get("item_pk")
                net = alloc.get("net", 0)
                gst = alloc.get("gst", 0)
                allocation_type = alloc.get("allocation_type", 0)
                notes = alloc.get("notes", "")
                if not item_pk:
                    raise ValueError("Missing item_pk in allocation")
                try:
                    costing_obj = Costing.objects.get(pk=item_pk)
                except Costing.DoesNotExist:
                    raise ValueError(f"Costing object not found for pk: {item_pk}")
                new_alloc = Invoice_allocations.objects.create(
                    invoice_pk=invoice,
                    item=costing_obj,
                    amount=net,
                    gst_amount=gst,
                    notes=notes,
                    allocation_type=allocation_type
                )
                new_allocations.append(new_alloc.invoice_allocations_pk)
        message = "Progress claim allocations updated successfully" if updating else "Progress claim data posted successfully"
        return JsonResponse({
            "success": True,
            "message": message,
            "updated_invoice": invoice.invoice_pk,
            "created_allocations": new_allocations,
            "was_update": updating
        }, status=200)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Invoices.DoesNotExist:
        return JsonResponse({"error": f"Invoice not found with id: {invoice_id}"}, status=404)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)


@csrf_exempt
def post_direct_cost_data(request):
    """Post direct cost data and create invoice allocations."""
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        invoice_id = data.get("invoice_id")
        allocations = data.get("allocations", [])
        updating = data.get("updating", False)
        if not invoice_id:
            return JsonResponse({"error": "No invoice_id provided"}, status=400)
        invoice = Invoices.objects.get(pk=invoice_id)
        invoice.invoice_status = 1
        invoice.invoice_type = 1
        invoice.save()
        if updating:
            existing_count = Invoice_allocations.objects.filter(invoice_pk=invoice).count()
            Invoice_allocations.objects.filter(invoice_pk=invoice).delete()
            print(f"Deleted {existing_count} existing allocations for invoice {invoice_id}")
        new_allocations = []
        for alloc in allocations:
            item_pk = alloc.get("item_pk")
            net = alloc.get("net", 0)
            gst = alloc.get("gst", 0)
            notes = alloc.get("notes", "")
            uncommitted_new = alloc.get("uncommitted_new")
            if not item_pk:
                continue
            costing_obj = Costing.objects.get(pk=item_pk)
            if uncommitted_new is not None:
                costing_obj.uncommitted_amount = uncommitted_new
                costing_obj.save()
            new_alloc = Invoice_allocations.objects.create(
                invoice_pk=invoice,
                item=costing_obj,
                amount=net,
                gst_amount=gst,
                notes=notes,
                allocation_type=0
            )
            new_allocations.append(new_alloc.invoice_allocations_pk)
        message = "Direct cost allocations updated successfully" if updating else "Direct cost data posted successfully"
        return JsonResponse({
            "message": message,
            "updated_invoice": invoice.invoice_pk,
            "created_allocations": new_allocations,
            "was_update": updating
        }, status=200)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Invoices.DoesNotExist:
        return JsonResponse({"error": f"Invoice not found with id: {invoice_id}"}, status=404)
    except Costing.DoesNotExist as e:
        return JsonResponse({"error": f"Costing object not found: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
