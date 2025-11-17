"""
Bills views for dashboard app
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
import requests
from core.models import Invoices, Contacts, XeroInstances, Projects, Invoice_allocations
from core.views.xero import get_xero_auth, handle_xero_request_errors, parse_xero_validation_errors
from decimal import Decimal
from datetime import date

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@handle_xero_request_errors
def send_bill(request):
    """
    Send invoice and its allocations to Xero, then update status to 2 if successful.
    Expected POST data:
    - invoice_pk: int
    - xero_instance_or_project: str (format: 'xero_123' or 'project_456')
    - supplier_pk: int
    - invoice_number: str
    - total_net: decimal
    - total_gst: decimal
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        invoice_pk = data.get('invoice_pk')
        xero_instance_or_project = data.get('xero_instance_or_project')
        supplier_pk = data.get('supplier_pk')
        invoice_number = data.get('invoice_number')
        total_net = data.get('total_net')
        total_gst = data.get('total_gst')
        
        # Check all required fields
        if not all([invoice_pk, xero_instance_or_project, supplier_pk, invoice_number, total_net is not None, total_gst is not None]):
            return JsonResponse({
                'status': 'error',
                'message': 'Missing required fields'
            }, status=400)
        
        # Get the invoice
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        except Invoices.DoesNotExist:
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
        project = None
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
        elif xero_instance_or_project.startswith('project_'):
            project_id = int(xero_instance_or_project.replace('project_', ''))
            try:
                project = Projects.objects.get(projects_pk=project_id)
                if not project.xero_instance:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Project does not have a Xero Instance assigned'
                    }, status=400)
                xero_instance = project.xero_instance
                instance_pk = xero_instance.xero_instance_pk
            except Projects.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Project not found'
                }, status=404)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid xero_instance_or_project format'
            }, status=400)
        
        # Get allocations for this invoice
        allocations = Invoice_allocations.objects.filter(invoice_pk=invoice).select_related('xero_account')
        
        # Check if allocations exist - this determines the workflow
        if allocations.exists():
            # Bills - Direct workflow: Validate allocations and send to Xero
            logger.info(f"Bills - Direct: Validating allocations and sending to Xero for invoice {invoice_pk}")
            
            # Check supplier has Xero contact ID (required for Xero API)
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
            
            logger.info(f"Sending bill {invoice_pk} to Xero for instance: {xero_instance.xero_name}")
            
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
                "Type": "ACCPAY",  # Bill (purchase invoice)
                "Contact": {
                    "ContactID": supplier.xero_contact_id
                },
                "Date": date.today().strftime('%Y-%m-%d'),
                "DueDate": date.today().strftime('%Y-%m-%d'),  # Set to today for now
                "InvoiceNumber": invoice_number,
                "LineItems": line_items,
                "Status": "DRAFT"  # Send as draft for review
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
            
            # Success! Parse response
            xero_response = response.json()
            logger.info(f"Xero response: {json.dumps(xero_response, indent=2)}")
            
            # Extract Xero Invoice ID from response
            xero_invoice_id = None
            if 'Invoices' in xero_response and len(xero_response['Invoices']) > 0:
                xero_invoice_id = xero_response['Invoices'][0].get('InvoiceID')
            
            # Update invoice in database - only now that Xero succeeded
            invoice.xero_instance = xero_instance
            invoice.project = project
            invoice.contact_pk = supplier
            invoice.supplier_invoice_number = invoice_number
            invoice.total_net = Decimal(str(total_net))
            invoice.total_gst = Decimal(str(total_gst))
            invoice.invoice_status = 2  # Set status to 2 (sent to Xero)
            
            invoice.save()
            
            logger.info(f"Successfully sent invoice {invoice_pk} to Xero (InvoiceID: {xero_invoice_id})")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Invoice sent to Xero successfully',
                'invoice_pk': invoice.invoice_pk,
                'xero_invoice_id': xero_invoice_id
            })
        else:
            # Bills - Inbox workflow: Just update invoice and set status to 0 (ready for allocation)
            logger.info(f"Bills - Inbox: Moving invoice {invoice_pk} to Bills - Direct (status 0)")
            
            # Update invoice in database
            invoice.xero_instance = xero_instance
            invoice.project = project
            invoice.contact_pk = supplier
            invoice.supplier_invoice_number = invoice_number
            invoice.total_net = Decimal(str(total_net))
            invoice.total_gst = Decimal(str(total_gst))
            invoice.invoice_status = 0  # Set status to 0 (created, ready for allocation in Bills - Direct)
            
            invoice.save()
            
            logger.info(f"Successfully moved invoice {invoice_pk} to Bills - Direct")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Invoice moved to Bills - Direct successfully',
                'invoice_pk': invoice.invoice_pk
            })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_bill: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
