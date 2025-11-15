#!/usr/bin/env python3
"""
Script to send test emails to the receive_email endpoint for testing Bills modal
Creates 3 emails with 3 PDF attachments each
"""

import requests
import json
import base64
from datetime import datetime, timedelta
import random

# Configuration
API_URL = "http://localhost:8000/core/api/receive_email/"
API_SECRET_KEY = "05817a8c12b4f2d5b173953b3a0ab58a70a2f18b84ceaed32326e7e87cf6ed0e"

# Sample supplier email addresses and names
suppliers = [
    {"email": "invoices@acmesupplies.com", "name": "ACME Supplies Ltd", "company": "ACME Supplies"},
    {"email": "billing@builderswarehouse.com", "name": "Builders Warehouse", "company": "Builders Warehouse"},
    {"email": "accounts@concreteplus.com.au", "name": "Concrete Plus Pty Ltd", "company": "Concrete Plus"},
]

# Sample invoice data
invoice_data = [
    {"invoice_no": "INV-2024-001", "net": 1250.00, "gst": 125.00},
    {"invoice_no": "INV-2024-002", "net": 3480.50, "gst": 348.05},
    {"invoice_no": "INV-2024-003", "net": 890.00, "gst": 89.00},
]

def create_simple_pdf_base64(invoice_no, supplier_name, net, gst):
    """Create a simple PDF in base64 format"""
    # Very basic PDF structure - minimal valid PDF
    pdf_content = f"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 700 Td
(INVOICE: {invoice_no}) Tj
0 -20 Td
(Supplier: {supplier_name}) Tj
0 -20 Td
(Net Amount: ${net:.2f}) Tj
0 -20 Td
(GST: ${gst:.2f}) Tj
0 -20 Td
(Total: ${net + gst:.2f}) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
567
%%EOF"""
    
    return base64.b64encode(pdf_content.encode()).decode()

def send_test_email(email_index):
    """Send a test email with 3 PDF attachments"""
    supplier = suppliers[email_index]
    base_date = datetime.now() - timedelta(days=random.randint(1, 10))
    
    # Generate a unique message ID
    message_id = f"test-email-{email_index + 1}-{int(base_date.timestamp())}@mason.build"
    
    # Create 3 attachments for this email
    attachments = []
    for i, inv_data in enumerate(invoice_data):
        pdf_content = create_simple_pdf_base64(
            inv_data['invoice_no'],
            supplier['company'],
            inv_data['net'],
            inv_data['gst']
        )
        
        attachments.append({
            'filename': f"{inv_data['invoice_no']}.pdf",
            'content': pdf_content,
            'content_type': 'application/pdf'
        })
    
    # Email body
    email_body_html = f"""
    <html>
    <body>
        <p>Dear Customer,</p>
        <p>Please find attached invoices for your recent purchases from {supplier['company']}.</p>
        <p>Attached invoices:</p>
        <ul>
            <li>{invoice_data[0]['invoice_no']} - ${invoice_data[0]['net'] + invoice_data[0]['gst']:.2f}</li>
            <li>{invoice_data[1]['invoice_no']} - ${invoice_data[1]['net'] + invoice_data[1]['gst']:.2f}</li>
            <li>{invoice_data[2]['invoice_no']} - ${invoice_data[2]['net'] + invoice_data[2]['gst']:.2f}</li>
        </ul>
        <p>Please process payment within 30 days.</p>
        <p>Best regards,<br>{supplier['name']}<br>Accounts Department</p>
    </body>
    </html>
    """
    
    email_body_text = f"""
    Dear Customer,
    
    Please find attached invoices for your recent purchases from {supplier['company']}.
    
    Attached invoices:
    - {invoice_data[0]['invoice_no']} - ${invoice_data[0]['net'] + invoice_data[0]['gst']:.2f}
    - {invoice_data[1]['invoice_no']} - ${invoice_data[1]['net'] + invoice_data[1]['gst']:.2f}
    - {invoice_data[2]['invoice_no']} - ${invoice_data[2]['net'] + invoice_data[2]['gst']:.2f}
    
    Please process payment within 30 days.
    
    Best regards,
    {supplier['name']}
    Accounts Department
    """
    
    # Prepare the email data
    email_data = {
        'message_id': message_id,
        'from_address': supplier['email'],
        'to_address': 'test@mail.mason.build',
        'subject': f'Invoice Batch {base_date.strftime("%Y-%m-%d")} - {supplier["company"]}',
        'body_html': email_body_html,
        'body_text': email_body_text,
        'received_date': base_date.isoformat(),
        'attachments': attachments
    }
    
    # Send to API
    headers = {
        'X-API-Secret': API_SECRET_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(API_URL, json=email_data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Email {email_index + 1} sent successfully!")
            print(f"   From: {supplier['email']}")
            print(f"   Subject: {email_data['subject']}")
            print(f"   Attachments: {len(attachments)}")
            print(f"   Response: {result}")
        else:
            print(f"❌ Error sending email {email_index + 1}: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Exception sending email {email_index + 1}: {str(e)}")
    
    print()

def main():
    print("=" * 60)
    print("Sending 3 test emails to test@mail.mason.build")
    print("Each email will have 3 PDF attachments")
    print("=" * 60)
    print()
    
    # Send 3 emails
    for i in range(3):
        send_test_email(i)
    
    print("=" * 60)
    print("Done! Check your Bills -> Inbox modal for new entries")
    print("=" * 60)

if __name__ == "__main__":
    main()
