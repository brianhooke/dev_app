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

def main(request, division):
    costings = costing_service.get_costings_for_division(division)
    contacts_list = contact_service.get_checked_contacts(division)
    contacts_unfiltered_list = contact_service.get_all_contacts(division)
    quote_allocations = quote_service.get_quote_allocations_for_division(division)
    quote_allocations_sums_dict = quote_service.get_quote_allocations_sums_dict()
    committed_values = {pk: amount for pk, amount in Committed()}
    costings = costing_service.enrich_costings_with_committed(costings, committed_values)
    print('\n=== DEBUG: Invoice Allocations ===')    
    all_allocations = Invoice_allocations.objects.all().select_related('invoice_pk', 'item')
    print('\nAll Invoice Allocations:')
    for alloc in all_allocations:
        print(f"Invoice {alloc.invoice_pk.invoice_pk} - Item {alloc.item.costing_pk}: Amount {alloc.amount}")
    invoice_allocations_sums_dict = bill_service.get_invoice_allocations_sums_dict()
    paid_invoice_allocations_dict = bill_service.get_paid_invoice_allocations_dict()
    print('\ninvoice_allocations_sums_dict:', invoice_allocations_sums_dict)
    print('\npaid_invoice_allocations_dict:', paid_invoice_allocations_dict)
    costings = costing_service.enrich_costings_with_bill_data(
        costings, 
        invoice_allocations_sums_dict, 
        paid_invoice_allocations_dict
    )
    category_totals = costing_service.calculate_category_totals(costings, field='sc_invoiced')
    print('\nCategory Totals:')
    for cat, total in category_totals.items():
        print(f"Category '{cat}': Total {total}")
    items = costing_service.get_items_list(costings)
    committed_quotes_list = quote_service.get_committed_quotes_list(division)
    committed_quotes_json = json.dumps(committed_quotes_list, cls=DjangoJSONEncoder)
    quote_allocations_json = json.dumps(list(quote_allocations), cls=DjangoJSONEncoder)
    contacts_in_quotes_list = quote_service.get_contacts_in_quotes(division)
    contacts_not_in_quotes_list = quote_service.get_contacts_not_in_quotes(division)
    totals = aggregation_service.calculate_dashboard_totals(costings)
    total_contract_budget = totals['total_contract_budget']
    total_uncommitted = totals['total_uncommitted']
    total_committed = totals['total_committed']
    total_forecast_budget = totals['total_forecast_budget']
    total_sc_invoiced = totals['total_sc_invoiced']
    total_fixed_on_site = totals['total_fixed_on_site']
    total_sc_paid = totals['total_sc_paid']
    total_c2c = totals['total_c2c']
    po_globals = pos_service.get_po_globals()
    po_orders_list = pos_service.get_po_orders_list(division)
    invoices_list = bill_service.get_invoices_list(division)
    invoices_unallocated_list = bill_service.get_unallocated_invoices(division)
    invoices_allocated_list = bill_service.get_allocated_invoices(division)
    sc_totals_dict = bill_service.get_invoice_totals_by_hc_claim()
    hc_claims_list, approved_claims_list = invoice_service.get_hc_claims_list(sc_totals_dict)
    hc_claims_json = json.dumps(hc_claims_list, cls=DjangoJSONEncoder)
    approved_claims_json = json.dumps(approved_claims_list, cls=DjangoJSONEncoder)
    hc_variations_list = invoice_service.get_hc_variations_list()
    hc_variations_json = json.dumps(hc_variations_list, cls=DjangoJSONEncoder)
    hc_variation_allocations_list = invoice_service.get_hc_variation_allocations_list()
    hc_variation_allocations_json = json.dumps(hc_variation_allocations_list, cls=DjangoJSONEncoder)
    current_hc_claim = invoice_service.get_current_hc_claim()
    current_hc_claim_display_id = current_hc_claim.display_id if current_hc_claim else None
    current_hc_claim_date = current_hc_claim.date if current_hc_claim else None
    hc_claim_wip_adjustments = invoice_service.get_hc_claim_wip_adjustments(current_hc_claim)
    if current_hc_claim:
        for c in costings:
            c['hc_prev_invoiced'] = 0
            c['hc_this_claim_invoices'] = 0
            if c['category_order_in_list'] == -1 and current_hc_claim:
                hc_alloc = HC_claim_allocations.objects.filter(
                    hc_claim_pk=current_hc_claim,
                    item=c['costing_pk']
                ).first()
                if hc_alloc:
                    c['hc_this_claim_invoices'] = hc_alloc.sc_invoiced
            else:
                hc_this, hc_prev = bill_service.calculate_hc_claim_invoices(
                    c['costing_pk'], 
                    current_hc_claim
                )
                c['hc_this_claim_invoices'] = hc_this
                c['hc_prev_invoiced'] = hc_prev
    else:
        for c in costings:
            c['hc_prev_invoiced'] = 0
            c['hc_this_claim_invoices'] = 0
    for c in costings:
        c['hc_prev_fixedonsite'] = 0
    if current_hc_claim:
        for c in costings:
            prev_alloc = (
                HC_claim_allocations.objects
                .filter(item=c['costing_pk'], hc_claim_pk__lt=current_hc_claim.hc_claim_pk)
                .order_by('-hc_claim_pk')
                .first()
            )
            c['hc_prev_fixedonsite'] = prev_alloc.fixed_on_site if prev_alloc else 0
    else:
        for c in costings:
            c['hc_prev_fixedonsite'] = 0
    for c in costings:
        c['hc_prev_claimed'] = 0
        allocs = HC_claim_allocations.objects.filter(item=c['costing_pk'])
        for al in allocs:
            hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
            if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
                c['hc_prev_claimed'] += al.hc_claimed
    for c in costings:
        c['qs_claimed'] = 0
        allocs = HC_claim_allocations.objects.filter(item=c['costing_pk'])
        for al in allocs:
            hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
            if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
                c['qs_claimed'] += al.qs_claimed
    for c in costings:
        c['qs_this_claim'] = min(c['fixed_on_site'],c['contract_budget']-(c['committed']+c['uncommitted']-(c['hc_prev_invoiced']+c['hc_this_claim_invoices']))-c['qs_claimed'])
    spv_data = SPVData.objects.first()
    progress_claim_quote_allocations = quote_service.get_progress_claim_quote_allocations()
    progress_claim_invoice_allocations = bill_service.get_progress_claim_invoice_allocations()
    contract_budget_totals = costing_service.get_contract_budget_totals(division)
    claim_category_totals = (HC_claim_allocations.objects.filter(category__division=division)
        .values('hc_claim_pk', 'hc_claim_pk__display_id', 'category__invoice_category')
        .annotate(
            total_hc_claimed=Sum('hc_claimed'),
            total_qs_claimed=Sum('qs_claimed'),
            total_contract_budget=Sum('contract_budget'),
            max_order=Max('category__order_in_list'),
            latest_category=Max('category__category')
        ).order_by('hc_claim_pk', 'max_order'))
    claim_category_totals_dict = {}
    claim_category_totals_dict[0] = {
        "display_id": "Contract Budget",
        "categories": [{
            "categories_pk": None,
            "category": i['category__invoice_category'],
            "total_hc_claimed": float(i['total_contract_budget']) if i['total_contract_budget'] else 0.0,
            "total_qs_claimed": 0.0
        } for i in contract_budget_totals]
    }
    for i in claim_category_totals:
        pk = i['hc_claim_pk']
        if pk not in claim_category_totals_dict:
            claim_category_totals_dict[pk] = {
                "display_id": i['hc_claim_pk__display_id'],
                "categories": []
            }
        claim_category_totals_dict[pk]["categories"].append({
            "categories_pk": None,
            "category": i['category__invoice_category'],
            "total_hc_claimed": float(i['total_hc_claimed']) if i['total_hc_claimed'] else 0.0,
            "total_qs_claimed": float(i['total_qs_claimed']) if i['total_qs_claimed'] else 0.0,
            "total_contract_budget": float(i['total_contract_budget']) if i['total_contract_budget'] else 0.0
        })
    claim_category_totals_list = [{'hc_claim_pk': k, **v} for k, v in claim_category_totals_dict.items()]
    claim_category_totals_json = json.dumps(claim_category_totals_list)
    base_table_dropdowns = {}
    costing_pks = Costing.objects.filter(category__division=division).values_list('costing_pk', flat=True)
    for costing_pk in costing_pks:
        base_table_dropdowns[costing_pk] = {
            "committed": {},
            "invoiced_direct": {},
            "invoiced_all": {},
            "uncommitted": 0.0
        }
        costing = Costing.objects.get(costing_pk=costing_pk)
        is_margin = costing.category.order_in_list == -1
        committed_items, total_committed = quote_service.get_committed_items_for_costing(costing_pk)
        if committed_items:
            base_table_dropdowns[costing_pk]["committed"] = committed_items
        base_table_dropdowns[costing_pk]["uncommitted"] = float(costing.contract_budget) - total_committed
        invoice_directs = Invoice_allocations.objects.filter(
            item_id=costing_pk,
            invoice_pk__invoice_division=division
        ).filter(
            Q(allocation_type=1) | 
            Q(allocation_type=0, invoice_pk__invoice_type=1)
        ).select_related('invoice_pk__contact_pk').order_by('invoice_pk__invoice_date')
        base_table_dropdowns[costing_pk]["invoiced_direct"] = [{
            "supplier": invoice.invoice_pk.contact_pk.contact_name,
            "supplier_original": invoice.invoice_pk.contact_pk.contact_name,
            "date": invoice.invoice_pk.invoice_date.strftime('%d/%m/%Y'),
            "invoice_num": invoice.invoice_pk.supplier_invoice_number,
            "amount": float(invoice.amount)
        } for invoice in invoice_directs]
        invoice_alls = Invoice_allocations.objects.filter(
            item_id=costing_pk,
            invoice_pk__invoice_division=division
        ).select_related('invoice_pk__contact_pk').order_by('invoice_pk__invoice_date')
        base_table_dropdowns[costing_pk]["invoiced_all"] = [{
            "supplier": invoice.invoice_pk.contact_pk.contact_name,
            "supplier_original": invoice.invoice_pk.contact_pk.contact_name,
            "date": invoice.invoice_pk.invoice_date.strftime('%d/%m/%Y'),
            "invoice_num": invoice.invoice_pk.supplier_invoice_number,
            "amount": float(invoice.amount)
        } for invoice in invoice_alls]
        hc_claims_data = HC_claims.objects.filter(
            status__gt=0,
            hc_claim_allocations__item=costing_pk
        ).annotate(
            total_sc_invoiced=Sum('hc_claim_allocations__sc_invoiced', 
                                filter=Q(hc_claim_allocations__item=costing_pk))
        ).values('display_id', 'date', 'total_sc_invoiced')
        if hc_claims_data.exists():
            hc_claims_items = [{
                "supplier": f"HC Claim {claim['display_id']}",
                "supplier_original": f"HC Claim {claim['display_id']}",
                "date": claim['date'].strftime('%d/%m/%Y'),
                "invoice_num": str(claim['display_id']),
                "amount": float(claim['total_sc_invoiced'])
            } for claim in hc_claims_data]
            base_table_dropdowns[costing_pk]["invoiced_all"].extend(hc_claims_items)
    for pk in costing_pks:
        costing = Costing.objects.get(costing_pk=pk)
    context = {
        "division": division,
        "costings": costings,
        "contacts_in_quotes": contacts_in_quotes_list,
        "contacts_not_in_quotes": contacts_not_in_quotes_list,
        "contacts": contacts_list,
        "contacts_unfiltered": contacts_unfiltered_list,
        "committed_values": committed_values,
        "items": items,
        "hc_claim_wip_adjustments": hc_claim_wip_adjustments,
        "committed_quotes": committed_quotes_json,
        "quote_allocations": quote_allocations_json,
        "current_page": "build" if division == 2 else "quotes",
        "project_name": settings.PROJECT_NAME,
        "is_homepage": division == 1,
        "totals": {
            "total_contract_budget": total_contract_budget,
            "total_forecast_budget": total_forecast_budget,
            "total_uncommitted": total_uncommitted,
            "total_committed": total_committed,
            "total_sc_invoiced": total_sc_invoiced,
            "total_fixed_on_site": total_fixed_on_site,
            "total_sc_paid": total_sc_paid,
            "total_c2c": total_c2c
        },
        "po_globals": po_globals,
        "po_orders": po_orders_list,
        "invoices": invoices_list,
        "invoices_unallocated": invoices_unallocated_list,
        "invoices_allocated": invoices_allocated_list,
        "hc_claims": hc_claims_json,
        "approved_claims": approved_claims_json,
        "hc_variations": hc_variations_json,
        "hc_variation_allocations": hc_variation_allocations_json,
        "current_hc_claim_display_id": current_hc_claim_display_id,
        "current_hc_claim_date": current_hc_claim_date,
        "spv_data": spv_data,
        "progress_claim_quote_allocations_json": json.dumps(progress_claim_quote_allocations),
        "progress_claim_invoice_allocations_json": json.dumps(progress_claim_invoice_allocations),
        "claim_category_totals": claim_category_totals_json,
        "base_table_dropdowns_json": json.dumps(base_table_dropdowns).replace('"', '\"')
    }
    return render(request,"core/homepage.html" if division == 1 else "core/build.html",context)
def homepage_view(request):
    return main(request, 1)
def build_view(request):
    return main(request, 2)
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
def xeroapi(request):
  template = loader.get_template('homepage.html')
  return HttpResponse(template.render())
@limits(calls=60, period=60)
@sleep_and_retry

def make_api_request(url, headers):
    response = requests.get(url, headers=headers)
    return response
# ============================================================================
# DEPRECATED: Old Custom Connection (Client Credentials) - DO NOT USE
# Use OAuth2 flow in xero_oauth.py instead
# ============================================================================

# client_id = settings.XERO_CLIENT_ID
# client_id = settings.XERO_CLIENT_ID
# client_secret = settings.XERO_CLIENT_SECRET
# client_project = settings.XERO_PROJECT_ID

# def get_xero_token(request, division):
#     """DEPRECATED: Use OAuth2 via xero_oauth.py instead"""
#     division = int(division) if isinstance(division, str) else division
#     scopes_list = [
#         "accounting.transactions",
#         "accounting.transactions.read",
#         "accounting.reports.read",
#         "accounting.reports.tenninetynine.read",
#         "accounting.budgets.read",
#         "accounting.journals.read",
#         "accounting.settings",
#         "accounting.settings.read",
#         "accounting.contacts",
#         "accounting.contacts.read",
#         "accounting.attachments",
#         "accounting.attachments.read",
#         "files",
#         "files.read"
#     ]
#     scopes = ' '.join(scopes_list)
#     if division == 1:
#         client_id = settings.MDG_XERO_CLIENT_ID
#         client_secret = settings.MDG_XERO_CLIENT_SECRET
#     elif division == 2:
#         client_id = settings.MB_XERO_CLIENT_ID
#         client_secret = settings.MB_XERO_CLIENT_SECRET
#     else:
#         raise ValueError(f"Invalid division: {division}")
#     credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
#     headers = {
#         'Authorization': f'Basic {credentials}',
#         'Content-Type': 'application/x-www-form-urlencoded'
#     }
#     data = {
#         'grant_type': 'client_credentials',
#         'scope': scopes
#     }
#     response = requests.post('https://identity.xero.com/connect/token', headers=headers, data=data)
#     response_data = response.json()
#     logger.info(f"Xero token response: {response.status_code}")
#     logger.info(f"Xero token response data: {response_data}")
#     if response.status_code != 200:
#         raise ValueError(f"Failed to get Xero token: {response_data}")
#     if 'access_token' not in response_data:
#         raise ValueError(f"No access token in response: {response_data}")
#     request.session['access_token'] = response_data['access_token']
#     return JsonResponse(response_data)

# @csrf_exempt
# def get_xero_contacts(request):
#     """DEPRECATED: Use pull_xero_contacts in xero.py instead"""
#     division = int(request.GET.get('division', 0))
#     get_xero_token(request, division)
#     access_token = request.session.get('access_token')
#     headers = {
#         'Authorization': 'Bearer ' + access_token,
#         'Accept': 'application/json'
#     }
#     response = requests.get('https://api.xero.com/api.xro/2.0/Contacts', headers=headers)
#     data = response.json()
#     contacts = data['Contacts']
#     for contact in contacts:
#         xero_contact_id = contact['ContactID']
#         contact_name = contact.get('Name', 'Not Set')
#         contact_email = 'Not Set'
#         existing_contact = Contacts.objects.filter(xero_contact_id=xero_contact_id).first()
#         if existing_contact:
#             if existing_contact.division != division:
#                 existing_contact.division = division
#                 existing_contact.save()
#         else:
#             new_contact = Contacts(
#                 xero_contact_id=xero_contact_id,
#                 division=division,
#                 contact_name=contact_name,
#                 contact_email=contact_email
#             )
#             new_contact.save()
#     return JsonResponse(data)
@csrf_exempt
def mark_sent_to_boutique(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
            invoice.invoice_status = 4
            invoice.save()
            return JsonResponse({"status": "success", "message": f"Invoice {invoice_pk} marked as sent to boutique."}, status=200)
        except Invoices.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invoice does not exist."}, status=400)
    else:
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=400)
@csrf_exempt
def test_contact_id(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        except Invoices.DoesNotExist:
            return JsonResponse({"error": "No invoice found with the provided invoice_pk."}, status=400)
        contact = invoice.contact_pk
        return JsonResponse({'contact_id': contact.xero_contact_id})
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
    
    if template_type == 'allocated':
        # Allocated invoices - read-only display with Unallocate/Approve buttons
        context = {
            'main_table_title': 'Invoices',
            'main_table_columns': [
                {'header': 'Supplier', 'width': '22%'},
                {'header': 'Invoice #', 'width': '18%'},
                {'header': '$ Net', 'width': '15%'},
                {'header': '$ GST', 'width': '15%'},
                {'header': 'Unallocate', 'width': '15%'},
                {'header': 'Approve', 'width': '15%'},
            ],
            'allocations_columns': [
                {'header': 'Item', 'width': '40%'},
                {'header': '$ Net', 'width': '20%', 'still_to_allocate_id': 'TotalNet'},
                {'header': '$ GST', 'width': '20%', 'still_to_allocate_id': 'TotalGst'},
                {'header': 'Notes', 'width': '20%'},
            ],
            'readonly': True,
        }
        return render(request, 'core/invoices_allocated.html', context)
    
    # Unallocated invoices - editable with Allocate/Delete buttons
    context = {
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


def quotes_view(request):
    """Render the quotes section template."""
    # Define column configurations for the reusable template
    context = {
        'main_table_title': 'Quotes',
        'main_table_columns': [
            {'header': 'Supplier', 'width': '30%'},
            {'header': '$ Net', 'width': '20%'},
            {'header': 'Quote #', 'width': '25%'},
            {'header': 'Save', 'width': '15%'},
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


def po_view(request):
    """Render the PO section template using reusable allocations section."""
    # Define column configurations for the reusable template
    context = {
        'main_table_title': 'Purchase Orders',
        'main_table_columns': [
            {'header': 'Supplier', 'width': '18%'},
            {'header': 'First Name', 'width': '10%'},
            {'header': 'Last Name', 'width': '10%'},
            {'header': 'Email Address', 'width': '20%'},
            {'header': 'Amount', 'width': '12%'},
            {'header': 'Sent', 'width': '6%'},
            {'header': 'Update', 'width': '12%'},
            {'header': 'Email', 'width': '12%'},
        ],
        'allocations_columns': [
            {'header': 'Item', 'width': '50%'},
            {'header': 'Amount', 'width': '25%', 'still_to_allocate_id': 'RemainingNet'},
            {'header': 'Quote #', 'width': '25%'},
        ],
    }
    return render(request, 'core/po_new.html', context)


def get_project_invoices(request, project_pk):
    """
    Get invoices for a project filtered by status.
    Query params:
    - status: invoice_status to filter by (default: 0 for unallocated)
    """
    try:
        status = int(request.GET.get('status', 0))
        
        # Get invoices for this project with the specified status
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
        
        # Get costing items for this project
        costing_items = list(Costing.objects.filter(
            project_id=project_pk
        ).select_related('category').values(
            'costing_pk', 'item', 'category__category'
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


@csrf_exempt
def get_unallocated_invoice_allocations(request, invoice_pk):
    """
    Get all allocations for a specific invoice (for unallocated invoices section).
    """
    try:
        allocations = Invoice_allocations.objects.filter(
            invoice_pk_id=invoice_pk
        ).select_related('item').order_by('invoice_allocations_pk')
        
        allocations_data = []
        for alloc in allocations:
            allocations_data.append({
                'allocation_pk': alloc.invoice_allocations_pk,
                'item_pk': alloc.item_id,
                'item_name': alloc.item.item if alloc.item else None,
                'amount': float(alloc.amount) if alloc.amount else 0,
                'gst_amount': float(alloc.gst_amount) if alloc.gst_amount else 0,
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
        
        # Create new allocation with defaults
        allocation = Invoice_allocations.objects.create(
            invoice_pk_id=invoice_pk,
            item_id=data.get('item_pk') or None,
            amount=data.get('amount', 0),
            gst_amount=data.get('gst_amount', 0),
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
    Mark an invoice as approved (invoice_status = 2).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        invoice.invoice_status = 2
        invoice.save()
        
        return JsonResponse({'status': 'success'})
        
    except Invoices.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f'Error approving invoice: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)