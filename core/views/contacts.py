import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Contacts

logger = logging.getLogger(__name__)


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
