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
logger.setLevel(logging.INFO)  # Set logging level to INFO


@csrf_exempt
def commit_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        total_cost = data['total_cost']
        supplier_quote_number = data['supplier_quote_number']  # Get the supplier quote number
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
            notes = allocation.get('notes', '')  # Get the notes, default to '' if not present
            if amount == '':
                amount = '0'
            Quote_allocations.objects.create(quotes_pk=quote, item=item, amount=amount, notes=notes)  # Assign the Costing instance to item
            # Update the Costing.uncommitted field
            uncommitted = allocation['uncommitted']
            item.uncommitted = uncommitted
            item.save()
        return JsonResponse({'status': 'success'})


@csrf_exempt
def update_quote(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        quote_id = data.get('quote_id')
        total_cost = data.get('total_cost')
        supplier_quote_number = data.get('supplier_quote_number')  # Get the supplier quote number
        allocations = data.get('allocations')
        try:
            quote = Quotes.objects.get(pk=quote_id)
        except Quotes.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Quote not found'})
        quote.total_cost = total_cost
        quote.supplier_quote_number = supplier_quote_number
        quote.save()
        # Delete the existing allocations for the quote
        Quote_allocations.objects.filter(quotes_pk=quote_id).delete()
        # Save the new allocations
        for allocation in allocations:
            notes = allocation.get('notes', '')  # Get the notes, default to '' if not present
            item = Costing.objects.get(pk=allocation['item'])
            alloc = Quote_allocations(quotes_pk=quote, item=item, amount=allocation['amount'], notes=notes)
            alloc.save()
            # Update the Costing.uncommitted field
            uncommitted = allocation['uncommitted']
            Costing.objects.filter(item=allocation['item']).update(uncommitted=uncommitted)
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@csrf_exempt
def delete_quote(request):
    if request.method == 'DELETE':
        # Parse the request body to get the supplier quote number
        data = json.loads(request.body)
        supplier_quote_number = data.get('supplier_quote_number')
        
        if not supplier_quote_number:
            return JsonResponse({'status': 'fail', 'message': 'Supplier quote number is required'}, status=400)
            
        # Get the quote from the database
        try:
            quote = Quotes.objects.get(supplier_quote_number=supplier_quote_number)
        except Quotes.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Quote not found'}, status=404)
        # Delete the quote
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

# create new design or report category


@csrf_exempt
def update_uncommitted(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        uncommitted = data.get('uncommitted')
        notes = data.get('notes')  # Get the notes data from the request
        # Get the Costing object and update it
        try:
            costing = Costing.objects.get(costing_pk=costing_pk)
            costing.uncommitted = uncommitted
            costing.uncommitted_notes = notes  # Update the notes field
            costing.save()
            # Return a JSON response indicating success
            return JsonResponse({'status': 'success'})
        except Costing.DoesNotExist:
            # If the Costing object is not found, return an error response
            return JsonResponse({'status': 'error', 'message': 'Costing not found'}, status=404)
    # If not a POST request, return a method not allowed response
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

logger = logging.getLogger(__name__)


def get_quotes_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')
    contact = Contacts.objects.filter(contact_name=supplier_name).first()
    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)

    quotes = Quotes.objects.filter(contact_pk=contact).prefetch_related(
        Prefetch('quote_allocations_set', queryset=Quote_allocations.objects.all(), to_attr='fetched_allocations')  # Changed to_attr to 'fetched_allocations'
    )

    quotes_data = []
    for quote in quotes:
        quote_info = {
            "quotes_pk": quote.quotes_pk,
            "supplier_quote_number": quote.supplier_quote_number,
            "total_cost": str(quote.total_cost),  # Assuming decimal should be string for JSON
            "quote_allocations": [
                {
                    "quote_allocations_pk": allocation.quote_allocations_pk,
                    "item": allocation.item.item,  # Assuming 'item' is a ForeignKey to Costing model
                    "amount": str(allocation.amount),
                    "notes": allocation.notes or ""
                } for allocation in quote.fetched_allocations  # Use the new attribute name here
            ]
        }
        quotes_data.append(quote_info)
    return JsonResponse(quotes_data, safe=False)