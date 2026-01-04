#!/usr/bin/env python3
"""
Local Email Testing Script

Simulates Lambda sending an email to your local Django server.
Use this for testing email processing without deploying or using ngrok.

Usage:
    python test_email_locally.py
"""

import requests
import json
from datetime import datetime

# Local server URL
LOCAL_API_URL = "http://localhost:8000/core/api/receive_email/"

# API secret key (must match your local settings)
API_SECRET_KEY = "change-me-in-production-use-strong-random-key"

# Sample email data
email_data = {
    "message_id": f"test-local-{int(datetime.now().timestamp())}",
    "from_address": "supplier@example.com",
    "to_address": "test@mail.mason.build",
    "cc_address": "",
    "subject": "Test Invoice - Local Testing",
    "body_text": "Please find attached the invoice for recent work.\n\nThank you!",
    "body_html": "<p>Please find attached the invoice for recent work.</p><p>Thank you!</p>",
    "received_at": datetime.utcnow().isoformat() + "Z",
    "s3_bucket": "dev-app-emails",
    "s3_key": "test-inbox/sample-email",
    "attachments": [
        {
            "filename": "invoice-12345.pdf",
            "content_type": "application/pdf",
            "size_bytes": 125000,
            "s3_bucket": "dev-app-emails",
            "s3_key": "attachments/test/invoice-12345.pdf"
        },
        {
            "filename": "receipt.pdf",
            "content_type": "application/pdf",
            "size_bytes": 85000,
            "s3_bucket": "dev-app-emails",
            "s3_key": "attachments/test/receipt.pdf"
        }
    ]
}

def test_local_email():
    """Send test email to local Django server"""
    
    print("=" * 60)
    print("LOCAL EMAIL TESTING")
    print("=" * 60)
    print(f"\nSending test email to: {LOCAL_API_URL}")
    print(f"From: {email_data['from_address']}")
    print(f"To: {email_data['to_address']}")
    print(f"Subject: {email_data['subject']}")
    print(f"Attachments: {len(email_data['attachments'])}")
    print("-" * 60)
    
    try:
        response = requests.post(
            LOCAL_API_URL,
            headers={
                "Content-Type": "application/json",
                "X-API-Secret": API_SECRET_KEY
            },
            json=email_data,
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 60)
            print("✅ SUCCESS!")
            print("=" * 60)
            print(f"Email ID: {result.get('email_id')}")
            print(f"Attachments Saved: {result.get('attachment_count')}")
            print(f"Invoices Created: {result.get('invoices_count')}")
            print(f"Invoice IDs: {result.get('invoices_created')}")

            # Simulate moving invoices from inbox to trigger recent activity
            if result.get('invoices_created'):
                print(f"\n🔄 Simulating 'move from inbox' action for recent activity...")
                import django
                import os
                os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dev_app.settings.local')
                django.setup()
                
                from core.models import Bills
                from django.utils import timezone
                import time
                
                # Update the invoices to simulate moving from inbox
                invoices = Bills.objects.filter(bill_pk__in=result['invoices_created'])
                for invoice in invoices:
                    # Update status and timestamp to simulate moving from inbox
                    invoice.bill_status = 0  # Move to Direct status
                    invoice.updated_at = timezone.now()
                    invoice.save()
                    print(f"  ✓ Moved invoice {invoice.bill_pk} from inbox")
                
                print(f"✅ Recent activity entries created!")
            print("\nCheck your local admin:")
            print("  http://localhost:8000/admin/core/receivedemail/")
            print("  http://localhost:8000/admin/core/invoices/?auto_created__exact=1")
        else:
            print("\n" + "=" * 60)
            print("❌ ERROR")
            print("=" * 60)
            
    except requests.exceptions.ConnectionError:
        print("\n" + "=" * 60)
        print("❌ CONNECTION ERROR")
        print("=" * 60)
        print("\nCouldn't connect to local server!")
        print("Make sure Django is running:")
        print("  python manage.py runserver 8000")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test_local_email()
