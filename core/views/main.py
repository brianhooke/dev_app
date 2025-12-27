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
from ..models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Bills, Bill_allocations, HC_claims, HC_claim_allocations, Projects, Hc_variation, Hc_variation_allocations
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
from ..models import Bills, Contacts, Costing, Categories, Quote_allocations, Quotes, Po_globals, Po_orders, SPVData
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