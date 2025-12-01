"""
Dashboard app views.

Response Helpers:
- error_response(message, status) - Standardized error JSON response
- success_response(message, data) - Standardized success JSON response

Dashboard View:
1. dashboard_view - Main dashboard homepage

Contacts Views:
2. verify_contact_details - Save verified contact details to separate verified fields
   Uses validators from dashboard.validators for email, BSB, account, ABN validation
3. pull_xero_contacts - Pull contacts from Xero API, insert/update locally
   Uses loop-based field comparison for efficient updates
4. get_contacts_by_instance - Get ACTIVE contacts with verified status (0/1/2)
   Uses Contact.verified_status model property
5. create_contact - Create contact in Xero + local DB
6. update_contact_details - Update bank details, email, ABN in Xero
7. update_contact_status - Archive/unarchive contact in Xero

Bills Views:
8. send_bill - Send invoice to Xero (Direct mode) or move to Direct (Inbox mode)

Dependencies:
- Validators: dashboard.validators (validate_email, validate_bsb, validate_account_number, validate_abn)
- Xero helpers: core.views.xero (get_xero_auth, format_bank_details, parse_xero_validation_errors)
- Decorator: @handle_xero_request_errors for Xero API exception handling
- Model property: Contact.verified_status for verification status calculation
"""

import json
import logging
import requests
import csv
import uuid
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.exceptions import ValidationError
from core.models import Contacts, SPVData, XeroInstances, Invoices, Projects, Invoice_allocations, Categories, Costing, Quotes, Quote_allocations, Po_orders, Po_order_detail, Units
from decimal import Decimal
from datetime import date
from io import StringIO, TextIOWrapper, BytesIO
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from xhtml2pdf import pisa
try:
    from PyPDF2 import PdfMerger, PdfReader
except ImportError:
    from pypdf import PdfMerger, PdfReader
# Import helpers from core.views.xero
from core.views.xero import get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors
# Import validators
from .validators import validate_email, validate_bsb, validate_account_number, validate_abn, validate_required_field

logger = logging.getLogger(__name__)


# Response helper functions
def error_response(message, status=400):
    """Return a standardized error JSON response."""
    return JsonResponse({'status': 'error', 'message': message}, status=status)


def success_response(message, data=None):
    """Return a standardized success JSON response."""
    response = {'status': 'success', 'message': message}
    if data:
        response.update(data)
    return JsonResponse(response)


def dashboard_view(request):
    """
    Main dashboard view - serves as the application homepage.
    """
    spv_data = SPVData.objects.first()
    
    # Navigation items for navbar
    nav_items = [
        {'label': 'Dashboard', 'url': '/', 'id': 'dashboardLink', 'page_id': 'dashboard'},
        {'divider': True},
        {'label': 'Bills', 'url': '#', 'id': 'billsLink', 'page_id': 'bills', 'submenu': [
            {'label': 'Inbox', 'id': 'billsInboxLink', 'page_id': 'bills_inbox'},
            {'label': 'Direct', 'id': 'billsDirectLink', 'page_id': 'bills_direct'},
        ]},
        {'label': 'Projects', 'url': '#', 'id': 'projectsLink', 'page_id': 'projects'},
        {'label': 'Stocktake', 'url': '#', 'id': 'stocktakeLink', 'page_id': 'stocktake', 'disabled': True},
        {'label': 'Staff Hours', 'url': '#', 'id': 'staffHoursLink', 'page_id': 'staff_hours', 'disabled': True},
        {'label': 'Contacts', 'url': '#', 'id': 'contactsLink', 'page_id': 'contacts'},
        {'label': 'Xero', 'url': '#', 'id': 'xeroLink', 'page_id': 'xero'},
        {'divider': True},
        {'label': 'Settings', 'url': '#', 'id': 'settingsLink', 'page_id': 'settings'},
    ]
    
    # Contacts table configuration
    contacts_columns = ["Name", "First Name", "Last Name", "Email Address", "BSB", "Account Number", "ABN", "Verify", "Update"]
    contacts_rows = []  # No data for now
    
    # Get XeroInstances for dropdown
    xero_instances = XeroInstances.objects.all()
    
    # Serialize xero_instances for JavaScript
    import json
    xero_instances_json = json.dumps([
        {
            'xero_instance_pk': instance.xero_instance_pk,
            'xero_name': instance.xero_name
        }
        for instance in xero_instances
    ])
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
        "nav_items": nav_items,
        "contacts_columns": contacts_columns,
        "contacts_rows": contacts_rows,
        "xero_instances": xero_instances,
        "xero_instances_json": xero_instances_json,
        "settings": settings,  # Add settings to context for environment indicator
    }
    
    return render(request, "dashboard/dashboard.html", context)


@csrf_exempt
def verify_contact_details(request, contact_pk):
    """
    Save verified contact details to separate verified fields.
    All fields are required except ABN (verified_tax_number).
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract and validate fields using validators
            try:
                verified_name = validate_required_field(data.get('name', ''), 'Name')
                verified_email = validate_email(data.get('email', ''))
                bsb_digits = validate_bsb(data.get('bsb', ''))
                verified_account = validate_account_number(data.get('account_number', ''))
                tax_digits = validate_abn(data.get('tax_number', ''))
                verified_notes = validate_required_field(data.get('notes', ''), 'Notes')
            except ValidationError as e:
                return error_response(str(e))
            
            # Get the contact
            contact = Contacts.objects.get(contact_pk=contact_pk)
            
            # Save verified details
            contact.verified_name = verified_name
            contact.verified_email = verified_email
            contact.verified_bank_bsb = bsb_digits
            contact.verified_bank_account_number = verified_account
            contact.verified_tax_number = tax_digits
            contact.verified_notes = verified_notes
            contact.bank_details_verified = 1  # Mark as verified
            contact.save()
            
            logger.info(f"Successfully verified contact details for {contact.name} (PK: {contact_pk})")
            
            return success_response(
                'Contact details verified successfully',
                {
                    'contact': {
                        'contact_pk': contact.contact_pk,
                        'verified_name': contact.verified_name,
                        'verified_email': contact.verified_email,
                        'verified_bank_bsb': contact.verified_bank_bsb,
                        'verified_bank_account_number': contact.verified_bank_account_number,
                        'verified_tax_number': contact.verified_tax_number,
                        'verified_notes': contact.verified_notes,
                        'bank_details_verified': contact.bank_details_verified
                    }
                }
            )
            
        except Contacts.DoesNotExist:
            return error_response('Contact not found', 404)
        except json.JSONDecodeError:
            return error_response('Invalid JSON data')
        except Exception as e:
            logger.error(f"Error verifying contact details: {str(e)}", exc_info=True)
            return error_response(f'Unexpected error: {str(e)}', 500)
    
    return error_response('Only POST method is allowed', 405)


@csrf_exempt
@handle_xero_request_errors
def pull_xero_contacts(request, instance_pk):
    """
    Pull contacts from Xero API for a specific instance.
    Only inserts new contacts, does not update existing ones.
    """
    if request.method == 'POST':
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        logger.info(f"Using tenant_id: {tenant_id} for instance: {xero_instance.xero_name}")
        
        # Step 3: Fetch contacts from Xero API (includes archived contacts)
        # IMPORTANT: Using paging ensures ContactPersons field is populated
        # Without paging, Xero only returns subset of fields
        xero_contacts = []
        page = 1
        
        while True:
            logger.info(f"Fetching page {page} of contacts...")
            contacts_response = requests.get(
                f'https://api.xero.com/api.xro/2.0/Contacts?includeArchived=true&page={page}',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json',
                    'Xero-tenant-id': tenant_id
                },
                timeout=30
            )
            
            if contacts_response.status_code != 200:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Failed to fetch contacts from Xero: {contacts_response.status_code}'
                }, status=400)
            
            contacts_data = contacts_response.json()
            page_contacts = contacts_data.get('Contacts', [])
            
            if not page_contacts:
                break  # No more contacts
            
            xero_contacts.extend(page_contacts)
            logger.info(f"Fetched {len(page_contacts)} contacts from page {page}. Total so far: {len(xero_contacts)}")
            page += 1
        
        logger.info(f"Received {len(xero_contacts)} contacts from Xero API")
        
        # Step 4: Process contacts - insert new ones and update existing ones
        new_contacts_count = 0
        updated_contacts_count = 0
        unchanged_contacts_count = 0
        contact_person_updates = 0  # Track contact_person field updates
        
        for xero_contact in xero_contacts:
            contact_id = xero_contact.get('ContactID')
            
            # Extract contact data from Xero
            name = xero_contact.get('Name', '')
            email = xero_contact.get('EmailAddress', '')
            status = xero_contact.get('ContactStatus', '')
            
            # Extract first and last name from top-level fields
            first_name = xero_contact.get('FirstName', '')
            last_name = xero_contact.get('LastName', '')
            
            # Special logging for the specific contact the user mentioned
            if contact_id == '8be41fd0-1cd9-46a9-9904-6bd765130e07':
                logger.info(f"🔍 TARGET CONTACT '{name}' - FirstName: '{first_name}', LastName: '{last_name}'")
            
            if first_name or last_name:
                logger.info(f"Contact '{name}' (ID: {contact_id[:8]}...) - FirstName: '{first_name}', LastName: '{last_name}'")
            
            # Parse bank account details
            bank_account_details = xero_contact.get('BankAccountDetails', '')
            bank_bsb = ''
            bank_account_number = ''
            
            if bank_account_details:
                # Remove spaces and dashes for parsing
                cleaned = bank_account_details.replace(' ', '').replace('-', '')
                
                # BSB is first 6 digits, rest is account number
                if len(cleaned) >= 6:
                    bank_bsb = cleaned[:6]
                    bank_account_number = cleaned[6:]
                else:
                    # If less than 6 digits, store as-is in account number
                    bank_account_number = cleaned
            
            # Keep original for reference
            bank_details = bank_account_details
            tax_number = xero_contact.get('TaxNumber', '')
            
            # Check if contact already exists
            try:
                existing_contact = Contacts.objects.get(xero_contact_id=contact_id)
                
                # Log existing first/last name for target contact
                if contact_id == '8be41fd0-1cd9-46a9-9904-6bd765130e07':
                    logger.info(f"🔍 TARGET CONTACT - DB first_name before: '{existing_contact.first_name}'")
                    logger.info(f"🔍 TARGET CONTACT - DB last_name before: '{existing_contact.last_name}'")
                    logger.info(f"🔍 TARGET CONTACT - New first_name: '{first_name}', last_name: '{last_name}'")
                
                # Compare and update if any field has changed
                fields_to_update = {
                    'name': name,
                    'email': email,
                    'status': status,
                    'first_name': first_name,
                    'last_name': last_name,
                    'bank_details': bank_details,
                    'bank_bsb': bank_bsb,
                    'bank_account_number': bank_account_number,
                    'tax_number': tax_number
                }
                
                updated = False
                changed_fields = []
                for field, value in fields_to_update.items():
                    current_value = getattr(existing_contact, field)
                    if current_value != value:
                        setattr(existing_contact, field, value)
                        updated = True
                        changed_fields.append(field)
                        
                        # Special logging for first_name/last_name changes
                        if field in ['first_name', 'last_name']:
                            logger.info(f"✅ Contact '{name}' - {field} UPDATED from '{current_value}' to '{value}'")
                            if field == 'first_name' or field == 'last_name':
                                contact_person_updates += 1
                
                if updated:
                    existing_contact.save()
                    updated_contacts_count += 1
                    logger.info(f"Updated contact: {name} (ID: {contact_id})")
                else:
                    unchanged_contacts_count += 1
                    
            except Contacts.DoesNotExist:
                # Create new contact
                Contacts.objects.create(
                    xero_instance=xero_instance,
                    xero_contact_id=contact_id,
                    name=name,
                    email=email,
                    status=status,
                    first_name=first_name,
                    last_name=last_name,
                    bank_details=bank_details,
                    bank_bsb=bank_bsb,
                    bank_account_number=bank_account_number,
                    bank_details_verified=0,
                    tax_number=tax_number
                )
                new_contacts_count += 1
                logger.info(f"Created new contact: {name} (ID: {contact_id})")
        
        logger.info(f"📊 CONTACT NAME SUMMARY: {contact_person_updates} first_name/last_name fields updated")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully pulled contacts from Xero',
            'details': {
                'total_xero_contacts': len(xero_contacts),
                'new_contacts_added': new_contacts_count,
                'contacts_updated': updated_contacts_count,
                'contacts_unchanged': unchanged_contacts_count,
                'contact_person_updates': contact_person_updates
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)

def get_contacts_by_instance(request, instance_pk):
    """
    Get all ACTIVE contacts for a specific Xero instance, sorted alphabetically by name.
    Archived contacts are stored in the database but not displayed in the UI.
    Includes verified status: 0=not verified, 1=verified and matches, 2=verified but changed
    """
    if request.method == 'GET':
        try:
            contacts = Contacts.objects.filter(
                xero_instance_id=instance_pk,
                status='ACTIVE'
            ).order_by('name')
            
            # Build contact list with verified status from model property
            contacts_list = []
            for contact in contacts:
                contacts_list.append({
                    'contact_pk': contact.contact_pk,
                    'xero_instance_id': contact.xero_instance_id,
                    'xero_contact_id': contact.xero_contact_id,
                    'name': contact.name,
                    'first_name': contact.first_name or '',
                    'last_name': contact.last_name or '',
                    'email': contact.email,
                    'status': contact.status,
                    'bank_bsb': contact.bank_bsb,
                    'bank_account_number': contact.bank_account_number,
                    'tax_number': contact.tax_number,
                    'verified': contact.verified_status,  # Use model property
                    'verified_name': contact.verified_name or '',
                    'verified_email': contact.verified_email or '',
                    'verified_bank_bsb': contact.verified_bank_bsb or '',
                    'verified_bank_account_number': contact.verified_bank_account_number or '',
                    'verified_tax_number': contact.verified_tax_number or '',
                    'verified_notes': contact.verified_notes or ''
                })
            
            return JsonResponse(contacts_list, safe=False)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only GET method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def create_contact(request, instance_pk):
    """
    Create a new contact in Xero and local database using OAuth2 tokens.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        bsb = data.get('bsb', '')
        account_number = data.get('account_number', '')
        tax_number = data.get('tax_number', '')
        
        # Validation: Name and Email are required
        if not name:
            return JsonResponse({
                'status': 'error',
                'message': 'Name is required'
            }, status=400)
        
        if not email:
            return JsonResponse({
                'status': 'error',
                'message': 'Email is required'
            }, status=400)
            
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare contact data for Xero
        bank_account_details = format_bank_details(bsb, account_number)
        
        contact_data = {
            'Contacts': [{
                'Name': name,
                'EmailAddress': email,
                'BankAccountDetails': bank_account_details,
                'TaxNumber': tax_number.replace(' ', '') if tax_number else ''
            }]
        }
        
        logger.info(f"Creating contact - Name: {name}, Email: {email}, BSB: {bsb}, Account: {account_number}, Tax: {tax_number}")
        
        create_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=contact_data,
            timeout=30
        )
        
        logger.info(f"Xero API response status: {create_response.status_code}")
        logger.info(f"Xero API response: {create_response.text}")
        
        if create_response.status_code != 200:
            # Parse Xero validation errors using helper
            error_message = parse_xero_validation_errors(create_response) or f'Failed to create contact in Xero: {create_response.status_code}'
            
            return JsonResponse({
                'status': 'error',
                'message': error_message
            }, status=400)
        
        # Extract the created contact from Xero response
        response_data = create_response.json()
        xero_contact = response_data['Contacts'][0]
        xero_contact_id = xero_contact['ContactID']
        contact_status = xero_contact.get('ContactStatus', 'ACTIVE')
        
        # Save to local database
        new_contact = Contacts(
            xero_instance=xero_instance,
            xero_contact_id=xero_contact_id,
            name=name,
            email=email,
            status=contact_status,
            bank_bsb=bsb.replace('-', '') if bsb else '',
            bank_account_number=account_number,
            tax_number=tax_number.replace(' ', '') if tax_number else '',
            bank_details=bank_account_details,
            checked=0  # Default unchecked
        )
        new_contact.save()
        
        logger.info(f"Successfully created contact {name} in database with ID {new_contact.contact_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contact created successfully',
            'contact': {
                'contact_pk': new_contact.contact_pk,
                'name': new_contact.name,
                'email': new_contact.email,
                'bank_bsb': new_contact.bank_bsb,
                'bank_account_number': new_contact.bank_account_number,
                'tax_number': new_contact.tax_number
            }
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def update_contact_details(request, instance_pk, contact_pk):
    """
    Update a contact's details in Xero using OAuth2 tokens.
    Accepts flexible data - can update just name/first_name/last_name/email (from PO table)
    or full contact details including bank info (from Contacts modal).
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name', '')  # Optional: Supplier name (used by PO table)
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        email = data.get('email', '')
        bsb = data.get('bsb', '')  # Optional
        account_number = data.get('account_number', '')  # Optional
        tax_number = data.get('tax_number', '')  # Optional
        
        # Get the contact
        contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare update data for Xero - only include provided fields
        xero_contact_data = {
            'ContactID': contact.xero_contact_id
        }
        
        # Add name if provided (from PO table)
        if name:
            xero_contact_data['Name'] = name
        
        # Add first/last name if provided
        if first_name:
            xero_contact_data['FirstName'] = first_name
        if last_name:
            xero_contact_data['LastName'] = last_name
        
        # Add email if provided
        if email:
            xero_contact_data['EmailAddress'] = email
        
        # Add bank details if provided (from Contacts modal)
        if bsb or account_number:
            bank_account_details = format_bank_details(bsb, account_number)
            xero_contact_data['BankAccountDetails'] = bank_account_details
        
        # Add tax number if provided (from Contacts modal)
        if tax_number:
            xero_contact_data['TaxNumber'] = tax_number.replace(' ', '')
        
        update_data = {
            'Contacts': [xero_contact_data]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id} - Fields: {list(xero_contact_data.keys())}")
        
        update_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=update_data,
            timeout=30
        )
        
        logger.info(f"Xero API response status: {update_response.status_code}")
        logger.info(f"Xero API response: {update_response.text}")
        
        if update_response.status_code != 200:
            # Parse Xero validation errors using helper
            error_message = parse_xero_validation_errors(update_response) or f'Failed to update contact in Xero: {update_response.status_code}'
            
            return JsonResponse({
                'status': 'error',
                'message': error_message
            }, status=400)
        
        # Update local database - only update provided fields
        if name:
            contact.name = name
        if first_name:
            contact.first_name = first_name
        if last_name:
            contact.last_name = last_name
        if email:
            contact.email = email
        if bsb:
            contact.bank_bsb = bsb.replace('-', '')
        if account_number:
            contact.bank_account_number = account_number
        if tax_number:
            contact.tax_number = tax_number.replace(' ', '')
        if bsb or account_number:
            contact.bank_details = bank_account_details
        
        contact.save()
        
        logger.info(f"Successfully updated contact {contact.name} in database")
        
        # Return updated contact data
        response_data = {
            'status': 'success',
            'message': 'Contact updated successfully',
            'contact': {
                'name': contact.name,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'email': contact.email,
                'bank_bsb': contact.bank_bsb,
                'bank_account_number': contact.bank_account_number,
                'tax_number': contact.tax_number
            }
        }
        
        return JsonResponse(response_data)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


@csrf_exempt
@handle_xero_request_errors
def update_contact_status(request, instance_pk, contact_pk):
    """
    Update a contact's status in Xero using OAuth2 tokens.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        archive = data.get('archive', False)  # True to archive, False to unarchive
        
        # Get the contact
        contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Update contact status in Xero
        new_status = 'ARCHIVED' if archive else 'ACTIVE'
        
        update_data = {
            'Contacts': [{
                'ContactID': contact.xero_contact_id,
                'ContactStatus': new_status
            }]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id} to status {new_status}")
        
        update_response = requests.post(
            'https://api.xero.com/api.xro/2.0/Contacts',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Xero-tenant-id': tenant_id
            },
            json=update_data,
            timeout=10
        )
        
        logger.info(f"Xero API response status: {update_response.status_code}")
        logger.info(f"Xero API response: {update_response.text}")
        
        if update_response.status_code not in [200, 201]:
            logger.error(f"Xero API error: {update_response.text}")
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to update contact in Xero: {update_response.status_code}'
            }, status=400)
        
        # Update local database
        contact.status = new_status
        contact.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Contact {"archived" if archive else "unarchived"} successfully',
            'new_status': new_status
        })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


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
            
            # Success\! Parse response
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


# ============================================================================
# ITEMS (CATEGORIES & COSTINGS) VIEWS
# ============================================================================

@require_http_methods(["GET"])
def get_project_categories(request, project_pk):
    """
    Get all categories for a specific project, ordered by order_in_list.
    """
    try:
        from core.models import Categories
        
        categories = Categories.objects.filter(
            project_id=project_pk
        ).order_by('order_in_list').values('categories_pk', 'category', 'order_in_list')
        
        categories_list = list(categories)
        
        logger.info(f"Retrieved {len(categories_list)} categories for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'categories': categories_list
        })
        
    except Exception as e:
        logger.error(f"Error getting project categories: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting categories: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def get_project_items(request, project_pk):
    """
    Get all items (costings) for a specific project, grouped by category.
    """
    try:
        from core.models import Costing
        
        items = Costing.objects.filter(
            project_id=project_pk
        ).select_related('category', 'unit').order_by('category__order_in_list', 'order_in_list')
        
        items_list = []
        for item in items:
            items_list.append({
                'costing_pk': item.costing_pk,
                'item': item.item,
                'unit': item.unit.unit_name if item.unit else None,
                'unit_pk': item.unit.unit_pk if item.unit else None,
                'order_in_list': int(item.order_in_list),
                'category__category': item.category.category,
                'category__order_in_list': int(item.category.order_in_list),
                'uncommitted_amount': float(item.uncommitted_amount) if item.uncommitted_amount else 0,
                'uncommitted_qty': float(item.uncommitted_qty) if item.uncommitted_qty else None,
                'uncommitted_rate': float(item.uncommitted_rate) if item.uncommitted_rate else None,
            })
        
        logger.info(f"Retrieved {len(items_list)} items for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'items': items_list
        })
        
    except Exception as e:
        logger.error(f"Error getting project items: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting items: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_category(request, project_pk):
    """
    Create a new category for a project.
    
    Expected POST data:
    - category: str (max 20 chars)
    - order_in_list: int
    """
    try:
        from core.models import Categories, Projects
        
        data = json.loads(request.body)
        
        # Validate required fields
        category_name = data.get('category', '').strip()
        order_in_list = data.get('order_in_list')
        
        if not category_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Category name is required'
            }, status=400)
        
        if len(category_name) > 20:
            return JsonResponse({
                'status': 'error',
                'message': 'Category name must be 20 characters or less'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Check for duplicate category name (case-insensitive)
        existing_category = Categories.objects.filter(
            project=project,
            category__iexact=category_name
        ).first()
        
        if existing_category:
            return JsonResponse({
                'status': 'error',
                'message': f'A category named "{existing_category.category}" already exists for this project'
            }, status=400)
        
        # Reorder existing categories if needed
        # If inserting at position N and there are already items at N or higher, increment them
        categories_to_reorder = Categories.objects.filter(
            project=project,
            order_in_list__gte=order_in_list
        ).order_by('-order_in_list')  # Order descending to avoid conflicts
        
        for cat in categories_to_reorder:
            cat.order_in_list += 1
            cat.save()
        
        logger.info(f"Reordered {categories_to_reorder.count()} categories to make space at position {order_in_list}")
        
        # Create the category
        category = Categories.objects.create(
            project=project,
            category=category_name,
            invoice_category=category_name,  # Default to same as category
            order_in_list=order_in_list,
            division=0  # Default division
        )
        
        logger.info(f"Created category '{category_name}' for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Category created successfully',
            'category': {
                'categories_pk': category.categories_pk,
                'category': category.category,
                'order_in_list': int(category.order_in_list)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating category: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating category: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_item(request, project_pk):
    """
    Create a new item (costing) for a project.
    
    Expected POST data:
    - item: str (max 20 chars)
    - unit: int (unit_pk, optional)
    - category_pk: int
    - order_in_list: int
    """
    try:
        from core.models import Costing, Categories, Projects, Units
        
        data = json.loads(request.body)
        
        # Validate required fields
        item_name = data.get('item', '').strip()
        unit_pk = data.get('unit')  # Now expecting unit_pk instead of unit name
        category_pk = data.get('category_pk')
        order_in_list = data.get('order_in_list')
        
        if not item_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Item name is required'
            }, status=400)
        
        # Validate unit if provided
        unit_obj = None
        if unit_pk:
            try:
                unit_obj = Units.objects.get(unit_pk=unit_pk)
            except Units.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid unit selected'
                }, status=400)
        
        if len(item_name) > 20:
            return JsonResponse({
                'status': 'error',
                'message': 'Item name must be 20 characters or less'
            }, status=400)
        
        if not category_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Category is required'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the category
        try:
            category = Categories.objects.get(categories_pk=category_pk, project=project)
        except Categories.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Category not found for this project'
            }, status=404)
        
        # Reorder existing items in this category if needed
        # If inserting at position N and there are already items at N or higher, increment them
        items_to_reorder = Costing.objects.filter(
            project=project,
            category=category,
            order_in_list__gte=order_in_list
        ).order_by('-order_in_list')  # Order descending to avoid conflicts
        
        for item_obj in items_to_reorder:
            item_obj.order_in_list += 1
            item_obj.save()
        
        logger.info(f"Reordered {items_to_reorder.count()} items in category '{category.category}' to make space at position {order_in_list}")
        
        # Create the item
        item = Costing.objects.create(
            project=project,
            category=category,
            item=item_name,
            unit=unit_obj,  # Now using the Units ForeignKey object
            order_in_list=order_in_list,
            xero_account_code='',  # Default empty
            contract_budget=0,
            uncommitted_amount=0,
            fixed_on_site=0,
            sc_invoiced=0,
            sc_paid=0
        )
        
        logger.info(f"Created item '{item_name}' in category '{category.category}' for project {project_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item created successfully',
            'item': {
                'costing_pk': item.costing_pk,
                'item': item.item,
                'category': category.category,
                'category_pk': category.categories_pk
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error creating item: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_category(request, project_pk, category_pk):
    """
    Reorder a category to a new position.
    All items in the category move with it.
    
    Expected POST data:
    - new_order: int (new position in list)
    """
    try:
        from core.models import Categories, Projects
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order position is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the category to move
        try:
            category = Categories.objects.get(categories_pk=category_pk, project=project)
        except Categories.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Category not found'
            }, status=404)
        
        old_order = int(category.order_in_list)
        new_order = int(new_order)
        
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'No change in position'
            })
        
        # Get all categories for this project
        categories = Categories.objects.filter(project=project).exclude(categories_pk=category_pk).order_by('order_in_list')
        
        # Update order_in_list for all affected categories
        if new_order < old_order:
            # Moving up: increment categories between new_order and old_order
            for cat in categories:
                if new_order <= int(cat.order_in_list) < old_order:
                    cat.order_in_list += 1
                    cat.save()
        else:
            # Moving down: decrement categories between old_order and new_order
            for cat in categories:
                if old_order < int(cat.order_in_list) <= new_order:
                    cat.order_in_list -= 1
                    cat.save()
        
        # Update the moved category
        category.order_in_list = new_order
        category.save()
        
        logger.info(f"Reordered category '{category.category}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Category reordered successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error reordering category: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering category: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_item(request, project_pk, item_pk):
    """
    Reorder an item to a new position within its category.
    Items can only be reordered within their own category.
    
    Expected POST data:
    - new_order: int (new position in list within the category)
    """
    try:
        from core.models import Costing, Projects
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order position is required'
            }, status=400)
        
        # Get the project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get the item to move
        try:
            item = Costing.objects.get(costing_pk=item_pk, project=project)
        except Costing.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found'
            }, status=404)
        
        old_order = int(item.order_in_list)
        new_order = int(new_order)
        
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'No change in position'
            })
        
        # Get all items in the same category
        items = Costing.objects.filter(
            project=project,
            category=item.category
        ).exclude(costing_pk=item_pk).order_by('order_in_list')
        
        # Update order_in_list for all affected items in this category
        if new_order < old_order:
            # Moving up: increment items between new_order and old_order
            for itm in items:
                if new_order <= int(itm.order_in_list) < old_order:
                    itm.order_in_list += 1
                    itm.save()
        else:
            # Moving down: decrement items between old_order and new_order
            for itm in items:
                if old_order < int(itm.order_in_list) <= new_order:
                    itm.order_in_list -= 1
                    itm.save()
        
        # Update the moved item
        item.order_in_list = new_order
        item.save()
        
        logger.info(f"Reordered item '{item.item}' in category '{item.category.category}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item reordered successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        logger.error(f"Error reordering item: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering item: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def download_items_csv_template(request):
    """
    Download an example CSV template for bulk category and item upload.
    
    Format:
    Category,Item,Unit,Category Order,Item Order
    Preliminaries,Site Establishment,item,1,1
    Preliminaries,Temp Fencing,m,1,2
    Excavation,Bulk Excavation,m3,2,1
    
    Valid units: item, each, m, m2, m3, ton
    """
    try:
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="items_upload_template.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(['Category', 'Item', 'Unit', 'Category Order', 'Item Order'])
        
        # Write example data with various units
        writer.writerow(['Preliminaries', 'Site Establishment', 'item', '1', '1'])
        writer.writerow(['Preliminaries', 'Temp Fencing', 'm', '1', '2'])
        writer.writerow(['Preliminaries', 'Site Signage', 'each', '1', '3'])
        writer.writerow(['Excavation', 'Bulk Excavation', 'm3', '2', '1'])
        writer.writerow(['Excavation', 'Trench Excavation', 'm3', '2', '2'])
        writer.writerow(['Concrete', 'Footings', 'm3', '3', '1'])
        writer.writerow(['Concrete', 'Slab', 'm2', '3', '2'])
        writer.writerow(['Concrete', 'Walls', 'm2', '3', '3'])
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating CSV template: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error generating template: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_items_csv(request, project_pk):
    """
    Upload and process CSV file to create categories and items in bulk.
    
    Expected CSV format:
    Category,Item,Unit,Category Order,Item Order
    Preliminaries,Site Establishment,item,1,1
    
    - Adds to existing categories/items (does not replace)
    - Creates categories if they don't exist
    - Handles duplicate category names within same project
    - Validates order numbers
    - Validates units: item, each, m, m2, m3, ton
    """
    try:
        # Get project
        try:
            project = Projects.objects.get(projects_pk=project_pk)
        except Projects.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Project not found'
            }, status=404)
        
        # Get CSV file from request
        if 'csv_file' not in request.FILES:
            return JsonResponse({
                'status': 'error',
                'message': 'No CSV file provided'
            }, status=400)
        
        csv_file = request.FILES['csv_file']
        
        # Validate file type
        if not csv_file.name.endswith('.csv'):
            return JsonResponse({
                'status': 'error',
                'message': 'File must be a CSV'
            }, status=400)
        
        # Read and parse CSV with robust encoding handling
        try:
            # Try to decode with multiple encodings (handles Excel, Google Sheets, etc.)
            file_bytes = csv_file.read()
            file_data = None
            
            # Try UTF-8 with BOM first (Excel on Windows)
            try:
                file_data = file_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                pass
            
            # Try UTF-8 without BOM
            if file_data is None:
                try:
                    file_data = file_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    pass
            
            # Try Latin-1 / ISO-8859-1 (fallback, rarely fails)
            if file_data is None:
                try:
                    file_data = file_bytes.decode('latin-1')
                except UnicodeDecodeError:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Unable to decode CSV file. Please ensure it is saved as UTF-8.'
                    }, status=400)
            
            # Normalize line endings (handles Windows, Mac, Unix)
            file_data = file_data.replace('\r\n', '\n').replace('\r', '\n')
            
            # Parse CSV
            csv_reader = csv.DictReader(StringIO(file_data))
            
            # Validate headers exist
            if not csv_reader.fieldnames:
                return JsonResponse({
                    'status': 'error',
                    'message': 'CSV file appears to be empty or has no headers'
                }, status=400)
            
            # Normalize header names (strip whitespace, case-insensitive)
            # Map common variations to expected names
            header_map = {}
            for field in csv_reader.fieldnames:
                field_lower = field.strip().lower()
                if field_lower in ['category', 'category name']:
                    header_map[field] = 'Category'
                elif field_lower in ['item', 'item name']:
                    header_map[field] = 'Item'
                elif field_lower in ['unit', 'units']:
                    header_map[field] = 'Unit'
                elif field_lower in ['category order', 'categoryorder', 'cat order']:
                    header_map[field] = 'Category Order'
                elif field_lower in ['item order', 'itemorder']:
                    header_map[field] = 'Item Order'
            
            # Check if we have all required headers (Unit is optional for backward compatibility)
            required = {'Category', 'Item', 'Category Order', 'Item Order'}
            if not required.issubset(set(header_map.values())):
                missing = required - set(header_map.values())
                return JsonResponse({
                    'status': 'error',
                    'message': f'CSV missing required columns: {", ".join(missing)}'
                }, status=400)
            
            # Track created items
            categories_created = 0
            items_created = 0
            category_cache = {}  # Cache created/existing categories {name: category_obj}
            errors = []
            
            # Create reverse map for easy lookup
            reverse_map = {v: k for k, v in header_map.items()}
            
            # Process each row
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                try:
                    # Skip completely empty rows
                    if not any(row.values()):
                        continue
                    
                    # Validate required fields using mapped headers
                    category_name = row.get(reverse_map['Category'], '').strip()
                    item_name = row.get(reverse_map['Item'], '').strip()
                    item_unit = row.get(reverse_map.get('Unit', ''), '').strip() if 'Unit' in reverse_map else ''
                    category_order = row.get(reverse_map['Category Order'], '').strip()
                    item_order = row.get(reverse_map['Item Order'], '').strip()
                    
                    if not category_name:
                        errors.append(f"Row {row_num}: Missing category name")
                        continue
                    
                    if not item_name:
                        errors.append(f"Row {row_num}: Missing item name")
                        continue
                    
                    # Validate and look up unit if provided
                    unit_obj = None
                    if item_unit:
                        # Look up the Units object by unit_name
                        unit_obj = Units.objects.filter(unit_name__iexact=item_unit).first()
                        if not unit_obj:
                            # List valid units from database
                            valid_units = list(Units.objects.values_list('unit_name', flat=True))
                            errors.append(f"Row {row_num}: Invalid unit '{item_unit}'. Must be one of: {', '.join(valid_units)}")
                            continue
                    
                    if not category_order or not category_order.isdigit():
                        errors.append(f"Row {row_num}: Invalid category order")
                        continue
                    
                    if not item_order or not item_order.isdigit():
                        errors.append(f"Row {row_num}: Invalid item order")
                        continue
                    
                    category_order_int = int(category_order)
                    item_order_int = int(item_order)
                    
                    # Get or create category
                    if category_name in category_cache:
                        category = category_cache[category_name]
                    else:
                        # Check if category already exists for this project
                        existing_category = Categories.objects.filter(
                            project=project,
                            category=category_name
                        ).first()
                        
                        if existing_category:
                            category = existing_category
                        else:
                            # Create new category (division is required, set to 0 as default)
                            category = Categories.objects.create(
                                project=project,
                                category=category_name,
                                division=0,
                                invoice_category='',
                                order_in_list=category_order_int
                            )
                            categories_created += 1
                        
                        category_cache[category_name] = category
                    
                    # Check if item already exists
                    existing_item = Costing.objects.filter(
                        project=project,
                        category=category,
                        item=item_name
                    ).first()
                    
                    if existing_item:
                        # Skip if item already exists
                        errors.append(f"Row {row_num}: Item '{item_name}' already exists in category '{category_name}'")
                        continue
                    
                    # Create item with required fields set to defaults
                    Costing.objects.create(
                        project=project,
                        category=category,
                        item=item_name,
                        unit=unit_obj,  # ForeignKey to Units model
                        order_in_list=item_order_int,
                        xero_account_code='',
                        contract_budget=0,
                        uncommitted_amount=0,
                        fixed_on_site=0,
                        sc_invoiced=0,
                        sc_paid=0
                    )
                    items_created += 1
                    
                except Exception as row_error:
                    errors.append(f"Row {row_num}: {str(row_error)}")
                    continue
            
            # Prepare response
            response_data = {
                'status': 'success',
                'categories_created': categories_created,
                'items_created': items_created
            }
            
            if errors:
                response_data['warnings'] = errors
                response_data['message'] = f"Processed with {len(errors)} warning(s)"
            
            return JsonResponse(response_data)
            
        except csv.Error as e:
            return JsonResponse({
                'status': 'error',
                'message': f'CSV parsing error: {str(e)}'
            }, status=400)
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing CSV: {str(e)}'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error uploading CSV: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error uploading CSV: {str(e)}'
        }, status=500)


def generate_po_html(project, supplier, items, total_amount, po_url=None):
    """
    Generate HTML for PO PDF with professional formatting.
    Shared between email and download endpoints.
    Dynamically scales row height based on number of items.
    """
    # Dynamic scaling based on number of items to fit on one A4 page
    # 1-10 items: Full padding (12px), large font (12px) - comfortable spacing
    # 11-20 items: Medium padding (8px), medium font (11px) - balanced
    # 21-30 items: Tight padding (6px), small font (10px) - maximum density
    num_items = len(items)
    if num_items <= 10:
        td_padding = "12px"
        font_size = "12px"
        header_padding = "14px 12px"
    elif num_items <= 20:
        td_padding = "8px"
        font_size = "11px"
        header_padding = "10px 12px"
    else:  # 21-30 items
        td_padding = "6px"
        font_size = "10px"
        header_padding = "8px 12px"
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                color: #333;
                position: relative;
            }}
            .header {{
                text-align: center;
                margin-bottom: {f'15px' if num_items > 20 else '20px'};
                position: relative;
            }}
            h1 {{
                color: #2c3e50;
                font-size: {f'24px' if num_items > 20 else '28px'};
                margin: 0 0 8px 0;
                font-weight: bold;
            }}
            .subheading-container {{
                position: relative;
            }}
            h2 {{
                color: #7f8c8d;
                font-size: {f'16px' if num_items > 20 else '18px'};
                margin: 0;
                font-weight: normal;
                display: inline-block;
            }}
            .date-inline {{
                position: absolute;
                right: 0;
                top: 50%;
                transform: translateY(-50%);
                color: #95a5a6;
                font-size: {f'10px' if num_items > 20 else '11px'};
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: {f'10px' if num_items > 20 else '15px'};
                border: 1px solid #ddd;
            }}
            thead th {{
                background-color: #34495e;
                color: white;
                padding: {f'8px 6px' if num_items > 20 else '10px 8px'};
                text-align: left;
                font-weight: bold;
                font-size: {f'13px' if num_items > 20 else '14px'};
                border-bottom: 2px solid #2c3e50;
            }}
            thead th.amount {{
                text-align: right;
            }}
            tbody td {{
                padding: {f'6px' if num_items > 20 else '8px'};
                border-bottom: 1px solid #ecf0f1;
                font-size: {f'12px' if num_items > 20 else '13px'};
                vertical-align: top;
            }}
            tbody td.amount {{
                text-align: right;
                font-weight: 500;
            }}
            tfoot td {{
                background-color: #ecf0f1;
                font-weight: bold;
                padding: {f'8px 6px' if num_items > 20 else '10px 8px'};
                border-top: 2px solid #34495e;
                border-bottom: none;
                font-size: {f'13px' if num_items > 20 else '14px'};
            }}
            tfoot td.amount {{
                text-align: right;
            }}
            .footer {{
                margin-top: {f'12px' if num_items > 20 else '18px'};
                text-align: left;
            }}
            .po-url {{
                margin-top: {f'10px' if num_items > 20 else '15px'};
                margin-bottom: {f'10px' if num_items > 20 else '15px'};
                padding: {f'12px' if num_items > 20 else '15px'};
                background-color: #fff3cd;
                border: 2px solid #ffc107;
                border-radius: 8px;
            }}
            .po-url-title {{
                color: #2c3e50;
                font-weight: bold;
                font-size: {f'13px' if num_items > 20 else '15px'};
                margin-bottom: 10px;
            }}
            .po-url a {{
                color: #0066cc;
                text-decoration: underline;
                font-weight: 600;
                font-size: {f'12px' if num_items > 20 else '14px'};
                word-break: break-all;
            }}
            .claims-process {{
                margin-top: {f'10px' if num_items > 20 else '15px'};
                padding: {f'10px' if num_items > 20 else '12px'};
                background-color: #f8f9fa;
                border-left: 4px solid #34495e;
            }}
            .claims-heading {{
                color: #2c3e50;
                font-size: {f'12px' if num_items > 20 else '13px'};
                font-weight: bold;
                margin-bottom: {f'6px' if num_items > 20 else '8px'};
            }}
            .claims-text {{
                color: #555;
                font-size: {f'10px' if num_items > 20 else '11px'};
                line-height: 1.5;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Purchase Order</h1>
            <div class="subheading-container">
                <h2>{project.project} - {supplier.name}</h2>
                <div class="date-inline">Generated on {date.today().strftime('%B %d, %Y')}</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th style="width: 50%;">Description</th>
                    <th class="amount" style="width: 25%;">Amount</th>
                    <th style="width: 25%;">Quote #</th>
                </tr>
            </thead>
            <tbody>
    '''
    
    for item in items:
        html_content += f'''
                <tr>
                    <td style="width: 50%;">{item['description']}</td>
                    <td class="amount" style="width: 25%;">${item['amount']:,.2f}</td>
                    <td style="width: 25%;">{item['quote_numbers']}</td>
                </tr>
        '''
    
    html_content += f'''
            </tbody>
            <tfoot>
                <tr>
                    <td style="width: 50%;">TOTAL</td>
                    <td class="amount" style="width: 25%;">${total_amount:,.2f}</td>
                    <td style="width: 25%;"></td>
                </tr>
            </tfoot>
        </table>
        
        <div class="footer">
    '''
    
    if po_url:
        html_content += f'''
            <div class="po-url">
                <div class="po-url-title">Your Unique Payment Processing Link For All Claims:</div>
                <a href="{po_url}">{po_url}</a>
            </div>
            
            <div class="claims-process">
                <div class="claims-heading">Claims Process</div>
                <p class="claims-text">
                    1) Click your unique url above to submit your claim for approval by the 25th of the month.<br><br>
                    2) You will receive an email when your claim is approved or rejected by the end of the month.<br><br>
                    3) Once approved, click your unique url and upload your invoice matching the approved claim amount.
                </p>
            </div>
        '''
    
    html_content += '''
        </div>
    </body>
    </html>
    '''
    
    return html_content


@csrf_exempt
def send_po_email(request, project_pk, supplier_pk):
    """
    Generate PO PDF and send email to supplier.
    Reuses existing email configuration (invoices@mason.build).
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get project and supplier details
        project = Projects.objects.get(projects_pk=project_pk)
        supplier = Contacts.objects.get(contact_pk=supplier_pk)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if not quotes.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No quotes found for this supplier'
            }, status=404)
        
        # Group allocations by item
        from collections import defaultdict
        items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': []})
        
        for quote in quotes:
            for allocation in quote.quote_allocations.all():
                item_name = allocation.item.item
                items_map[item_name]['amount'] += allocation.amount
                if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                    items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
        
        # Convert to list
        items = [
            {
                'description': item_name,
                'amount': float(data['amount']),
                'quote_numbers': ', '.join(data['quote_numbers'])
            }
            for item_name, data in items_map.items()
        ]
        
        # Calculate total
        total_amount = sum(item['amount'] for item in items)
        
        # Create Po_orders entry with unique URL (before PDF generation)
        unique_id = str(uuid.uuid4())
        po_order = Po_orders.objects.create(
            po_supplier=supplier,
            project=project,
            unique_id=unique_id,
            po_sent=True
        )
        
        # Create Po_order_detail records for each quote allocation
        from datetime import date
        for quote in quotes:
            for allocation in quote.quote_allocations.all():
                Po_order_detail.objects.create(
                    po_order_pk=po_order,
                    date=date.today(),
                    costing=allocation.item,
                    quote=quote,
                    amount=allocation.amount,
                    qty=allocation.qty if hasattr(allocation, 'qty') and allocation.qty else None,
                    unit=allocation.item.unit if hasattr(allocation.item, 'unit') else None,
                    rate=allocation.rate if hasattr(allocation, 'rate') and allocation.rate else None,
                    variation_note=None
                )
        
        logger.info(f"Created Po_order with {Po_order_detail.objects.filter(po_order_pk=po_order).count()} detail records")
        
        # Generate URL dynamically from the request
        # This ensures the URL matches the environment (local/AWS) automatically
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        
        # Force HTTPS for production domains (AWS load balancer may terminate SSL)
        if 'mason.build' in host or 'elasticbeanstalk.com' in host:
            scheme = 'https'
        
        po_url = f"{scheme}://{host}/po/{unique_id}/"
        
        # Generate HTML for PDF using shared function with clickable URL
        html_content = generate_po_html(project, supplier, items, total_amount, po_url)
        
        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate PDF'
            }, status=500)
        
        pdf_buffer.seek(0)
        pdf_content = pdf_buffer.read()
        
        # Collect unique quote numbers from items (in order of appearance)
        quote_numbers_in_order = []
        for item in items:
            for qn in item['quote_numbers'].split(', '):
                qn = qn.strip()
                if qn and qn not in quote_numbers_in_order:
                    quote_numbers_in_order.append(qn)
        
        # Fetch quote PDFs in order of appearance
        quote_pdfs_to_attach = []
        for quote_num in quote_numbers_in_order:
            try:
                quote = Quotes.objects.get(
                    supplier_quote_number=quote_num,
                    project=project,
                    contact_pk=supplier
                )
                if quote.pdf:
                    quote_pdfs_to_attach.append(quote.pdf)
            except Quotes.DoesNotExist:
                logger.warning(f"Quote {quote_num} not found for supplier {supplier.name}")
                continue
        
        # Merge PO PDF with quote PDFs
        if quote_pdfs_to_attach:
            try:
                merger = PdfMerger()
                
                # Add the PO PDF first
                po_pdf_buffer = BytesIO(pdf_content)
                merger.append(po_pdf_buffer)
                
                # Add each quote PDF in order
                for quote_pdf in quote_pdfs_to_attach:
                    quote_pdf.open('rb')
                    merger.append(quote_pdf)
                    quote_pdf.close()
                
                # Write merged PDF to buffer
                merged_buffer = BytesIO()
                merger.write(merged_buffer)
                merger.close()
                
                # Use merged PDF as the final content
                merged_buffer.seek(0)
                final_pdf_content = merged_buffer.read()
                logger.info(f"Merged PO PDF with {len(quote_pdfs_to_attach)} quote PDFs")
            except Exception as e:
                logger.error(f"Error merging PDFs: {e}", exc_info=True)
                # Fall back to PO PDF only if merge fails
                final_pdf_content = pdf_content
        else:
            # No quote PDFs to attach, use PO PDF only
            final_pdf_content = pdf_content
        
        # Save combined PDF to Po_orders model for record keeping
        pdf_filename = f'PO_{project.project}_{supplier.name}_{unique_id[:8]}.pdf'
        po_order.pdf.save(pdf_filename, ContentFile(final_pdf_content), save=True)
        
        # Prepare email
        supplier_name = supplier.first_name or supplier.name.split()[0] if supplier.name else 'there'
        supplier_last_name = supplier.last_name or ''
        full_name = f"{supplier_name} {supplier_last_name}".strip()
        
        subject = 'Purchase Order'
        
        # Plain text version (fallback)
        text_message = f'''Dear {full_name},

Please see attached purchase order with payment claim instructions.

Please read the payment claim instructions carefully to ensure your claim is processed and paid on time.

View payment claim instructions: {po_url}

Regards,
Mason'''
        
        # HTML version with hyperlink
        html_message = f'''
        <html>
        <body>
            <p>Dear {full_name},</p>
            
            <p>Please see attached purchase order with <a href="{po_url}">payment claim instructions</a>.</p>
            
            <p>Please read the payment claim instructions carefully to ensure your claim is processed and paid on time.</p>
            
            <p>Regards,<br>
            Mason</p>
        </body>
        </html>
        '''
        
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [supplier.email] if supplier.email else []
        
        if not recipient_list:
            return JsonResponse({
                'status': 'error',
                'message': 'Supplier has no email address'
            }, status=400)
        
        # Create email with attachment (combined PO + Quotes PDF)
        email = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
        email.attach_alternative(html_message, "text/html")
        email.attach(f'PO_{project.project}.pdf', final_pdf_content, 'application/pdf')
        
        # Add CC if configured
        if hasattr(settings, 'EMAIL_CC') and settings.EMAIL_CC:
            cc_addresses = settings.EMAIL_CC.split(';')
            email.cc = cc_addresses
        
        # Send email
        email.send()
        
        logger.info(f"PO email sent to {supplier.email} for project {project.project}")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Purchase order sent to {supplier.email}'
        })
        
    except Projects.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Project not found'
        }, status=404)
    except Contacts.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Supplier not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error sending PO email: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to send email: {str(e)}'
        }, status=500)


@csrf_exempt
def download_po_pdf(request, project_pk, supplier_pk):
    """
    Generate PO PDF and return as download.
    """
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Only POST method is allowed'
        }, status=405)
    
    try:
        # Get project and supplier details
        project = Projects.objects.get(projects_pk=project_pk)
        supplier = Contacts.objects.get(contact_pk=supplier_pk)
        
        # Get all quotes for this project and supplier
        quotes = Quotes.objects.filter(
            project=project,
            contact_pk=supplier
        ).prefetch_related('quote_allocations')
        
        if not quotes.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No quotes found for this supplier'
            }, status=404)
        
        # Group allocations by item
        from collections import defaultdict
        items_map = defaultdict(lambda: {'amount': Decimal('0'), 'quote_numbers': []})
        
        for quote in quotes:
            for allocation in quote.quote_allocations.all():
                item_name = allocation.item.item
                items_map[item_name]['amount'] += allocation.amount
                if quote.supplier_quote_number and quote.supplier_quote_number not in items_map[item_name]['quote_numbers']:
                    items_map[item_name]['quote_numbers'].append(quote.supplier_quote_number)
        
        # Convert to list
        items = [
            {
                'description': item_name,
                'amount': float(data['amount']),
                'quote_numbers': ', '.join(data['quote_numbers'])
            }
            for item_name, data in items_map.items()
        ]
        
        # Calculate total
        total_amount = sum(item['amount'] for item in items)
        
        # Generate HTML for PDF using shared function
        html_content = generate_po_html(project, supplier, items, total_amount)
        
        # Convert HTML to PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to generate PDF'
            }, status=500)
        
        pdf_buffer.seek(0)
        
        # Return PDF as download
        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="PO_{project.project}_{supplier.name}.pdf"'
        
        logger.info(f"PO PDF downloaded for project {project.project}, supplier {supplier.name}")
        
        return response
        
    except Projects.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Project not found'
        }, status=404)
    except Contacts.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Supplier not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error generating PO PDF: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Failed to generate PDF: {str(e)}'
        }, status=500)


@csrf_exempt
def get_units(request):
    """
    Get all units ordered by order_in_list
    """
    try:
        from core.models import Units
        
        units = Units.objects.all().order_by('order_in_list')
        
        units_data = [{
            'unit_pk': unit.unit_pk,
            'unit_name': unit.unit_name,
            'order_in_list': unit.order_in_list
        } for unit in units]
        
        return JsonResponse({
            'status': 'success',
            'units': units_data
        })
        
    except Exception as e:
        logger.error(f"Error getting units: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting units: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_unit(request):
    """
    Add a new unit
    
    Expected POST data:
    {
        "unit_name": string,
        "order_in_list": int
    }
    """
    try:
        from core.models import Units
        
        data = json.loads(request.body)
        
        unit_name = data.get('unit_name', '').strip()
        order_in_list = data.get('order_in_list')
        
        if not unit_name:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit name is required'
            }, status=400)
        
        if order_in_list is None:
            return JsonResponse({
                'status': 'error',
                'message': 'Order in list is required'
            }, status=400)
        
        # Check if unit name already exists
        if Units.objects.filter(unit_name=unit_name).exists():
            return JsonResponse({
                'status': 'error',
                'message': f'Unit "{unit_name}" already exists'
            }, status=400)
        
        # Get all units and adjust their order if needed
        existing_units = Units.objects.filter(order_in_list__gte=order_in_list).order_by('-order_in_list')
        
        # Shift existing units down
        for unit in existing_units:
            unit.order_in_list += 1
            unit.save()
        
        # Create new unit
        new_unit = Units.objects.create(
            unit_name=unit_name,
            order_in_list=order_in_list
        )
        
        logger.info(f"Added new unit: {unit_name} at position {order_in_list}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit added successfully',
            'unit': {
                'unit_pk': new_unit.unit_pk,
                'unit_name': new_unit.unit_name,
                'order_in_list': new_unit.order_in_list
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error adding unit: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reorder_unit(request, unit_pk):
    """
    Reorder a unit by updating its order_in_list
    
    Expected POST data:
    {
        "new_order": int
    }
    """
    try:
        from core.models import Units
        from django.db import transaction
        
        data = json.loads(request.body)
        new_order = data.get('new_order')
        
        if new_order is None:
            return JsonResponse({
                'status': 'error',
                'message': 'New order is required'
            }, status=400)
        
        # Get the unit to reorder
        try:
            unit = Units.objects.get(unit_pk=unit_pk)
        except Units.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit not found'
            }, status=404)
        
        old_order = unit.order_in_list
        
        # If order hasn't changed, no need to do anything
        if old_order == new_order:
            return JsonResponse({
                'status': 'success',
                'message': 'Unit order unchanged'
            })
        
        # Use transaction to ensure all updates happen together
        with transaction.atomic():
            # First, move the dragged unit to a temporary position (9999) to free up its current position
            unit.order_in_list = 9999
            unit.save()
            
            if new_order < old_order:
                # Moving up: shift items down between new_order and old_order
                units_to_shift = Units.objects.filter(
                    order_in_list__gte=new_order,
                    order_in_list__lt=old_order
                ).order_by('-order_in_list')  # Update in reverse order to avoid conflicts
                
                for u in units_to_shift:
                    u.order_in_list += 1
                    u.save()
                
            else:
                # Moving down: shift items up between old_order and new_order
                units_to_shift = Units.objects.filter(
                    order_in_list__gt=old_order,
                    order_in_list__lte=new_order
                ).order_by('order_in_list')  # Update in forward order to avoid conflicts
                
                for u in units_to_shift:
                    u.order_in_list -= 1
                    u.save()
            
            # Finally, update the dragged unit to its final position
            unit.order_in_list = new_order
            unit.save()
        
        logger.info(f"Reordered unit '{unit.unit_name}' from position {old_order} to {new_order}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit reordered successfully'
        })
        
    except Exception as e:
        logger.error(f"Error reordering unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error reordering unit: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_unit(request):
    """
    Delete a unit
    
    Expected POST data:
    {
        "unit_pk": int
    }
    """
    try:
        from core.models import Units
        
        data = json.loads(request.body)
        
        unit_pk = data.get('unit_pk')
        
        if not unit_pk:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit PK is required'
            }, status=400)
        
        # Get the unit
        try:
            unit = Units.objects.get(unit_pk=unit_pk)
        except Units.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Unit not found'
            }, status=404)
        
        unit_name = unit.unit_name
        order = unit.order_in_list
        
        # Delete the unit
        unit.delete()
        
        # Adjust order of remaining units
        remaining_units = Units.objects.filter(order_in_list__gt=order).order_by('order_in_list')
        for remaining_unit in remaining_units:
            remaining_unit.order_in_list -= 1
            remaining_unit.save()
        
        logger.info(f"Deleted unit: {unit_name}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Unit deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting unit: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Error deleting unit: {str(e)}'
        }, status=500)
