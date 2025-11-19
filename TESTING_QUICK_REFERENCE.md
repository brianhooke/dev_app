# Playwright Testing - Quick Reference Card

## 🚀 Running Tests

```bash
# FIRST: Start Django server in another terminal
python manage.py runserver

# Run all tests (headless)
npm test

# Run with browser visible (see what's happening)
npm run test:headed

# Interactive UI mode (BEST for debugging)
npm run test:ui

# Debug mode (step through line by line)
npm run test:debug

# Run specific test file
npm run test:bills-inbox
npm run test:bills-direct

# View last test report
npm run test:report
```

## 📝 Common Test Patterns

### Navigate & Wait
```javascript
await page.goto('/dashboard/');
await page.waitForLoadState('networkidle');
await page.waitForSelector('#element', { state: 'visible' });
```

### Click & Fill
```javascript
await page.click('#button');
await page.fill('#input', 'value');
await page.selectOption('#select', { index: 1 });
```

### Find Elements
```javascript
page.locator('#id')                    // By ID
page.locator('.class')                 // By class
page.locator('text=Click me')          // By text
page.locator('#table tbody tr').first() // First element
row.locator('.button')                 // Within parent
```

### Assertions
```javascript
await expect(element).toBeVisible();
await expect(element).toBeHidden();
await expect(element).toBeEnabled();
await expect(element).toBeDisabled();
await expect(element).toHaveText('Expected');
await expect(element).toHaveClass(/btn-success/);
await expect(element).toHaveCount(5);
```

## 🐛 Debugging Tips

### 1. Use UI Mode (Best!)
```bash
npm run test:ui
```
- See each step
- Time-travel through test
- Inspect DOM at any point

### 2. Add Screenshots
```javascript
await page.screenshot({ path: 'debug.png' });
```

### 3. Pause Execution
```javascript
await page.pause(); // Opens Playwright Inspector
```

### 4. Console Logs
```javascript
page.on('console', msg => console.log('Browser:', msg.text()));
```

## ✅ Current Test Coverage

### Bills - Inbox (5 tests)
- ✅ GST accepts 0
- ✅ GST rejects empty
- ✅ No allocation validation
- ✅ PDF viewer fixed height
- ✅ Button state matches validation

### Bills - Direct (6 tests)
- ✅ Button starts grey if invalid
- ✅ Button turns green when valid
- ✅ Pull Xero button visible
- ✅ PDF viewer fixed height
- ✅ Allocations section visible
- ✅ Validates allocations

## 📚 Full Documentation

- **`TESTING_GUIDE.md`** - Complete guide with examples
- **`tests/README.md`** - Quick start for tests directory
- **[Playwright Docs](https://playwright.dev/)** - Official documentation

## 🎯 When to Write Tests

1. **After fixing a bug** - Prevent it from coming back
2. **Before deploying** - Catch issues early
3. **For critical flows** - Login, checkout, data submission
4. **When refactoring** - Ensure nothing breaks

## 💡 Pro Tips

- Run `npm run test:ui` first time to see tests in action
- Use `test.only()` to run single test while developing
- Add `// Bug: ...` comments to explain why test exists
- Keep tests focused - one thing per test
- Use descriptive test names

---

**Need help?** Read `TESTING_GUIDE.md` for detailed examples!
