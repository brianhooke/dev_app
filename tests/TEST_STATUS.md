# Playwright Test Status

## Current Status: Ready to Test ✅

### Test Data Created
- ✅ 9 invoices generated using `test_email_sender.py`
- ✅ 3 emails with 3 PDFs each
- ✅ All bills have status -2 (Bills - Inbox)

**To generate more test data:**
```bash
python3 test_email_sender.py
```

**Note:** PDFs won't display in viewer (no S3 URLs in local testing), but bills data exists for Playwright tests.

### Test Fixes Applied
1. ✅ Fixed duplicate ID selectors
2. ✅ Added dropdown population waits
3. ✅ Fixed allocations section selector

### Known Issues

#### 1. Duplicate HTML IDs (App Issue, Not Test Issue)
The following IDs appear multiple times in the DOM:
- `#viewerSection`
- `#pullXeroAccountsBtn`
- `#allocationsSection`

**Workaround:** Tests use specific selectors like `#billsInboxSection #viewerSection`

**Recommendation:** Fix the HTML to use unique IDs or classes instead.

#### 2. No Bills - Direct Test Data
Currently all test bills have status -2 (Inbox). Bills - Direct tests need bills with status 0.

**To fix:**
1. Go to Django admin
2. Change some invoice status from -2 to 0
3. Ensure they have xero_instance set
4. Ensure project_pk is NULL

Or run the email sender script again and manually move bills to Direct mode via the UI.

## Running Tests

```bash
# Make sure Django is running
python manage.py runserver

# Run tests with UI (recommended)
npm run test:ui

# Or run headless
npm test
```

## Expected Results

### Bills - Inbox (5 tests)
- Should mostly pass now with test data
- May need to adjust for specific validation rules

### Bills - Direct (7 tests)  
- Will fail until we have status=0 bills
- Need to create Direct mode test data

## Next Steps

1. Create Bills - Direct test data (status=0)
2. Run tests and fix any remaining issues
3. Consider fixing duplicate ID issue in HTML
4. Add more comprehensive test coverage
