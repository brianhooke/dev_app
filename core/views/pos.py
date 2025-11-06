"""
Pos-related views.
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

@csrf_exempt
def create_po_order(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        supplier_pk = data.get('supplierPk')
        notes = data.get('notes', {})
        rows = data.get('rows', [])
        po_order = pos_service.create_po_order(supplier_pk, notes, rows)
        return JsonResponse({'status': 'success', 'message': 'PO Order created successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
def generate_po_pdf(request, po_order_pk):
    po_globals = pos_service.get_po_globals()
    po_order, po_order_details = pos_service.get_po_order_details(po_order_pk)
    company_details = po_globals
    letterhead = Letterhead.objects.first()
    if letterhead is not None:
        letterhead_path = letterhead.letterhead_path.name  
        if settings.DEBUG:  
            letterhead_full_path = default_storage.path(letterhead_path)
            with open(letterhead_full_path, "rb") as f:
                letterhead_pdf_content = f.read()
            letterhead_pdf = PdfReader(BytesIO(letterhead_pdf_content))
        else:
            letterhead_url = letterhead.letterhead_path.url
            response = requests.get(letterhead_url)
            letterhead_pdf = PdfReader(BytesIO(response.content))
    else:
        raise Exception("No Letterhead instance found.")
    content_buffer = BytesIO()
    p = canvas.Canvas(content_buffer, pagesize=A4)
    if company_details:
        details = [
            ("PO Reference: ", company_details.reference),
            ("Invoicee: ", company_details.invoicee),
            ("ABN: ", company_details.ABN),
            ("Email: ", company_details.email),
            ("Address: ", company_details.address)
        ]
        y_position = A4[1] - 2.5 * inch  
        max_length = 40  
        for label, text in details:
            wrapped_lines = wrap_text(f"{label}{text}", max_length)
            for line in wrapped_lines:
                if label in line:
                    bold_text, regular_text = line.split(label, 1)
                    p.setFont("Helvetica-Bold", 10)
                    p.drawString(5.5 * inch, y_position, f"{label}{bold_text}")
                    p.setFont("Helvetica", 10)
                    p.drawString(5.5 * inch + p.stringWidth(f"{label}{bold_text}", "Helvetica-Bold", 10), y_position, regular_text.strip())
                else:
                    p.setFont("Helvetica", 10)
                    p.drawString(5.5 * inch, y_position, line)
                y_position -= 12  
        y_position -= 12
        today = date.today().strftime("%d %b %Y")
        p.setFont("Helvetica", 12)
        p.drawString(inch/2, y_position, today)
        y_position -= 12  
    p.setFont("Helvetica-Bold", 15)
    supplier_name = po_order.po_supplier.contact_name  
    project_address = po_globals.project_address  
    purchase_order_text = f"{project_address} Purchase Order - {supplier_name}"
    wrapped_po_text = wrap_text(purchase_order_text, 80)
    text_widths = [p.stringWidth(line, "Helvetica-Bold", 15) for line in wrapped_po_text]
    max_text_width = max(text_widths)
    x_position = (A4[0] - max_text_width) / 2  
    y_position = A4[1] / 1.6
    for line in wrapped_po_text:
        p.drawString(x_position, y_position, line)
        y_position -= 22  
    p.setLineWidth(1)
    p.line(x_position, y_position - 2, x_position + max_text_width, y_position - 2)
    y_position -= 36
    p.setFont("Helvetica-Bold", 12)
    table_headers = ["Claim Category", "Quote # or Variation", "Amount ($)*"]
    col_widths = [2.5 * inch, 3.5 * inch, 1 * inch]  
    x_start = inch / 2
    cell_height = 18
    for i, header in enumerate(table_headers):
        header_x_position = x_start + sum(col_widths[:i]) + 2
        if i == 2:  
            header_x_position = x_start + sum(col_widths[:i]) + col_widths[i] / 2 - p.stringWidth(header, "Helvetica-Bold", 12) / 2
        p.drawString(header_x_position, y_position + 2, header)  
        p.line(header_x_position, y_position, header_x_position + p.stringWidth(header, "Helvetica-Bold", 12), y_position)  
    y_position -= cell_height
    total_amount = 0  
    p.setFont("Helvetica", 10)  
    for detail in po_order_details:
        row_data = [
            detail.costing.item,  
            f"Variation: {detail.variation_note}" if detail.quote is None else detail.quote.supplier_quote_number,  
            f"{detail.amount:,.2f}"  
        ]
        max_line_lengths = [
            int(col_widths[0] / 7),  
            int(col_widths[1] / 5),  
            int(col_widths[2] / 7)   
        ]
        total_amount += detail.amount
        row_heights = []
        for i, cell in enumerate(row_data):
            wrapped_lines = wrap_text(str(cell), max_line_lengths[i])
            row_heights.append(len(wrapped_lines) * cell_height)
            p.setStrokeColor(colors.grey, 0.25)  
            p.line(x_start, y_position, x_start + sum(col_widths), y_position)  
            p.setStrokeColor(colors.black)  
            max_row_height = max(row_heights)
        for i, cell in enumerate(row_data):
            wrapped_lines = wrap_text(str(cell), max_line_lengths[i])
            for line_num, line in enumerate(wrapped_lines):
                if i == 2:  
                    line_width = p.stringWidth(line, "Helvetica", 10)
                    p.drawString(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position + 2 - (line_num * cell_height), line)  
                else:
                    p.drawString(x_start + sum(col_widths[:i]) + 2, y_position + 2 - (line_num * cell_height), line)  
        y_position -= max_row_height
    p.setFont("Helvetica-Bold", 12)
    total_row_data = [
        "Total",
        "",  
        f"{total_amount:,.2f}"  
    ]
    for i, cell in enumerate(total_row_data):
        if i == 2:  
            line_width = p.stringWidth(cell, "Helvetica-Bold", 12)
            p.drawString(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position + 2, cell)  
            p.line(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position, x_start + sum(col_widths[:i+1]) - line_width - 2 + p.stringWidth(cell, "Helvetica-Bold", 12), y_position)  
        else:
            p.drawString(x_start + sum(col_widths[:i]) + 2, y_position + 2, cell)  
    y_position -= (cell_height * 2.5)
    p.setFont("Helvetica", 10)
    fixed_text = "* All amounts are net of GST. Supplier to add GST if applicable."
    for line in wrap_text(fixed_text, 110):
        p.drawString(x_start, y_position, line)
        y_position -= (cell_height) * 0.75  
    y_position -= (cell_height) * 0.75  
    notes = [po_order.po_note_1, po_order.po_note_2, po_order.po_note_3]
    for note in notes:
        for line in wrap_text(note, 115):
            p.drawString(x_start, y_position, line)
            y_position -= (cell_height) * 0.75  
        y_position -= (cell_height) * 0.75  
    p.showPage()
    p.save()
    content_buffer.seek(0)
    content_pdf = PdfReader(content_buffer)
    output_pdf = PdfWriter()
    page = letterhead_pdf.pages[0]
    page.merge_page(content_pdf.pages[0])
    output_pdf.add_page(page)
    merged_buffer = BytesIO()
    output_pdf.write(merged_buffer)
    merged_buffer.seek(0)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="PO_{po_order_pk}.pdf"'
    response.write(merged_buffer.getvalue())
    merged_buffer.close()
    return response
@csrf_exempt
def view_po_pdf(request, po_order_pk):
    return render(request, 'core/view_po_pdf.html', {'po_order_pk': po_order_pk})
def wrap_text(text, max_length):
    words = text.split(' ')
    lines = []
    current_line = ''
    for word in words:
        if len(current_line) + len(word) + 1 <= max_length:
            current_line += ' ' + word if current_line else word
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines
@csrf_exempt
def send_po_email(request, po_order_pk, recipient_list):
    po_order = Po_orders.objects.get(po_order_pk=po_order_pk)
    contact_name = po_order.po_supplier.contact_name  
    subject = 'Purchase Order'
    message = f'''Dear {contact_name},
Please see Purchase Order from Mason attached for the specified works and amount.

Ensure your claim clearly specifies the PO number and the amount being claimed against each claim category as specified in the PO to ensure there are no delays processing your claim.

Best regards,
Brian Hooke.
    '''
    from_email = settings.DEFAULT_FROM_EMAIL

    pdf_buffer = generate_po_pdf_bytes(request, po_order_pk)

    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach(f'PO_{po_order_pk}.pdf', pdf_buffer, 'application/pdf')

    po_order_details = Po_order_detail.objects.filter(po_order_pk=po_order_pk)
    processed_quotes = set()
    for po_order_detail in po_order_details:
        if po_order_detail.quote is not None and po_order_detail.quote.quotes_pk not in processed_quotes:
            quote_pdf_path = po_order_detail.quote.pdf.name
            if default_storage.exists(quote_pdf_path):
                with default_storage.open(quote_pdf_path, 'rb') as f:
                    email.attach(f'Quote_{po_order_detail.quote.quotes_pk}.pdf', f.read(), 'application/pdf')
                processed_quotes.add(po_order_detail.quote.quotes_pk)

    cc_addresses = settings.EMAIL_CC.split(';')
    email.cc = cc_addresses

    try:
        email.send()
        po_order.po_sent = True  
        po_order.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def generate_po_pdf_bytes(request, po_order_pk):
    response = generate_po_pdf(request, po_order_pk)
    return response.content
@csrf_exempt
def send_po_email_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            po_order_pks = data.get('po_order_pks', [])
            for po_order_pk in po_order_pks:
                po_order = Po_orders.objects.get(po_order_pk=po_order_pk)
                recipient_list = [po_order.po_supplier.contact_email]
                send_po_email(request, po_order_pk, recipient_list)
            return JsonResponse({'status': 'Emails sent'})
        except Exception as e:
            logger.error(f'Error in send_po_email_view: {e}')
            return JsonResponse({'status': 'Error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'Error', 'message': 'Invalid request method.'}, status=400)