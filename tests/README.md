# Playwright Tests

## Quick Start

### 1. Start Django Server

```bash
python manage.py runserver
```

### 2. Run Tests

```bash
# Run all tests (headless)
npm test

# Run with browser visible (recommended for first time)
npm run test:headed

# Run interactive UI mode (best for debugging)
npm run test:ui
```

## Test Files

- **`bills-inbox.spec.js`** - Tests for Bills - Inbox functionality
- **`bills-direct.spec.js`** - Tests for Bills - Direct functionality

## What These Tests Cover

### v56 Bug Fixes

All tests verify bugs that were fixed in v56 to prevent regressions:

1. ✅ GST validation accepts 0 but rejects empty
2. ✅ Bills - Inbox Send button doesn't validate allocations
3. ✅ Bills - Direct Send button starts grey if invalid
4. ✅ PDF viewer height is fixed (not dependent on table rows)
5. ✅ Button color matches click handler validation

## Adding New Tests

See `TESTING_GUIDE.md` in the project root for detailed instructions.

### Quick Template

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/');
    // Setup code
  });

  test('should do something', async ({ page }) => {
    // Test code
    await expect(page.locator('#element')).toBeVisible();
  });
});
```

## Debugging

```bash
# Step through tests
npm run test:debug

# View last test report
npm run test:report
```

## Need Help?

Read the full `TESTING_GUIDE.md` in the project root!
