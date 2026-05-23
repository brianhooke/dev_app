"""
PO (Purchase Order) related views.

Template Rendering:
- po_view -- Render the PO section template (supports project_pk query param).

Public PO Pages (Supplier-Facing):
- view_po_by_unique_id -- Public landing page for suppliers to view a PO
  and submit/edit progress claims.
- view_po_pdf_by_unique_id -- Serve the saved PDF for a PO via its unique_id.

Progress Claims:
- submit_po_claim   -- Supplier submits/updates a progress claim
                       (creates a Bills row with status 100).
- approve_po_claim  -- Principal approves a pending progress claim
                       (100 -> 101). Login-required.
- upload_bill_pdf   -- Supplier uploads the invoice PDF for an approved
                       claim (101 -> 102).

Internal Read APIs:
- get_po_table_data_for_invoice -- Pivot the PO/claims data for an
  already-allocated bill (used in the allocated-invoices view).

Note: the legacy create/generate/send endpoints were deleted in the
audit fix-pass (B16-B19). The live "send PO" path lives in
core/views/dashboard.py:send_po_email and reads from quotes directly,
so the parallel implementation that used to live here is now dead.
"""
import json
import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from ..models import (
    Bill_allocations, Bills, Contacts, Costing,
    Po_orders, Po_order_detail, Projects, Quotes,
)

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


def view_po_by_unique_id(request, unique_id):
    """
    Public view for suppliers to access their PO via unique URL.
    Displays payment schedule table for supplier to fill out.
    """
    try:
        po_order = Po_orders.objects.select_related(
            'po_supplier', 'project', 'project__project_type'
        ).get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project

        # Check if construction project - use rates_based flag
        is_construction = bool(
            project.project_type and project.project_type.rates_based == 1
        )
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')

        # Group every dict below by costing_pk (not the costing's item
        # string) so two costings with the same display name in
        # different categories can't silently collapse into one row,
        # and so the costing_pk we send to the supplier always
        # round-trips back to the right Costing on submit (B13).
        if is_construction:
            items_map = defaultdict(lambda: {
                'contract_sum': Decimal('0'),
                'contract_qty': Decimal('0'),
                'quote_numbers': [],
                'description': None,
                'unit': None,
            })

            po_details = Po_order_detail.objects.select_related(
                'costing', 'costing__unit', 'quote'
            ).filter(po_order_pk=po_order)
            logger.info(
                f"PO Public URL - PO pk={po_order.po_order_pk}, "
                f"found {po_details.count()} Po_order_detail records"
            )

            for detail in po_details:
                if not detail.costing:
                    continue
                key = detail.costing.costing_pk
                bucket = items_map[key]
                bucket['description'] = detail.costing.item
                bucket['unit'] = (
                    str(detail.costing.unit) if detail.costing.unit else '-'
                )
                if detail.qty and detail.rate:
                    bucket['contract_sum'] += detail.qty * detail.rate
                    bucket['contract_qty'] += detail.qty
                elif detail.amount:
                    bucket['contract_sum'] += detail.amount

                if detail.quote and detail.quote.supplier_quote_number:
                    qn = detail.quote.supplier_quote_number
                    if qn not in bucket['quote_numbers']:
                        bucket['quote_numbers'].append(qn)
        else:
            items_map = defaultdict(lambda: {
                'amount': Decimal('0'),
                'quote_numbers': [],
                'description': None,
            })

            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    if not allocation.item:
                        continue
                    key = allocation.item.costing_pk
                    bucket = items_map[key]
                    bucket['description'] = allocation.item.item
                    bucket['amount'] += allocation.amount or Decimal('0')

                    if quote.supplier_quote_number and quote.supplier_quote_number not in bucket['quote_numbers']:
                        bucket['quote_numbers'].append(quote.supplier_quote_number)
        
        # Get previous approved claims. We include every status from
        # "approved + bill uploaded" (102) onward so claims that have
        # since been pushed to Xero (104) or settled don't silently
        # drop out of the supplier's history (B8). The set lives on
        # the Bills model so other reports stay in sync.
        completed_invoices = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status__gte=Bills.STATUS_PO_APPROVED_BILL_UPLOADED,
        ).order_by('bill_date', 'bill_pk')
        
        # Build list of individual claims for expandable view.
        # Allocation totals are bucketed by costing_pk to match items_map (B13).
        individual_claims = []
        claim_number = 1

        previous_claims_by_costing = defaultdict(Decimal)
        for invoice in completed_invoices:
            invoice_pdf_url = None
            if invoice.pdf and hasattr(invoice.pdf, 'url'):
                invoice_pdf_url = invoice.pdf.url

            claim_data = {
                'claim_number': claim_number,
                'bill_pk': invoice.bill_pk,
                'invoice_pdf_url': invoice_pdf_url,
                'allocations': {},  # costing_pk -> claim amount (float)
            }
            allocations = Bill_allocations.objects.filter(bill=invoice)
            for alloc in allocations:
                if not alloc.item:
                    continue
                key = alloc.item.costing_pk
                # For construction: use amount if available, else qty * rate
                if is_construction and alloc.amount is None and alloc.qty and alloc.rate:
                    claim_amount = alloc.qty * alloc.rate
                else:
                    claim_amount = alloc.amount or Decimal('0')
                previous_claims_by_costing[key] += claim_amount
                claim_data['allocations'][key] = float(claim_amount)
            individual_claims.append(claim_data)
            claim_number += 1

        # Check for pending claim (bill_status = STATUS_PO_PROGRESS_SUBMITTED, 100)
        pending_invoice = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=Bills.STATUS_PO_PROGRESS_SUBMITTED,
        ).first()

        # Check for approved claim awaiting invoice upload (bill_status = STATUS_PO_APPROVED_NO_BILL, 101)
        approved_invoice = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status=Bills.STATUS_PO_APPROVED_NO_BILL,
        ).first()

        pending_claims_by_costing = {}
        approved_claims_by_costing = {}

        if pending_invoice:
            for alloc in Bill_allocations.objects.filter(bill=pending_invoice):
                if alloc.item:
                    pending_claims_by_costing[alloc.item.costing_pk] = float(alloc.amount)

        if approved_invoice:
            for alloc in Bill_allocations.objects.filter(bill=approved_invoice):
                if alloc.item:
                    approved_claims_by_costing[alloc.item.costing_pk] = float(alloc.amount)
        
        items = []
        for costing_pk, data in items_map.items():
            if is_construction:
                contract_sum = float(data['contract_sum'])
                contract_qty = float(data['contract_qty'])
                contract_rate = contract_sum / contract_qty if contract_qty > 0 else 0.0
            else:
                contract_sum = float(data['amount'])
                contract_qty = 0.0
                contract_rate = 0.0

            previous_claims = float(previous_claims_by_costing.get(costing_pk, Decimal('0')))
            this_claim = (
                pending_claims_by_costing.get(costing_pk, 0.0)
                or approved_claims_by_costing.get(costing_pk, 0.0)
            )
            still_to_claim = contract_sum - previous_claims - this_claim

            previous_claims_percent = (previous_claims / contract_sum * 100) if contract_sum > 0 else 0.0
            this_claim_percent = (this_claim / contract_sum * 100) if contract_sum > 0 else 0.0
            still_to_claim_percent = (still_to_claim / contract_sum * 100) if contract_sum > 0 else 0.0

            item_individual_claims = []
            for claim in individual_claims:
                claim_amount = claim['allocations'].get(costing_pk, 0.0)
                claim_percent = (claim_amount / contract_sum * 100) if contract_sum > 0 else 0.0
                item_individual_claims.append({
                    'claim_number': claim['claim_number'],
                    'amount': claim_amount,
                    'percent': claim_percent,
                })

            item_data = {
                'description': data['description'],
                'costing_pk': costing_pk,
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
            # Only authenticated users (Mason staff) can approve / edit a
            # supplier's claim. The supplier-facing page is public, so we
            # hide the Approve/Edit-Claim buttons for anonymous viewers.
            # The /po/<id>/approve/ endpoint also checks login server-side.
            'is_admin': request.user.is_authenticated,
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
    if not request.user.is_authenticated:
        return JsonResponse(
            {'status': 'error', 'message': 'Login required to approve claims.'},
            status=401,
        )

    try:
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
                            bill=invoice,
                            item=costing,
                        ).first()

                        if allocation:
                            allocation.amount = approved_amount
                            allocation.save()
                            logger.info(f"Updated allocation for costing {costing_pk}: {submitted_amount} -> {approved_amount}")
                    except Costing.DoesNotExist:
                        logger.warning(f"Costing {costing_pk} not found when updating allocation")

        # Recalculate invoice totals from allocations (in case any were modified)
        totals = Bill_allocations.objects.filter(bill=invoice).aggregate(
            total_net=Sum('amount'),
            total_gst=Sum('gst_amount'),
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
        po_order = Po_orders.objects.get(unique_id=unique_id)
        supplier = po_order.po_supplier
        project = po_order.project

        data = json.loads(request.body)
        claims = data.get('claims', [])
        pending_bill_pk = data.get('pending_bill_pk')
        
        if not claims:
            return JsonResponse({'status': 'error', 'message': 'No claims provided'}, status=400)
        
        # Track if this is a resubmission.
        is_resubmission = False
        invoice = None

        # Check if updating an existing pending invoice or creating a new one.
        if pending_bill_pk:
            try:
                invoice = Bills.objects.select_for_update().get(
                    bill_pk=pending_bill_pk,
                    project=project,
                    contact_pk=supplier,
                    bill_status=Bills.STATUS_PO_PROGRESS_SUBMITTED,
                )
                is_resubmission = True
            except Bills.DoesNotExist:
                # Stale pending_bill_pk (already approved or different project) —
                # fall through to the lookup below so we don't accidentally
                # create a second pending row for the same supplier (B15).
                invoice = None

        # If the client didn't pass a pending_bill_pk, or the one it passed
        # has already moved on, look up any existing pending row for this
        # supplier+project before creating a new one.
        if not invoice:
            invoice = (
                Bills.objects
                .select_for_update()
                .filter(
                    project=project,
                    contact_pk=supplier,
                    bill_status=Bills.STATUS_PO_PROGRESS_SUBMITTED,
                )
                .order_by('-bill_pk')
                .first()
            )
            if invoice is not None:
                is_resubmission = True

        # Atomically replace allocations on the existing pending invoice,
        # or create a fresh one if no pending row exists. The whole
        # delete + recreate runs inside transaction.atomic() so a mid-way
        # failure can't leave the supplier with no allocations (B14).
        with transaction.atomic():
            if invoice is None:
                invoice = Bills.objects.create(
                    project=project,
                    contact_pk=supplier,
                    bill_status=Bills.STATUS_PO_PROGRESS_SUBMITTED,
                    bill_type=2,  # Progress Claim
                    bill_date=date.today(),
                    total_net=Decimal('0'),
                    total_gst=Decimal('0'),
                )
            else:
                Bill_allocations.objects.filter(bill=invoice).delete()

            total_net = Decimal('0')
            for claim in claims:
                costing_pk = claim.get('costing_pk')
                amount = Decimal(str(claim.get('amount', 0)))

                if amount > 0 and costing_pk:
                    try:
                        costing = Costing.objects.get(costing_pk=costing_pk)
                    except Costing.DoesNotExist:
                        logger.warning(f"Costing {costing_pk} not found")
                        continue
                    Bill_allocations.objects.create(
                        bill=invoice,
                        item=costing,
                        amount=amount,
                        gst_amount=Decimal('0.00'),
                        allocation_type=0,
                        notes='Payment claim submitted by contractor',
                    )
                    total_net += amount

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

    Now that send_po_email upserts a single canonical Po_orders row per
    (project, supplier), we just serve that one row's PDF (B9/B10).
    """
    try:
        po_order = Po_orders.objects.get(unique_id=unique_id)

        if not po_order.pdf or not po_order.pdf.name:
            logger.warning(
                f'PDF not found for PO unique_id={unique_id}, '
                f'supplier={po_order.po_supplier_id}, project={po_order.project_id}'
            )
            return HttpResponse(
                'PDF not found. Please re-send the PO email to generate a new PDF.',
                status=404,
            )

        try:
            logger.info(f'Serving PDF: {po_order.pdf.name}')

            if not po_order.pdf.storage.exists(po_order.pdf.name):
                logger.warning(f'PDF file does not exist in storage: {po_order.pdf.name}')
                return HttpResponse(
                    'PDF file not found in storage. Please re-send the PO email to regenerate.',
                    status=404,
                )

            po_order.pdf.open('rb')
            pdf_content = po_order.pdf.read()
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = (
                f'inline; filename="{po_order.pdf.name.split("/")[-1]}"'
            )
            po_order.pdf.close()
            return response
        except FileNotFoundError:
            logger.error(
                f'PDF file not found: {po_order.pdf.name}. '
                f'May be a legacy record from before S3 storage was configured.'
            )
            return HttpResponse(
                'PDF file not found. Please re-send the PO email to regenerate.',
                status=404,
            )
        except Exception as e:
            logger.error(f'Error reading PDF file {po_order.pdf.name}: {e}', exc_info=True)
            return HttpResponse(
                'Error reading PDF file. Please re-send the PO email to regenerate.',
                status=500,
            )

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
        
        # Group by costing_pk (B13) — see view_po_by_unique_id for the
        # rationale.
        if is_construction:
            items_map = defaultdict(lambda: {
                'contract_sum': Decimal('0'),
                'contract_qty': Decimal('0'),
                'quote_numbers': [],
                'description': None,
                'unit': None,
            })

            po_details = Po_order_detail.objects.select_related(
                'costing', 'costing__unit', 'quote'
            ).filter(po_order_pk=po_order)

            for detail in po_details:
                if not detail.costing:
                    continue
                key = detail.costing.costing_pk
                bucket = items_map[key]
                bucket['description'] = detail.costing.item
                bucket['unit'] = (
                    str(detail.costing.unit) if detail.costing.unit else '-'
                )
                if detail.qty and detail.rate:
                    bucket['contract_sum'] += detail.qty * detail.rate
                    bucket['contract_qty'] += detail.qty
                elif detail.amount:
                    bucket['contract_sum'] += detail.amount

                if detail.quote and detail.quote.supplier_quote_number:
                    qn = detail.quote.supplier_quote_number
                    if qn not in bucket['quote_numbers']:
                        bucket['quote_numbers'].append(qn)
        else:
            items_map = defaultdict(lambda: {
                'amount': Decimal('0'),
                'quote_numbers': [],
                'description': None,
            })

            for quote in quotes:
                for allocation in quote.quote_allocations.all():
                    if not allocation.item:
                        continue
                    key = allocation.item.costing_pk
                    bucket = items_map[key]
                    bucket['description'] = allocation.item.item
                    bucket['amount'] += allocation.amount or Decimal('0')

                    if quote.supplier_quote_number and quote.supplier_quote_number not in bucket['quote_numbers']:
                        bucket['quote_numbers'].append(quote.supplier_quote_number)

        # Get all approved claims. Include 102+ so claims that have
        # advanced to 103 (paid) or 104 (sent to Xero) stay visible (B8).
        completed_invoices = Bills.objects.filter(
            project=project,
            contact_pk=supplier,
            bill_status__gte=Bills.STATUS_PO_APPROVED_BILL_UPLOADED,
        ).order_by('bill_date', 'bill_pk')

        individual_claims = []
        claim_number = 1
        previous_claims_by_costing = defaultdict(Decimal)
        for inv in completed_invoices:
            invoice_pdf_url = None
            if inv.pdf and hasattr(inv.pdf, 'url'):
                invoice_pdf_url = inv.pdf.url

            claim_data = {
                'claim_number': claim_number,
                'bill_pk': inv.bill_pk,
                'invoice_pdf_url': invoice_pdf_url,
                'allocations': {},
            }
            for alloc in Bill_allocations.objects.filter(bill=inv):
                if not alloc.item:
                    continue
                key = alloc.item.costing_pk
                if is_construction and alloc.amount is None and alloc.qty and alloc.rate:
                    claim_amount = alloc.qty * alloc.rate
                else:
                    claim_amount = alloc.amount or Decimal('0')
                previous_claims_by_costing[key] += claim_amount
                claim_data['allocations'][key] = float(claim_amount)
            individual_claims.append(claim_data)
            claim_number += 1

        items = []
        for costing_pk, data in items_map.items():
            if is_construction:
                contract_sum = float(data['contract_sum'])
                contract_qty = float(data['contract_qty'])
                contract_rate = contract_sum / contract_qty if contract_qty > 0 else 0.0
            else:
                contract_sum = float(data['amount'])
                contract_qty = 0.0
                contract_rate = 0.0

            previous_claims = float(previous_claims_by_costing.get(costing_pk, Decimal('0')))
            still_to_claim = contract_sum - previous_claims

            previous_claims_percent = (previous_claims / contract_sum * 100) if contract_sum > 0 else 0.0
            still_to_claim_percent = (still_to_claim / contract_sum * 100) if contract_sum > 0 else 0.0
            complete_percent = previous_claims_percent

            item_individual_claims = []
            for claim in individual_claims:
                claim_amount = claim['allocations'].get(costing_pk, 0.0)
                claim_percent = (claim_amount / contract_sum * 100) if contract_sum > 0 else 0.0
                item_individual_claims.append({
                    'claim_number': claim['claim_number'],
                    'amount': claim_amount,
                    'percent': claim_percent,
                })

            item_data = {
                'description': data['description'],
                'costing_pk': costing_pk,
                'contract_sum': contract_sum,
                'quote_numbers': ', '.join(data['quote_numbers']),
                'complete_percent': complete_percent,
                'previous_claims': previous_claims,
                'previous_claims_percent': previous_claims_percent,
                'still_to_claim': still_to_claim,
                'still_to_claim_percent': still_to_claim_percent,
                'individual_claims': item_individual_claims,
            }

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


