"""
Bills views for dashboard app
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from core.models import Invoices, Contacts, XeroInstances, Projects
from decimal import Decimal


@csrf_exempt
@require_http_methods(["POST"])
def send_bill(request):
    """
    Update invoice with user-entered data and set status to 0
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
        
        if xero_instance_or_project.startswith('xero_'):
            xero_instance_id = int(xero_instance_or_project.replace('xero_', ''))
            try:
                xero_instance = XeroInstances.objects.get(xero_instance_pk=xero_instance_id)
            except XeroInstances.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Xero Instance not found'
                }, status=404)
        elif xero_instance_or_project.startswith('project_'):
            project_id = int(xero_instance_or_project.replace('project_', ''))
            try:
                project = Projects.objects.get(projects_pk=project_id)
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
        
        # Update invoice
        invoice.xero_instance = xero_instance
        invoice.project = project
        invoice.contact_pk = supplier
        invoice.supplier_invoice_number = invoice_number
        invoice.total_net = Decimal(str(total_net))
        invoice.total_gst = Decimal(str(total_gst))
        invoice.invoice_status = 2  # Set status to 2 (sent to Xero)
        
        invoice.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Invoice updated successfully',
            'invoice_pk': invoice.invoice_pk
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
