import csv
from decimal import Decimal, InvalidOperation
from django.template import loader
from .forms import CSVUploadForm
from django.http import HttpResponse, JsonResponse
from .models import Categories, Contacts, Quotes, Costing, Quote_allocations, DesignCategories, PlanPdfs, ReportPdfs, ReportCategories, Po_globals, Po_orders, Po_order_detail, SPVData, Letterhead, Invoices, Invoice_allocations, HC_claims, HC_claim_allocations, Projects
import json
from django.shortcuts import render
from django.forms.models import model_to_dict
from django.db.models import Sum, Case, When, IntegerField, Q, F, Prefetch
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
from .models import Invoices, Contacts, Costing, Categories, Quote_allocations, Quotes, Po_globals, Po_orders, SPVData
import json
from django.db.models import Q
import ssl
import urllib.request
from django.core.exceptions import ValidationError
from .formulas import Committed
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction


ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set logging level to INFO

def drawings(request):
    return render(request, 'drawings.html')

def main(request, division):
    costings = Costing.objects.filter(category__division=division).order_by('category__order_in_list','category__category','item')
    costings = [model_to_dict(costing) for costing in costings]
    for c in costings:
        cat_obj = Categories.objects.get(pk=c['category'])
        c['category'] = cat_obj.category
    contacts = Contacts.objects.filter(division=division,checked=True).order_by('contact_name').values()
    contacts_list = list(contacts)
    contacts_unfiltered = Contacts.objects.filter(division=division).order_by('contact_name').values()
    contacts_unfiltered_list = list(contacts_unfiltered)
    quote_allocations = Quote_allocations.objects.filter(item__category__division=division).select_related('item').all()
    quote_allocations = [{**model_to_dict(ca),'item_name': ca.item.item}for ca in quote_allocations]
    quote_allocations_sums = Quote_allocations.objects.values('item').annotate(total_amount=Sum('amount'))
    quote_allocations_sums_dict = {i['item']: i['total_amount'] for i in quote_allocations_sums}
    committed_values = {pk: amount for pk, amount in Committed()}
    for c in costings:
        c['committed'] = committed_values.get(c['costing_pk'],0)
    print('\n=== DEBUG: Invoice Allocations ===')    
    # Get all invoice allocations and print their details
    all_allocations = Invoice_allocations.objects.all().select_related('invoice_pk', 'item')
    print('\nAll Invoice Allocations:')
    for alloc in all_allocations:
        print(f"Invoice {alloc.invoice_pk.invoice_pk} - Item {alloc.item.costing_pk}: Amount {alloc.amount}")
    
    # Get and print the sums
    invoice_allocations_sums = Invoice_allocations.objects.values('item').annotate(total_amount=Sum('amount'))
    print('\nRaw invoice_allocations_sums:')
    for sum_item in invoice_allocations_sums:
        print(f"Item {sum_item['item']}: Total {sum_item['total_amount']}")
    
    invoice_allocations_sums_dict = {i['item']: i['total_amount'] for i in invoice_allocations_sums}
    print('\ninvoice_allocations_sums_dict:', invoice_allocations_sums_dict)
    
    # Print how the totals are being assigned
    print('\nAssigning totals to costings:')
    for c in costings:
        original_value = invoice_allocations_sums_dict.get(c['costing_pk'], 0)
        c['sc_invoiced'] = original_value
        c['sc_paid'] = 0
        print(f"Costing {c['costing_pk']}: Found in sums_dict: {c['costing_pk'] in invoice_allocations_sums_dict}, Value: {original_value} (type: {type(original_value)})")
    
    # Print category groupings and their totals
    print('\nCategory Totals:')
    category_totals = {}
    for c in costings:
        cat = c['category']
        if cat not in category_totals:
            category_totals[cat] = 0
        category_totals[cat] += c['sc_invoiced']
    
    for cat, total in category_totals.items():
        print(f"Category '{cat}': Total {total}")
    items = [{'item': c['item'],'uncommitted': c['uncommitted'],'committed': c['committed']} for c in costings]
    committed_quotes = Quotes.objects.filter(contact_pk__division=division).values('quotes_pk','supplier_quote_number','total_cost','pdf','contact_pk','contact_pk__contact_name')
    committed_quotes_list = list(committed_quotes)
    for q in committed_quotes_list:
        if settings.DEBUG: q['pdf'] = settings.MEDIA_URL + q['pdf']
        else: q['pdf'] = settings.MEDIA_URL + q['pdf']
    committed_quotes_json = json.dumps(committed_quotes_list, cls=DjangoJSONEncoder)
    quote_allocations_json = json.dumps(list(quote_allocations), cls=DjangoJSONEncoder)
    contact_pks_in_quotes = Quotes.objects.filter(contact_pk__division=division).values_list('contact_pk',flat=True).distinct()
    contacts_in_quotes = Contacts.objects.filter(pk__in=contact_pks_in_quotes,division=division)
    contacts_in_quotes_list = []
    for contact in contacts_in_quotes:
        d = contact.__dict__
        d['quotes'] = list(contact.quotes_set.values('quotes_pk','supplier_quote_number','total_cost','pdf','contact_pk'))
        contacts_in_quotes_list.append(d)
    contacts_not_in_quotes = Contacts.objects.exclude(pk__in=contact_pks_in_quotes,division=division).values()
    contacts_not_in_quotes_list = list(contacts_not_in_quotes)
    total_contract_budget = sum(c['contract_budget'] for c in costings)
    total_uncommitted = sum(c['uncommitted'] for c in costings)
    total_committed = sum(c['committed'] for c in costings)
    total_forecast_budget = total_committed + total_uncommitted
    total_sc_invoiced = sum(c['sc_invoiced'] for c in costings)
    total_fixed_on_site = sum(c['fixed_on_site'] for c in costings)
    total_sc_paid = sum(c['sc_paid'] for c in costings)
    po_globals = Po_globals.objects.first()
    po_orders = Po_orders.objects.filter(po_supplier__division=division).select_related('po_supplier').all()
    po_orders_list = []
    for order in po_orders:
        po_orders_list.append({'po_order_pk': order.po_order_pk,'po_supplier': order.po_supplier_id,'supplier_name': order.po_supplier.contact_name,'supplier_email': order.po_supplier.contact_email,'po_note_1': order.po_note_1,'po_note_2': order.po_note_2,'po_note_3': order.po_note_3,'po_sent': order.po_sent})
    invoices = Invoices.objects.filter(invoice_division=division).select_related('contact_pk','associated_hc_claim').order_by(F('associated_hc_claim__pk').desc(nulls_first=True)).all()
    invoices_list = [{'invoice_pk': i.invoice_pk,'invoice_status': i.invoice_status,'contact_name': i.contact_pk.contact_name,'total_net': i.total_net,'total_gst': i.total_gst,'supplier_invoice_number': i.supplier_invoice_number,'pdf_url': i.pdf.url,'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,'invoice_date': i.invoice_date,'invoice_due_date': i.invoice_due_date}for i in invoices]
    invoices_unallocated = Invoices.objects.filter(invoice_status=0,invoice_division=division).select_related('contact_pk','associated_hc_claim')
    invoices_unallocated_list = []
    quotes_contact_pks = set(Quotes.objects.values_list('contact_pk',flat=True))
    for i in invoices_unallocated:
        invoices_unallocated_list.append({'invoice_pk': i.invoice_pk,'contact_pk': i.contact_pk.pk,'invoice_status': i.invoice_status,'contact_name': i.contact_pk.contact_name,'total_net': i.total_net,'total_gst': i.total_gst,'supplier_invoice_number': i.supplier_invoice_number,'pdf_url': i.pdf.url,'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,'invoice_date': i.invoice_date,'invoice_due_date': i.invoice_due_date,'possible_progress_claim': 1 if i.contact_pk.pk in quotes_contact_pks else 0})
    invoices_allocated = Invoices.objects.exclude(invoice_status=0).filter(invoice_division=division).select_related('contact_pk','associated_hc_claim')
    invoices_allocated_list = [{'invoice_pk': i.invoice_pk,'invoice_status': i.invoice_status,'contact_name': i.contact_pk.contact_name,'total_net': i.total_net,'total_gst': i.total_gst,'supplier_invoice_number': i.supplier_invoice_number,'pdf_url': i.pdf.url,'associated_hc_claim': i.associated_hc_claim.hc_claim_pk if i.associated_hc_claim else None,'display_id': i.associated_hc_claim.display_id if i.associated_hc_claim else None,'invoice_date': i.invoice_date,'invoice_due_date': i.invoice_due_date}for i in invoices_allocated]
    # Get HC and QS claim totals from HC_claim_allocations
    hc_qs_totals = HC_claim_allocations.objects.values('hc_claim_pk').annotate(
        hc_total=Sum('hc_claimed'),
        qs_total=Sum('qs_claimed')
    )
    hc_qs_totals_dict = {item['hc_claim_pk']: {
        'hc_total': float(item['hc_total'] or 0), 
        'qs_total': float(item['qs_total'] or 0)
    } for item in hc_qs_totals}
    
    # Get invoice totals for each HC claim
    sc_totals = Invoices.objects.filter(associated_hc_claim__isnull=False).values('associated_hc_claim').annotate(
        sc_total=Sum('total_net')
    )
    sc_totals_dict = {item['associated_hc_claim']: float(item['sc_total'] or 0) for item in sc_totals}
    
    hc_claims_list = []
    hc_claims_qs = HC_claims.objects.all().order_by('-display_id')
    for claim in hc_claims_qs:
        claim_totals = hc_qs_totals_dict.get(claim.hc_claim_pk, {'hc_total': 0.0, 'qs_total': 0.0})
        d = {
            'hc_claim_pk': claim.hc_claim_pk,
            'date': claim.date.strftime('%Y-%m-%d') if claim.date else None,
            'status': claim.status,
            'display_id': claim.display_id,
            'invoicee': claim.invoicee if claim.invoicee else None,
            'hc_total': claim_totals['hc_total'],
            'qs_total': claim_totals['qs_total'],
            'sc_total': sc_totals_dict.get(claim.hc_claim_pk, 0.0)
        }
        hc_claims_list.append(d)
    hc_claims_json = json.dumps(hc_claims_list, cls=DjangoJSONEncoder)
    current_hc_claim = HC_claims.objects.filter(status=0).first()
    current_hc_claim_display_id = current_hc_claim.display_id if current_hc_claim else None
    hc_claim_wip_adjustments = {}
    if current_hc_claim:
        hc_claim_allocs = HC_claim_allocations.objects.filter(hc_claim_pk=current_hc_claim.hc_claim_pk)
        hc_claim_wip_adjustments = {a.item.costing_pk: a.adjustment for a in hc_claim_allocs}
    if current_hc_claim:
        for c in costings:
            c['hc_prev_invoiced'] = 0
            c['hc_this_claim_invoices'] = 0
            allocs = Invoice_allocations.objects.filter(item=c['costing_pk'])
            for al in allocs:
                inv = Invoices.objects.get(invoice_pk=al.invoice_pk.pk)
                if inv.associated_hc_claim and inv.associated_hc_claim.pk == current_hc_claim.pk:
                    c['hc_this_claim_invoices'] += al.amount
                elif inv.associated_hc_claim and inv.associated_hc_claim.pk < current_hc_claim.pk:
                    c['hc_prev_invoiced'] += al.amount
    else:
        for c in costings:
            c['hc_prev_invoiced'] = 0
            c['hc_this_claim_invoices'] = 0
    for c in costings:
        c['hc_prev_fixedonsite'] = 0
        allocs = HC_claim_allocations.objects.filter(item=c['costing_pk'])
        for al in allocs:
            hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
            if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
                c['hc_prev_fixedonsite'] += al.fixed_on_site
    for c in costings:
        c['hc_prev_claimed'] = 0
        allocs = HC_claim_allocations.objects.filter(item=c['costing_pk'])
        for al in allocs:
            hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
            if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
                c['hc_prev_claimed'] += al.hc_claimed
    for c in costings:
        c['qs_claimed'] = 0
        allocs = HC_claim_allocations.objects.filter(item=c['costing_pk'])
        for al in allocs:
            hcc = HC_claims.objects.get(hc_claim_pk=al.hc_claim_pk.pk)
            if current_hc_claim and hcc.hc_claim_pk < current_hc_claim.pk:
                c['qs_claimed'] += al.qs_claimed
    for c in costings:
        c['qs_this_claim'] = max(0,min(c['fixed_on_site'],c['contract_budget']-(c['committed']+c['uncommitted']-(c['hc_prev_invoiced']+c['hc_this_claim_invoices']))-c['qs_claimed']))
    spv_data = SPVData.objects.first()
    distinct_contacts_quotes = Quotes.objects.values_list("contact_pk", flat=True).distinct()
    progress_claim_quote_allocations = []
    for cid in distinct_contacts_quotes:
        qs_for_c = Quotes.objects.filter(contact_pk=cid)
        c_entry = {"contact_pk": cid,"quotes": []}
        for q in qs_for_c:
            q_allocs = Quote_allocations.objects.filter(quotes_pk=q)
            alloc_list = []
            for qa in q_allocs:
                alloc_list.append({"item_pk": qa.item.pk,"item_name": qa.item.item,"amount": str(qa.amount)})
            c_entry["quotes"].append({"quote_number": q.quotes_pk,"allocations": alloc_list})
        progress_claim_quote_allocations.append(c_entry)
    distinct_contacts_invoices = Invoices.objects.exclude(invoice_status=0).values_list("contact_pk",flat=True).distinct()
    progress_claim_invoice_allocations = []
    for cid in distinct_contacts_invoices:
        invs_for_c = Invoices.objects.filter(contact_pk=cid).exclude(invoice_status=0).order_by("invoice_date")
        c_entry = {"contact_pk": cid,"invoices": []}
        for inv in invs_for_c:
            i_allocs = Invoice_allocations.objects.filter(invoice_pk=inv)
            alloc_list = []
            for ia in i_allocs:
                allocation_type_str = "progress_claim" if inv.invoice_type == 2 and ia.allocation_type == 0 else "direct_cost"
                alloc_list.append({"item_pk": ia.item.pk,"item_name": ia.item.item,"amount": str(ia.amount),"invoice_allocation_type": allocation_type_str})
            c_entry["invoices"].append({"invoice_number": inv.invoice_pk,"allocations": alloc_list})
        progress_claim_invoice_allocations.append(c_entry)
    claim_category_totals = (HC_claim_allocations.objects.filter(category__division=division)
        .values('hc_claim_pk', 'hc_claim_pk__display_id', 'category__categories_pk', 'category__category')
        .annotate(
            total_hc_claimed=Sum('hc_claimed'),
            total_qs_claimed=Sum('qs_claimed')
        ).order_by('hc_claim_pk', 'category__order_in_list'))
    contract_budget_totals = (Costing.objects.filter(category__division=division)
        .values('category__categories_pk', 'category__category')
        .annotate(total_contract_budget=Sum('contract_budget'))
        .order_by('category__order_in_list'))
    claim_category_totals_dict = {}
    claim_category_totals_dict[0] = {
        "display_id": "Contract Budget",
        "categories": [{
            "categories_pk": i['category__categories_pk'],
            "category": i['category__category'],
            "total_hc_claimed": float(i['total_contract_budget']) if i['total_contract_budget'] else 0.0,
            "total_qs_claimed": 0.0
        } for i in contract_budget_totals]
    }
    for i in claim_category_totals:
        pk = i['hc_claim_pk']
        if pk not in claim_category_totals_dict:
            claim_category_totals_dict[pk] = {
                "display_id": i['hc_claim_pk__display_id'],
                "categories": []
            }
        claim_category_totals_dict[pk]["categories"].append({
            "categories_pk": i['category__categories_pk'],
            "category": i['category__category'],
            "total_hc_claimed": float(i['total_hc_claimed']) if i['total_hc_claimed'] else 0.0,
            "total_qs_claimed": float(i['total_qs_claimed']) if i['total_qs_claimed'] else 0.0
        })
    claim_category_totals_list = [{'hc_claim_pk': k, **v} for k, v in claim_category_totals_dict.items()]
    print("\nClaim Category Totals List:", claim_category_totals_list, "\n")
    claim_category_totals_json = json.dumps(claim_category_totals_list)
    
    # Build base_table_dropdowns
    base_table_dropdowns = {}
    
    # Get all costing PKs
    costing_pks = Costing.objects.filter(category__division=division).values_list('costing_pk', flat=True)
    
    for costing_pk in costing_pks:
        base_table_dropdowns[costing_pk] = {
            "committed": {},
            "invoiced_direct": {},
            "invoiced_all": {}
        }
        
        # Get committed data (from Quote_allocations)
        quote_allocations = Quote_allocations.objects.filter(
            item_id=costing_pk
        ).select_related('quotes_pk__contact_pk')
        
        if quote_allocations.exists():
            base_table_dropdowns[costing_pk]["committed"] = [
                {
                    "supplier": qa.quotes_pk.contact_pk.contact_name,
                    "quote_num": qa.quotes_pk.supplier_quote_number,
                    "amount": float(qa.amount)
                } for qa in quote_allocations
            ]
        
        # Get invoiced_direct data
        invoice_directs = Invoice_allocations.objects.filter(
            item_id=costing_pk,
            invoice_pk__invoice_division=division
        ).filter(
            Q(allocation_type=1) | 
            Q(allocation_type=0, invoice_pk__invoice_type=1)
        ).select_related('invoice_pk__contact_pk').order_by('invoice_pk__invoice_date')
        
        base_table_dropdowns[costing_pk]["invoiced_direct"] = [{
            "supplier": invoice.invoice_pk.contact_pk.contact_name,
            "date": invoice.invoice_pk.invoice_date.strftime('%d/%m/%Y'),
            "invoice_num": invoice.invoice_pk.supplier_invoice_number,
            "amount": float(invoice.amount)
        } for invoice in invoice_directs]
        
        # Get invoiced_all data
        invoice_alls = Invoice_allocations.objects.filter(
            item_id=costing_pk,
            invoice_pk__invoice_division=division
        ).select_related('invoice_pk__contact_pk').order_by('invoice_pk__invoice_date')
        
        base_table_dropdowns[costing_pk]["invoiced_all"] = [{
            "supplier": invoice.invoice_pk.contact_pk.contact_name,
            "date": invoice.invoice_pk.invoice_date.strftime('%d/%m/%Y'),
            "invoice_num": invoice.invoice_pk.supplier_invoice_number,
            "amount": float(invoice.amount)
        } for invoice in invoice_alls]
    
    print("\nbase_table_dropdowns:", json.dumps(base_table_dropdowns, indent=2), "\n")
    
    context = {
        "division": division,
        "costings": costings,
        "contacts_in_quotes": contacts_in_quotes_list,
        "contacts_not_in_quotes": contacts_not_in_quotes_list,
        "contacts": contacts_list,
        "contacts_unfiltered": contacts_unfiltered_list,
        "committed_values": committed_values,
        "items": items,
        "hc_claim_wip_adjustments": hc_claim_wip_adjustments,
        "committed_quotes": committed_quotes_json,
        "quote_allocations": quote_allocations_json,
        "current_page": "build" if division == 2 else "quotes",
        "project_name": settings.PROJECT_NAME,
        "is_homepage": division == 1,
        "totals": {
            "total_contract_budget": total_contract_budget,
            "total_forecast_budget": total_forecast_budget,
            "total_uncommitted": total_uncommitted,
            "total_committed": total_committed,
            "total_sc_invoiced": total_sc_invoiced,
            "total_fixed_on_site": total_fixed_on_site,
            "total_sc_paid": total_sc_paid
        },
        "po_globals": po_globals,
        "po_orders": po_orders_list,
        "invoices": invoices_list,
        "invoices_unallocated": invoices_unallocated_list,
        "invoices_allocated": invoices_allocated_list,
        "hc_claims": hc_claims_json,
        "current_hc_claim_display_id": current_hc_claim_display_id,
        "spv_data": spv_data,
        "progress_claim_quote_allocations_json": json.dumps(progress_claim_quote_allocations),
        "progress_claim_invoice_allocations_json": json.dumps(progress_claim_invoice_allocations),
        "claim_category_totals": claim_category_totals_json,
        "base_table_dropdowns_json": json.dumps(base_table_dropdowns).replace('"', '\"')
    }
    return render(request,"homepage.html" if division == 1 else "build.html",context)


def homepage_view(request): #if Contacts.division is 1, Developer
    return main(request, 1)

def build_view(request):  #if Contacts.division is 2, Builder
    return main(request, 2)

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
def create_contacts(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        contacts = data.get('contacts')  # Get the contacts list from the data
        division = data.get('division')  # Get the division from the data
        if contacts:  # Check if contacts is not None
            for contact in contacts:  # Iterate over the contacts
                if contact['name']:  # Only create a contact if a name was provided
                    Contacts.objects.create(contact_name=contact['name'], contact_email=contact['email'], division=division)
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
    letterhead = Letterhead.objects.first()
    if letterhead is not None:
        letterhead_path = letterhead.letterhead_path.name  # Get the file name or path as a string
        if settings.DEBUG:  # Assuming DEBUG=True means local development
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
    col_widths = [2.5 * inch, 3.5 * inch, 1 * inch]  # Adjusted column widths
    x_start = inch / 2
    cell_height = 18
    for i, header in enumerate(table_headers):
        header_x_position = x_start + sum(col_widths[:i]) + 2
        if i == 2:  # Center the 'Amount' column header
            header_x_position = x_start + sum(col_widths[:i]) + col_widths[i] / 2 - p.stringWidth(header, "Helvetica-Bold", 12) / 2
        p.drawString(header_x_position, y_position + 2, header)  # Adjust for padding
        p.line(header_x_position, y_position, header_x_position + p.stringWidth(header, "Helvetica-Bold", 12), y_position)  # Draw underline
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
            p.setStrokeColor(colors.grey, 0.25)  # Set color to grey with 50% transparency
            p.line(x_start, y_position, x_start + sum(col_widths), y_position)  # Draw underline
            p.setStrokeColor(colors.black)  # Set color back to black for subsequent drawing        
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
            p.line(x_start + sum(col_widths[:i+1]) - line_width - 2, y_position, x_start + sum(col_widths[:i+1]) - line_width - 2 + p.stringWidth(cell, "Helvetica-Bold", 12), y_position)  # Draw underline
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
    # Retrieve the Po_orders instance
    po_order = Po_orders.objects.get(po_order_pk=po_order_pk)
    contact_name = po_order.po_supplier.contact_name  # Get the contact name
    subject = 'Purchase Order'
    message = f'''Dear {contact_name},

Please see Purchase Order from Mason attached for the specified works and amount.

Ensure your claim clearly specifies the PO number and the amount being claimed against each claim category as specified in the PO to ensure there are no delays processing your claim.

Best regards,
Brian Hooke.
    '''
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

    # Add CC addresses
    cc_addresses = settings.EMAIL_CC.split(';')
    email.cc = cc_addresses

    # Send the email and update po_sent if successful
    try:
        email.send()
        po_order.po_sent = True  # Update the po_sent field to 1 (True)
        po_order.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

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

@csrf_exempt
def associate_sc_claims_with_hc_claim(request):
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=400)

        logger.info('Processing associate_sc_claims_with_hc_claim request')
        
        # Parse JSON data
        data = json.loads(request.body)
        logger.info(f'Request data: {data}')
        selected_invoices = data.get('selectedInvoices', [])
        logger.info(f'Selected invoices: {selected_invoices}')

        if not selected_invoices:
            logger.warning('No invoices selected')
            return JsonResponse({'error': 'No invoices selected'}, status=400)

        # Check if there are any HC_claims entries
        if HC_claims.objects.exists():
            latest_hc_claim = HC_claims.objects.latest('hc_claim_pk')
            logger.info(f'Latest HC claim status: {latest_hc_claim.status}')
            
            if latest_hc_claim.status == 0:
                logger.warning('Found existing HC claim in progress')
                return JsonResponse({
                    'error': 'There is a HC claim in progress. Complete this claim before starting another.'
                }, status=400)

        # Create a new HC_claims entry
        new_hc_claim = HC_claims.objects.create(date=datetime.now(), status=0)
        logger.info(f'Created new HC claim with pk: {new_hc_claim.hc_claim_pk}')

        # Update the associated_hc_claim for each selected invoice
        update_result = Invoices.objects.filter(invoice_pk__in=selected_invoices).update(associated_hc_claim=new_hc_claim)
        logger.info(f'Updated {update_result} invoices with new HC claim')

        return JsonResponse({
            'latest_hc_claim_pk': new_hc_claim.hc_claim_pk,
            'invoices_updated': update_result
        })

    except Exception as e:
        logger.error(f'Error in associate_sc_claims_with_hc_claim: {str(e)}', exc_info=True)
        return JsonResponse({'error': 'Internal server error occurred'}, status=500)

@csrf_exempt
def update_fixedonsite(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        costing_pk = data.get('costing_pk')
        fixed_on_site = data.get('fixed_on_site')
        # Get the Costing object and update it
        costing = Costing.objects.get(pk=costing_pk)
        costing.fixed_on_site = fixed_on_site
        costing.save()
        # Return a JSON response
        return JsonResponse({'status': 'success'})

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
            Categories.objects.all().delete()
            logger.info('All existing Categories objects deleted')
            for row in reader:
                Categories.objects.create(
                    category=row['category'],
                    division=row['division'],
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

@csrf_exempt
def upload_costings(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        csv_reader = csv.DictReader(csv_file.read().decode('utf-8').splitlines())
        try:
            for row in csv_reader:
                logger.debug(f"Processing row: {row}")
                category_name = row['category']
                category, created = Categories.objects.get_or_create(category=category_name)
                logger.debug(f"Category: {category}, Created: {created}")
                Costing.objects.update_or_create(
                    category=category,
                    item=row['item'],
                    defaults={
                        'xero_account_code': row.get('xero_account_code', ''),  # Set default to empty string
                        'contract_budget': Decimal(row.get('contract_budget', '0.00')),  # Set default to 0.00
                        'uncommitted': Decimal(row.get('uncommitted', '0.00')),  # Set default to 0.00
                        'sc_invoiced': Decimal(row.get('sc_invoiced', '0.00')),  # Set default to 0.00
                        'sc_paid': Decimal(row.get('sc_paid', '0.00')),  # Set default to 0.00
                        'fixed_on_site': Decimal(row.get('fixed_on_site', '0.00')),  # Set default to 0.00
                    }
                )
                logger.debug(f"Updated or created Costing for item: {row['item']}")
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})

@csrf_exempt
def update_contract_budget_amounts(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        skipped_rows = []
        updated_rows = []
        try:
            # Read the CSV file
            decoded_file = csv_file.read().decode('utf-8-sig').splitlines()  # utf-8-sig to handle BOM
            csv_reader = csv.DictReader(decoded_file)
            logger.info("Starting to process CSV file for contract budget updates")
            logger.info(f"CSV Headers: {csv_reader.fieldnames}")

            # Process each row in the CSV
            row_count = 0
            for row in csv_reader:
                row_count += 1
                try:
                    # Only strip whitespace from contract_budget, preserve spaces in category and item
                    if row.get('contract_budget'):
                        row['contract_budget'] = row['contract_budget'].strip()
                    logger.info(f"Processing row {row_count}: {row}")

                    # First find the category by its name
                    category = Categories.objects.get(category=row['category'])
                    logger.info(f"Found category: {category.category} (pk={category.categories_pk})")
                    
                    # Then find the costing entry that matches both category and item
                    try:
                        costing = Costing.objects.get(
                            category=category,
                            item=row['item']
                        )
                        logger.info(f"Found costing: {costing.item} (pk={costing.costing_pk})")
                        
                        # Update the contract_budget
                        old_budget = costing.contract_budget
                        try:
                            # Remove any currency symbols and commas
                            budget_str = row['contract_budget'].replace('$', '').replace(',', '')
                            new_budget = Decimal(budget_str)
                            
                            # Only update if the value has changed
                            if new_budget != old_budget:
                                costing.contract_budget = new_budget
                                costing.save()
                                logger.info(f"Updated contract_budget for {row['category']} - {row['item']} from {old_budget} to {new_budget}")
                                
                                updated_rows.append({
                                    'category': row['category'],
                                    'item': row['item'],
                                    'old_budget': str(old_budget),
                                    'new_budget': str(new_budget)
                                })
                            else:
                                logger.info(f"Skipping update for {row['category']} - {row['item']} as budget hasn't changed ({old_budget})")
                                
                        except (ValueError, InvalidOperation) as e:
                            logger.error(f"Invalid budget value '{row['contract_budget']}' for {row['category']} - {row['item']}: {str(e)}")
                            skipped_rows.append({
                                'category': row['category'],
                                'item': row['item'],
                                'reason': f'Invalid budget value: {row["contract_budget"]}'
                            })
                            continue
                            
                    except Costing.DoesNotExist:
                        logger.warning(f"No costing found for category: {row['category']}, item: {row['item']}")
                        skipped_rows.append({
                            'category': row['category'],
                            'item': row['item'],
                            'reason': 'No matching costing entry found'
                        })
                        continue
                        
                except Categories.DoesNotExist:
                    logger.warning(f"Category not found: {row['category']}")
                    skipped_rows.append({
                        'category': row['category'],
                        'item': row['item'],
                        'reason': f'Category not found: {row["category"]}'
                    })
                    continue
                except Exception as e:
                    logger.error(f"Error processing row: {row}. Error: {str(e)}")
                    skipped_rows.append({
                        'category': row['category'],
                        'item': row['item'],
                        'reason': f'Error: {str(e)}'
                    })
                    continue

            response_data = {
                'message': 'File processed successfully',
                'updated': len(updated_rows),
                'skipped': len(skipped_rows),
                'updated_rows': updated_rows,
                'skipped_rows': skipped_rows
            }
            
            logger.info(f"Completed processing CSV file. Updated: {len(updated_rows)}, Skipped: {len(skipped_rows)}")
            if updated_rows:
                logger.info("Updated rows:")
                for row in updated_rows:
                    logger.info(f"  {row['category']} - {row['item']}: {row['old_budget']} -> {row['new_budget']}")
            if skipped_rows:
                logger.info("Skipped rows:")
                for row in skipped_rows:
                    logger.info(f"  {row['category']} - {row['item']}: {row['reason']}")
            
            # If we skipped any rows, return a 206 Partial Content status
            status_code = 206 if skipped_rows else 200
            return JsonResponse(response_data, status=status_code)
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return JsonResponse({
                'error': f'Error processing file: {str(e)}',
                'updated_rows': updated_rows,
                'skipped_rows': skipped_rows
            }, status=400)
            
    return JsonResponse({'error': 'No file uploaded'}, status=400)

@csrf_exempt
def upload_letterhead(request):
    if request.method == 'POST':
        file = request.FILES['letterhead_path']
        file.name = 'letterhead.pdf'  # Set the filename
        # Save the file to S3
        file_path = default_storage.save(file.name, file)
        # Create a new letterhead with the uploaded file
        letterhead = Letterhead(letterhead_path=file_path)
        letterhead.save()
        # Delete all existing letterheads except the new one
        Letterhead.objects.exclude(id=letterhead.id).delete()
        return JsonResponse({'message': 'File uploaded successfully'})
    else:
        return JsonResponse({'error': 'Invalid request method'})

@csrf_exempt
def upload_invoice(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        invoice_number = request.POST.get('invoice_number')
        invoice_total = request.POST.get('invoice_total')
        invoice_total_gst = request.POST.get('invoice_total_gst') # Get the GST total value
        invoice_date = request.POST.get('invoice_date')
        invoice_due_date = request.POST.get('invoice_due_date')
        invoice_division = request.POST.get('invoiceDivision') # Get the invoice division
        pdf_file = request.FILES.get('pdf')
        try:
            contact = Contacts.objects.get(pk=supplier_id)
            invoice = Invoices(
                supplier_invoice_number=invoice_number,
                total_net=invoice_total,
                total_gst=invoice_total_gst, # Set the GST total value
                invoice_status=0, # Set the invoice status to 0
                invoice_date=invoice_date,
                invoice_due_date=invoice_due_date,
                invoice_division=invoice_division, # Set the invoice division
                pdf=pdf_file,
                contact_pk=contact
            )
            invoice.save()
            return JsonResponse({'success': True})
        except Contacts.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Supplier not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def upload_invoice_allocations(request):
    if request.method == 'POST':
        invoice_pk = request.POST.get('invoice_pk')
        allocations = json.loads(request.POST.get('allocations'))
        try:
            invoice = Invoices.objects.get(pk=invoice_pk)
            for allocation in allocations:
                item_id = allocation.get('item')
                if item_id:
                    item = Costing.objects.get(pk=item_id)
                    amount = Decimal(str(allocation.get('thisInvoice', 0)))  # Convert to Decimal
                    gst_amount = Decimal(str(allocation.get('gst_amount', 0)))  # Extract and convert gst_amount to Decimal
                    uncommitted = Decimal(str(allocation.get('uncommitted', 0)))  # Extract and convert to Decimal
                    notes = allocation.get('notes', '')

                    # Create Invoice Allocation
                    Invoice_allocations.objects.create(
                        invoice_pk=invoice,
                        item=item,
                        amount=amount,
                        gst_amount=gst_amount,  # Add gst_amount to the allocation
                        notes=notes
                    )

                    # Update uncommitted field in Costing model
                    item.uncommitted = uncommitted  # Set uncommitted field to the provided value
                    item.save()

            # Set invoice status to 1 after successful upload of allocations
            invoice.invoice_status = 1
            invoice.save()
            return JsonResponse({'success': True})
        except Invoices.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invoice not found'})
        except Costing.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Costing item not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

# add checkbox to contacts
@csrf_exempt
def update_contacts(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        for contact in data:
            try:
                contact_obj = Contacts.objects.get(contact_pk=contact['contact_pk'])
                contact_obj.checked = contact['checked']
                contact_obj.contact_email = contact['contact_email']
                contact_obj.save()
            except Contacts.DoesNotExist:
                return JsonResponse({'error': 'Contact with pk {} does not exist'.format(contact['contact_pk'])}, status=400)
        return JsonResponse({'message': 'Contacts updated successfully'})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)

# Xero Integration
def xeroapi(request):
  template = loader.get_template('homepage.html')
  return HttpResponse(template.render())
# Define rate limits for Xero API calls
@limits(calls=60, period=60)  # 60 calls per minute
@sleep_and_retry

def make_api_request(url, headers):
    response = requests.get(url, headers=headers)
    return response

client_id = settings.XERO_CLIENT_ID
client_id = settings.XERO_CLIENT_ID
client_secret = settings.XERO_CLIENT_SECRET
client_project = settings.XERO_PROJECT_ID

def get_xero_token(request, division):
    # Convert division to int if it's a string
    division = int(division) if isinstance(division, str) else division
    
    scopes_list = [
        "accounting.transactions",
        "accounting.transactions.read",
        "accounting.reports.read",
        "accounting.reports.tenninetynine.read",
        "accounting.budgets.read",
        "accounting.journals.read",
        "accounting.settings",
        "accounting.settings.read",
        "accounting.contacts",
        "accounting.contacts.read",
        "accounting.attachments",
        "accounting.attachments.read",
        "files",
        "files.read"
    ]
    scopes = ' '.join(scopes_list)  # Convert list to space-separated string
    # Set the client_id and client_secret based on the division
    if division == 1:
        client_id = settings.MDG_XERO_CLIENT_ID
        client_secret = settings.MDG_XERO_CLIENT_SECRET
    elif division == 2:
        client_id = settings.MB_XERO_CLIENT_ID
        client_secret = settings.MB_XERO_CLIENT_SECRET
    else:
        raise ValueError(f"Invalid division: {division}")

    # Prepare the header
    credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    # Prepare the body
    data = {
        'grant_type': 'client_credentials',
        'scope': scopes
    }
    # Make the POST request
    response = requests.post('https://identity.xero.com/connect/token', headers=headers, data=data)
    response_data = response.json()
    
    # Log the response for debugging
    logger.info(f"Xero token response: {response.status_code}")
    logger.info(f"Xero token response data: {response_data}")
    
    if response.status_code != 200:
        raise ValueError(f"Failed to get Xero token: {response_data}")
    
    if 'access_token' not in response_data:
        raise ValueError(f"No access token in response: {response_data}")
    
    # Store the access token in a session variable
    request.session['access_token'] = response_data['access_token']
    return JsonResponse(response_data)

@csrf_exempt
def get_xero_contacts(request):
    division = int(request.GET.get('division', 0))  # Default to 0 if division is not provided
    get_xero_token(request, division)
    access_token = request.session.get('access_token')
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json'
    }
    response = requests.get('https://api.xero.com/api.xro/2.0/Contacts', headers=headers)
    data = response.json()
    contacts = data['Contacts']
    for contact in contacts:
        xero_contact_id = contact['ContactID']
        contact_name = contact.get('Name', 'Not Set')
        contact_email = 'Not Set'
        existing_contact = Contacts.objects.filter(xero_contact_id=xero_contact_id).first()
        if existing_contact:
            if existing_contact.division != division:
                existing_contact.division = division
                existing_contact.save()
        else:
            new_contact = Contacts(
                xero_contact_id=xero_contact_id,
                division=division,
                contact_name=contact_name,
                contact_email=contact_email
            )
            new_contact.save()
    return JsonResponse(data)

@csrf_exempt
def post_invoice(request):
    logger.info('Starting post_invoice function')
    body = json.loads(request.body)
    invoice_pk = body.get('invoice_pk')
    division = int(body.get('division', 0))  # Default to 0 if division is not provided
    logger.info(f'Division: {division}')
    logger.info(f'Invoice PK: {invoice_pk}')
    invoice = Invoices.objects.get(pk=invoice_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    invoice_allocations = Invoice_allocations.objects.filter(invoice_pk_id=invoice_pk)
    line_items = []
    for invoice_allocation in invoice_allocations:
        costing = Costing.objects.get(pk=invoice_allocation.item_id)
        line_item = {
            "Description": invoice_allocation.notes,
            "Quantity": 1,
            "UnitAmount": str(invoice_allocation.amount),
            "AccountCode": costing.xero_account_code,
            "TaxType": "INPUT",
            "TaxAmount": str(invoice_allocation.gst_amount),
        }
        line_items.append(line_item)
    get_xero_token(request, division)
    access_token = request.session.get('access_token')
    logger.info(f'Access Token: {access_token}')
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "Type": "ACCPAY",
        "Contact": {"ContactID": Contacts.objects.first().xero_contact_id},
        "Date": invoice.invoice_date.isoformat(),
        "DueDate": invoice.invoice_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_invoice_number,
        "Url": request.build_absolute_uri(invoice.pdf.url),  # Generate absolute URL
        "LineItems": line_items
    }
    logger.info('Sending request to Xero API')
    logger.info('Data: %s', json.dumps(data))  # Log the data
    response = requests.post('https://api.xero.com/api.xro/2.0/Invoices', headers=headers, data=json.dumps(data))
    try:
        response_data = response.json()
    except json.JSONDecodeError:
        logger.error('Empty response from Xero API')
        return JsonResponse({'status': 'error', 'message': 'Empty response from Xero API'})
    if 'Status' in response_data and response_data['Status'] == 'OK':
        invoice_id = response_data['Invoices'][0]['InvoiceID']
        logger.info(f'Invoice created with ID: {invoice_id}')
        invoice.invoice_status = 2
        invoice.invoice_xero_id = invoice_id
        invoice.save()
        file_url = invoice.pdf.url
        file_name = file_url.split('/')[-1]
        urlretrieve(file_url, file_name)
        with open(file_name, 'rb') as f:
            file_data = f.read()
        headers['Content-Type'] = 'application/octet-stream'
        logger.info('Sending request to attach file to invoice')
        response = requests.post(f'https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}', headers=headers, data=file_data)
        if response.status_code == 200:
            logger.info('File attached successfully')
            return JsonResponse({'status': 'success', 'message': 'Invoice and attachment created successfully.'})
        else:
            logger.error('Failed to attach file to invoice')
            return JsonResponse({'status': 'error', 'message': 'Invoice created but attachment failed to upload.'})
    else:
        logger.error('Unexpected response from Xero API: %s', response_data)
        return JsonResponse({'status': 'error', 'message': 'Unexpected response from Xero API', 'response_data': response_data})

@csrf_exempt
def test_xero_invoice(request):
    logger.info('Starting post_invoice function')
    body = json.loads(request.body)
    invoice_pk = body.get('invoice_pk')
    logger.info(f'Invoice PK: {invoice_pk}')
    invoice = Invoices.objects.get(pk=invoice_pk)
    contact = Contacts.objects.get(pk=invoice.contact_pk_id)
    invoice_allocations = Invoice_allocations.objects.filter(invoice_pk_id=invoice_pk)
    line_items = []
    for invoice_allocation in invoice_allocations:
        costing = Costing.objects.get(pk=invoice_allocation.item_id)
        line_item = {
            "Description": invoice_allocation.notes,
            "Quantity": 1,
            "UnitAmount": str(invoice_allocation.amount),
            "AccountCode": costing.xero_account_code,
            "TaxType": "INPUT",
            "TaxAmount": str(invoice_allocation.gst_amount),
        }
        line_items.append(line_item)
    get_xero_token(request)
    access_token = request.session.get('access_token')
    headers = {
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "Type": "ACCPAY",
        "Contact": {"ContactID": Contacts.objects.first().xero_contact_id},
        # "Contact": {
        #     "ContactID": "54134e47-8357-448c-8e4b-7472f6beb963"
        # },
        "Date": invoice.invoice_date.isoformat(),
        "DueDate": invoice.invoice_due_date.isoformat(),
        "InvoiceNumber": invoice.supplier_invoice_number,
        "Url": "https://precastappbucket.s3.amazonaws.com/drawings/P071.pdf",
        # "Url": request.build_absolute_uri(invoice.pdf.url),  # Generate absolute URL
        "LineItems": line_items
    }
    logger.info('Sending request to Xero API')
    logger.info('Data: %s', json.dumps(data))  # Log the data
    response = requests.post('https://api.xero.com/api.xro/2.0/Invoices', headers=headers, data=json.dumps(data))
    response_data = response.json()
    if 'Status' in response_data and response_data['Status'] == 'OK':
        invoice_id = response_data['Invoices'][0]['InvoiceID']
        logger.info(f'Invoice created with ID: {invoice_id}')
        # file_url = invoice.pdf.url
        file_url = 'https://precastappbucket.s3.amazonaws.com/drawings/P071.pdf'
        file_name = file_url.split('/')[-1]
        urlretrieve(file_url, file_name)
        with open(file_name, 'rb') as f:
            file_data = f.read()
        headers['Content-Type'] = 'application/octet-stream'
        logger.info('Sending request to attach file to invoice')
        response = requests.post(f'https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{file_name}', headers=headers, data=file_data)
        if response.status_code == 200:
            logger.info('File attached successfully')
            return JsonResponse({'status': 'success', 'message': 'Invoice and attachment created successfully.'})
        else:
            logger.error('Failed to attach file to invoice')
            return JsonResponse({'status': 'error', 'message': 'Invoice created but attachment failed to upload.'})
    else:
        logger.error('Unexpected response from Xero API: %s', response_data)
        return JsonResponse({'status': 'error', 'message': 'Unexpected response from Xero API', 'response_data': response_data})

@csrf_exempt
def mark_sent_to_boutique(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
            invoice.invoice_status = 4
            invoice.save()
            return JsonResponse({"status": "success", "message": f"Invoice {invoice_pk} marked as sent to boutique."}, status=200)
        except Invoices.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invoice does not exist."}, status=400)
    else:
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=400)

@csrf_exempt
def test_contact_id(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        invoice_pk = data.get('invoice_pk')
        try:
            invoice = Invoices.objects.get(invoice_pk=invoice_pk)
        except Invoices.DoesNotExist:
            return JsonResponse({"error": "No invoice found with the provided invoice_pk."}, status=400)
        contact = invoice.contact_pk
        return JsonResponse({'contact_id': contact.xero_contact_id})

@csrf_exempt
def update_hc_claim_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            current_hc_claim_display_id = data.get('current_hc_claim_display_id', '0')
            hc_claim = HC_claims.objects.get(status=0)  # There will only be one entry with status=0
            for entry in data.get('hc_claim_data', []):
                category = Categories.objects.get(category=entry['category'])
                item = Costing.objects.get(costing_pk=entry['item_id'])
                obj, created = HC_claim_allocations.objects.update_or_create(
                    hc_claim_pk=hc_claim,
                    category=category,
                    item=item,
                    defaults={
                        'contract_budget': entry['contract_budget'],
                        'working_budget': entry['working_budget'],
                        'uncommitted': entry['uncommitted'],
                        'committed': entry['committed'],
                        'fixed_on_site': entry['fixed_on_site_current'],
                        'fixed_on_site_previous': entry['fixed_on_site_previous'],
                        'fixed_on_site_this': entry['fixed_on_site_this'],
                        'sc_invoiced': entry['sc_invoiced'],
                        'sc_invoiced_previous': entry['sc_invoiced_previous'],
                        'adjustment': entry['adjustment'],
                        'hc_claimed': entry['hc_claimed'],
                        'hc_claimed_previous': entry['hc_claimed_previous'],
                        'qs_claimed': entry['qs_claimed'],
                        'qs_claimed_previous': entry['qs_claimed_previous'],
                    }
                )
            if current_hc_claim_display_id != '0':
                hc_claim_to_update = HC_claims.objects.get(display_id=current_hc_claim_display_id)
                hc_claim_to_update.status = 1  # Set status to 1 for approved
                hc_claim_to_update.save()
            return JsonResponse({'status': 'success', 'message': 'Data saved successfully!'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f"Unexpected error: {str(e)}"}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

def get_claim_table(request, claim_id):
    claim_id = request.GET.get('claim_id')  # Retrieve claim_id from query parameters
    if not claim_id:
        return HttpResponseBadRequest("Missing claim_id")

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

def get_invoices_by_supplier(request):
    supplier_name = request.GET.get('supplier', '')

    contact = Contacts.objects.filter(contact_name=supplier_name).first()

    if not contact:
        return JsonResponse({"error": "Supplier not found"}, status=404)

    invoices = Invoices.objects.filter(contact_pk=contact, invoice_status=2).prefetch_related(
        Prefetch('invoice_allocations_set', queryset=Invoice_allocations.objects.all(), to_attr='fetched_allocations')
    )

    if not invoices.exists():  # Handle no invoices
        return JsonResponse({"message": "No invoices found for this supplier with status=2"}, safe=False)

    invoices_data = []
    for invoice in invoices:
        invoice_info = {
            "invoice_pk": invoice.invoice_pk,
            "supplier_invoice_number": invoice.supplier_invoice_number,  # Correct field name
            "total_net": str(invoice.total_net),  # Correct field name
            "total_gst": str(invoice.total_gst),  # Correct field name
            "invoice_date": invoice.invoice_date.strftime("%Y-%m-%d"),  # Format date for JSON
            "invoice_due_date": invoice.invoice_due_date.strftime("%Y-%m-%d"),  # Format date for JSON
            "invoice_allocations": [
                {
                    "invoice_allocations_pk": allocation.invoice_allocations_pk,
                    "item": allocation.item.item,  # Assuming 'item' is a ForeignKey to Costing model
                    "amount": str(allocation.amount),
                    "gst_amount": str(allocation.gst_amount),
                    "notes": allocation.notes or ""
                } for allocation in invoice.fetched_allocations  # Use the prefetch_related attribute
            ]
        }
        invoices_data.append(invoice_info)

    return JsonResponse(invoices_data, safe=False)


@csrf_exempt
def post_progress_claim_data(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        invoice_id = data.get("invoice_id")
        allocations = data.get("allocations", [])
        if not invoice_id:
            return JsonResponse({"error": "No invoice_id provided"}, status=400)
        if not allocations:
            return JsonResponse({"error": "No allocations provided"}, status=400)
        new_allocations = []  # Initialize the list
        # Wrap all database operations in a transaction
        with transaction.atomic():
            invoice = Invoices.objects.get(pk=invoice_id)
            invoice.invoice_status = 1  # allocated
            invoice.invoice_type = 2    # progress claim
            invoice.save()
            for alloc in allocations:
                item_pk = alloc.get("item_pk")
                net = alloc.get("net", 0)
                gst = alloc.get("gst", 0)
                allocation_type = alloc.get("allocation_type", 0)
                if not item_pk:
                    raise ValueError("Missing item_pk in allocation")
                try:
                    costing_obj = Costing.objects.get(pk=item_pk)
                except Costing.DoesNotExist:
                    raise ValueError(f"Costing object not found for pk: {item_pk}")
                new_alloc = Invoice_allocations.objects.create(
                    invoice_pk=invoice,
                    item=costing_obj,
                    amount=net,
                    gst_amount=gst,
                    notes="",
                    allocation_type=allocation_type
                )
                new_allocations.append(new_alloc.invoice_allocations_pk)
        return JsonResponse({
            "success": True,
            "message": "Progress claim data posted successfully",
            "updated_invoice": invoice.invoice_pk,
            "created_allocations": new_allocations
        }, status=200)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Invoices.DoesNotExist:
        return JsonResponse({"error": f"Invoice not found with id: {invoice_id}"}, status=404)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

@csrf_exempt
def post_direct_cost_data(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST allowed"}, status=405)
    try:
        data = json.loads(request.body.decode('utf-8'))
        invoice_id = data.get("invoice_id")
        allocations = data.get("allocations", [])

        if not invoice_id:
            return JsonResponse({"error": "No invoice_id provided"}, status=400)

        invoice = Invoices.objects.get(pk=invoice_id)

        invoice.invoice_status = 1
        invoice.invoice_type = 1  # Direct Cost
        invoice.save()

        new_allocations = []
        for alloc in allocations:
            item_pk = alloc.get("item_pk")
            net = alloc.get("net", 0)
            gst = alloc.get("gst", 0)
            notes = alloc.get("notes", "")
            uncommitted_new = alloc.get("uncommitted_new")  # optional new field if you want to store it

            if not item_pk:
                continue

            costing_obj = Costing.objects.get(pk=item_pk)

            if uncommitted_new is not None:
                costing_obj.uncommitted = uncommitted_new
                costing_obj.save()

            new_alloc = Invoice_allocations.objects.create(
                invoice_pk=invoice,
                item=costing_obj,
                amount=net,
                gst_amount=gst,
                notes=notes,
                allocation_type=0  # or 1 if you prefer 'direct cost in progress claim'—depends on your usage
            )
            new_allocations.append(new_alloc.invoice_allocations_pk)

        return JsonResponse({
            "message": "Direct cost data posted successfully",
            "updated_invoice": invoice.invoice_pk,
            "created_allocations": new_allocations
        }, status=200)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def send_hc_claim_to_xero(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    try:
        data = json.loads(request.body)
        hc_claim_pk = data.get('hc_claim_pk')
        xero_contact_id = data.get('xero_contact_id')
        contact_name = data.get('contact_name')
        categories = data.get('categories', [])
        if not all([hc_claim_pk, xero_contact_id, contact_name]):
            return JsonResponse({'success': False, 'error': 'Missing required data'})
        hc_claim = HC_claims.objects.get(pk=hc_claim_pk)
        get_xero_token(request, 2)  # Ignoring the returned JsonResponse
        access_token = request.session.get('access_token')
        if not access_token:
            return JsonResponse({'success': False, 'error': 'No access token found in session'})
        url = 'https://api.xero.com/api.xro/2.0/Invoices'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        project_id = settings.XERO_PROJECT_ID
        logger.info(f"Retrieving project with XERO_PROJECT_ID: {project_id}")
        try:
            project = Projects.objects.get(xero_project_id=project_id)
            logger.info(f"Retrieved project: {project.__dict__}")
        except Projects.DoesNotExist:
            logger.error(f"No project found with xero_project_id: {project_id}")
            return JsonResponse({"error": "Project not found"}, status=404)
        except Exception as e:
            logger.error(f"Error retrieving project: {str(e)}")
            return JsonResponse({"error": f"Error retrieving project: {str(e)}"}, status=500)
        sales_account = project.xero_sales_account
        if not sales_account:
            return JsonResponse({'success': False, 'error': 'Sales account not configured'})
        line_items = []
        for cat_data in categories:
            cat_obj = Categories.objects.get(categories_pk=cat_data['categories_pk'])
            amount = Decimal(str(cat_data['amount']))
            line_items.append({
                "Description": cat_obj.category,
                "Quantity": "1.0",
                "UnitAmount": str(amount),
                "AccountCode": sales_account,
                "TaxType": "OUTPUT",
                "TaxAmount": str(amount * Decimal('0.1')),
                "Tracking": [
                    {
                        "Name": "Project",
                        "Option": project.project
                    }
                ]
            })
        invoice_data = {
            "Type": "ACCREC",
            "Contact": {"ContactID": xero_contact_id},
            "LineItems": line_items,
            "Date": hc_claim.date.strftime("%Y-%m-%d"),
            "DueDate": (hc_claim.date + timedelta(days=30)).strftime("%Y-%m-%d"),
            "Status": "DRAFT"
        }
        response = requests.post(url, headers=headers, json=invoice_data)
        response_data = response.json()
        logger.info(f"Xero response code: {response.status_code}")
        logger.info(f"Xero response JSON: {response_data}")
        if response.status_code == 200 and response_data.get('Status') == 'OK':
            invoice_id = response_data['Invoices'][0]['InvoiceID']
            hc_claim.status = 2
            hc_claim.invoicee = contact_name
            hc_claim.save()
            return JsonResponse({'success': True, 'invoice_id': invoice_id})
        else:
            return JsonResponse({
                'success': False,
                'error': f"Xero API error: {response_data.get('ErrorNumber', 'Unknown error')} - {response_data}"
            })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
