# Test Database Setup for E2E Tests

## Overview

Playwright E2E tests now run against a **separate test database** (`db_test.sqlite3`) to avoid modifying production data.

## Quick Start

### First Time Setup

```bash
# 1. Create and seed test database
npm run test:setup

# 2. Start test server (in separate terminal)
npm run test:server

# 3. Run tests (in another terminal)
npm run test:e2e
```

### Daily Workflow

```bash
# Terminal 1: Start test server
npm run test:server

# Terminal 2: Run tests
npm run test:e2e          # Headless
npm run test:e2e:ui       # Interactive UI (recommended)
npm run test:e2e:headed   # See browser
npm run test:e2e:debug    # Step-by-step debugging
```

## Available Commands

### Setup & Database

- `npm run test:setup` - Create test database and seed with test data
- `npm run test:reset` - Delete test database and recreate from scratch
- `npm run test:server` - Start Django server with test database

### Running Tests

- `npm run test:e2e` - Run all tests (headless)
- `npm run test:e2e:ui` - Interactive test UI (best for development)
- `npm run test:e2e:headed` - Run with visible browser
- `npm run test:e2e:debug` - Debug mode with Playwright Inspector
- `npm run test:bills-inbox` - Run only Bills Inbox tests
- `npm run test:bills-direct` - Run only Bills Direct tests
- `npm run test:report` - View last test report

### Safety

- `npm test` - **BLOCKED** - Shows warning to use `test:e2e` instead

## Test Data

The test database includes:

- **1 User**: `testuser` / `testpass123`
- **1 Xero Instance**: "Test Xero Instance"
- **2 Suppliers**: "Test Supplier 1", "Test Supplier 2"
- **1 Project**: "Test Project"
- **2 Xero Accounts**: "Test Account 1", "Test Account 2"
- **4 Invoices**:
  - 2 in Inbox (status=-2, no data filled)
  - 1 in Direct with valid allocations (status=0, green button)
  - 1 in Direct without allocations (status=0, grey button)

## File Structure

```
dev_app/
├── dev_app/settings/
│   └── test.py              # Test database configuration
├── tests/
│   ├── seed_test_data.py    # Seeds test database
│   ├── bills-inbox.spec.js  # Inbox tests
│   └── bills-direct.spec.js # Direct tests
├── db_test.sqlite3          # Test database (gitignored)
└── media_test/              # Test media files (gitignored)
```

## Important Notes

### ✅ Safe to Modify

Tests can now freely:
- Select suppliers
- Fill invoice fields
- Create allocations
- Click "Send to Xero"
- Delete invoices

**All changes only affect the test database!**

### 🔄 Resetting Data

If tests corrupt the test database:

```bash
npm run test:reset
```

This will:
1. Delete `db_test.sqlite3`
2. Run migrations
3. Seed fresh test data

### 🚫 Production Database

The production database (`db.sqlite3`) is **never touched** by tests.

To run the normal development server:

```bash
python manage.py runserver  # Uses db.sqlite3
```

## Troubleshooting

### Tests fail with "No bills found"

The test database needs to be seeded:

```bash
npm run test:setup
```

### Test server shows wrong database

Check the console output when starting the server. You should see:

```
============================================================
🧪 RUNNING IN TEST MODE
📁 Test Database: /path/to/db_test.sqlite3
📁 Test Media: /path/to/media_test
============================================================
```

If you don't see this, make sure you're using:

```bash
npm run test:server
```

Not:

```bash
python manage.py runserver  # Wrong - uses production DB
```

### Want to inspect test database

```bash
# Open test database in SQLite
sqlite3 db_test.sqlite3

# Or use Django shell with test settings
python manage.py shell --settings=dev_app.settings.test
```

## CI/CD Integration

For automated testing in CI/CD:

```bash
# In CI pipeline
npm run test:setup
npm run test:server &
sleep 5  # Wait for server to start
npm run test:e2e
```

## Benefits

✅ **Safe** - Never modifies production data  
✅ **Fast** - SQLite test database is quick  
✅ **Repeatable** - Fresh data every time  
✅ **Isolated** - Tests don't interfere with development  
✅ **Debuggable** - Can inspect test database anytime  

## Next Steps

1. Add more test data scenarios as needed
2. Create test fixtures for complex scenarios
3. Add database snapshots for faster resets
4. Integrate with CI/CD pipeline
