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

from ..models import Bills, Bill_allocations, Contacts, Projects, XeroInstances
from .xero import get_xero_auth, parse_xero_validation_errors, handle_xero_request_errors

logger = logging.getLogger(__name__)


def bills_global_inbox_view(request):
    """Render the Bills - Inbox section template using allocations_layout.
    
    Inbox mode shows unprocessed email bills (status = -2).
    No allocations table - just main table and PDF viewer.
    """
    # Main table columns for Inbox view
    main_table_columns = [
        {'header': 'Xero / Project', 'width': '10%'},
        {'header': 'Supplier', 'width': '23%'},
        {'header': 'Bill #', 'width': '10%'},
        {'header': '$ Net', 'width': '11%'},
        {'header': '$ GST', 'width': '11%'},
        {'header': 'Email', 'width': '8%', 'class': 'col-action-first'},
        {'header': 'Send', 'width': '12%', 'class': 'col-action'},
        {'header': 'Archive', 'width': '10%', 'class': 'col-action'},
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
        {'header': 'Xero / Project', 'width': '10%'},
        {'header': 'Supplier', 'width': '23%'},
        {'header': 'Bill #', 'width': '10%'},
        {'header': '$ Net', 'width': '11%'},
        {'header': '$ GST', 'width': '11%'},
        {'header': 'Email', 'width': '8%', 'class': 'col-action-first'},
        {'header': 'Send to Xero', 'width': '12%', 'class': 'col-action'},
        {'header': 'Return', 'width': '10%', 'class': 'col-action'},
    ]
    
    # Allocations columns for Direct view
    allocations_columns = [
        {'header': 'Xero Account', 'width': '30%'},
        {'header': '$ Net', 'width': '15%', 'still_to_allocate_id': 'RemainingNet'},
        {'header': '$ GST', 'width': '15%', 'still_to_allocate_id': 'RemainingGst'},
        {'header': 'Notes', 'width': '35%'},
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
        {'header': 'Project', 'width': '12%', 'sortable': True},
        {'header': 'Xero Instance', 'width': '12%', 'sortable': True},
        {'header': 'Xero Account', 'width': '12%', 'sortable': True},
        {'header': 'Supplier', 'width': '12%', 'sortable': True},
        {'header': '$ Gross', 'width': '12%', 'sortable': True},
        {'header': '$ Net', 'width': '11%', 'sortable': True},
        {'header': '$ GST', 'width': '11%', 'sortable': True},
        {'header': 'Send', 'width': '7%', 'class': 'col-action-first'},
        {'header': 'Return', 'width': '7%', 'class': 'col-action'},
    ]
    
    # Allocations columns for Approvals view (read-only)
    allocations_columns = [
        {'header': 'Costing Item', 'width': '30%'},
        {'header': '$ Net', 'width': '20%', 'still_to_allocate_id': 'TotalNet'},
        {'header': '$ GST', 'width': '20%', 'still_to_allocate_id': 'TotalGst'},
        {'header': 'Notes', 'width': '30%'},
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
        allocations = Bill_allocations.objects.filter(bill=invoice).select_related('xero_account')
        
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
        
        # Check all allocations have Xero accounts
        for allocation in allocations:
            if not allocation.xero_account:
                return JsonResponse({
                    'status': 'error',
                    'message': 'All allocations must have a Xero Account selected'
                }, status=400)
        
        # Get Xero authentication
        xero_inst, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_inst:
            return access_token  # This is the error response
        
        logger.info(f"Sending bill {bill_pk} to Xero for instance: {xero_instance.xero_name}")
        
        # Build line items from allocations
        line_items = []
        for allocation in allocations:
            line_item = {
                "Description": allocation.notes or "No description",
                "Quantity": 1,
                "UnitAmount": float(allocation.amount),
                "AccountCode": allocation.xero_account.account_code,
                "TaxType": "INPUT" if allocation.gst_amount and allocation.gst_amount > 0 else "NONE",
                "TaxAmount": float(allocation.gst_amount) if allocation.gst_amount else 0
            }
            line_items.append(line_item)
        
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
