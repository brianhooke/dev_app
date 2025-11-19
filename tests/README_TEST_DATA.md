# Test Data Setup for Playwright Tests

## Overview

Playwright tests require bills data to test Bills - Inbox and Bills - Direct functionality.

## Method 1: Send Test Emails (Recommended)

Send emails with PDF attachments to `test@mail.mason.build` to automatically generate test bills.

### Using the Python Script

```bash
# Install dependencies
pip install reportlab

# Set SMTP credentials
export SMTP_SERVER='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USER='your-email@gmail.com'
export SMTP_PASSWORD='your-app-password'
export FROM_EMAIL='your-email@gmail.com'

# Run the script
python tests/generate_test_bills.py
```

### Manual Email Method

1. Create a simple invoice PDF
2. Send email to `test@mail.mason.build` with:
   - Subject: "Invoice from Test Supplier"
   - Attachment: invoice.pdf
   - Body: Invoice details
3. Wait 2-3 minutes for processing
4. Bills should appear in Bills - Inbox

## Method 2: Create Bills Directly in Database

If you have Django admin access:

1. Go to Django admin
2. Create Invoice records with:
   - **Bills - Inbox**: `invoice_status = -2`
   - **Bills - Direct**: `invoice_status = 0`
3. Ensure bills have:
   - Xero instance
   - Supplier (contact)
   - Invoice number
   - Net and GST amounts
   - PDF attachment

## Required Test Data

### Bills - Inbox (status = -2)
- Minimum 3 bills
- Various suppliers
- Different amounts
- All with PDF attachments

### Bills - Direct (status = 0)
- Minimum 3 bills
- Xero instance assigned
- No project assigned
- All with PDF attachments

## Verifying Test Data

Before running tests, verify:

```bash
# Start Django server
python manage.py runserver

# Open browser to http://127.0.0.1:8000/
# Click Bills > Inbox - should see bills
# Click Bills > Direct - should see bills
```

## Running Tests

Once test data is ready:

```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Run specific suite
npm run test:bills-inbox
npm run test:bills-direct
```

## Cleaning Up Test Data

After testing, you can:
1. Archive test bills via the UI
2. Delete from Django admin
3. Or leave them for future test runs
