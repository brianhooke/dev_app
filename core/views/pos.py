"""
PO (Purchase Order) related views.

Template Rendering:
1. po_view - Render PO section template (supports project_pk query param)

PO Creation:
2. create_po_order - Create new PO order from supplier and line items

PDF Generation:
3. generate_po_pdf - Generate PO PDF document with letterhead
4. generate_po_pdf_bytes - Generate PO PDF as bytes (for email attachment)
5. wrap_text - Helper: Wrap text for PDF layout

Email:
6. send_po_email - Send PO email to supplier with PDF and quote attachments
7. send_po_email_view - View handler for sending PO email (POST endpoint)

Public PO Pages (Supplier Access):
8. view_po_by_unique_id - Public landing page for suppliers to view PO and submit claims
9. view_po_pdf_by_unique_id - Serve saved PDF for PO via unique_id

Progress Claims:
10. submit_po_claim - Submit or update a progress claim (creates Invoice with status=100)
11. approve_po_claim - Approve pending progress claim (status 100 -> 101)
12. upload_bill_pdf - Upload invoice PDF for approved claim (status 101 -> 102)

Data Retrieval:
13. get_po_table_data_for_invoice - Get PO table data for invoice (allocated bills view)
14. get_quotes_by_supplier - Get quotes filtered by supplier
"""
import json
import logging
import ssl
from datetime import date
from io import BytesIO

import requests
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ..models import Letterhead, Po_globals, Po_orders, Po_order_detail, Projects
from ..services import pos as pos_service

ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  


def po_view(request):
    """Render the PO section template with column configuration.
    
    Accepts project_pk as query parameter to enable self-contained operation.
    Example: /core/po/?project_pk=123
    
    Returns construction-specific columns when project_type == 'construction'.
    """
    project_pk = request.GET.get('project_pk')
    xero_instance_pk = None
    is_construction = False
    
    if project_pk:
        try:
            project = Projects.objects.get(pk=project_pk)
            xero_instance_pk = project.xero_instance_id if project.xero_instance else None
            # Use rates_based flag from ProjectTypes instead of hardcoded project type names
            is_construction = (project.project_type and project.project_type.rates_based == 1)
        except Projects.DoesNotExist:
            pass
    
    context = {
        'project_pk': project_pk,
        'xero_instance_pk': xero_instance_pk,
        'is_construction': is_construction,
        'main_table_columns': [
            {'header': 'Supplier', 'width': '25%', 'sortable': True},
            {'header': 'First Name', 'width': '10%', 'sortable': True},
            {'header': 'Last Name', 'width': '10%', 'sortable': True},
            {'header': 'Email', 'width': '20%', 'sortable': True},
            {'header': 'Amount', 'width': '12%', 'sortable': True},
            {'header': 'Sent', 'width': '4%', 'class': 'col-action-first'},
            {'header': 'Update', 'width': '12%', 'class': 'col-action'},
            {'header': 'Email', 'width': '7%', 'class': 'col-action'},
        ],
    }
    return render(request, 'core/po.html', context)


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


def view_po_by_unique_id(request, unique_id):
    """
    Public view for suppliers to access their PO via unique URL.
    Displays payment schedule table for supplier to fill out.
    """
    try:
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project
        
        # Get the most recent PO for this supplier/project (same as PDF view)
        # This ensures we show details from the same PO that the PDF displays
        most_recent_po = Po_orders.objects.filter(
            po_supplier=supplier,
            project=project
        ).order_by('-created_at').first()
        
        if most_recent_po:
            po_order = most_recent_po
        
        # Check if construction project - use rates_based flag
        is_construction = (project.project_type and project.project_type.rates_based == 1)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        # Group allocations by item
        from collections import defaultdict
        import logging
        logger = logging.getLogger(__name__)
        
        if is_construction:
            # For construction: aggregate from Po_order_detail
            items_map = defaultdict(lambda: {
                'contract_sum': Decimal('0'),
                'contract_qty': Decimal('0'),
                'quote_numbers': [],
                'costing_pk': None,
                'unit': None
            })
            
            # Get all Po_order_details for this PO
            po_details = Po_order_detail.objects.filter(po_order_pk=po_order)
            logger.info(f"PO Public URL - PO pk={po_order.po_order_pk}, found {po_details.count()} Po_order_detail records")
            
            for detail in po_details:
                item_name = detail.costing.item
                items_map[item_name]['costing_pk'] = detail.costing.costing_pk
                items_map[item_name]['unit'] = detail.costing.unit or '-'
                
                # Sum qty and calculate contract sum (qty * rate)
                if detail.qty and detail.rate:
                    items_map[item_name]['contract_sum'] += detail.qty * detail.rate
                    items_map[item_name]['contract_qty'] += detail.qty
                elif detail.amount:
                    items_map[item_name]['contract_sum'] += detail.amount
                
                # Track quote numbers
                if detail.quote and detail.quote.supplier_quote_number:
                    if detail.quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(detail.quote.supplier_quote_number)
        else:
            items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': [], 'costing_pk': None})
            
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    item_name = allocation.item.item
                    items_map[item_name]['amount'] += allocation.amount
                    items_map[item_name]['costing_pk'] = allocation.item.costing_pk
                    
                    if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
        
        # Get previous approved claims (bill_status = 102, approved AND invoice uploaded)
        from core.models import Bill_allocations, Bills
        completed_invoices = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=102
        ).order_by('bill_date', 'bill_pk')
        
        # Build list of individual claims for expandable view
        individual_claims = []  # List of {claim_number, bill_pk, allocations_by_item}
        claim_number = 1
        
        # Calculate previous claims by item (only status 102)
        previous_claims_by_item = defaultdict(Decimal)
        for invoice in completed_invoices:
            # Get invoice PDF URL if available
            invoice_pdf_url = None
            if invoice.pdf and hasattr(invoice.pdf, 'url'):
                invoice_pdf_url = invoice.pdf.url
            
            claim_data = {
                'claim_number': claim_number,
                'bill_pk': invoice.bill_pk,
                'invoice_pdf_url': invoice_pdf_url,
                'allocations': {}  # item_name -> {amount, percent}
            }
            allocations = Bill_allocations.objects.filter(bill_pk=invoice)
            for alloc in allocations:
                if alloc.item:
                    item_name = alloc.item.item
                    # For construction: use amount if available, else qty * rate
                    if is_construction and alloc.amount is None and alloc.qty and alloc.rate:
                        claim_amount = alloc.qty * alloc.rate
                    else:
                        claim_amount = alloc.amount or Decimal('0')
                    previous_claims_by_item[item_name] += claim_amount
                    claim_data['allocations'][item_name] = float(claim_amount)
            individual_claims.append(claim_data)
            claim_number += 1
        
        # Check for pending claim (bill_status = 100)
        pending_invoice = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=100
        ).first()
        
        # Check for approved claim awaiting invoice upload (bill_status = 101)
        approved_invoice = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=101
        ).first()
        
        pending_claims_by_item = {}
        approved_claims_by_item = {}
        
        if pending_invoice:
            allocations = Bill_allocations.objects.filter(bill_pk=pending_invoice)
            for alloc in allocations:
                if alloc.item:
                    item_name = alloc.item.item
                    pending_claims_by_item[item_name] = float(alloc.amount)
        
        if approved_invoice:
            allocations = Bill_allocations.objects.filter(bill_pk=approved_invoice)
            for alloc in allocations:
                if alloc.item:
                    item_name = alloc.item.item
                    approved_claims_by_item[item_name] = float(alloc.amount)
        
        # Convert to list
        items = []
        for item_name, data in items_map.items():
            if is_construction:
                contract_sum = float(data['contract_sum'])
                contract_qty = float(data['contract_qty'])
                # Calculate contract rate as contract_sum / contract_qty
                contract_rate = contract_sum / contract_qty if contract_qty > 0 else 0.0
            else:
                contract_sum = float(data['amount'])
                contract_qty = 0.0
                contract_rate = 0.0
                
            previous_claims = float(previous_claims_by_item.get(item_name, Decimal('0')))
            this_claim = pending_claims_by_item.get(item_name, 0.0) or approved_claims_by_item.get(item_name, 0.0)
            still_to_claim = contract_sum - previous_claims - this_claim
            
            # Calculate percentages
            previous_claims_percent = (previous_claims / contract_sum * 100) if contract_sum > 0 else 0.0
            this_claim_percent = (this_claim / contract_sum * 100) if contract_sum > 0 else 0.0
            still_to_claim_percent = (still_to_claim / contract_sum * 100) if contract_sum > 0 else 0.0
            
            # Build individual claim data for this item
            item_individual_claims = []
            for claim in individual_claims:
                claim_amount = claim['allocations'].get(item_name, 0.0)
                claim_percent = (claim_amount / contract_sum * 100) if contract_sum > 0 else 0.0
                item_individual_claims.append({
                    'claim_number': claim['claim_number'],
                    'amount': claim_amount,
                    'percent': claim_percent
                })
            
            item_data = {
                'description': item_name,
                'costing_pk': data['costing_pk'],
                'contract_sum': contract_sum,
                'quote_numbers': ', '.join(data['quote_numbers']),
                'complete_percent': 0.0,
                'previous_claims': previous_claims,
                'previous_claims_percent': previous_claims_percent,
                'this_claim': this_claim,
                'this_claim_percent': this_claim_percent,
                'still_to_claim': still_to_claim,
                'still_to_claim_percent': still_to_claim_percent,
                'individual_claims': item_individual_claims,
            }
            
            # Add construction-specific fields
            if is_construction:
                item_data['unit'] = data.get('unit', '-')
                item_data['contract_qty'] = contract_qty
                item_data['contract_rate'] = contract_rate
            
            items.append(item_data)
        
        context = {
            'po_order': po_order,
            'supplier': supplier,
            'project': project,
            'items': items,
            'is_construction': is_construction,
            'pending_bill_pk': pending_invoice.bill_pk if pending_invoice else None,
            'approved_bill_pk': approved_invoice.bill_pk if approved_invoice else None,
            'has_pending_claim': pending_invoice is not None,
            'has_approved_claim': approved_invoice is not None,
            'previous_claims_count': len(individual_claims),
            'previous_claims_range': range(1, len(individual_claims) + 1),
            'individual_claims': individual_claims,
        }
        
        return render(request, 'core/po_public.html', context)
        
    except Po_orders.DoesNotExist:
        return HttpResponse('Purchase Order not found', status=404)


@csrf_exempt
def approve_po_claim(request, unique_id):
    """
    Approve a pending progress claim for a PO.
    Updates bill_status from 100 to 101.
    If claim was edited before approval, updates allocations and sends comparison email.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        import json
        from core.models import Bills, Bill_allocations, Costing
        from decimal import Decimal
        
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project
        
        data = json.loads(request.body)
        pending_bill_pk = data.get('pending_bill_pk')
        is_edit_claim_mode = data.get('is_edit_claim_mode', False)
        approved_claims = data.get('approved_claims', [])
        
        if not pending_bill_pk:
            return JsonResponse({'status': 'error', 'message': 'No pending invoice specified'}, status=400)
        
        # Get the pending invoice
        try:
            invoice = Bills.objects.get(
                bill_pk=pending_bill_pk,
                project=project,
                contact_pk=supplier,
                bill_status=100
            )
        except Bills.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Pending invoice not found'}, status=404)
        
        # Track if any values were modified
        has_modifications = False
        comparison_data = []
        
        # If we have approved_claims data, update the allocations if modified
        if approved_claims:
            for claim in approved_claims:
                costing_pk = claim.get('costing_pk')
                submitted_amount = Decimal(str(claim.get('submitted_amount', 0)))
                approved_amount = Decimal(str(claim.get('approved_amount', 0)))
                
                # Check if there's a difference
                if abs(submitted_amount - approved_amount) > Decimal('0.01'):
                    has_modifications = True
                
                comparison_data.append({
                    'description': claim.get('description', ''),
                    'contract_sum': claim.get('contract_sum', 0),
                    'submitted_percent': claim.get('submitted_percent', 0),
                    'submitted_amount': float(submitted_amount),
                    'approved_percent': claim.get('approved_percent', 0),
                    'approved_amount': float(approved_amount),
                    'difference': float(approved_amount - submitted_amount)
                })
                
                # Update the allocation if modified
                if costing_pk and abs(submitted_amount - approved_amount) > Decimal('0.01'):
                    try:
                        costing = Costing.objects.get(costing_pk=costing_pk)
                        allocation = Bill_allocations.objects.filter(
                            bill_pk=invoice,
                            item=costing
                        ).first()
                        
                        if allocation:
                            allocation.amount = approved_amount
                            allocation.save()
                            logger.info(f"Updated allocation for costing {costing_pk}: {submitted_amount} -> {approved_amount}")
                    except Costing.DoesNotExist:
                        logger.warning(f"Costing {costing_pk} not found when updating allocation")
        
        # Recalculate invoice totals from allocations (in case any were modified)
        from django.db.models import Sum
        totals = Bill_allocations.objects.filter(bill_pk=invoice).aggregate(
            total_net=Sum('amount'),
            total_gst=Sum('gst_amount')
        )
        invoice.total_net = totals['total_net'] or Decimal('0')
        invoice.total_gst = totals['total_gst'] or Decimal('0')
        
        # Update status to approved (but no invoice uploaded yet)
        invoice.bill_status = 101
        invoice.save()
        
        logger.info(f"Updated invoice {invoice.bill_pk} totals: net={invoice.total_net}, gst={invoice.total_gst}")
        
        logger.info(f"Progress claim approved for PO {unique_id}, Invoice {invoice.bill_pk}, modifications: {has_modifications}")
        
        # Send notification email to supplier
        if supplier.email:
            # Build PO URL
            po_url = request.build_absolute_uri(f'/po/{unique_id}/')
            
            # Get supplier contact details
            first_name = supplier.first_name or ''
            last_name = supplier.last_name or ''
            
            # Get project manager name
            project_manager = project.manager or 'The Project Team'
            
            # Build comparison table if there were modifications
            comparison_table_html = ''
            comparison_table_text = ''
            
            if has_modifications and comparison_data:
                # Calculate totals
                total_submitted = sum(item['submitted_amount'] for item in comparison_data)
                total_approved = sum(item['approved_amount'] for item in comparison_data)
                total_difference = sum(item['difference'] for item in comparison_data)
                
                # Build HTML table
                comparison_rows_html = ''
                for item in comparison_data:
                    diff_color = '#28a745' if item['difference'] >= 0 else '#dc3545'
                    diff_sign = '+' if item['difference'] >= 0 else ''
                    comparison_rows_html += f'''
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;">{item['description']}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{item['submitted_percent']:.2f}%</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${item['submitted_amount']:,.2f}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">{item['approved_percent']:.2f}%</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${item['approved_amount']:,.2f}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: right; color: {diff_color};">{diff_sign}${item['difference']:,.2f}</td>
                    </tr>'''
                
                total_diff_color = '#28a745' if total_difference >= 0 else '#dc3545'
                total_diff_sign = '+' if total_difference >= 0 else ''
                
                comparison_table_html = f'''
                <div style="margin: 20px 0;">
                    <h3 style="color: #333; margin-bottom: 10px;">Claim Comparison</h3>
                    <p style="color: #666; margin-bottom: 15px;">Your submitted claim was adjusted before approval. Please see the comparison below:</p>
                    <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: left;">Item</th>
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">Submitted %</th>
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">Submitted $</th>
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">Approved %</th>
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">Approved $</th>
                                <th style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">Difference</th>
                            </tr>
                        </thead>
                        <tbody>
                            {comparison_rows_html}
                        </tbody>
                        <tfoot>
                            <tr style="background-color: #f8f9fa; font-weight: bold;">
                                <td style="padding: 10px 8px; border: 1px solid #ddd;">TOTAL</td>
                                <td style="padding: 10px 8px; border: 1px solid #ddd;"></td>
                                <td style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">${total_submitted:,.2f}</td>
                                <td style="padding: 10px 8px; border: 1px solid #ddd;"></td>
                                <td style="padding: 10px 8px; border: 1px solid #ddd; text-align: right;">${total_approved:,.2f}</td>
                                <td style="padding: 10px 8px; border: 1px solid #ddd; text-align: right; color: {total_diff_color};">{total_diff_sign}${total_difference:,.2f}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                '''
                
                # Build plain text comparison
                comparison_table_text = '\n\nCLAIM COMPARISON\n' + '='*50 + '\n'
                comparison_table_text += 'Your submitted claim was adjusted before approval:\n\n'
                for item in comparison_data:
                    diff_sign = '+' if item['difference'] >= 0 else ''
                    comparison_table_text += f"{item['description']}:\n"
                    comparison_table_text += f"  Submitted: {item['submitted_percent']:.2f}% (${item['submitted_amount']:,.2f})\n"
                    comparison_table_text += f"  Approved:  {item['approved_percent']:.2f}% (${item['approved_amount']:,.2f})\n"
                    comparison_table_text += f"  Difference: {diff_sign}${item['difference']:,.2f}\n\n"
                
                total_diff_sign = '+' if total_difference >= 0 else ''
                comparison_table_text += f"\nTOTAL:\n"
                comparison_table_text += f"  Submitted: ${total_submitted:,.2f}\n"
                comparison_table_text += f"  Approved:  ${total_approved:,.2f}\n"
                comparison_table_text += f"  Difference: {total_diff_sign}${total_difference:,.2f}\n"
            
            # Email subject - indicate if modified
            if has_modifications:
                subject = f"Progress Claim Approved (with adjustments) - {project.project}"
            else:
                subject = f"Progress Claim Approved - {project.project}"
            
            # Plain text message
            text_message = f"""
Dear {first_name} {last_name},

Your claim for {project.project} has been approved.
{comparison_table_text}
Please upload your invoice promptly at the link below to ensure it is processed on time.

{po_url}

Regards,
{project_manager}
            """.strip()
            
            # HTML message
            html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #27ae60 0%, #229954 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">✓ Progress Claim Approved</h2>
        </div>
        <div class="content">
            <p>Dear {first_name} {last_name},</p>
            
            <p>Your claim for <strong>{project.project}</strong> has been approved.</p>
            
            {comparison_table_html}
            
            <p>Please upload your invoice promptly to ensure it is processed on time.</p>
            
            <a href="{po_url}" class="button">Upload Invoice Now</a>
            
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
                Or copy and paste this link into your browser:<br>
                <a href="{po_url}">{po_url}</a>
            </p>
            
            <p style="margin-top: 30px;">
                Regards,<br>
                <strong>{project_manager}</strong>
            </p>
        </div>
        <div class="footer">
            <p>This is an automated notification from Mason Build</p>
        </div>
    </div>
</body>
</html>
            """.strip()
            
            # Send email
            try:
                from_email = 'purchase_orders@mason.build'
                email = EmailMultiAlternatives(subject, text_message, from_email, [supplier.email])
                email.attach_alternative(html_message, "text/html")
                email.send()
                logger.info(f"Sent claim approval notification to: {supplier.email}, has_modifications: {has_modifications}")
            except Exception as e:
                logger.error(f"Error sending claim approval notification: {e}", exc_info=True)
                # Don't fail the request if email fails
        
        return JsonResponse({
            'status': 'success',
            'message': 'Claim approved successfully',
            'bill_pk': invoice.bill_pk
        })
        
    except Po_orders.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'PO not found'}, status=404)
    except Exception as e:
        logger.error(f'Error approving claim: {e}', exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def submit_po_claim(request, unique_id):
    """
    Submit or update a progress claim for a PO.
    Creates/updates Invoice with status=100 and Bill_allocations.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        import json
        from datetime import date
        from core.models import Bill_allocations, Bills, Costing
        
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project
        
        data = json.loads(request.body)
        claims = data.get('claims', [])
        pending_bill_pk = data.get('pending_bill_pk')
        
        if not claims:
            return JsonResponse({'status': 'error', 'message': 'No claims provided'}, status=400)
        
        # Track if this is a resubmission
        is_resubmission = False
        
        # Check if updating existing pending invoice or creating new
        if pending_bill_pk:
            try:
                invoice = Bills.objects.get(
                    bill_pk=pending_bill_pk,
                    project=project,
                    contact_pk=supplier,
                    bill_status=100
                )
                # This is a resubmission
                is_resubmission = True
                # Delete existing allocations to replace with new ones
                Bill_allocations.objects.filter(bill_pk=invoice).delete()
            except Bills.DoesNotExist:
                # Pending invoice not found, create new
                invoice = None
        else:
            invoice = None
        
        # Create new invoice if needed
        if not invoice:
            invoice = Bills.objects.create(
                project=project,
                contact_pk=supplier,
                bill_status=100,  # Submitted awaiting approval
                bill_type=2,  # Progress Claim
                bill_date=date.today(),
                total_net=Decimal('0'),
                total_gst=Decimal('0')
            )
        
        # Create invoice allocations
        total_net = Decimal('0')
        for claim in claims:
            costing_pk = claim.get('costing_pk')
            amount = Decimal(str(claim.get('amount', 0)))
            
            if amount > 0 and costing_pk:
                try:
                    costing = Costing.objects.get(costing_pk=costing_pk)
                    Bill_allocations.objects.create(
                        bill_pk=invoice,
                        item=costing,
                        amount=amount,
                        gst_amount=Decimal('0.00'),
                        allocation_type=0,
                        notes='Payment claim submitted by contractor'
                    )
                    total_net += amount
                except Costing.DoesNotExist:
                    logger.warning(f"Costing {costing_pk} not found")
                    continue
        
        # Update invoice totals
        invoice.total_net = total_net
        invoice.total_gst = Decimal('0.00')
        invoice.save()
        
        logger.info(f"Progress claim submitted for PO {unique_id}, Invoice {invoice.bill_pk}")
        
        # Send notification emails to contracts admin team
        if project.contracts_admin_emails:
            # Parse email addresses (semicolon-separated)
            admin_emails = [email.strip() for email in project.contracts_admin_emails.split(';') if email.strip()]
            
            if admin_emails:
                # Build PO URL
                po_url = request.build_absolute_uri(f'/po/{unique_id}/')
                
                # Determine action text
                action = "Resubmitted" if is_resubmission else "Submitted"
                
                # Email subject
                subject = f"Progress Claim {action} - {supplier.name} - {project.project}"
                
                # Plain text message
                text_message = f"""
{supplier.name} has {action} a Progress Claim for Approval.

Project: {project.project}
Supplier: {supplier.name}
Total Amount: ${total_net:,.2f}

View and approve the claim here:
{po_url}

This is an automated notification from the Mason Build platform.
                """.strip()
                
                # HTML message
                html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #27ae60 0%, #229954 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .details {{ background: white; padding: 15px; border-left: 4px solid #667eea; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">Progress Claim {action}</h2>
        </div>
        <div class="content">
            <p><strong>{supplier.name}</strong> has {action.lower()} a progress claim for approval.</p>
            
            <div class="details">
                <p><strong>Project:</strong> {project.project}</p>
                <p><strong>Supplier:</strong> {supplier.name}</p>
                <p><strong>Total Amount:</strong> ${total_net:,.2f}</p>
            </div>
            
            <p>Click the button below to view and approve the claim:</p>
            
            <a href="{po_url}" class="button">View & Approve Claim</a>
            
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
                Or copy and paste this link into your browser:<br>
                <a href="{po_url}">{po_url}</a>
            </p>
        </div>
        <div class="footer">
            <p>This is an automated notification from Mason Build</p>
        </div>
    </div>
</body>
</html>
                """.strip()
                
                # Send email
                try:
                    from_email = 'purchase_orders@mason.build'
                    email = EmailMultiAlternatives(subject, text_message, from_email, admin_emails)
                    email.attach_alternative(html_message, "text/html")
                    email.send()
                    logger.info(f"Sent progress claim notification to: {', '.join(admin_emails)}")
                except Exception as e:
                    logger.error(f"Error sending progress claim notification: {e}", exc_info=True)
                    # Don't fail the request if email fails
        
        return JsonResponse({
            'status': 'success',
            'message': 'Claim submitted for approval',
            'bill_pk': invoice.bill_pk
        })
        
    except Po_orders.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'PO not found'}, status=404)
    except Exception as e:
        logger.error(f'Error submitting claim: {e}', exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def upload_bill_pdf(request, unique_id):
    """
    Upload invoice PDF for an approved claim.
    Updates bill_status from 101 to 102.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        from core.models import Bills
        
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project
        
        # Get the approved invoice (status 101)
        try:
            invoice = Bills.objects.get(
                project=project,
                contact_pk=supplier,
                bill_status=101
            )
        except Bills.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'No approved claim awaiting invoice upload'}, status=404)
        
        # Check if PDF file was uploaded
        if 'invoice_pdf' not in request.FILES:
            return JsonResponse({'status': 'error', 'message': 'No PDF file provided'}, status=400)
        
        pdf_file = request.FILES['invoice_pdf']
        
        # Validate file type
        if not pdf_file.name.lower().endswith('.pdf'):
            return JsonResponse({'status': 'error', 'message': 'Only PDF files are allowed'}, status=400)
        
        # Save the PDF
        invoice.pdf = pdf_file
        invoice.bill_status = 102  # Approved and invoice uploaded
        invoice.save()
        
        logger.info(f"Invoice PDF uploaded for PO {unique_id}, Invoice {invoice.bill_pk}, status updated to 102")
        
        # Send notification emails to contracts admin team
        if project.contracts_admin_emails:
            # Parse email addresses (semicolon-separated)
            admin_emails = [email.strip() for email in project.contracts_admin_emails.split(';') if email.strip()]
            
            if admin_emails:
                # Build PO URL
                po_url = request.build_absolute_uri(f'/po/{unique_id}/')
                
                # Email subject
                subject = f"Invoice Uploaded - {supplier.name} - {project.project}"
                
                # Plain text message
                text_message = f"""
Invoice Uploaded for Progress Claim

{supplier.name} has uploaded their invoice for the approved progress claim.

Project: {project.project}
Supplier: {supplier.name}
Invoice Amount: ${invoice.total_net:,.2f}

You can review the invoice and claim details here:
{po_url}

This is an automated notification from the Mason Build platform.
                """.strip()
                
                # HTML message
                html_message = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: linear-gradient(135deg, #27ae60 0%, #229954 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .details {{ background: white; padding: 15px; border-left: 4px solid #3498db; margin: 15px 0; }}
        .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">📄 Invoice Uploaded</h2>
        </div>
        <div class="content">
            <p><strong>{supplier.name}</strong> has uploaded their invoice for the approved progress claim.</p>
            
            <div class="details">
                <p><strong>Project:</strong> {project.project}</p>
                <p><strong>Supplier:</strong> {supplier.name}</p>
                <p><strong>Invoice Amount:</strong> ${invoice.total_net:,.2f}</p>
            </div>
            
            <p>You can review the invoice and claim details by clicking the button below:</p>
            
            <a href="{po_url}" class="button">Review Invoice & Claim</a>
            
            <p style="margin-top: 20px; font-size: 14px; color: #666;">
                Or copy and paste this link into your browser:<br>
                <a href="{po_url}">{po_url}</a>
            </p>
        </div>
        <div class="footer">
            <p>This is an automated notification from Mason Build</p>
        </div>
    </div>
</body>
</html>
                """.strip()
                
                # Send email
                try:
                    from_email = 'purchase_orders@mason.build'
                    email = EmailMultiAlternatives(subject, text_message, from_email, admin_emails)
                    email.attach_alternative(html_message, "text/html")
                    email.send()
                    logger.info(f"Sent invoice upload notification to: {', '.join(admin_emails)}")
                except Exception as e:
                    logger.error(f"Error sending invoice upload notification: {e}", exc_info=True)
                    # Don't fail the request if email fails
        
        return JsonResponse({
            'status': 'success',
            'message': 'Invoice uploaded successfully',
            'bill_pk': invoice.bill_pk
        })
        
    except Po_orders.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'PO not found'}, status=404)
    except Exception as e:
        logger.error(f'Error uploading invoice PDF: {e}', exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def view_po_pdf_by_unique_id(request, unique_id):
    """
    Serve the saved PDF for a PO by unique_id.
    Used in iframe on the public landing page.
    Returns the most recent PDF (by created_at) for this supplier/project.
    """
    try:
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project
        
        # Get the most recent Po_orders for this supplier and project that has a PDF
        # Exclude both null and empty string values
        from django.db.models import Q
        most_recent_po = Po_orders.objects.filter(
            po_supplier=supplier,
            project=project
        ).exclude(
            Q(pdf__isnull=True) | Q(pdf='')
        ).order_by('-created_at').first()
        
        if not most_recent_po or not most_recent_po.pdf or not most_recent_po.pdf.name:
            logger.warning(f'PDF not found for PO unique_id={unique_id}, supplier={supplier}, project={project}')
            return HttpResponse('PDF not found. Please re-send the PO email to generate a new PDF.', status=404)
        
        # Serve the saved PDF file
        try:
            logger.info(f'Serving PDF: {most_recent_po.pdf.name}')
            
            # Check if file exists in storage before trying to open
            if not most_recent_po.pdf.storage.exists(most_recent_po.pdf.name):
                logger.warning(f'PDF file does not exist in storage: {most_recent_po.pdf.name}')
                return HttpResponse('PDF file not found in storage. Please re-send the PO email to regenerate.', status=404)
            
            # Open the file explicitly before reading (required for S3)
            most_recent_po.pdf.open('rb')
            pdf_content = most_recent_po.pdf.read()
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{most_recent_po.pdf.name.split("/")[-1]}"'
            # Close the file after reading
            most_recent_po.pdf.close()
            return response
        except FileNotFoundError as e:
            logger.error(f'PDF file not found: {most_recent_po.pdf.name}. This may be a legacy record from before S3 storage was configured.')
            return HttpResponse('PDF file not found. Please re-send the PO email to regenerate.', status=404)
        except Exception as e:
            logger.error(f'Error reading PDF file {most_recent_po.pdf.name}: {e}', exc_info=True)
            return HttpResponse(f'Error reading PDF file. Please re-send the PO email to regenerate.', status=500)
        
    except Po_orders.DoesNotExist:
        return HttpResponse('Purchase Order not found', status=404)
    except Exception as e:
        logger.error(f'Error serving PO PDF: {e}', exc_info=True)
        return HttpResponse(f'Error: {str(e)}', status=500)


def get_po_table_data_for_invoice(request, bill_pk):
    """
    Get PO table data for an invoice (used in allocated invoices view).
    Returns the same data as the PO public page table.
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get the invoice
        invoice = Bills.objects.select_related('contact_pk', 'project').get(bill_pk=bill_pk)
        supplier = invoice.contact_pk
        project = invoice.project
        
        logger.info(f"get_po_table_data_for_invoice: bill_pk={bill_pk}, supplier={supplier}, project={project}")
        
        if not supplier or not project:
            logger.warning(f"Invoice {bill_pk} missing supplier ({supplier}) or project ({project})")
            return JsonResponse({'status': 'error', 'message': 'Invoice missing supplier or project'}, status=400)
        
        # Find the PO for this supplier/project
        po_order = Po_orders.objects.filter(
            po_supplier=supplier,
            project=project
        ).order_by('-created_at').first()
        
        if not po_order:
            return JsonResponse({'status': 'error', 'message': 'No PO found for this invoice'}, status=404)
        
        # Check if construction project - use rates_based flag
        is_construction = (project.project_type and project.project_type.rates_based == 1)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if is_construction:
            # For construction: aggregate from Po_order_detail
            items_map = defaultdict(lambda: {
                'contract_sum': Decimal('0'),
                'contract_qty': Decimal('0'),
                'quote_numbers': [],
                'costing_pk': None,
                'unit': None
            })
            
            # Get all Po_order_details for this PO
            po_details = Po_order_detail.objects.select_related('costing', 'quote').filter(po_order_pk=po_order)
            
            for detail in po_details:
                if not detail.costing:
                    continue  # Skip if no costing linked
                    
                item_name = detail.costing.item
                items_map[item_name]['costing_pk'] = detail.costing.costing_pk
                # Convert unit to string (it's a ForeignKey to Units model)
                items_map[item_name]['unit'] = str(detail.costing.unit) if detail.costing.unit else '-'
                
                # Sum qty and calculate contract sum (qty * rate)
                if detail.qty and detail.rate:
                    items_map[item_name]['contract_sum'] += detail.qty * detail.rate
                    items_map[item_name]['contract_qty'] += detail.qty
                elif detail.amount:
                    items_map[item_name]['contract_sum'] += detail.amount
                
                # Track quote numbers
                if detail.quote and detail.quote.supplier_quote_number:
                    if detail.quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(detail.quote.supplier_quote_number)
        else:
            items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': [], 'costing_pk': None})
            
            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    if not allocation.item:
                        continue  # Skip if no item linked
                    item_name = allocation.item.item
                    items_map[item_name]['amount'] += allocation.amount or Decimal('0')
                    items_map[item_name]['costing_pk'] = allocation.item.costing_pk
                    
                    if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                        items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
        
        # Get all approved claims (bill_status = 102)
        completed_invoices = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=102
        ).order_by('bill_date', 'bill_pk')
        
        # Build list of individual claims
        individual_claims = []
        claim_number = 1
        
        # Calculate previous claims by item (only status 102)
        previous_claims_by_item = defaultdict(Decimal)
        for inv in completed_invoices:
            invoice_pdf_url = None
            if inv.pdf and hasattr(inv.pdf, 'url'):
                invoice_pdf_url = inv.pdf.url
            
            claim_data = {
                'claim_number': claim_number,
                'bill_pk': inv.bill_pk,
                'invoice_pdf_url': invoice_pdf_url,
                'allocations': {}
            }
            allocations = Bill_allocations.objects.filter(bill_pk=inv)
            for alloc in allocations:
                if alloc.item:
                    item_name = alloc.item.item
                    if is_construction and alloc.amount is None and alloc.qty and alloc.rate:
                        claim_amount = alloc.qty * alloc.rate
                    else:
                        claim_amount = alloc.amount or Decimal('0')
                    previous_claims_by_item[item_name] += claim_amount
                    claim_data['allocations'][item_name] = float(claim_amount)
            individual_claims.append(claim_data)
            claim_number += 1
        
        # Convert to list
        items = []
        for item_name, data in items_map.items():
            if is_construction:
                contract_sum = float(data['contract_sum'])
                contract_qty = float(data['contract_qty'])
                contract_rate = contract_sum / contract_qty if contract_qty > 0 else 0.0
            else:
                contract_sum = float(data['amount'])
                contract_qty = 0.0
                contract_rate = 0.0
                
            previous_claims = float(previous_claims_by_item.get(item_name, Decimal('0')))
            still_to_claim = contract_sum - previous_claims
            
            # Calculate percentages
            previous_claims_percent = (previous_claims / contract_sum * 100) if contract_sum > 0 else 0.0
            still_to_claim_percent = (still_to_claim / contract_sum * 100) if contract_sum > 0 else 0.0
            complete_percent = previous_claims_percent  # Complete = what's been claimed
            
            # Build individual claim data for this item
            item_individual_claims = []
            for claim in individual_claims:
                claim_amount = claim['allocations'].get(item_name, 0.0)
                claim_percent = (claim_amount / contract_sum * 100) if contract_sum > 0 else 0.0
                item_individual_claims.append({
                    'claim_number': claim['claim_number'],
                    'amount': claim_amount,
                    'percent': claim_percent
                })
            
            item_data = {
                'description': item_name,
                'costing_pk': data['costing_pk'],
                'contract_sum': contract_sum,
                'quote_numbers': ', '.join(data['quote_numbers']),
                'complete_percent': complete_percent,
                'previous_claims': previous_claims,
                'previous_claims_percent': previous_claims_percent,
                'still_to_claim': still_to_claim,
                'still_to_claim_percent': still_to_claim_percent,
                'individual_claims': item_individual_claims,
            }
            
            # Add construction-specific fields
            if is_construction:
                item_data['unit'] = data.get('unit', '-')
                item_data['contract_qty'] = contract_qty
                item_data['contract_rate'] = contract_rate
            
            items.append(item_data)
        
        logger.info(f"Returning PO data: {len(items)} items, {len(individual_claims)} claims")
        
        return JsonResponse({
            'status': 'success',
            'po_unique_id': po_order.unique_id or '',
            'supplier_name': supplier.name if supplier else 'Unknown',
            'project_name': project.project if project else 'Unknown',
            'is_construction': is_construction,
            'items': items,
            'individual_claims': individual_claims,
        })
        
    except Bills.DoesNotExist:
        logger.error(f'Invoice not found: {bill_pk}')
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        import traceback
        logger.error(f'Error in get_po_table_data_for_invoice for invoice {bill_pk}: {e}')
        logger.error(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def get_quotes_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')
    contact = Contacts.objects.filter(contact_name=supplier_name).first()
    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)
    quotes = Quotes.objects.filter(contact_pk=contact).prefetch_related(
        Prefetch('quote_allocations_set', queryset=Quote_allocations.objects.all(), to_attr='fetched_allocations')  
    )
    quotes_data = []
    for quote in quotes:
        quote_info = {
            "quotes_pk": quote.quotes_pk,
            "supplier_quote_number": quote.supplier_quote_number,
            "total_cost": str(quote.total_cost),  
            "quote_allocations": [
                {
                    "quote_allocations_pk": allocation.quote_allocations_pk,
                    "item": allocation.item.item,  
                    "amount": str(allocation.amount),
                    "notes": allocation.notes or ""
                } for allocation in quote.fetched_allocations  
            ]
        }
        quotes_data.append(quote_info)
    return JsonResponse(quotes_data, safe=False)