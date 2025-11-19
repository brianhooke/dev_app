# Playwright Tests - Quick Start

## The Problem

All 11 tests are failing because **there's no test data**. The tests expect bills in the database but the tables are empty.

## The Solution

Send test emails to generate bills automatically.

## Steps to Fix

### 1. Set up email credentials

```bash
export SMTP_SERVER='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USER='your-email@gmail.com'
export SMTP_PASSWORD='your-app-password'
export FROM_EMAIL='your-email@gmail.com'
```

**Note:** For Gmail, you need an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

### 2. Generate test bills

```bash
python tests/generate_test_bills.py
```

This will send 6 test invoices to `test@mail.mason.build`:
- 3 for Bills - Inbox (status -2)
- 3 for Bills - Direct (status 0)

### 3. Wait for processing

Wait 2-3 minutes for the emails to be processed and bills to appear in the system.

### 4. Verify bills are loaded

```bash
# Start Django server
python manage.py runserver

# Open http://127.0.0.1:8000/
# Click Bills > Inbox - should see 3+ bills
# Click Bills > Direct - should see 3+ bills
```

### 5. Run tests

```bash
# Run all tests with UI (recommended)
npm run test:ui

# Or run headless
npm test

# Or run specific suite
npm run test:bills-inbox
npm run test:bills-direct
```

## Alternative: Manual Email

If the script doesn't work, manually send emails:

1. Create a simple PDF invoice
2. Email to: `test@mail.mason.build`
3. Subject: "Invoice from Test Supplier"
4. Attach the PDF
5. Wait 2-3 minutes
6. Check Bills - Inbox

Send at least 3 emails for Inbox and 3 for Direct testing.

## Current Test Status

- **11 tests failing** - No test data (expected)
- **1 test passing** - "Send to Xero button: starts grey when validation fails"
  - This test passes because it only checks initial state, doesn't need data

Once test data is loaded, all 12 tests should pass! ✅
