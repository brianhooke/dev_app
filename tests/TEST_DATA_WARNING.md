# ⚠️ TEST DATA WARNING

## Issue: Tests Modify Production Database

The current Playwright tests are modifying the actual database by:
- Selecting suppliers on invoices
- Filling in invoice numbers, NET, GST values
- Creating allocations
- Potentially sending invoices to Xero

**This is causing data corruption where invoices are getting unexpected supplier assignments.**

## Solutions

### Option 1: Use Separate Test Database (RECOMMENDED)
- Configure Django to use a test database when running tests
- Add `TEST_DATABASE` setting in Django settings
- Tests can modify data freely without affecting production

### Option 2: Read-Only Tests
- Rewrite tests to only verify UI behavior without modifying data
- Use assertions on existing data
- Don't fill forms or click save buttons

### Option 3: Cleanup After Tests
- Add `afterEach` hooks to revert all changes
- Store original values and restore them
- More complex and error-prone

## Immediate Action Required

**STOP RUNNING TESTS AGAINST PRODUCTION DATABASE**

The tests should be disabled or modified until a proper test database is configured.

## Files Affected
- `tests/bills-inbox.spec.js` - All tests modify invoice data
- `tests/bills-direct.spec.js` - All tests modify invoice data and allocations
