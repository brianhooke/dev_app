import csv
from django.template import loader
from .forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from .models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, Build_costing, Build_categories, Committed_allocations, Hc_claims, Hc_claim_lines, Committed_quotes, Claims, Claim_allocations
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum
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
from datetime import datetime, date
import re
from django.core.mail import send_mail
from django.db.models import F
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



logger = logging.getLogger(__name__)

def drawings(request):
    return render(request, 'drawings.html')


def main(request):
    costings = Costing.objects.all().order_by('category__order_in_list', 'category__category', 'item')
    costings = [model_to_dict(costing) for costing in costings]
    for costing in costings:
        category = Categories.objects.get(pk=costing['category'])
        costing['category'] = category.category
    contacts = Contacts.objects.values()
    contacts_list = list(contacts)
    quote_allocations = Quote_allocations.objects.select_related('item').all()
    quote_allocations = [
        {
            **model_to_dict(ca),
            'item_name': ca.item.item
        }
        for ca in quote_allocations
    ]
    quote_allocations_sums = Quote_allocations.objects.values('item').annotate(total_amount=Sum('amount'))
    quote_allocations_sums_dict = {item['item']: item['total_amount'] for item in quote_allocations_sums}
    for costing in costings:
        costing['committed'] = quote_allocations_sums_dict.get(costing['costing_pk'], 0)    
    items = [{'item': costing['item'], 'uncommitted': costing['uncommitted'], 'committed': costing['committed']} for costing in costings]
    committed_quotes = Quotes.objects.all().values('quotes_pk', 'total_cost', 'pdf', 'contact_pk', 'contact_pk__contact_name')
    committed_quotes_list = list(committed_quotes)
    for quote in committed_quotes_list:
        if settings.DEBUG:
            quote['pdf'] = settings.MEDIA_URL + quote['pdf']
        else:
            quote['pdf'] = settings.MEDIA_URL + quote['pdf']   
    committed_quotes_json = json.dumps(committed_quotes_list, default=str)
    quote_allocations_json = json.dumps(list(quote_allocations), default=str)
    contact_pks_in_quotes = Quotes.objects.values_list('contact_pk', flat=True).distinct()
    contacts_in_quotes = Contacts.objects.filter(pk__in=contact_pks_in_quotes).values()
    contacts_in_quotes_list = list(contacts_in_quotes)
    contacts_not_in_quotes = Contacts.objects.exclude(pk__in=contact_pks_in_quotes).values()
    contacts_not_in_quotes_list = list(contacts_not_in_quotes)
    # totals for homepage bottom table row
    total_contract_budget = sum(costing['contract_budget'] for costing in costings)
    total_uncommitted = sum(costing['uncommitted'] for costing in costings)
    total_committed = sum(costing['committed'] for costing in costings)
    total_forecast_budget = total_committed + total_uncommitted
    total_sc_invoiced = sum(costing['sc_invoiced'] for costing in costings)
    total_sc_paid = sum(costing['sc_paid'] for costing in costings)

    # Fetch Po_globals data
    po_globals = Po_globals.objects.first()
    # Fetch Po_orders data
    po_orders = Po_orders.objects.select_related('po_supplier').all()
    po_orders_list = []
    for order in po_orders:
        po_orders_list.append({
            'po_order_pk': order.po_order_pk,
            'po_supplier': order.po_supplier_id,
            'supplier_name': order.po_supplier.contact_name,
            'supplier_email': order.po_supplier.contact_email,  # Add this line
            'po_note_1': order.po_note_1,
            'po_note_2': order.po_note_2,
            'po_note_3': order.po_note_3,
            'po_sent': order.po_sent  # Include the po_sent field
        })

    context = {
        'costings': costings,
        'contacts_in_quotes': contacts_in_quotes_list,
        'contacts_not_in_quotes': contacts_not_in_quotes_list,
        'contacts': contacts_list,
        'items': items,
        'committed_quotes': committed_quotes_json,
        'quote_allocations': quote_allocations_json,
        'current_page': 'quotes',
        'project_name': settings.PROJECT_NAME,
        'is_homepage': True,
        'totals': {
            'total_contract_budget': total_contract_budget,
            'total_forecast_budget': total_forecast_budget,
            'total_uncommitted': total_uncommitted,
            'total_committed': total_committed,
            'total_sc_invoiced': total_sc_invoiced,
            'total_sc_paid': total_sc_paid,
        },
        'po_globals': po_globals,
        'po_orders': po_orders_list,
    }
    return render(request, 'homepage.html', context)


def alphanumeric_sort_key(s):
    return [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', s)]

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
    return render(request, 'drawings.html', context)

def model_viewer_view(request):
    model_path = '3d/model.dae'
    full_path = os.path.join(settings.MEDIA_URL, model_path)
    logging.info(f'Full path to the model file: {full_path}')
    context = {'model_path': full_path,
               'current_page': 'model_viewer',
               'project_name': settings.PROJECT_NAME,
               }  # Relative path
    return render(request, 'model_viewer.html', context)

# def model_viewer_view(request):
#     context = {
#         'project_name': settings.PROJECT_NAME,
#     }
#     return render(request, 'model_viewer.html', context)

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
        for item in allocations:
            amount = item['amount']
            notes = item.get('notes', '')  # Get the notes, default to '' if not present
            if amount == '':
                amount = '0'
            Quote_allocations.objects.create(quotes_pk=quote, item=costing, amount=amount, notes=notes)  # Assign the Costing instance to item
            # Update the Costing.uncommitted field
            uncommitted = item['uncommitted']
            Costing.objects.filter(item=item['item']).update(uncommitted=uncommitted)
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
  

# Function to upload changes from the 'uncommitted' popup
@csrf_exempt
def update_costing(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_id = data.get('costing_id')
        uncommitted = data.get('uncommitted')
        # Get the Costing object and update it
        costing = Build_costing.objects.get(id=costing_id)
        costing.uncommitted = uncommitted
        costing.save()
        # Return a JSON response
        return JsonResponse({'status': 'success'})
    
    
@csrf_exempt
def create_contacts(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        contacts = data.get('contacts')  # Get the contacts list from the data
        if contacts:  # Check if contacts is not None
            for contact in contacts:  # Iterate over the contacts
                if contact['name']:  # Only create a contact if a name was provided
                    Contacts.objects.create(contact_name=contact['name'], contact_email=contact['email'])
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'No contacts provided'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'})

@csrf_exempt
def delete_quote(request):
    if request.method == 'DELETE':
        # Parse the request body to get the quote id
        data = json.loads(request.body)
        quote_id = data.get('id')
        # Get the quote from the database
        try:
            quote = Quotes.objects.get(pk=quote_id)
        except Quotes.DoesNotExist:
            return JsonResponse({'status': 'fail', 'message': 'Quote not found'}, status=404)
        # Delete the quote
        quote.delete()

        return JsonResponse({'status': 'success', 'message': 'Quote deleted successfully'})

    else:
        return JsonResponse({'status': 'fail', 'message': 'Invalid request method'}, status=405)
    
#function to accept supplier (contact_pk) & retun list of existing quoted line items for Purchase Order creation
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
def create_plan(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        category_name = data.get('plan')
        category_type = data.get('categoryType')
        if category_name:
            if category_type == 1:  # Plan
                new_category = DesignCategories(design_category=category_name)
            elif category_type == 2:  # Report
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

#split and upload new design pdf's, and correspondingly the planPdfs table with the pdf details.
@csrf_exempt
def upload_design_pdf(request):
    if request.method == 'POST':
        logger.info('Received POST request.')
        try:
            pdf_file = request.FILES['pdfFile']
            category_select = request.POST['categorySelect']
            pdf_name_values = json.loads(request.POST['pdfNameValues'])
            rev_num_values = json.loads(request.POST['revNumValues'])  # Extract revNumValues
            logger.info(f'pdf_name_values: {pdf_name_values}')
            logger.info(f'rev_num_values: {rev_num_values}')
        except Exception as e:
            logger.error(f'Error parsing POST data: {e}')
            return JsonResponse({'status': 'error', 'error': 'Error parsing POST data'}, status=400)
        # Log the types of pdf_name_values and rev_num_values
        logger.info(f'Type of pdf_name_values: {type(pdf_name_values)}')
        logger.info(f'Type of rev_num_values: {type(rev_num_values)}')
        # Get the category
        category = DesignCategories.objects.get(design_category_pk=category_select)
        logger.info(f'Category: {category.design_category}')
        # Split the PDF into individual pages
        pdf = PdfReader(pdf_file)
        pages = pdf.pages  # pages is a _VirtualList of Page objects
        logger.info(f'Number of pages: {len(pages)}')
        for page_number, page in enumerate(pages):
            try:
                pdf_writer = PdfWriter()
                pdf_writer.add_page(page)
            except AssertionError:
                logger.error(f'Error processing page {page_number}. Skipping.')
                continue
            # Get plan_number and rev_number from the data sent from the JavaScript
            plan_number = pdf_name_values.get(str(page_number + 1), None)
            rev_number = rev_num_values.get(str(page_number + 1), None)
            if not plan_number or not rev_number:
                logger.warning(f'Missing plan_number or rev_number for page {page_number}. Skipping.')
                continue
            # Save each page as a separate file
            output_filename = f'plans/{category.design_category}_{plan_number}_{rev_number}.pdf'
            logger.info(f'Saving page {page_number} as {output_filename}.')
            # Save the file to S3
            output_pdf = BytesIO()
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            default_storage.save(output_filename, output_pdf)
            # Create a new PlanPdfs object for each page
            PlanPdfs.objects.create(
                file=output_filename,
                design_category=category,
                plan_number=plan_number,
                rev_number=rev_number
            )
            logger.info(f'Successfully created PlanPdfs object for page {page_number}.')         
    return JsonResponse({'status': 'success'})

#get the design pdf usually to view in the iframe window.
@csrf_exempt
def get_design_pdf_url(request, design_category, plan_number, rev_number=None):
    try:
        if rev_number is None:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number)
        else:
            plan_pdf = PlanPdfs.objects.get(design_category=design_category, plan_number=plan_number, rev_number=rev_number)
        file_url = plan_pdf.file.url
        if file_url.startswith('/media/media/'):
            file_url = '/media/' + file_url[12:]  # Remove only the extra 'media/' prefix
        # Fetch the revision numbers
        rev_numbers = PlanPdfs.objects.filter(design_category=design_category, plan_number=plan_number).values_list('rev_number', flat=True)
        return JsonResponse({'file_url': file_url, 'rev_numbers': list(rev_numbers)})
    except PlanPdfs.DoesNotExist:
        return JsonResponse({'error': 'PlanPdfs not found'}, status=404)

#upload new report pdf's, and correspondingly the reportPdfs table with the pdf details.
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
        # Get the category
        category = ReportCategories.objects.get(report_category_pk=category_select)
        logger.info(f'Category: {category.report_category}')
        # Use pdf_name_value as the plan_number
        plan_number = pdf_name_value
        if not plan_number:
            logger.warning(f'Missing plan_number. Skipping.')
            return JsonResponse({'status': 'error', 'error': 'Missing plan_number'}, status=400)
        # Save the file
        datetime_str = datetime.now().strftime("%Y%m%d%H%M%S")  # Format datetime as YYYYMMDDHHMMSS
        output_filename = f'reports/{category.report_category}_{plan_number}_{datetime_str}.pdf'
        logger.info(f'Saving file as {output_filename}.')
        # Save the file to S3
        default_storage.save(output_filename, pdf_file)
        # Create a new ReportPdfs object
        ReportPdfs.objects.create(
            file=output_filename,
            report_category=category,
            report_reference=plan_number
        )
        logger.info(f'Successfully created ReportPdfs object.')         
    return JsonResponse({'status': 'success'})

#get the design pdf usually to view in the iframe window.
@csrf_exempt
def get_report_pdf_url(request, report_category, report_reference=None):
    try:
        if report_reference:
            report_pdf = ReportPdfs.objects.get(report_category=report_category, report_reference=report_reference)
            file_url = report_pdf.file.url
            if file_url.startswith('/media/media/'):
                file_url = '/media/' + file_url[12:]  # Remove only the extra 'media/' prefix
            return JsonResponse({'file_url': file_url})
        else:
            report_pdfs = ReportPdfs.objects.filter(report_category=report_category)
            response_data = []
            for report_pdf in report_pdfs:
                file_url = report_pdf.file.url
                if file_url.startswith('/media/media/'):
                    file_url = '/media/' + file_url[12:]  # Remove only the extra 'media/' prefix
                response_data.append({
                    'file_url': file_url,
                    'report_reference': report_pdf.report_reference
                })
            return JsonResponse({'data': response_data})
    except ReportPdfs.DoesNotExist:
        return JsonResponse({'error': 'ReportPdfs not found'}, status=404)
    
@csrf_exempt
def create_po_order(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        
        # Extract supplier PK
        supplier_pk = data.get('supplierPk')
        supplier = Contacts.objects.get(pk=supplier_pk)
        
        # Extract notes
        notes = data.get('notes', {})
        note1 = notes.get('note1', '')
        note2 = notes.get('note2', '')
        note3 = notes.get('note3', '')
        
        # Create Po_orders entry
        po_order = Po_orders.objects.create(
            po_supplier=supplier,
            po_note_1=note1,
            po_note_2=note2,
            po_note_3=note3
        )
        
        # Extract and save rows data
        rows = data.get('rows', [])
        for row in rows:
            item_pk = row.get('itemPk')
            quote_id = row.get('quoteId')
            amount = row.get('amount')
            variation_note = row.get('notes', '')  # Get the variation note

            # Ensure quote is optional
            quote = Quotes.objects.get(pk=quote_id) if quote_id else None
            costing = Costing.objects.get(pk=item_pk)  # Fetch the related Costing instance

            Po_order_detail.objects.create(
                po_order_pk=po_order,
                date=date.today(),
                costing=costing,
                quote=quote,
                amount=amount,
                variation_note=variation_note if variation_note else None  # Save the variation note or None
            )
        return JsonResponse({'status': 'success', 'message': 'PO Order created successfully.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

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

def generate_po_pdf(request, po_order_pk):
    po_globals = Po_globals.objects.first()
    po_order = Po_orders.objects.get(pk=po_order_pk)
    po_order_details = Po_order_detail.objects.filter(po_order_pk=po_order_pk).select_related('costing', 'quote')
    company_details = Po_globals.objects.first()
    letterhead_path = os.path.join(settings.MEDIA_ROOT, 'letterhead/letterhead.pdf')
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
        y_position = A4[1] - 2.5 * inch  # Starting Y position below the letterhead
        max_length = 40  # Maximum characters per line
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
                y_position -= 12  # Move to the next line
        y_position -= 12
        today = date.today().strftime("%d %b %Y")
        p.setFont("Helvetica", 12)
        p.drawString(inch/2, y_position, today)
        y_position -= 12  # Move to the next line
    p.setFont("Helvetica-Bold", 15)
    supplier_name = po_order.po_supplier.contact_name  # Get the supplier's name
    project_address = po_globals.project_address  # Get the job address
    purchase_order_text = f"{project_address} Purchase Order - {supplier_name}"
    wrapped_po_text = wrap_text(purchase_order_text, 80)
    text_widths = [p.stringWidth(line, "Helvetica-Bold", 15) for line in wrapped_po_text]
    max_text_width = max(text_widths)
    x_position = (A4[0] - max_text_width) / 2  # Center the text
    y_position = A4[1] / 1.6
    for line in wrapped_po_text:
        p.drawString(x_position, y_position, line)
        y_position -= 22  # Adjust for line height
    p.setLineWidth(1)
    p.line(x_position, y_position - 2, x_position + max_text_width, y_position - 2)
    y_position -= 36
    p.setFont("Helvetica-Bold", 12)
    table_headers = ["Claim Category", "Quote # or Variation", "Amount ($)*"]
    col_widths = [2 * inch, 4 * inch, 1 * inch]  # Adjusted column widths
    x_start = inch / 2
    cell_height = 18
    for i, header in enumerate(table_headers):
        header_x_position = x_start + sum(col_widths[:i]) + 2
        if i == 2:  # Center the 'Amount' column header
            header_x_position = x_start + sum(col_widths[:i]) + col_widths[i] / 2 - p.stringWidth(header, "Helvetica-Bold", 12) / 2
        p.drawString(header_x_position, y_position + 2, header)  # Adjust for padding
    y_position -= cell_height
    total_amount = 0  # Initialize total amount
    p.setFont("Helvetica", 10)  # Smaller font size for table contents
    for detail in po_order_details:
        row_data = [
            detail.costing.item,  # Using item of costing
            f"Variation: {detail.variation_note}" if detail.quote is None else detail.quote.supplier_quote_number,  # Using supplier_quote_number if quote is not None
            f"{detail.amount:,.2f}"  # Amount with thousand comma separator
        ]
        max_line_lengths = [
            int(col_widths[0] / 7),  # Claim Category
            int(col_widths[1] / 5),  # Quote # or Variation
            int(col_widths[2] / 7)   # Amount
        ]
        total_amount += detail.amount
        row_heights = []
        for i, cell in enumerate(row_data):
            wrapped_lines = wrap_text(str(cell), max_line_lengths[i])
            row_heights.append(len(wrapped_lines) * cell_height)
        max_row_height = max(row_heights)
        for i, cell in enumerate(row_data):
            wrapped_lines = wrap_text(str(cell), max_line_lengths[i])
            for line_num, line in enumerate(wrapped_lines):
                if i == 2:  # Align 'Amount' column to the right
                    line_width = p.stringWidth(line, "Helvetica", 10)
                    p.drawString(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position + 2 - (line_num * cell_height), line)  # Adjust for padding and right alignment
                else:
                    p.drawString(x_start + sum(col_widths[:i]) + 2, y_position + 2 - (line_num * cell_height), line)  # Adjust for padding
        y_position -= max_row_height
    p.setFont("Helvetica-Bold", 12)
    total_row_data = [
        "Total",
        "",  # Empty cell
        f"{total_amount:,.2f}"  # Total amount with thousand comma separator
    ]
    for i, cell in enumerate(total_row_data):
        if i == 2:  # Align 'Amount' column to the right
            line_width = p.stringWidth(cell, "Helvetica-Bold", 12)
            p.drawString(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position + 2, cell)  # Adjust for padding and right alignment
        else:
            p.drawString(x_start + sum(col_widths[:i]) + 2, y_position + 2, cell)  # Adjust for padding
    y_position -= (cell_height * 2.5)
    p.setFont("Helvetica", 10)
    fixed_text = "* All amounts are net of GST. Supplier to add GST if applicable."
    for line in wrap_text(fixed_text, 110):
        p.drawString(x_start, y_position, line)
        y_position -= (cell_height) * 0.75  # Consistent line break
    y_position -= (cell_height) * 0.75  # Blank row
    notes = [po_order.po_note_1, po_order.po_note_2, po_order.po_note_3]
    for note in notes:
        for line in wrap_text(note, 115):
            p.drawString(x_start, y_position, line)
            y_position -= (cell_height) * 0.75  # Consistent line break
        y_position -= (cell_height) * 0.75  # Blank row
    p.showPage()
    p.save()
    content_buffer.seek(0)
    content_pdf = PdfReader(content_buffer)
    letterhead_pdf = PdfReader(open(letterhead_path, "rb"))
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
    return render(request, 'view_po_pdf.html', {'po_order_pk': po_order_pk})

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
def send_po_email(request, po_order_pk, recipient_list):
    subject = 'Purchase Order'
    message = 'Please see attached PO.'
    from_email = settings.DEFAULT_FROM_EMAIL
    # Generate the PO PDF
    pdf_buffer = generate_po_pdf_bytes(request, po_order_pk)
    # Create the email
    email = EmailMessage(subject, message, from_email, recipient_list)
    email.attach(f'PO_{po_order_pk}.pdf', pdf_buffer, 'application/pdf')
    # Attach additional PDFs
    po_order_details = Po_order_detail.objects.filter(po_order_pk=po_order_pk)
    processed_quotes = set()
    for po_order_detail in po_order_details:
        if po_order_detail.quote is not None and po_order_detail.quote.quotes_pk not in processed_quotes:
            quote_pdf_path = po_order_detail.quote.pdf.name
            if default_storage.exists(quote_pdf_path):
                with default_storage.open(quote_pdf_path, 'rb') as f:
                    email.attach(f'Quote_{po_order_detail.quote.quotes_pk}.pdf', f.read(), 'application/pdf')
                processed_quotes.add(po_order_detail.quote.quotes_pk)
    # Send the email
    try:
        email.send()
        logger.info('Email sent successfully.')
        # Update po_sent field
        po_order = Po_orders.objects.get(po_order_pk=po_order_pk)
        po_order.po_sent = 1
        po_order.save()
    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        raise

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

# def (request):
#     return render(request, 'build.html')

# Build Contract Functions
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

def build_view(request):
    form = CSVUploadForm()
    # Retrieve all Build_costing objects and order them
    costings = Build_costing.objects.all().order_by('category__order_in_list', 'category__category', 'item')
    costings = [model_to_dict(costing) for costing in costings]
    # Replace category FK with category name
    for costing in costings:
        category = Build_categories.objects.get(pk=costing['category'])
        costing['category'] = category.category
    # Retrieve contacts
    contacts = Contacts.objects.values()
    contacts_list = list(contacts)
    # Retrieve committed allocations and calculate sums
    committed_allocations = Committed_allocations.objects.select_related('item', 'quote').all()
    committed_allocations_list = [
        {
            'quote_id': allocation.quote_id,
            'item_id': allocation.item_id,
            'amount': str(allocation.amount),
            'notes': allocation.notes,
            'item_name': allocation.item.item,
        }
        for allocation in committed_allocations
    ]
    committed_allocations_json = json.dumps(committed_allocations_list, default=str)

    committed_allocations_sums = Committed_allocations.objects.values('item').annotate(total_amount=Sum('amount'))
    committed_allocations_sums_dict = {item['item']: item['total_amount'] for item in committed_allocations_sums}
    
    # Add committed sums to each costing
    for costing in costings:
        costing['committed'] = committed_allocations_sums_dict.get(costing['id'], 0)
    
    # Retrieve HC claim lines and calculate sums
    hc_claim_lines_sums = Hc_claim_lines.objects.values('item_id').annotate(total_amount=Sum('amount'))
    hc_claim_lines_sums_dict = {item['item_id']: item['total_amount'] for item in hc_claim_lines_sums}
    
    # Add HC claimed amounts to each costing
    for costing in costings:
        hc_claimed_amount = hc_claim_lines_sums_dict.get(costing['id'])
        if hc_claimed_amount is not None:
            costing['hc_claimed_amount'] = str(hc_claimed_amount)
        else:
            costing['hc_claimed_amount'] = '0.00'
        costing['hc_claimed'] = hc_claimed_amount or 0
    
    items = [{'item': costing['item'], 'uncommitted': costing['uncommitted'], 'committed': costing['committed']} for costing in costings]
    
    # Retrieve committed quotes and convert to JSON
    committed_quotes = Committed_quotes.objects.all().values('quote', 'supplier_quote_number', 'total_cost', 'pdf', 'contact_pk', 'contact_pk__contact_name')
    committed_quotes_list = list(committed_quotes)
    for quote in committed_quotes_list:
        quote['pdf'] = settings.MEDIA_URL + quote['pdf']
    committed_quotes_json = json.dumps(committed_quotes_list, default=str)
    
    # Retrieve claims and convert to JSON
    claims = Claims.objects.all()
    claims_list = []
    for claim in claims:
        claim_dict = model_to_dict(claim)
        claim_dict['supplier_name'] = claim.get_supplier_name()
        claims_list.append(claim_dict)
    claims_json = json.dumps(claims_list, default=str)
    
    claim_allocations = Claim_allocations.objects.all()
    claim_allocations_json = serializers.serialize('json', claim_allocations)
    
    # Calculate totals
    total_committed = sum(costing['committed'] for costing in costings)
    totals = {
        'total_contract_budget': Build_costing.objects.aggregate(Sum('contract_budget'))['contract_budget__sum'] or 0,
        'total_committed': total_committed,
        'total_uncommitted': Build_costing.objects.aggregate(Sum('uncommitted'))['uncommitted__sum'] or 0,
        'total_complete_on_site': Build_costing.objects.aggregate(Sum('complete_on_site'))['complete_on_site__sum'] or 0,
        'total_hc_next_claim': Build_costing.objects.aggregate(Sum('hc_next_claim'))['hc_next_claim__sum'] or 0,
        'total_hc_received': Build_costing.objects.aggregate(Sum('hc_received'))['hc_received__sum'] or 0,
        'total_sc_invoiced': Build_costing.objects.aggregate(Sum('sc_invoiced'))['sc_invoiced__sum'] or 0,
        'total_sc_paid': Build_costing.objects.aggregate(Sum('sc_paid'))['sc_paid__sum'] or 0,
    }
    totals['total_forecast_budget'] = totals['total_committed'] + totals['total_uncommitted']
    
    context = {
        'current_page': 'build',
        'form': form,
        'costings': costings,
        'contacts': contacts_list,
        'items': items,
        'totals': totals,
        'committed_quotes': committed_quotes_json,
        'committed_allocations': committed_allocations_json,
        'claims': claims_json,
        'claim_allocations': claim_allocations_json,
        'hc_claim_lines_sums': hc_claim_lines_sums_dict,
    }
    return render(request, 'build.html', context)




@csrf_exempt
def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            print(next(reader))  # This will print the first row of the CSV to your console
            # Delete existing data
            Build_costing.objects.all().delete()
            for row in reader:
                # category, created = Build_categories.objects.get_or_create(category=row['category'])
                category, created = Build_categories.objects.get_or_create(
                    category=row['category'], 
                    defaults={'order_in_list': row['category']}  # use the 'category' value from the CSV as 'order_in_list'
                )
                Build_costing.objects.create(
                    category=category,
                    item=row['item'],
                    contract_budget=row['contract_budget'],
                    uncommitted=row['uncommitted'],
                    complete_on_site=row['complete_on_site'],
                    hc_next_claim=row['hc_next_claim'],
                    hc_received=row['hc_received'],
                    sc_invoiced=row['sc_invoiced'],
                    sc_paid=row['sc_paid'],
                    notes=row['notes']
                )
            return JsonResponse({"message": "CSV file uploaded successfully"}, status=200)
        else:
            return JsonResponse({"message": str(form.errors)}, status=400)
    else:
        form = CSVUploadForm()

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
            reader = csv.DictReader(decoded_file)  # Reset the reader after getting the first row
            Build_categories.objects.all().delete()
            logger.info('All existing Categories objects deleted')
            for row in reader:
                Build_categories.objects.create(
                    category=row['category'],
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


def update_costs(request):
    if request.method == 'POST':
        costing_id = request.POST.get('id')
        uncommitted = request.POST.get('uncommitted')
        # Make sure you're handling type conversion and validation properly here
        try:
            costing = Build_costing.objects.get(id=costing_id)
            costing.uncommitted = uncommitted
            costing.save()
            return JsonResponse({'status': 'success'})
        except Build_costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Costing not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    
@csrf_exempt
def update_complete_on_site(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_id = data.get('id')
        complete_on_site_data = data.get('complete_on_site')
        try:
            complete_on_site = float(complete_on_site_data)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid complete_on_site value'}, status=400)
        try:
            costing = Build_costing.objects.get(pk=costing_id)
            costing.complete_on_site = complete_on_site
            costing.save()
            return JsonResponse({'status': 'success'})
        except Build_costing.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Costing not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    
@csrf_exempt
def update_build_quote(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        quote_id = data.get('quote_id')
        supplier_quote_number = data.get('supplier_quote_number')
        total_cost = data.get('total_cost')
        contact_pk = data.get('contact_pk')
        allocations = data.get('allocations')
        
        try:
            quote = Committed_quotes.objects.get(pk=quote_id)
        except Committed_quotes.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Quote not found'})

        quote.total_cost = total_cost
        quote.contact_pk_id = contact_pk  # Update the contact_pk field
        quote.supplier_quote_number = supplier_quote_number  # Update the supplier_quote_number field
        quote.save()

        # Delete the existing allocations for the quote
        Committed_allocations.objects.filter(quote_id=quote_id).delete()
        
        # Save the new allocations
        for allocation in allocations:
            notes = allocation.get('notes', '')  # Get the notes, default to '' if not present
            alloc = Committed_allocations(
                quote_id=quote_id,
                item_id=allocation['item'],
                amount=allocation['amount'],
                notes=notes
            )
            alloc.save()
            
            # Update the Costing.uncommitted field
            uncommitted = allocation['uncommitted']
            Build_costing.objects.filter(pk=allocation['item']).update(uncommitted=uncommitted)

        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@csrf_exempt
def commit_build_data(request):
    if request.method == 'POST':
        try:
            logger.info("Received POST request to commit_build_data")
            data = json.loads(request.body)
            logger.info("Request data: %s", data)

            total_cost = data['total_cost']
            pdf_data = data['pdf']
            contact_pk = data['contact_pk']
            supplier_quote_number = data['supplier_quote_number']
            allocations = data.get('allocations')

            logger.info("Parsed data - total_cost: %s, contact_pk: %s, supplier_quote_number: %s, allocations: %s", total_cost, contact_pk, supplier_quote_number, allocations)

            format, imgstr = pdf_data.split(';base64,')
            ext = format.split('/')[-1]
            contact = get_object_or_404(Contacts, pk=contact_pk)
            supplier = contact.contact_name

            logger.info("Contact found - supplier: %s", supplier)

            unique_filename = supplier + " " + str(uuid.uuid4()) + '.' + ext
            pdf_file = ContentFile(base64.b64decode(imgstr), name=unique_filename)
            quote = Committed_quotes.objects.create(
                total_cost=total_cost,
                pdf=pdf_file,
                contact_pk=contact,
                supplier_quote_number=supplier_quote_number
            )

            for item in allocations:
                amount = item['amount']
                notes = item.get('notes', '')  # Get the notes, default to '' if not present
                if amount == '':
                    amount = '0'
                costing = get_object_or_404(Build_costing, pk=item['item'])  # Retrieve the Costing instance with the ID item['item']
                Committed_allocations.objects.create(quote=quote, item=costing, amount=amount, notes=notes)  # Assign the Costing instance to item
                # Update the Costing.uncommitted field
                uncommitted = item['uncommitted']
                Build_costing.objects.filter(pk=item['item']).update(uncommitted=uncommitted)

                logger.info("Allocation created for item: %s, amount: %s, notes: %s", item['item'], amount, notes)

            logger.info("All allocations processed successfully")

            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error("Error processing commit_build_data: %s", str(e), exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    else:
        logger.warning("Received non-POST request to commit_build_data")
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)