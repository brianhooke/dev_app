"""
Bills Global views - serves bills_global_inbox/direct/approvals templates.

These views handle the global Bills section accessible from the navbar,
which includes Inbox, Direct, and Approvals modes.

Template Rendering:
1. bills_global_inbox_view - Render Bills Inbox (status = -2, unprocessed email bills)
2. bills_global_direct_view - Render Bills Direct (status = 0, ready for allocation)
3. bills_global_approvals_view - Render Bills Approvals (status 2/103, approved bills)

API Endpoints:
4. send_bill_direct - Send bill to Xero (Bills Direct workflow)

All templates use allocations_layout.html for consistent layout:
- Inbox: hide_allocations=True (main table + PDF viewer only)
- Direct: all 3 sections (main table, allocations table, PDF viewer)
- Approvals: all 3 sections (main table, allocations table, PDF viewer)
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from datetime import date
import json
import logging
import requests
from urllib.parse import quote

from ..models import Bills, Bill_allocations, Contacts, Projects, XeroInstances, XeroAccounts
from .xero import get_xero_auth, parse_xero_validation_errors, handle_xero_request_errors

logger = logging.getLogger(__name__)


def bills_global_inbox_view(request):
    """Render the Bills - Inbox section template using allocations_layout.
    
    Inbox mode shows unprocessed email bills (status = -2).
    No allocations table - just main table and PDF viewer.
    """
    # Main table columns for Inbox view
    main_table_columns = [
        {'header': 'Xero / Project', 'width': '14%'},
        {'header': 'Supplier', 'width': '18%'},
        {'header': 'Bill #', 'width': '10%'},
        {'header': '$ Gross', 'width': '11%'},
        {'header': '$ Net', 'width': '11%'},
        {'header': '$ GST', 'width': '11%'},
        {'header': 'Email', 'width': '7%', 'class': 'col-action-first'},
        {'header': 'Send', 'width': '6%', 'class': 'col-action'},
        {'header': 'Archive', 'width': '6%', 'class': 'col-action'},
    ]
    
    context = {
        'main_table_columns': main_table_columns,
        'allocations_columns': [],  # Not used - allocations hidden
    }
    return render(request, 'core/bills_global_inbox.html', context)


def bills_global_direct_view(request):
    """Render the Bills - Direct section template using allocations_layout.
    
    Direct mode shows bills ready for allocation (status = 0, has xero_instance, no project).
    Shows main table, allocations table, and PDF viewer.
    """
    # Main table columns for Direct view
    main_table_columns = [
        {'header': 'Xero / Project', 'width': '14%'},
        {'header': 'Supplier', 'width': '20%'},
        {'header': 'Bill #', 'width': '10%'},
        {'header': '$ Gross', 'width': '9%'},
        {'header': '$ Net', 'width': '9%'},
        {'header': '$ GST', 'width': '9%'},
        {'header': 'Email', 'width': '7%', 'class': 'col-action-first'},
        {'header': 'Send to Xero', 'width': '10%', 'class': 'col-action'},
        {'header': 'Return', 'width': '7%', 'class': 'col-action'},
    ]
    
    # Allocations columns for Direct view
    allocations_columns = [
        {'header': 'Xero Account', 'width': '23%'},
        {'header': 'Tracking', 'width': '18%'},
        {'header': '$ Gross', 'width': '11%', 'still_to_allocate_id': 'RemainingGross'},
        {'header': '$ Net', 'width': '11%', 'still_to_allocate_id': 'RemainingNet'},
        {'header': '$ GST', 'width': '11%', 'still_to_allocate_id': 'RemainingGst'},
        {'header': 'Notes', 'width': '21%'},
        {'header': '', 'width': '5%', 'class': 'col-action-first'},  # Delete button
    ]
    
    context = {
        'main_table_columns': main_table_columns,
        'allocations_columns': allocations_columns,
    }
    return render(request, 'core/bills_global_direct.html', context)


def bills_global_approvals_view(request):
    """Render the Bills - Approvals section template using allocations_layout.
    
    Approvals mode shows bills approved and ready to send to Xero (status 2 or 103).
    Shows main table, allocations table, and PDF viewer.
    """
    # Main table columns for Approvals view
    main_table_columns = [
        {'header': 'Project', 'width': '14%', 'sortable': True},
        {'header': 'Xero Instance', 'width': '14%', 'sortable': True},
        {'header': 'Supplier', 'width': '14%', 'sortable': True},
        {'header': '$ Gross', 'width': '13%', 'sortable': True},
        {'header': '$ Net', 'width': '13%', 'sortable': True},
        {'header': '$ GST', 'width': '13%', 'sortable': True},
        {'header': 'Send', 'width': '8%', 'class': 'col-action-first'},
        {'header': 'Return', 'width': '8%', 'class': 'col-action'},
    ]
    
    # Allocations columns for Approvals view (read-only)
    allocations_columns = [
        {'header': 'Xero Account', 'width': '18%'},
        {'header': 'Tracking Category', 'width': '18%'},
        {'header': 'Costing Item', 'width': '14%'},
        {'header': '$ Gross', 'width': '12%', 'still_to_allocate_id': 'TotalGross'},
        {'header': '$ Net', 'width': '12%', 'still_to_allocate_id': 'TotalNet'},
        {'header': '$ GST', 'width': '12%', 'still_to_allocate_id': 'TotalGst'},
        {'header': 'Notes', 'width': '14%'},
    ]
    
    context = {
        'main_table_columns': main_table_columns,
        'allocations_columns': allocations_columns,
        'readonly': True,
    }
    return render(request, 'core/bills_global_approvals.html', context)


@csrf_exempt
@require_http_methods(["POST"])
@handle_xero_request_errors
def send_bill_direct(request):
    """
    Send bill to Xero from Bills - Direct workflow.
    
    Expected POST data:
    - bill_pk: int
    - xero_instance_or_project: str (format: 'xero_123')
    - supplier_pk: int
    - bill_number: str
    - total_net: decimal
    - total_gst: decimal
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        bill_pk = data.get('bill_pk')
        xero_instance_or_project = data.get('xero_instance_or_project')
        supplier_pk = data.get('supplier_pk')
        bill_number = data.get('bill_number')
        total_net = data.get('total_net')
        total_gst = data.get('total_gst')
        
        # Check all required fields
        if not all([bill_pk, xero_instance_or_project, supplier_pk, total_net is not None, total_gst is not None]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            }, status=400)
        
        # Get the invoice
        try:
            invoice = Bills.objects.get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invoice not found'
            }, status=404)
        
        # Get supplier
        try:
            supplier = Contacts.objects.get(contact_pk=supplier_pk)
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier not found'
            }, status=404)
        
        # Parse xero_instance_or_project
        xero_instance = None
        instance_pk = None
        
        if xero_instance_or_project.startswith('xero_'):
            xero_instance_id = int(xero_instance_or_project.replace('xero_', ''))
            try:
                xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_id)
                instance_pk = xero_instance.xero_instance_pk
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Xero Instance not found'
                }, status=404)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid xero_instance_or_project format'
            }, status=400)
        
        # Get allocations for this invoice
        allocations = Bill_allocations.objects.filter(bill=invoice).select_related('xero_account', 'tracking_category')
        
        # Log what we received from frontend vs what's in database
        frontend_allocations = data.get('allocations', [])
        logger.info(f"[send_bill_direct] Bill PK: {bill_pk}")
        logger.info(f"[send_bill_direct] Frontend allocations received: {json.dumps(frontend_allocations, indent=2)}")
        logger.info(f"[send_bill_direct] Database allocations count: {allocations.count()}")
        
        for db_alloc in allocations:
            logger.info(f"[send_bill_direct] DB Allocation PK={db_alloc.bill_allocation_pk}:")
            logger.info(f"  - amount: {db_alloc.amount}")
            logger.info(f"  - gst_amount: {db_alloc.gst_amount}")
            logger.info(f"  - xero_account_id: {db_alloc.xero_account_id}")
            logger.info(f"  - xero_account: {db_alloc.xero_account}")
            if db_alloc.xero_account:
                logger.info(f"  - account_code: {db_alloc.xero_account.account_code}")
            logger.info(f"  - notes: {db_alloc.notes}")
        
        if not allocations.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No allocations found. Please add allocations before sending to Xero.'
            }, status=400)
        
        # Check supplier has Xero contact ID
        if not supplier.xero_contact_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier does not have a Xero Contact ID. Please sync contacts first.'
            }, status=400)
        
        # Check all allocations have Xero accounts and valid amounts
        for allocation in allocations:
            if not allocation.xero_account:
                return JsonResponse({
                    'status': 'error',
                    'message': 'All allocations must have a Xero Account selected'
                }, status=400)
            if not allocation.amount or float(allocation.amount) <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Allocation has invalid amount (${allocation.amount}). Please ensure all amounts are saved.'
                }, status=400)
        
        # Validate frontend amounts match database amounts (detect unsaved changes)
        frontend_allocations = data.get('allocations', [])
        if frontend_allocations:
            db_total_net = sum(float(a.amount) for a in allocations)
            db_total_gst = sum(float(a.gst_amount or 0) for a in allocations)
            frontend_total_net = sum(float(a.get('amount', 0)) for a in frontend_allocations)
            frontend_total_gst = sum(float(a.get('gst_amount', 0)) for a in frontend_allocations)
            
            logger.info(f"[send_bill_direct] Comparing totals - DB: net=${db_total_net}, gst=${db_total_gst} | Frontend: net=${frontend_total_net}, gst=${frontend_total_gst}")
            
            # Allow small tolerance for floating point
            if abs(db_total_net - frontend_total_net) > 0.01 or abs(db_total_gst - frontend_total_gst) > 0.01:
                logger.error(f"[send_bill_direct] MISMATCH! Database amounts don't match frontend. Possible unsaved changes.")
                return JsonResponse({
                    'status': 'error',
                    'message': f'Allocation amounts not saved correctly. Database shows ${db_total_net:.2f} but UI shows ${frontend_total_net:.2f}. Please refresh and re-enter allocations.'
                }, status=400)
        
        # Get Xero authentication
        xero_inst, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_inst:
            return access_token  # This is the error response
        
        logger.info(f"Sending bill {bill_pk} to Xero for instance: {xero_instance.xero_name}")
        
        # Build line items from allocations
        line_items = []
        for allocation in allocations:
            # Log each allocation being processed
            logger.info(f"[send_bill_direct] Processing allocation {allocation.bill_allocation_pk}:")
            logger.info(f"  - Building line item with amount={allocation.amount}, gst={allocation.gst_amount}")
            
            # Check for missing xero_account
            if not allocation.xero_account:
                logger.error(f"[send_bill_direct] MISSING xero_account for allocation {allocation.bill_allocation_pk}!")
                continue
            
            line_item = {
                "Description": allocation.notes or "No description",
                "Quantity": 1,
                "UnitAmount": float(allocation.amount) if allocation.amount else 0,
                "AccountCode": allocation.xero_account.account_code,
                "TaxType": "INPUT" if allocation.gst_amount and allocation.gst_amount > 0 else "NONE",
                "TaxAmount": float(allocation.gst_amount) if allocation.gst_amount else 0
            }
            
            logger.info(f"  - Line item built: {json.dumps(line_item)}")
            
            # Add tracking category if set
            if allocation.tracking_category:
                line_item["Tracking"] = [{
                    "Name": allocation.tracking_category.name,
                    "Option": allocation.tracking_category.option_name
                }]
            
            line_items.append(line_item)
        
        logger.info(f"[send_bill_direct] Total line items built: {len(line_items)}")
        logger.info(f"[send_bill_direct] Line items: {json.dumps(line_items, indent=2)}")
        
        # Build invoice payload for Xero
        invoice_payload = {
            "Type": "ACCPAY",
            "Contact": {
                "ContactID": supplier.xero_contact_id
            },
            "Date": date.today().strftime('%Y-%m-%d'),
            "DueDate": date.today().strftime('%Y-%m-%d'),
            "InvoiceNumber": bill_number or '',
            "LineItems": line_items,
            "Status": "DRAFT"
        }
        
        # Send to Xero API
        logger.info(f"Sending invoice to Xero: {json.dumps(invoice_payload, indent=2)}")
        
        response = requests.post(
            'https://api.xero.com/api.xro/2.0/Invoices',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json={"Invoices": [invoice_payload]},
            timeout=30
        )
        
        # Check response
        if response.status_code != 200:
            error_msg = parse_xero_validation_errors(response)
            if not error_msg:
                error_msg = f'Xero API error: {response.status_code} - {response.text}'
            logger.error(f"Xero API error: {error_msg}")
            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=response.status_code)
        
        # Success - parse response
        xero_response = response.json()
        logger.info(f"Xero response: {json.dumps(xero_response, indent=2)}")
        
        # Extract Xero Invoice ID
        xero_invoice_id = None
        if 'Invoices' in xero_response and len(xero_response['Invoices']) > 0:
            xero_invoice_id = xero_response['Invoices'][0].get('InvoiceID')
        
        # Update invoice status
        invoice.bill_status = 2  # Sent to Xero
        invoice.save()
        
        logger.info(f"Successfully sent bill {bill_pk} to Xero (InvoiceID: {xero_invoice_id})")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Bill sent to Xero successfully',
            'bill_pk': invoice.bill_pk,
            'xero_invoice_id': xero_invoice_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_bill_direct: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_bill_pdf_info(request):
    """
    Get PDF info for a bill before sending to Xero.
    Returns the PDF URL and source (invoice.pdf or email_attachment).
    """
    try:
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing bill_pk'
            }, status=400)
        
        try:
            invoice = Bills.objects.select_related('email_attachment').get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invoice not found'
            }, status=404)
        
        pdf_url = None
        source = None
        
        # Check invoice.pdf first (FileField)
        if invoice.pdf and invoice.pdf.name:
            try:
                pdf_url = invoice.pdf.url
                source = f"invoice.pdf (name: {invoice.pdf.name})"
                logger.info(f"Bill {bill_pk} PDF info: source=invoice.pdf, url={pdf_url}")
            except Exception as e:
                logger.error(f"Error getting invoice.pdf URL: {str(e)}")
                source = f"invoice.pdf ERROR: {str(e)}"
        
        # Check email_attachment if no invoice.pdf
        if not pdf_url and invoice.email_attachment:
            try:
                pdf_url = invoice.email_attachment.get_download_url()
                source = f"email_attachment (id: {invoice.email_attachment.id}, filename: {invoice.email_attachment.filename}, s3_key: {invoice.email_attachment.s3_key})"
                logger.info(f"Bill {bill_pk} PDF info: source=email_attachment, url={pdf_url}")
            except Exception as e:
                logger.error(f"Error getting email_attachment URL: {str(e)}")
                source = f"email_attachment ERROR: {str(e)}"
        
        if not pdf_url:
            source = f"NO PDF - invoice.pdf.name={invoice.pdf.name if invoice.pdf else None}, email_attachment_id={invoice.email_attachment_id}"
            logger.warning(f"Bill {bill_pk} has no PDF: {source}")
        
        return JsonResponse({
            'status': 'success',
            'bill_pk': bill_pk,
            'pdf_url': pdf_url,
            'source': source
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in get_bill_pdf_info: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@handle_xero_request_errors
def send_bill_to_xero(request):
    """
    Send an approved bill to Xero from Bills - Approvals workflow.
    
    Expected POST data:
    - bill_pk: int
    
    The bill already has all required data (supplier, allocations, etc.)
    since it was approved through the project workflow.
    """
    try:
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        
        if not bill_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Missing bill_pk'
            }, status=400)
        
        # Get the invoice
        try:
            invoice = Bills.objects.select_related(
                'contact_pk', 'project', 'xero_instance', 'project__xero_instance', 'email_attachment'
            ).get(bill_pk=bill_pk)
        except Bills.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Invoice not found'
            }, status=404)
        
        # Check status - must be approved (2) or PO approved (103)
        if invoice.bill_status not in [2, 103]:
            return JsonResponse({
                'status': 'error',
                'message': f'Invoice status {invoice.bill_status} is not approved'
            }, status=400)
        
        # Get supplier
        supplier = invoice.contact_pk
        if not supplier:
            return JsonResponse({
                'status': 'error',
                'message': 'Invoice has no supplier assigned'
            }, status=400)
        
        if not supplier.xero_contact_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier does not have a Xero Contact ID. Please sync contacts first.'
            }, status=400)
        
        # Get Xero instance (from invoice or project)
        xero_instance = invoice.xero_instance
        if not xero_instance and invoice.project:
            xero_instance = invoice.project.xero_instance
        
        if not xero_instance:
            return JsonResponse({
                'status': 'error',
                'message': 'No Xero instance found for this invoice'
            }, status=400)
        
        # Get allocations
        allocations = Bill_allocations.objects.filter(bill=invoice).select_related(
            'xero_account', 'tracking_category', 'item'
        )
        
        if not allocations.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No allocations found for this invoice'
            }, status=400)
        
        # Check all allocations have Xero accounts
        for allocation in allocations:
            if not allocation.xero_account:
                return JsonResponse({
                    'status': 'error',
                    'message': 'All allocations must have a Xero Account selected'
                }, status=400)
        
        # Get Xero authentication
        xero_inst, access_token, tenant_id = get_xero_auth(xero_instance.xero_instance_pk)
        if not xero_inst:
            return access_token  # This is the error response
        
        logger.info(f"Sending approved bill {bill_pk} to Xero for instance: {xero_instance.xero_name}")
        
        # Build line items from allocations
        line_items = []
        for allocation in allocations:
            line_item = {
                "Description": allocation.notes or (allocation.item.item if allocation.item else "No description"),
                "Quantity": float(allocation.qty) if allocation.qty else 1,
                "UnitAmount": float(allocation.amount) / (float(allocation.qty) if allocation.qty else 1),
                "AccountCode": allocation.xero_account.account_code,
                "TaxType": "INPUT" if allocation.gst_amount and allocation.gst_amount > 0 else "NONE",
                "TaxAmount": float(allocation.gst_amount) if allocation.gst_amount else 0
            }
            
            # Add tracking category if set
            if allocation.tracking_category:
                line_item["Tracking"] = [{
                    "Name": allocation.tracking_category.name,
                    "Option": allocation.tracking_category.option_name
                }]
            
            line_items.append(line_item)
        
        # Build invoice payload for Xero
        invoice_payload = {
            "Type": "ACCPAY",
            "Contact": {
                "ContactID": supplier.xero_contact_id
            },
            "Date": invoice.bill_date.strftime('%Y-%m-%d') if invoice.bill_date else date.today().strftime('%Y-%m-%d'),
            "DueDate": invoice.bill_due_date.strftime('%Y-%m-%d') if invoice.bill_due_date else date.today().strftime('%Y-%m-%d'),
            "InvoiceNumber": invoice.supplier_bill_number or '',
            "LineItems": line_items,
            "Status": "DRAFT"
        }
        
        # Send to Xero API
        logger.info(f"Sending invoice to Xero: {json.dumps(invoice_payload, indent=2)}")
        
        response = requests.post(
            'https://api.xero.com/api.xro/2.0/Invoices',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json={"Invoices": [invoice_payload]},
            timeout=30
        )
        
        # Check response
        if response.status_code != 200:
            error_msg = parse_xero_validation_errors(response)
            if not error_msg:
                error_msg = f'Xero API error: {response.status_code} - {response.text}'
            logger.error(f"Xero API error: {error_msg}")
            return JsonResponse({
                'status': 'error',
                'message': error_msg
            }, status=response.status_code)
        
        # Success - parse response
        xero_response = response.json()
        logger.info(f"Xero response: {json.dumps(xero_response, indent=2)}")
        
        # Extract Xero Invoice ID
        xero_invoice_id = None
        if 'Invoices' in xero_response and len(xero_response['Invoices']) > 0:
            xero_invoice_id = xero_response['Invoices'][0].get('InvoiceID')
        
        # Attach PDF to the Xero invoice if available
        attachment_status = None
        if xero_invoice_id:
            pdf_url = None
            file_name = None
            
            # Log what we have for debugging
            logger.info(f"Bill {bill_pk}: invoice.pdf={invoice.pdf}, invoice.pdf.name={invoice.pdf.name if invoice.pdf else None}, email_attachment_id={invoice.email_attachment_id}")
            
            # Check for PDF - first try invoice.pdf (FileField), then email_attachment
            # Note: FileField can be truthy even when empty, so check .name
            if invoice.pdf and invoice.pdf.name:
                try:
                    pdf_url = invoice.pdf.url
                    file_name = pdf_url.split('/')[-1]
                    logger.info(f"Found invoice.pdf: {pdf_url}")
                except Exception as e:
                    logger.error(f"Error getting invoice.pdf URL: {str(e)}")
            
            if not pdf_url and invoice.email_attachment:
                try:
                    pdf_url = invoice.email_attachment.get_download_url()
                    file_name = invoice.email_attachment.filename or f"bill_{bill_pk}.pdf"
                    logger.info(f"Found email_attachment: {pdf_url}, filename: {file_name}")
                except Exception as e:
                    logger.error(f"Error getting email_attachment URL: {str(e)}")
            
            if pdf_url and file_name:
                try:
                    # Download the PDF
                    logger.info(f"Downloading PDF from: {pdf_url}")
                    pdf_response = requests.get(pdf_url, timeout=30)
                    
                    if pdf_response.status_code == 200:
                        file_data = pdf_response.content
                        
                        # Upload attachment to Xero
                        # URL-encode the filename for the API endpoint
                        encoded_filename = quote(file_name, safe='')
                        logger.info(f"Uploading attachment '{file_name}' (encoded: {encoded_filename}) to Xero invoice {xero_invoice_id}, size: {len(file_data)} bytes")
                        attach_response = requests.post(
                            f'https://api.xero.com/api.xro/2.0/Invoices/{xero_invoice_id}/Attachments/{encoded_filename}',
                            headers={
                                'Authorization': f'Bearer {access_token}',
                                'Content-Type': 'application/pdf',
                                'Xero-tenant-id': tenant_id
                            },
                            data=file_data,
                            timeout=60
                        )
                        
                        if attach_response.status_code == 200:
                            logger.info(f"Successfully attached PDF to Xero invoice {xero_invoice_id}")
                            attachment_status = 'success'
                        else:
                            logger.error(f"Failed to attach PDF to Xero: {attach_response.status_code} - {attach_response.text}")
                            attachment_status = 'failed'
                    else:
                        logger.error(f"Failed to download PDF: {pdf_response.status_code}")
                        attachment_status = 'download_failed'
                except Exception as e:
                    logger.error(f"Error attaching PDF to Xero: {str(e)}", exc_info=True)
                    attachment_status = 'error'
            else:
                logger.info(f"No PDF found for bill {bill_pk}")
                attachment_status = 'no_pdf'
        
        # Update invoice status to "sent to Xero"
        if invoice.bill_status == 2:
            invoice.bill_status = 3  # Sent to Xero
        elif invoice.bill_status == 103:
            invoice.bill_status = 104  # PO sent to Xero
        
        invoice.bill_xero_id = xero_invoice_id
        invoice.save()
        
        logger.info(f"Successfully sent bill {bill_pk} to Xero (InvoiceID: {xero_invoice_id}, attachment: {attachment_status})")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Bill sent to Xero successfully' + ('' if attachment_status == 'success' else ' (PDF attachment may have failed)'),
            'bill_pk': invoice.bill_pk,
            'xero_invoice_id': xero_invoice_id,
            'attachment_status': attachment_status
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_bill_to_xero: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@csrf_exempt
def return_bill_to_project(request, invoice_id):
    """
    Return an approved invoice back to project (from Approvals).
    Status 2 -> 1 (allocated)
    Status 103 -> 102 (PO approved, invoice uploaded)
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        invoice = Bills.objects.get(bill_pk=invoice_id)
        
        if invoice.bill_status == 2:
            invoice.bill_status = 1
        elif invoice.bill_status == 103:
            invoice.bill_status = 102
        else:
            return JsonResponse({
                'status': 'error', 
                'message': f'Invoice status {invoice.bill_status} cannot be returned to project'
            }, status=400)
        
        invoice.save()
        
        return JsonResponse({
            'status': 'success',
            'new_status': invoice.bill_status,
            'message': 'Invoice returned to project'
        })
    except Bills.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
    except Exception as e:
        logger.error(f"Error returning invoice to project: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# =============================================================================
# Bills Global API Endpoints
# Moved from bills.py - used by bills_global_inbox/direct/approvals templates
# =============================================================================

@csrf_exempt
def archive_bill(request):
    """
    Archive a bill by setting bill_status to -1
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bill_pk = data.get('bill_pk')
            
            if not bill_pk:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice PK is required'
                }, status=400)
            
            # Get the invoice
            try:
                invoice = Bills.objects.get(bill_pk=bill_pk)
            except Bills.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice not found'
                }, status=404)
            
            # Update status to -1 (archived)
            invoice.bill_status = -1
            invoice.save()
            
            logger.info(f"Archived invoice #{bill_pk}")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Bill archived successfully',
                'bill_pk': bill_pk
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error archiving bill: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
def return_to_inbox(request):
    """
    Return a bill to inbox by clearing fields and setting status to -2
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bill_pk = data.get('bill_pk')
            
            if not bill_pk:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice PK is required'
                }, status=400)
            
            # Get the invoice
            try:
                invoice = Bills.objects.get(bill_pk=bill_pk)
            except Bills.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invoice not found'
                }, status=404)
            
            # Delete all associated allocations
            deleted_count = Bill_allocations.objects.filter(bill=invoice).delete()[0]
            logger.info(f"Deleted {deleted_count} allocations for invoice {bill_pk}")
            
            # Clear fields and set status to -2
            invoice.xero_instance = None
            invoice.project = None
            invoice.total_net = None
            invoice.total_gst = None
            invoice.supplier_bill_number = None
            invoice.contact_pk = None
            invoice.bill_status = -2
            
            invoice.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Bill returned to inbox successfully',
                'bill_pk': invoice.bill_pk
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Server error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


def get_bills_list(request):
    """
    Get list of all invoices for Bills modals (Inbox and Direct)
    Frontend will filter by bill_status as needed
    Also provides dropdown data for Xero instances, suppliers, and projects
    """
    # Get all invoices (frontend will filter by status)
    invoices = Bills.objects.select_related(
        'contact_pk', 'project', 'xero_instance', 'received_email', 'email_attachment'
    ).prefetch_related('bill_allocations').order_by('-created_at')
    
    # Get dropdown options
    xero_instances = XeroInstances.objects.all().values('xero_instance_pk', 'xero_name')
    suppliers = Contacts.objects.filter(status='ACTIVE').order_by('name').values('contact_pk', 'name', 'xero_instance_id')
    projects = Projects.objects.filter(archived=False).order_by('project').values('projects_pk', 'project', 'xero_instance_id')
    
    # Prepare bills data
    bills_data = []
    for invoice in invoices:
        try:
            # Get presigned S3 URL for attachment if it exists
            attachment_url = ''
            if invoice.email_attachment:
                try:
                    # Generate presigned URL (valid for 1 hour)
                    attachment_url = invoice.email_attachment.get_download_url()
                except Exception as e:
                    # If S3 URL generation fails, use empty string
                    logger.warning(f"Error getting download URL for attachment {invoice.email_attachment.id}: {str(e)}")
                    attachment_url = ''
            
            # Get email URL (link to received email in admin)
            email_url = ''
            if invoice.received_email:
                email_url = f"/admin/core/receivedemail/{invoice.received_email.id}/change/"
            
            # Determine xero_instance_id from either direct xero_instance or project
            xero_instance_id = None
            if invoice.xero_instance_id:
                xero_instance_id = invoice.xero_instance_id
            elif invoice.project and invoice.project.xero_instance_id:
                xero_instance_id = invoice.project.xero_instance_id
            
            # Get existing allocations for this invoice
            allocations = []
            for allocation in invoice.bill_allocations.all():
                allocations.append({
                    'allocation_pk': allocation.bill_allocation_pk,
                    'amount': float(allocation.amount) if allocation.amount is not None else None,
                    'gst_amount': float(allocation.gst_amount) if allocation.gst_amount is not None else None,
                    'notes': allocation.notes or '',
                    'xero_account_pk': allocation.xero_account_id if allocation.xero_account else None,
                })
            
            # Get PDF URL (local file or S3)
            pdf_url = invoice.pdf.url if invoice.pdf else ''
            
            bill = {
                'bill_pk': invoice.bill_pk,
                'bill_status': invoice.bill_status,
                'xero_instance_id': xero_instance_id,
                'xero_instance_pk': xero_instance_id,  # Add this for frontend compatibility
                'contact_pk': invoice.contact_pk.contact_pk if invoice.contact_pk else None,
                'project_pk': invoice.project.projects_pk if invoice.project else None,
                'supplier_bill_number': invoice.supplier_bill_number or '',
                'total_net': float(invoice.total_net) if invoice.total_net is not None else None,
                'total_gst': float(invoice.total_gst) if invoice.total_gst is not None else None,
                'pdf_url': pdf_url,
                'email_subject': invoice.received_email.subject if invoice.received_email else 'N/A',
                'email_from': invoice.received_email.from_address if invoice.received_email else 'N/A',
                'email_body_html': invoice.received_email.body_html if invoice.received_email else '',
                'email_body_text': invoice.received_email.body_text if invoice.received_email else '',
                'attachment_filename': invoice.email_attachment.filename if invoice.email_attachment else 'N/A',
                'attachment_url': attachment_url,
                'email_url': email_url,
                'allocations': allocations,
            }
            bills_data.append(bill)
        except Exception as e:
            # Log error but continue processing other invoices
            logger.error(f"Error processing invoice {invoice.bill_pk}: {str(e)}")
            continue
    
    return JsonResponse({
        'bills': bills_data,
        'xero_instances': list(xero_instances),
        'suppliers': list(suppliers),
        'projects': list(projects),
        'count': len(bills_data)
    })


def _pull_xero_accounts_for_instance(instance_pk):
    """
    Helper function to pull accounts and tracking categories for a single Xero instance.
    Returns a dict with results for this instance.
    Note: Does not use @handle_xero_request_errors decorator since it returns a dict, not a JsonResponse.
    """
    xero_instance = XeroInstances.objects.get(xero_instance_pk=instance_pk)
    logger.info(f"Processing Xero instance: {xero_instance.xero_name} (PK: {instance_pk})")
    
    # Get Xero authentication
    xero_inst, access_token, tenant_id = get_xero_auth(instance_pk)
    if not xero_inst:
        # access_token is actually a JsonResponse error when auth fails
        logger.error(f"Authentication failed for {xero_instance.xero_name}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'error',
            'message': 'Authentication failed - please re-authorize this Xero instance',
            'accounts_added': 0,
            'accounts_updated': 0,
            'accounts_unchanged': 0,
            'divisions_added': 0,
            'divisions_updated': 0,
            'divisions_unchanged': 0
        }
    
    logger.info(f"Successfully authenticated for {xero_instance.xero_name}, tenant_id: {tenant_id}")
    
    accounts_added = 0
    accounts_updated = 0
    accounts_unchanged = 0
    
    # Fetch Chart of Accounts from Xero
    accounts_response = requests.get(
        'https://api.xero.com/api.xro/2.0/Accounts',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Xero-tenant-id': tenant_id
        },
        timeout=30
    )
    
    if accounts_response.status_code != 200:
        error_msg = f'Failed to fetch accounts: {accounts_response.status_code}'
        logger.error(f"{xero_instance.xero_name}: {error_msg}")
        logger.error(f"Response body: {accounts_response.text[:500]}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'error',
            'message': error_msg,
            'accounts_added': 0,
            'accounts_updated': 0,
            'accounts_unchanged': 0
        }
    
    accounts_data = accounts_response.json()
    xero_accounts = accounts_data.get('Accounts', [])
    
    logger.info(f"Fetched {len(xero_accounts)} accounts from Xero for {xero_instance.xero_name} (PK: {xero_instance.xero_instance_pk})")
    
    # Get all existing account IDs for this instance (to detect deleted accounts)
    existing_account_ids = set(
        XeroAccounts.objects.filter(xero_instance=xero_instance)
        .exclude(account_status='DELETED_IN_XERO')
        .values_list('account_id', flat=True)
    )
    seen_account_ids = set()
    
    # Process each account
    for xero_account in xero_accounts:
        account_id = xero_account.get('AccountID')
        account_code = xero_account.get('Code', '')
        account_name = xero_account.get('Name', '')
        account_status = xero_account.get('Status', '')
        account_type = xero_account.get('Type', '')
        
        # Track this account as seen in Xero
        seen_account_ids.add(account_id)
        
        # Check if account already exists (using xero_instance + account_id as unique identifier)
        try:
            account, created = XeroAccounts.objects.update_or_create(
                xero_instance=xero_instance,
                account_id=account_id,
                defaults={
                    'account_name': account_name,
                    'account_code': account_code,
                    'account_status': account_status,
                    'account_type': account_type
                }
            )
            
            # Debug log for first few accounts
            if xero_accounts.index(xero_account) < 3:
                logger.info(f"  Account {account_code} ({account_name}) -> Instance PK: {account.xero_instance_id}, Created: {created}")
            
            if created:
                accounts_added += 1
            else:
                # Check if anything actually changed
                if (account.account_name == account_name and 
                    account.account_code == account_code and 
                    account.account_status == account_status and 
                    account.account_type == account_type):
                    accounts_unchanged += 1
                else:
                    accounts_updated += 1
        except Exception as e:
            # Handle duplicate account_code within same instance
            logger.warning(f"Skipping duplicate account {account_code} ({account_name}) for {xero_instance.xero_name}: {str(e)}")
            continue
    
    logger.info(f"Processed {len(xero_accounts)} accounts for {xero_instance.xero_name}")
    
    # Mark accounts that exist locally but not in Xero as DELETED_IN_XERO
    deleted_account_ids = existing_account_ids - seen_account_ids
    accounts_deleted = 0
    if deleted_account_ids:
        accounts_deleted = XeroAccounts.objects.filter(
            xero_instance=xero_instance,
            account_id__in=deleted_account_ids
        ).update(account_status='DELETED_IN_XERO')
        logger.info(f"Marked {accounts_deleted} accounts as DELETED_IN_XERO for {xero_instance.xero_name}")
    
    # Fetch Tracking Categories (Divisions) from Xero
    tracking_response = requests.get(
        'https://api.xero.com/api.xro/2.0/TrackingCategories',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Xero-tenant-id': tenant_id
        },
        timeout=30
    )
    
    if tracking_response.status_code != 200:
        logger.warning(f"Failed to fetch tracking categories for {xero_instance.xero_name}: {tracking_response.status_code}")
        return {
            'instance_name': xero_instance.xero_name,
            'status': 'partial',
            'message': f'Accounts synced but tracking categories failed: {tracking_response.status_code}',
            'accounts_added': accounts_added,
            'accounts_updated': accounts_updated,
            'tracking_categories_found': 0
        }
    
    return {
        'instance_name': xero_instance.xero_name,
        'status': 'success',
        'accounts_added': accounts_added,
        'accounts_updated': accounts_updated,
        'accounts_unchanged': accounts_unchanged,
        'accounts_deleted': accounts_deleted
    }


@csrf_exempt
def pull_xero_accounts_and_divisions(request):
    """
    Pull accounts from Xero API for all instances.
    Inserts new records and updates existing ones.
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get all Xero instances
        xero_instances = XeroInstances.objects.all()
        
        if not xero_instances.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No Xero instances found'
            }, status=404)
        
        total_accounts_added = 0
        total_accounts_updated = 0
        total_accounts_unchanged = 0
        instance_results = []
        
        # Process each Xero instance using the helper function
        for xero_instance in xero_instances:
            instance_pk = xero_instance.xero_instance_pk
            
            try:
                # Call helper function
                result = _pull_xero_accounts_for_instance(instance_pk)
                instance_results.append(result)
                
                # Aggregate totals
                total_accounts_added += result.get('accounts_added', 0)
                total_accounts_updated += result.get('accounts_updated', 0)
                total_accounts_unchanged += result.get('accounts_unchanged', 0)
                
            except Exception as e:
                logger.error(f"Error processing instance {xero_instance.xero_name}: {str(e)}", exc_info=True)
                instance_results.append({
                    'instance_name': xero_instance.xero_name,
                    'status': 'error',
                    'message': f'Error: {str(e)}',
                    'accounts_added': 0,
                    'accounts_updated': 0,
                    'accounts_unchanged': 0
                })
        
        return JsonResponse({
            'status': 'success',
            'message': f'Processed {len(xero_instances)} Xero instance(s)',
            'summary': {
                'total_accounts_added': total_accounts_added,
                'total_accounts_updated': total_accounts_updated,
                'total_accounts_unchanged': total_accounts_unchanged
            },
            'instances': instance_results
        })
        
    except Exception as e:
        logger.error(f"Error in pull_xero_accounts_and_divisions: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
def pull_xero_accounts(request, instance_pk):
    """
    Pull accounts from Xero API for a single instance.
    Inserts new records and updates existing ones.
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Call the helper function
        result = _pull_xero_accounts_for_instance(instance_pk)
        
        if result.get('status') == 'error':
            # Check if it's an auth error
            if 'authorization' in result.get('message', '').lower() or 'auth' in result.get('message', '').lower():
                return JsonResponse({
                    'status': 'error',
                    'message': result.get('message'),
                    'needs_auth': True
                }, status=401)
            return JsonResponse({
                'status': 'error',
                'message': result.get('message')
            }, status=400)
        
        return JsonResponse({
            'status': 'success',
            'instance_name': result.get('instance_name'),
            'accounts_added': result.get('accounts_added', 0),
            'accounts_updated': result.get('accounts_updated', 0),
            'accounts_unchanged': result.get('accounts_unchanged', 0),
            'accounts_deleted': result.get('accounts_deleted', 0)
        })
        
    except Exception as e:
        logger.error(f"Error in pull_xero_accounts: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }, status=500)


@csrf_exempt
def get_xero_accounts_by_instance(request, instance_pk):
    """
    Get all Xero accounts for a specific Xero instance.
    Used to populate the Xero Account dropdown in bill allocations.
    """
    try:
        accounts = XeroAccounts.objects.filter(
            xero_instance_id=instance_pk,
            account_status='ACTIVE'
        ).order_by('account_code').values(
            'xero_account_pk',
            'account_code',
            'account_name',
            'account_type'
        )
        
        return JsonResponse({
            'status': 'success',
            'accounts': list(accounts)
        })
        
    except Exception as e:
        logger.error(f"Error fetching Xero accounts for instance {instance_pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
def get_tracking_categories_by_instance(request, instance_pk):
    """
    Get all Xero tracking categories for a specific Xero instance.
    Used to populate the Tracking Category dropdown in bill allocations.
    Returns "name - option_name" format for display.
    """
    try:
        from core.models import XeroTrackingCategories
        
        categories = XeroTrackingCategories.objects.filter(
            xero_instance_id=instance_pk,
            status='ACTIVE'
        ).order_by('name', 'option_name')
        
        # Build list with "name - option_name" format
        tracking_list = []
        seen_combos = set()
        for cat in categories:
            if cat.name and cat.option_name:
                combo = f"{cat.name} - {cat.option_name}"
                if combo not in seen_combos:
                    tracking_list.append({
                        'tracking_category_pk': cat.tracking_category_pk,
                        'name': combo,
                        'category_name': cat.name,
                        'option_name': cat.option_name,
                    })
                    seen_combos.add(combo)
        
        # Sort alphabetically
        tracking_list.sort(key=lambda x: x['name'].lower())
        
        return JsonResponse({
            'status': 'success',
            'tracking_categories': tracking_list
        })
        
    except Exception as e:
        logger.error(f"Error fetching tracking categories for instance {instance_pk}: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error: {str(e)}'
        }, status=500)


@csrf_exempt
def create_bill_allocation(request):
    """
    Create a new invoice allocation entry.
    Called when a bill row is clicked or when user adds a new allocation row.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        bill_pk = data.get('bill_pk')
        amount = data.get('amount')
        gst_amount = data.get('gst_amount')
        xero_account_pk = data.get('xero_account_pk')
        
        if not bill_pk:
            return JsonResponse({'status': 'error', 'message': 'bill_pk is required'}, status=400)
        
        logger.info(f"[create_bill_allocation] Creating allocation with data: {data}")
        
        # Create allocation
        allocation = Bill_allocations.objects.create(
            bill_id=bill_pk,
            amount=amount or 0,
            gst_amount=gst_amount or 0,
            allocation_type=0,
            xero_account_id=xero_account_pk if xero_account_pk else None
        )
        
        logger.info(f"[create_bill_allocation] Created allocation {allocation.bill_allocation_pk}:")
        logger.info(f"  - bill_id: {bill_pk}")
        logger.info(f"  - amount: {allocation.amount}")
        logger.info(f"  - gst_amount: {allocation.gst_amount}")
        logger.info(f"  - xero_account_id: {allocation.xero_account_id}")
        
        return JsonResponse({
            'status': 'success',
            'allocation_pk': allocation.bill_allocation_pk
        })
        
    except Exception as e:
        logger.error(f"Error creating invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def update_bill_allocation(request):
    """
    Update an existing invoice allocation entry.
    Called when user changes Xero Account, Division, amounts, or description.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation_pk = data.get('allocation_pk')
        
        if not allocation_pk:
            return JsonResponse({'status': 'error', 'message': 'allocation_pk is required'}, status=400)
        
        try:
            allocation = Bill_allocations.objects.get(bill_allocation_pk=allocation_pk)
        except Bill_allocations.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
        
        # Update fields if provided
        logger.info(f"[update_bill_allocation] Updating allocation {allocation_pk} with data: {data}")
        
        if 'amount' in data:
            logger.info(f"  - Setting amount: {data['amount']}")
            allocation.amount = data['amount']
        if 'gst_amount' in data:
            logger.info(f"  - Setting gst_amount: {data['gst_amount']}")
            allocation.gst_amount = data['gst_amount']
        if 'notes' in data:
            logger.info(f"  - Setting notes: {data['notes']}")
            allocation.notes = data['notes']
        if 'xero_account_pk' in data:
            logger.info(f"  - Setting xero_account_id: {data['xero_account_pk']}")
            allocation.xero_account_id = data['xero_account_pk'] if data['xero_account_pk'] else None
        if 'tracking_category_pk' in data:
            logger.info(f"  - Setting tracking_category_id: {data['tracking_category_pk']}")
            allocation.tracking_category_id = data['tracking_category_pk'] if data['tracking_category_pk'] else None
        
        allocation.save()
        
        # Log the saved state
        logger.info(f"[update_bill_allocation] Saved allocation {allocation_pk}:")
        logger.info(f"  - amount: {allocation.amount}")
        logger.info(f"  - gst_amount: {allocation.gst_amount}")
        logger.info(f"  - xero_account_id: {allocation.xero_account_id}")
        logger.info(f"  - notes: {allocation.notes}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error updating invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def delete_bill_allocation(request):
    """
    Delete an invoice allocation entry.
    Called when user clicks the X button on an allocation row.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        allocation_pk = data.get('allocation_pk')
        
        if not allocation_pk:
            return JsonResponse({'status': 'error', 'message': 'allocation_pk is required'}, status=400)
        
        try:
            allocation = Bill_allocations.objects.get(bill_allocation_pk=allocation_pk)
            allocation.delete()
            
            logger.info(f"Deleted invoice allocation {allocation_pk}")
            return JsonResponse({'status': 'success'})
        except Bill_allocations.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Allocation not found'}, status=404)
        
    except Exception as e:
        logger.error(f"Error deleting invoice allocation: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
