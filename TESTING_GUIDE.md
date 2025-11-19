# Testing Guide - Playwright End-to-End Tests

## Overview

This project uses **Playwright** for end-to-end (E2E) testing to prevent regression bugs and ensure features work correctly before deployment.

## Why Playwright?

- ✅ **Catches Integration Bugs** - Tests the full user flow (click → fill form → submit)
- ✅ **Multi-Browser** - Automatically tests Chrome, Firefox, Safari
- ✅ **Great Debugging** - Screenshots, videos, trace viewer
- ✅ **Prevents Regressions** - Tests ensure old bugs don't come back

## Setup

### Installation (Already Done)

```bash
npm install -D @playwright/test
npx playwright install
```

### Project Structure

```
dev_app/
├── tests/                      # Test files
│   ├── bills-inbox.spec.js    # Bills - Inbox tests
│   ├── bills-direct.spec.js   # Bills - Direct tests
│   └── ...                     # More test files
├── playwright.config.js        # Playwright configuration
├── package.json                # NPM scripts for running tests
└── TESTING_GUIDE.md           # This file
```

## Running Tests

### Prerequisites

**IMPORTANT**: Django dev server must be running before tests!

```bash
# Terminal 1: Start Django dev server
python manage.py runserver

# Terminal 2: Run tests
npm test
```

### Test Commands

```bash
# Run all tests (headless mode)
npm test

# Run tests with browser visible (headed mode)
npm run test:headed

# Run tests with interactive UI (best for debugging)
npm run test:ui

# Run tests in debug mode (step through each action)
npm run test:debug

# Run specific test file
npm run test:bills-inbox
npm run test:bills-direct

# View last test report
npm run test:report
```

## Writing Tests

### Test Structure

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Feature Name', () => {
  
  test.beforeEach(async ({ page }) => {
    // Setup: Navigate to page, login, etc.
    await page.goto('/dashboard/');
  });

  test('should do something specific', async ({ page }) => {
    // Arrange: Set up test data
    await page.click('#someButton');
    
    // Act: Perform action
    await page.fill('#inputField', 'test value');
    await page.click('#submitButton');
    
    // Assert: Verify result
    await expect(page.locator('#result')).toHaveText('Expected text');
  });
});
```

### Common Patterns

#### Waiting for Elements

```javascript
// Wait for element to be visible
await page.waitForSelector('#elementId', { state: 'visible' });

// Wait for network to be idle
await page.waitForLoadState('networkidle');

// Wait for specific time (use sparingly)
await page.waitForTimeout(500);
```

#### Selecting Elements

```javascript
// By ID
page.locator('#elementId')

// By class
page.locator('.className')

// By text
page.locator('text=Button Text')

// First/nth element
page.locator('.item').first()
page.locator('.item').nth(2)

// Within a parent
const row = page.locator('#table tbody tr').first();
const button = row.locator('.send-btn');
```

#### Form Interactions

```javascript
// Fill text input
await page.fill('#inputId', 'value');

// Select dropdown
await page.selectOption('#selectId', 'optionValue');
await page.selectOption('#selectId', { index: 1 });

// Click button
await page.click('#buttonId');

// Check checkbox
await page.check('#checkboxId');
```

#### Assertions

```javascript
// Element visibility
await expect(element).toBeVisible();
await expect(element).toBeHidden();

// Element state
await expect(element).toBeEnabled();
await expect(element).toBeDisabled();

// Text content
await expect(element).toHaveText('Expected');
await expect(element).toContainText('Partial');

// CSS classes
await expect(element).toHaveClass(/btn-success/);

// Attributes
await expect(element).toHaveAttribute('data-id', '123');

// Count
await expect(page.locator('.item')).toHaveCount(5);
```

## Test Coverage - Current Tests

### Bills - Inbox Tests (`bills-inbox.spec.js`)

1. **GST validation: accepts 0 value**
   - Verifies GST field accepts 0 for GST-free invoices
   - Bug fixed: v56

2. **GST validation: rejects empty value**
   - Verifies GST field cannot be empty
   - Bug fixed: v56

3. **Send button: does not validate allocations**
   - Verifies Bills - Inbox doesn't check allocation validation
   - Bug fixed: v56

4. **PDF viewer: maintains height regardless of table rows**
   - Verifies PDF viewer has fixed height
   - Bug fixed: v56

5. **Send button validation: matches click handler validation**
   - Verifies button color matches actual validation state
   - Bug fixed: v56

### Bills - Direct Tests (`bills-direct.spec.js`)

1. **Send to Xero button: starts grey when validation fails**
   - Verifies button starts disabled/grey on page load
   - Bug fixed: v56

2. **Send to Xero button: turns green only when all fields valid**
   - Verifies button only enables after all validation passes
   - Bug fixed: v56

3. **Pull Xero Accounts button: visible in Direct mode**
   - Verifies button is visible at bottom of page
   - Bug fixed: v56

4. **PDF viewer: maintains height in Direct mode**
   - Verifies PDF viewer height with allocations visible
   - Bug fixed: v56

5. **Allocations section: visible in Direct mode**
   - Verifies allocations table is shown

6. **Send to Xero: validates allocations in Direct mode**
   - Verifies Direct mode DOES check allocations

## Best Practices

### 1. Test One Thing Per Test

❌ **Bad:**
```javascript
test('bills workflow', async ({ page }) => {
  // Tests 10 different things
});
```

✅ **Good:**
```javascript
test('GST accepts 0', async ({ page }) => {
  // Tests only GST = 0 validation
});

test('GST rejects empty', async ({ page }) => {
  // Tests only empty GST validation
});
```

### 2. Use Descriptive Test Names

❌ **Bad:**
```javascript
test('test 1', async ({ page }) => { ... });
```

✅ **Good:**
```javascript
test('Send button: does not validate allocations in Inbox mode', async ({ page }) => { ... });
```

### 3. Add Comments for Bug Context

```javascript
test('GST validation: accepts 0 value', async ({ page }) => {
  // This test verifies that GST field accepts 0 (for GST-free invoices)
  // Bug: Previously rejected 0 as invalid (fixed in v56)
  ...
});
```

### 4. Use beforeEach for Setup

```javascript
test.describe('Bills - Inbox', () => {
  test.beforeEach(async ({ page }) => {
    // Common setup for all tests
    await page.goto('/dashboard/');
    await page.click('#billsInboxLink');
  });

  test('test 1', async ({ page }) => {
    // Already on Bills - Inbox page
  });
});
```

### 5. Handle Async Properly

❌ **Bad:**
```javascript
page.click('#button'); // Missing await!
```

✅ **Good:**
```javascript
await page.click('#button');
```

## Debugging Tests

### 1. Run in Headed Mode

See the browser while tests run:
```bash
npm run test:headed
```

### 2. Use UI Mode (Recommended)

Interactive test runner with time-travel debugging:
```bash
npm run test:ui
```

### 3. Use Debug Mode

Step through test line by line:
```bash
npm run test:debug
```

### 4. Add Screenshots

```javascript
await page.screenshot({ path: 'debug-screenshot.png' });
```

### 5. Check Console Logs

```javascript
page.on('console', msg => console.log('Browser log:', msg.text()));
```

### 6. Pause Execution

```javascript
await page.pause(); // Opens Playwright Inspector
```

## CI/CD Integration (Future)

### GitHub Actions Example

```yaml
name: Playwright Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - uses: actions/setup-python@v4
      
      - name: Install dependencies
        run: |
          npm install
          pip install -r requirements.txt
      
      - name: Install Playwright
        run: npx playwright install --with-deps
      
      - name: Run Django migrations
        run: python manage.py migrate
      
      - name: Start Django server
        run: python manage.py runserver &
      
      - name: Run tests
        run: npm test
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

## When to Write Tests

### Always Write Tests For:

1. **Bug Fixes** - Prevent regression
2. **Critical User Flows** - Login, checkout, data submission
3. **Complex Features** - Multi-step workflows
4. **Frequently Broken Features** - Areas with history of bugs

### Example Workflow:

1. **Bug Reported**: "Send button shows allocation error in Bills - Inbox"
2. **Write Failing Test**: Test that reproduces the bug
3. **Fix Bug**: Make code changes
4. **Test Passes**: Verify fix works
5. **Deploy**: Test prevents future regressions

## Test Data Management

### Option 1: Use Fixtures (Recommended)

Create test data in Django fixtures:

```bash
python manage.py dumpdata app.Model --indent 2 > tests/fixtures/test_data.json
```

Load in tests:
```javascript
test.beforeEach(async ({ page }) => {
  // Load fixture via Django management command or API
});
```

### Option 2: Create via API

```javascript
test.beforeEach(async ({ request }) => {
  await request.post('/api/create-test-bill/', {
    data: { ... }
  });
});
```

### Option 3: Use Existing Data

Test against existing development database (be careful with modifications).

## Troubleshooting

### Tests Fail Locally But Pass on CI

- Check Django server is running
- Verify database has test data
- Check for timing issues (add waits)

### Tests Are Flaky (Sometimes Pass, Sometimes Fail)

- Add explicit waits instead of `waitForTimeout`
- Use `waitForSelector` with proper states
- Check for race conditions

### Tests Are Slow

- Run tests in parallel (default)
- Use `test.describe.configure({ mode: 'parallel' })`
- Optimize beforeEach setup

### Element Not Found

- Check selector is correct
- Add `await page.waitForSelector()`
- Verify element is actually rendered

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright API Reference](https://playwright.dev/docs/api/class-playwright)
- [Debugging Guide](https://playwright.dev/docs/debug)

## Next Steps

1. **Run Tests Locally**: `npm run test:ui`
2. **Write Tests for New Features**: Before deploying
3. **Set Up CI/CD**: Run tests on every push
4. **Expand Coverage**: Add tests for Contacts, Xero, etc.

---

**Remember**: Tests are living documentation. Keep them updated as features change!
