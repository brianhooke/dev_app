# 🎭 How to Run Playwright Tests

## ✅ Single Command - Everything Automated

```bash
npm run test:e2e
```

**That's it!** This command automatically:
1. ✅ Stops any running test server
2. ✅ Deletes old test database
3. ✅ Runs migrations
4. ✅ Seeds fresh test data
5. ✅ Starts test server
6. ✅ Runs all 12 Playwright tests
7. ✅ Stops test server when done

## 📊 Test Results

You should see:
- **12 tests running**
- **11-12 passing** (one may skip if no pre-allocated invoices)
- **Fresh database every time**
- **Production data completely safe**

## 🎨 Interactive UI Mode

For debugging and visual test running:

```bash
npm run test:e2e:ui
```

This opens the Playwright UI where you can:
- See all tests listed
- Run tests individually
- Watch browser automation live
- Debug failures step-by-step

## 📝 Other Commands

```bash
npm run test:e2e          # Headless (automated, best for CI)
npm run test:e2e:headed   # See browser while tests run
npm run test:e2e:ui       # Interactive UI (best for debugging)
npm run test:e2e:debug    # Step through each action
npm run test:report       # View last test report
```

## 🔄 How It Works

### Global Setup (automatic)
- Playwright runs `tests/global-setup.js` before tests
- Resets database to fresh state
- Starts Django test server
- Waits for server to be ready

### Tests Run
- All 12 tests execute with fresh data
- Tests can modify database safely
- Each test run starts with identical data

### Global Teardown (automatic)
- Playwright runs `tests/global-teardown.js` after tests
- Stops test server
- Cleans up

## 🎯 Best Practice Workflow

**Just run:**
```bash
npm run test:e2e
```

**Every single time** - the database resets automatically!

## ⚠️ Important Notes

1. **No manual setup needed** - everything is automated
2. **Fresh data every run** - tests always start with same state
3. **Production safe** - only touches `db_test.sqlite3`
4. **Server managed** - automatically started and stopped

## 🐛 If Tests Fail

1. **Check the error message** - Playwright shows exactly what failed
2. **Run in UI mode** - `npm run test:e2e:ui` to see what's happening
3. **Check test server** - should auto-start, but verify port 8000 is free
4. **View report** - `npm run test:report` for detailed failure info

## 📦 Test Data Created

Each test run creates:
- 1 user: `testuser` / `testpass123`
- 1 Xero instance: "Test Xero"
- 1 project: "Test Project"
- 2 suppliers: "Test Supplier 1", "Test Supplier 2" (marked as suppliers)
- 2 Xero accounts: "Test Account 1" (1000), "Test Account 2" (2000)
- 4 invoices: 2 in Inbox (status=-2), 2 in Direct (status=0)

## 🎉 Success!

When you see:
```
12 passed (17.1s)
```

All tests passed! Your code is working correctly and production data is safe.
