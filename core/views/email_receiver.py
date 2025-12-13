"""
API endpoint for receiving processed emails from Lambda
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.models import ReceivedEmail, EmailAttachment, Invoices
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

# API secret key for Lambda authentication - MUST be set in environment/settings
API_SECRET_KEY = getattr(settings, 'EMAIL_API_SECRET_KEY', None)
if not API_SECRET_KEY:
    logger.warning("EMAIL_API_SECRET_KEY not configured - email API will reject all requests")


@csrf_exempt
@require_http_methods(["POST"])
def receive_email(request):
    """
    API endpoint called by Lambda function when email is processed.
    Stores email and attachments in PostgreSQL.
    """
    # Verify API key
    api_key = request.headers.get('X-API-Secret', '')
    
    if not API_SECRET_KEY or api_key != API_SECRET_KEY:
        logger.warning(f"Unauthorized email API access attempt - keys don't match")
        return JsonResponse({
            'status': 'error',
            'message': 'Unauthorized'
        }, status=401)
    
    try:
        # Parse JSON payload from Lambda
        data = json.loads(request.body)
        
        # Extract email data
        message_id = data.get('message_id')
        
        # Check if email already exists (prevent duplicates)
        if ReceivedEmail.objects.filter(message_id=message_id).exists():
            logger.info(f"Email {message_id} already exists, skipping")
            return JsonResponse({
                'status': 'success',
                'message': 'Email already processed',
                'duplicate': True
            })
        
        # Parse received_at datetime
        received_at_str = data.get('received_at')
        try:
            received_at = datetime.fromisoformat(received_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError, TypeError):
            received_at = datetime.utcnow()
        
        # Create email record
        email = ReceivedEmail.objects.create(
            from_address=data.get('from_address', ''),
            to_address=data.get('to_address', ''),
            cc_address=data.get('cc_address', ''),
            subject=data.get('subject', ''),
            message_id=message_id,
            body_text=data.get('body_text', ''),
            body_html=data.get('body_html', ''),
            received_at=received_at,
            s3_bucket=data.get('s3_bucket', ''),
            s3_key=data.get('s3_key', ''),
            is_processed=False,
        )
        
        # Create attachment records
        attachments_data = data.get('attachments', [])
        attachments_created = []
        
        for att_data in attachments_data:
            # Check if this is a local test with base64 content
            base64_content = att_data.get('content')
            s3_bucket = att_data.get('s3_bucket', '')
            s3_key = att_data.get('s3_key', '')
            
            # If base64 content provided (local testing), save to local file
            if base64_content and settings.DEBUG:
                import base64
                import os
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                
                # Decode base64
                file_content = base64.b64decode(base64_content)
                
                # Create filename path
                filename = att_data.get('filename', 'unknown')
                file_path = f'test_attachments/{email.id}/{filename}'
                
                # Save file using Django's storage system
                saved_path = default_storage.save(file_path, ContentFile(file_content))
                
                # Use the saved path as s3_key for local files
                s3_bucket = 'local'
                s3_key = saved_path
                size_bytes = len(file_content)
            else:
                size_bytes = att_data.get('size_bytes', 0)
            
            attachment = EmailAttachment.objects.create(
                email=email,
                filename=att_data.get('filename', 'unknown'),
                content_type=att_data.get('content_type', 'application/octet-stream'),
                size_bytes=size_bytes,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
            )
            attachments_created.append(attachment.filename)
        
        logger.info(
            f"Received email: {email.subject[:50]} from {email.from_address} "
            f"with {len(attachments_created)} attachments"
        )
        
        # Auto-create Invoice entries for each attachment
        invoices_created = []
        for att_data in attachments_data:
            # Get the attachment object we just created
            attachment = EmailAttachment.objects.filter(
                email=email,
                filename=att_data.get('filename', 'unknown')
            ).first()
            
            if attachment:
                # Check if invoice already exists for this attachment (prevent duplicates)
                existing_invoice = Invoices.objects.filter(
                    email_attachment=attachment
                ).first()
                
                if not existing_invoice:
                    # Create new invoice entry
                    invoice = Invoices.objects.create(
                        received_email=email,
                        email_attachment=attachment,
                        auto_created=True,
                        invoice_status=-2,  # -2 = unprocessed email bill (shows in Bills modal)
                        invoice_type=0,     # Default type
                    )
                    invoices_created.append(invoice.invoice_pk)
                    logger.info(f"Auto-created Invoice #{invoice.invoice_pk} for attachment {attachment.filename}")
                else:
                    logger.info(f"Invoice already exists for attachment {attachment.filename}, skipping")
        
        # Mark email as processed if we created invoices
        if invoices_created:
            email.is_processed = True
            email.processing_notes = f"Auto-created {len(invoices_created)} invoice(s)"
            email.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Email received and stored',
            'email_id': email.id,
            'attachment_count': len(attachments_created),
            'attachments': attachments_created,
            'invoices_created': invoices_created,
            'invoices_count': len(invoices_created),
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in email API request: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Error processing received email: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_http_methods(["GET"])
def email_list(request):
    """
    Simple view to list received emails (for testing/debugging)
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    emails = ReceivedEmail.objects.all()[:50]  # Latest 50 emails
    
    data = []
    for email in emails:
        data.append({
            'id': email.id,
            'from': email.from_address,
            'to': email.to_address,
            'subject': email.subject,
            'received_at': email.received_at.isoformat(),
            'attachment_count': email.attachment_count,
            'is_processed': email.is_processed,
        })
    
    return JsonResponse({
        'count': len(data),
        'emails': data
    })
