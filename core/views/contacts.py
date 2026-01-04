"""
Contacts views.

This module handles contact-related views including the contacts table configuration.
Contacts uses allocations_layout.html with hide_viewer=True and hide_allocations=True
to display a full-width single table.

Endpoints:
- GET  /core/get_contacts_by_instance/{pk}/ - Get contacts for instance
- POST /core/pull_xero_contacts/{pk}/ - Sync contacts from Xero
- POST /core/create_contact/{pk}/ - Create contact in Xero + DB
- POST /core/update_contact_details/{pk}/{contact_pk}/ - Update contact
- POST /core/verify_contact_details/{contact_pk}/ - Save verified details
- POST /core/update_contact_status/{pk}/{contact_pk}/ - Archive/unarchive contact
"""

import json
import logging
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from core.models import Contacts
from core.views.xero import get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors
from core.validators import validate_email, validate_bsb, validate_account_number, validate_abn, validate_required_field

logger = logging.getLogger(__name__)


# Response helper functions
def error_response(message, status=400):
    """Standardized error response format."""
    return JsonResponse({'status': 'error', 'message': message}, status=status)

def success_response(message, data=None):
    """Standardized success response format."""
    response = {'status': 'success', 'message': message}
    if data:
        response.update(data)
    return JsonResponse(response)


def get_contacts_config():
    """
    Get the configuration for the contacts section.
    Returns a dict with all context variables needed for allocations_layout.html.
    """
    return {
        'section_id': 'contacts',
        'main_table_columns': [
            {'header': 'Name', 'width': '22%', 'sortable': True},
            {'header': 'First Name', 'width': '9%', 'sortable': True},
            {'header': 'Last Name', 'width': '9%', 'sortable': True},
            {'header': 'Email', 'width': '20%', 'sortable': True},
            {'header': 'BSB', 'width': '8%', 'sortable': True},
            {'header': 'Account', 'width': '8%', 'sortable': True},
            {'header': 'ABN', 'width': '10%', 'sortable': True},
            {'header': 'Verify', 'width': '7%', 'class': 'col-action-first'},
            {'header': 'Update', 'width': '7%', 'class': 'col-action'},
        ],
        'hide_viewer': True,
        'hide_allocations': True,
    }


# Backward compatibility - returns just columns list
def get_contacts_columns():
    """
    Get the column definitions for the contacts table.
    Returns a list of column dictionaries with header, width, and optional class.
    """
    return get_contacts_config()['main_table_columns']


# ============================================
# CONTACT ENDPOINTS
# ============================================

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
        
        # Fetch contacts from Xero API (includes archived contacts)
        # IMPORTANT: Using paging ensures ContactPersons field is populated
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
        
        # Process contacts - insert new ones and update existing ones
        new_contacts_count = 0
        updated_contacts_count = 0
        unchanged_contacts_count = 0
        contact_person_updates = 0
        
        for xero_contact in xero_contacts:
            contact_id = xero_contact.get('ContactID')
            
            # Extract contact data from Xero
            name = xero_contact.get('Name', '')
            email = xero_contact.get('EmailAddress', '')
            status = xero_contact.get('ContactStatus', '')
            first_name = xero_contact.get('FirstName', '')
            last_name = xero_contact.get('LastName', '')
            
            # Parse bank account details
            bank_account_details = xero_contact.get('BankAccountDetails', '')
            bank_bsb = ''
            bank_account_number = ''
            
            if bank_account_details:
                cleaned = bank_account_details.replace(' ', '').replace('-', '')
                if len(cleaned) >= 6:
                    bank_bsb = cleaned[:6]
                    bank_account_number = cleaned[6:]
                else:
                    bank_account_number = cleaned
            
            bank_details = bank_account_details
            tax_number = xero_contact.get('TaxNumber', '')
            
            # Check if contact already exists for this Xero instance
            try:
                existing_contact = Contacts.objects.get(xero_contact_id=contact_id, xero_instance=xero_instance)
                
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
                for field, value in fields_to_update.items():
                    current_value = getattr(existing_contact, field)
                    if current_value != value:
                        setattr(existing_contact, field, value)
                        updated = True
                        if field in ['first_name', 'last_name']:
                            contact_person_updates += 1
                
                if updated:
                    existing_contact.save()
                    updated_contacts_count += 1
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
                    'verified': contact.verified_status,
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
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
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
                'FirstName': first_name if first_name else '',
                'LastName': last_name if last_name else '',
                'EmailAddress': email,
                'BankAccountDetails': bank_account_details,
                'TaxNumber': tax_number.replace(' ', '') if tax_number else ''
            }]
        }
        
        logger.info(f"Creating contact - Name: {name}, Email: {email}")
        
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
        
        if create_response.status_code != 200:
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
            first_name=first_name if first_name else None,
            last_name=last_name if last_name else None,
            email=email,
            status=contact_status,
            bank_bsb=bsb.replace('-', '') if bsb else '',
            bank_account_number=account_number,
            tax_number=tax_number.replace(' ', '') if tax_number else '',
            bank_details=bank_account_details,
            checked=0
        )
        new_contact.save()
        
        logger.info(f"Successfully created contact {name} with ID {new_contact.contact_pk}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Contact created successfully',
            'contact': {
                'contact_pk': new_contact.contact_pk,
                'name': new_contact.name,
                'first_name': new_contact.first_name,
                'last_name': new_contact.last_name,
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
        name = data.get('name', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
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
        
        # Prepare update data for Xero - only include provided fields
        xero_contact_data = {
            'ContactID': contact.xero_contact_id
        }
        
        if name:
            xero_contact_data['Name'] = name
        if first_name:
            xero_contact_data['FirstName'] = first_name
        if last_name:
            xero_contact_data['LastName'] = last_name
        if email:
            xero_contact_data['EmailAddress'] = email
        
        bank_account_details = None
        if bsb or account_number:
            bank_account_details = format_bank_details(bsb, account_number)
            xero_contact_data['BankAccountDetails'] = bank_account_details
        
        if tax_number:
            xero_contact_data['TaxNumber'] = tax_number.replace(' ', '')
        
        update_data = {
            'Contacts': [xero_contact_data]
        }
        
        logger.info(f"Updating contact {contact.xero_contact_id}")
        
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
        
        if update_response.status_code != 200:
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
        if bank_account_details:
            contact.bank_details = bank_account_details
        
        contact.save()
        
        logger.info(f"Successfully updated contact {contact.name}")
        
        return JsonResponse({
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
        archive = data.get('archive', False)
        
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
