"""
Documents-related views.
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

def drawings(request):
    return render(request, 'core/drawings.html')

def drawings_view(request):
    def sort_key(x):
        try:
            return int(x)
        except ValueError:
            return x
    design_categories = DesignCategories.objects.all().order_by('design_category')
    report_categories = ReportCategories.objects.all().order_by('report_category')
    for category in design_categories:
        plan_pdfs = PlanPdfs.objects.filter(design_category=category).order_by('plan_number')
        plan_numbers = list(sorted(set(plan_pdfs.values_list('plan_number', flat=True)), key=alphanumeric_sort_key))    
        category.plan_numbers = plan_numbers
        category.file_paths = list(plan_pdfs.values_list('file', flat=True))
        rev_numbers_dict = {}
        for plan_number in plan_numbers:
            rev_numbers = plan_pdfs.filter(plan_number=plan_number).values_list('rev_number', flat=True)
            rev_numbers_dict[plan_number] = sorted(rev_numbers, key=lambda x: (isinstance(x, str), x))
            category.rev_numbers = json.dumps(rev_numbers_dict)
    for category in report_categories:
        report_pdfs = ReportPdfs.objects.filter(report_category=category).order_by('report_reference')
        report_references = list(sorted(set(report_pdfs.values_list('report_reference', flat=True)), key=sort_key))
        category.report_references = report_references
        category.file_paths = list(report_pdfs.values_list('file', flat=True))
    context = {
        'design_categories': design_categories,
        'report_categories': report_categories,
        'current_page': 'drawings',
        'project_name': settings.PROJECT_NAME,
    }
    return render(request, 'core/drawings.html', context)

def model_viewer_view(request):
    model_path = '3d/model.dae'
    full_path = os.path.join(settings.MEDIA_URL, model_path)
    logging.info(f'Full path to the model file: {full_path}')
    context = {'model_path': full_path,
               'current_page': 'model_viewer',
               'project_name': settings.PROJECT_NAME,
               }  
    return render(request, 'core/model_viewer.html', context)

@csrf_exempt
def create_plan(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        category_name = data.get('plan')
        category_type = data.get('categoryType')
        if category_name:
            if category_type == 1:  
                new_category = DesignCategories(design_category=category_name)
            elif category_type == 2:  
                new_category = ReportCategories(report_category=category_name)
            else:
                return JsonResponse({'status': 'error', 'error': 'Invalid category type'}, status=400)
            new_category.save()
            return JsonResponse({'status': 'success'}, status=201)
        else:
            return JsonResponse({'status': 'error', 'error': 'Invalid data'}, status=400)
    else:
        return JsonResponse({'status': 'error', 'error': 'Invalid method'}, status=405)

from django.core.files.storage import default_storage

@csrf_exempt
def upload_design_pdf(request):
    if request.method == 'POST':
        logger.info('Received POST request.')
        try:
            pdf_file = request.FILES['pdfFile']
            category_select = request.POST['categorySelect']
            pdf_name_values = json.loads(request.POST['pdfNameValues'])
            rev_num_values = json.loads(request.POST['revNumValues'])  
            logger.info(f'pdf_name_values: {pdf_name_values}')
            logger.info(f'rev_num_values: {rev_num_values}')
        except Exception as e:
            logger.error(f'Error parsing POST data: {e}')
            return JsonResponse({'status': 'error', 'error': 'Error parsing POST data'}, status=400)
        logger.info(f'Type of pdf_name_values: {type(pdf_name_values)}')
        logger.info(f'Type of rev_num_values: {type(rev_num_values)}')
        category = DesignCategories.objects.get(design_category_pk=category_select)
        logger.info(f'Category: {category.design_category}')
        pdf = PdfReader(pdf_file)
        pages = pdf.pages  
        logger.info(f'Number of pages: {len(pages)}')
        for page_number, page in enumerate(pages):
            try:
                pdf_writer = PdfWriter()
                pdf_writer.add_page(page)
            except AssertionError:
                logger.error(f'Error processing page {page_number}. Skipping.')
                continue
            plan_number = pdf_name_values.get(str(page_number + 1), None)
            rev_number = rev_num_values.get(str(page_number + 1), None)
            if not plan_number or not rev_number:
                logger.warning(f'Missing plan_number or rev_number for page {page_number}. Skipping.')
                continue
            output_filename = f'plans/{category.design_category}_{plan_number}_{rev_number}.pdf'
            logger.info(f'Saving page {page_number} as {output_filename}.')
            output_pdf = BytesIO()
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            default_storage.save(output_filename, output_pdf)
            PlanPdfs.objects.create(
                file=output_filename,
                design_category=category,
                plan_number=plan_number,
                rev_number=rev_number
            )
            logger.info(f'Successfully created PlanPdfs object for page {page_number}.')         
    return JsonResponse({'status': 'success'})

@csrf_exempt
def get_design_pdf_url(request, design_category, plan_number, rev_number=None):
    try:
        if rev_number is None:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number)
        else:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number, rev_number=rev_number)
        file_url = plan_pdf.file.url
        if file_url.startswith('/media/media/'):
            file_url = '/media/' + file_url[12:]  
        rev_numbers = PlanPdfs.objects.filter(design_category=design_category, plan_number=plan_number).values_list('rev_number', flat=True)
        return JsonResponse({'file_url': file_url, 'rev_numbers': list(rev_numbers)})
    except PlanPdfs.DoesNotExist:
        return JsonResponse({'error': 'PlanPdfs not found'}, status=404)

@csrf_exempt
def upload_report_pdf(request):
    if request.method == 'POST':
        logger.info('Received POST request.')
        try:
            pdf_file = request.FILES['pdfFile']
            category_select = request.POST['categorySelect']
            pdf_name_value = request.POST['pdfNameValue']
            logger.info(f'pdf_name_value: {pdf_name_value}')
        except Exception as e:
            logger.error(f'Error parsing POST data: {e}')
            return JsonResponse({'status': 'error', 'error': 'Error parsing POST data'}, status=400)
        category = ReportCategories.objects.get(report_category_pk=category_select)
        logger.info(f'Category: {category.report_category}')
        plan_number = pdf_name_value
        if not plan_number:
            logger.warning(f'Missing plan_number. Skipping.')
            return JsonResponse({'status': 'error', 'error': 'Missing plan_number'}, status=400)
        datetime_str = datetime.now().strftime("%Y%m%d%H%M%S")  
        output_filename = f'reports/{category.report_category}_{plan_number}_{datetime_str}.pdf'
        logger.info(f'Saving file as {output_filename}.')
        default_storage.save(output_filename, pdf_file)
        ReportPdfs.objects.create(
            file=output_filename,
            report_category=category,
            report_reference=plan_number
        )
        logger.info(f'Successfully created ReportPdfs object.')         
    return JsonResponse({'status': 'success'})

@csrf_exempt
def get_report_pdf_url(request, report_category, report_reference=None):
    try:
        if report_reference:
            report_pdf = ReportPdfs.objects.get(report_category=report_category, report_reference=report_reference)
            file_url = report_pdf.file.url
            if file_url.startswith('/media/media/'):
                file_url = '/media/' + file_url[12:]  
            return JsonResponse({'file_url': file_url})
        else:
            report_pdfs = ReportPdfs.objects.filter(report_category=report_category)
            response_data = []
            for report_pdf in report_pdfs:
                file_url = report_pdf.file.url
                if file_url.startswith('/media/media/'):
                    file_url = '/media/' + file_url[12:]  
                response_data.append({
                    'file_url': file_url,
                    'report_reference': report_pdf.report_reference
                })
            return JsonResponse({'data': response_data})
    except ReportPdfs.DoesNotExist:
        return JsonResponse({'error': 'ReportPdfs not found'}, status=404)

def alphanumeric_sort_key(s):
    return [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', s)]