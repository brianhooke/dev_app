"""
Contacts views.

This module handles contact-related views including the contacts table configuration.
Contacts uses allocations_layout.html with hide_viewer=True and hide_allocations=True
to display a full-width single table.

Endpoints:
- GET  /core/get_contacts_by_instance/{pk}/ - Get contacts for instance
- POST /core/verify_contact_details/{contact_pk}/ - Save verified details

Note: Xero API functions (pull_xero_contacts, create_contact, create_supplier,
update_contact_details, update_contact_status, pull_xero_tracking_categories)
have been moved to xero.py.
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from core.models import Contacts
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
