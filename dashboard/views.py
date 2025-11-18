"""
Dashboard app views.

Dashboard View:
1. dashboard_view - Main dashboard homepage

Contacts Views:
2. verify_contact_details - Save verified contact details to separate verified fields
3. pull_xero_contacts - Pull contacts from Xero API, insert/update locally
4. get_contacts_by_instance - Get ACTIVE contacts with verified status (0/1/2)
5. create_contact - Create contact in Xero + local DB
6. update_contact_details - Update bank details, email, ABN in Xero
7. update_contact_status - Archive/unarchive contact in Xero

Note: Contact functions 3-7 use helper functions from core.views.xero:
- get_xero_auth() - OAuth authentication
- format_bank_details() - BSB + account formatting
- parse_xero_validation_errors() - Error parsing
- @handle_xero_request_errors - Exception handling decorator
"""

import json
import logging
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.models import Contacts, SPVData, XeroInstances, Invoices, Projects, Invoice_allocations
from decimal import Decimal
from datetime import date
# Import helpers from core.views.xero
from core.views.xero import get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors

logger = logging.getLogger(__name__)


def dashboard_view(request):
    """
    Main dashboard view - serves as the application homepage.
    """
    spv_data = SPVData.objects.first()
    
    # Table configuration for dashboard
    table_columns = [
        "Fake 1", "Fake 2", "Fake 3", "Fake 4", "Fake 5",
        "Fake 6", "Fake 7", "Fake 8", "Fake 9", "Fake 10"
    ]
    
    # Navigation items for navbar
    nav_items = [
        {'label': 'Dashboard', 'url': '/', 'id': 'dashboardLink', 'page_id': 'dashboard'},
        {'divider': True},
        {'label': 'Bills', 'url': '#', 'id': 'billsLink', 'page_id': 'bills', 'submenu': [
            {'label': 'Inbox', 'id': 'billsInboxLink', 'page_id': 'bills_inbox'},
            {'label': 'Direct', 'id': 'billsDirectLink', 'page_id': 'bills_direct'},
        ]},
        {'label': 'Stocktake', 'url': '#', 'id': 'stocktakeLink', 'page_id': 'stocktake'},
        {'label': 'Staff Hours', 'url': '#', 'id': 'staffHoursLink', 'page_id': 'staff_hours'},
        {'label': 'Contacts', 'url': '#', 'id': 'contactsLink', 'page_id': 'contacts'},
        {'label': 'Xero', 'url': '#', 'id': 'xeroLink', 'page_id': 'xero'},
    ]
    
    # Contacts table configuration
    contacts_columns = ["Name", "Email Address", "BSB", "Account Number", "ABN", "Verify", "Update"]
    contacts_rows = []  # No data for now
    
    # Get XeroInstances for dropdown
    xero_instances = XeroInstances.objects.all()
    
    context = {
        "current_page": "dashboard",
        "project_name": settings.PROJECT_NAME,
        "spv_data": spv_data,
        "table_columns": table_columns,
        "table_rows": [],  # No data for now
        "show_totals": False,  # No totals row for dashboard
        "nav_items": nav_items,
        "contacts_columns": contacts_columns,
        "contacts_rows": contacts_rows,
        "xero_instances": xero_instances,
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
            
            # Extract fields from request
            verified_name = data.get('name', '').strip()
            verified_email = data.get('email', '').strip()
            verified_bsb = data.get('bsb', '').strip()
            verified_account = data.get('account_number', '').strip()
            verified_tax_number = data.get('tax_number', '').strip()
            verified_notes = data.get('notes', '').strip()
            
            # Validation - all fields required except tax_number (ABN)
            if not verified_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Name is required'
                }, status=400)
            
            if not verified_email:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Email is required'
                }, status=400)
            
            # Email format validation
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_regex, verified_email):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid email format'
                }, status=400)
            
            if not verified_bsb:
                return JsonResponse({
                    'status': 'error',
                    'message': 'BSB is required'
                }, status=400)
            
            # BSB should be 6 digits
            bsb_digits = verified_bsb.replace('-', '')
            if not bsb_digits.isdigit() or len(bsb_digits) != 6:
                return JsonResponse({
                    'status': 'error',
                    'message': 'BSB must be exactly 6 digits'
                }, status=400)
            
            if not verified_account:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Account Number is required'
                }, status=400)
            
            # Account should be at least 6 digits
            if not verified_account.isdigit() or len(verified_account) < 6:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Account Number must be at least 6 digits'
                }, status=400)
            
            if not verified_notes:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Notes are required'
                }, status=400)
            
            # Tax number (ABN) is optional, but if provided, must be 11 digits
            if verified_tax_number:
                tax_digits = verified_tax_number.replace(' ', '')
                if not tax_digits.isdigit() or len(tax_digits) != 11:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'ABN must be exactly 11 digits if provided'
                    }, status=400)
            
            # Get the contact
            contact = Contacts.objects.get(contact_pk=contact_pk)
            
            # Save verified details
            contact.verified_name = verified_name
            contact.verified_email = verified_email
            contact.verified_bank_bsb = bsb_digits  # Store without dash
            contact.verified_bank_account_number = verified_account
            contact.verified_tax_number = verified_tax_number.replace(' ', '') if verified_tax_number else ''
            contact.verified_notes = verified_notes
            contact.bank_details_verified = 1  # Mark as verified
            contact.save()
            
            logger.info(f"Successfully verified contact details for {contact.name} (PK: {contact_pk})")
            
            return JsonResponse({
                'status': 'success',
                'message': 'Contact details verified successfully',
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
            })
            
        except Contacts.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Contact not found'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            logger.error(f"Error verifying contact details: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'Unexpected error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Only POST method is allowed'
    }, status=405)


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
        contacts_response = requests.get(
            'https://api.xero.com/api.xro/2.0/Contacts?includeArchived=true',
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
        xero_contacts = contacts_data.get('Contacts', [])
        
        # Step 4: Process contacts - insert new ones and update existing ones
        new_contacts_count = 0
        updated_contacts_count = 0
        unchanged_contacts_count = 0
        
        for xero_contact in xero_contacts:
            contact_id = xero_contact.get('ContactID')
            
            # Extract contact data from Xero
            name = xero_contact.get('Name', '')
            email = xero_contact.get('EmailAddress', '')
            status = xero_contact.get('ContactStatus', '')
            
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
                
                # Compare and update if any field has changed
                updated = False
                if existing_contact.name != name:
                    existing_contact.name = name
                    updated = True
                if existing_contact.email != email:
                    existing_contact.email = email
                    updated = True
                if existing_contact.status != status:
                    existing_contact.status = status
                    updated = True
                if existing_contact.bank_details != bank_details:
                    existing_contact.bank_details = bank_details
                    updated = True
                if existing_contact.bank_bsb != bank_bsb:
                    existing_contact.bank_bsb = bank_bsb
                    updated = True
                if existing_contact.bank_account_number != bank_account_number:
                    existing_contact.bank_account_number = bank_account_number
                    updated = True
                if existing_contact.tax_number != tax_number:
                    existing_contact.tax_number = tax_number
                    updated = True
                
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
                    bank_details=bank_details,
                    bank_bsb=bank_bsb,
                    bank_account_number=bank_account_number,
                    bank_details_verified=0,
                    tax_number=tax_number
                )
                new_contacts_count += 1
                logger.info(f"Created new contact: {name} (ID: {contact_id})")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully pulled contacts from Xero',
            'details': {
                'total_xero_contacts': len(xero_contacts),
                'new_contacts_added': new_contacts_count,
                'contacts_updated': updated_contacts_count,
                'contacts_unchanged': unchanged_contacts_count
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
            
            # Build contact list with verified status
            contacts_list = []
            for contact in contacts:
                # Calculate verified status
                verified_status = 0  # Default: not verified
                
                # Check if any verified fields have data
                has_verified_data = any([
                    contact.verified_name,
                    contact.verified_email,
                    contact.verified_bank_bsb,
                    contact.verified_bank_account_number
                ])
                
                if has_verified_data:
                    # Check if verified fields match current fields
                    name_matches = contact.verified_name == contact.name
                    email_matches = contact.verified_email == contact.email
                    bsb_matches = contact.verified_bank_bsb == contact.bank_bsb
                    account_matches = contact.verified_bank_account_number == contact.bank_account_number
                    
                    if name_matches and email_matches and bsb_matches and account_matches:
                        verified_status = 1  # Verified and matches
                    else:
                        verified_status = 2  # Verified but data has changed
                
                contacts_list.append({
                    'contact_pk': contact.contact_pk,
                    'xero_instance_id': contact.xero_instance_id,
                    'xero_contact_id': contact.xero_contact_id,
                    'name': contact.name,
                    'email': contact.email,
                    'status': contact.status,
                    'bank_bsb': contact.bank_bsb,
                    'bank_account_number': contact.bank_account_number,
                    'tax_number': contact.tax_number,
                    'verified': verified_status,
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
    Update a contact's bank details and tax number in Xero using OAuth2 tokens.
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        email = data.get('email', '')
        bsb = data.get('bsb', '')
        account_number = data.get('account_number', '')
        tax_number = data.get('tax_number', '')
        
        # Get the contact
        contact = Contacts.objects.get(contact_pk=contact_pk, xero_instance_id=instance_pk)
        
        # Get Xero authentication
        xero_instance, access_token, tenant_id = get_xero_auth(instance_pk)
        if not xero_instance:
            return access_token  # This is the error response
        
        # Prepare update data for Xero
        bank_account_details = format_bank_details(bsb, account_number)
        
        update_data = {
            'Contacts': [{
                'ContactID': contact.xero_contact_id,
                'EmailAddress': email,
                'BankAccountDetails': bank_account_details,
                'TaxNumber': tax_number.replace(' ', '') if tax_number else ''
            }]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id} - Email: {email}, BSB: {bsb}, Account: {account_number}, Tax: {tax_number}")
        
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
        
        # Update local database
        contact.email = email
        contact.bank_bsb = bsb.replace('-', '')
        contact.bank_account_number = account_number
        contact.tax_number = tax_number.replace(' ', '')
        contact.bank_details = bank_account_details
        contact.save()
        
        logger.info(f"Successfully updated contact {contact.name} in database")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contact updated successfully',
            'contact': {
                'email': contact.email,
                'bank_bsb': contact.bank_bsb,
                'bank_account_number': contact.bank_account_number,
                'tax_number': contact.tax_number
            }
        })
    
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
