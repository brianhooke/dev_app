"""
AWS Lambda Function: Email Processor
Triggered by S3 when new email arrives
Parses email, extracts attachments, calls Django API
"""

import json
import boto3
import email
from email import policy
from email.parser import BytesParser
import os
import requests
from datetime import datetime
import base64

from xero_attachment_types import (
    is_allowed_xero_email_attachment_content_type,
    resolve_attachment_content_type,
)

s3 = boto3.client('s3')

# Django API endpoint (will be configured via Lambda environment variables)
DJANGO_API_URL = os.environ.get('DJANGO_API_URL', 'https://app.mason.build/api/receive_email/')
API_SECRET_KEY = os.environ.get('API_SECRET_KEY', 'your-secret-key-here')


def lambda_handler(event, context):
    """
    Main Lambda handler triggered by S3 email arrival
    """
    print(f"Event received: {json.dumps(event)}")
    
    for record in event['Records']:
        # Get S3 bucket and key from the event
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Processing email from s3://{bucket}/{key}")
        
        try:
            # Download email from S3
            response = s3.get_object(Bucket=bucket, Key=key)
            email_content = response['Body'].read()
            
            # Parse email
            msg = BytesParser(policy=policy.default).parsebytes(email_content)
            
            # Extract email data
            email_data = extract_email_data(msg, bucket, key)
            
            # Process attachments
            attachments = process_attachments(msg, bucket, key)
            email_data['attachments'] = attachments
            
            # Send to Django API
            send_to_django(email_data)
            
            print(f"Successfully processed email: {email_data['subject']}")
            
        except Exception as e:
            print(f"Error processing email {key}: {str(e)}")
            # Re-raise to trigger Lambda retry
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps('Email processed successfully')
    }


def extract_email_data(msg, bucket, s3_key):
    """
    Extract relevant data from email message
    """
    # Get email addresses
    from_addr = msg.get('From', '')
    to_addr = msg.get('To', '')
    cc_addr = msg.get('Cc', '')
    subject = msg.get('Subject', '')
    date_str = msg.get('Date', '')
    message_id = msg.get('Message-ID', '')
    
    # Parse date
    try:
        date = email.utils.parsedate_to_datetime(date_str)
    except:
        date = datetime.utcnow()
    
    # Extract body
    body_text = ""
    body_html = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain' and not body_text:
                body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            elif content_type == 'text/html' and not body_html:
                body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
    else:
        body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    
    return {
        'from_address': from_addr,
        'to_address': to_addr,
        'cc_address': cc_addr,
        'subject': subject,
        'body_text': body_text,
        'body_html': body_html,
        'received_at': date.isoformat(),
        'message_id': message_id,
        's3_bucket': bucket,
        's3_key': s3_key,
    }


def process_attachments(msg, bucket, email_key):
    """
    Extract and upload attachments to S3.
    MIME allowlist matches Xero Accounting / Files attachment expectations (see xero_attachment_types).
    Skips typical embedded HTML resources (Content-ID parts) unless they are real attachments.
    """
    attachments = []
    
    if not msg.is_multipart():
        return attachments
    
    attachment_counter = 0
    
    for part in msg.walk():
        # Skip non-attachment parts
        if part.get_content_maintype() == 'multipart':
            continue

        content_disposition = part.get('Content-Disposition', '') or ''
        cd_lower = content_disposition.lower()

        # Skip CID-embedded images used in HTML bodies (unless also a real attachment)
        if part.get('Content-ID') and 'attachment' not in cd_lower:
            continue

        if 'filename' not in cd_lower:
            continue
        if 'attachment' not in cd_lower and 'inline' not in cd_lower:
            continue

        filename = part.get_filename()
        if not filename:
            # Generate filename if none provided
            ext = part.get_content_subtype()
            filename = f"attachment_{attachment_counter}.{ext}"
            attachment_counter += 1

        declared_type = part.get_content_type()
        if not is_allowed_xero_email_attachment_content_type(declared_type, filename):
            print(
                f"Skipping attachment {declared_type!r} file={filename!r} "
                f"- not an allowed Xero-style bill attachment type"
            )
            continue

        # Get attachment content
        content = part.get_payload(decode=True)
        content_type = resolve_attachment_content_type(declared_type, filename)
        
        # Upload to S3 in attachments folder
        attachment_key = f"attachments/{email_key.replace('inbox/', '')}/{filename}"
        
        try:
            s3.put_object(
                Bucket=bucket,
                Key=attachment_key,
                Body=content,
                ContentType=content_type,
                Metadata={
                    'original-filename': filename,
                    'email-key': email_key
                }
            )
            
            attachments.append({
                'filename': filename,
                'content_type': content_type,
                'size_bytes': len(content),
                's3_bucket': bucket,
                's3_key': attachment_key,
            })
            
            print(f"Uploaded attachment: {filename} ({len(content)} bytes)")
            
        except Exception as e:
            print(f"Error uploading attachment {filename}: {str(e)}")
    
    return attachments


def send_to_django(email_data):
    """
    Send processed email data to Django API
    """
    headers = {
        'Content-Type': 'application/json',
        'X-API-Secret': API_SECRET_KEY
    }
    
    try:
        response = requests.post(
            DJANGO_API_URL,
            json=email_data,
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        print(f"Successfully sent to Django: {response.status_code}")
        
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Django API: {str(e)}")
        raise
