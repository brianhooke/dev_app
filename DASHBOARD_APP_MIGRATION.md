# Dashboard App Migration Summary

## Overview
Created new `dashboard` app as a PROJECT_TYPE at the same level as 'development', 'precast', 'pods', etc. Moved dashboard and contact-related functionality from `core` to the new `dashboard` app.

## Files Structure Created

```
dashboard/
├── __init__.py
├── admin.py
├── apps.py (DashboardConfig)
├── models.py
├── tests.py
├── urls.py (dashboard app URL patterns)
├── views.py (dashboard_view + all contact management views)
├── migrations/
│   └── __init__.py
├── services/
│   └── __init__.py
├── static/ (empty, ready for dashboard-specific static files)
└── templates/
    └── dashboard/
        ├── dashboard.html
        ├── dashboard_master.html
        ├── contacts.html
        └── xero_modals.html
```

## Files Moved

### From core/views/ to dashboard/
- `contacts.py` → `dashboard/views.py` (contact functions merged)
- `dashboard.py` → `dashboard/views.py` (dashboard_view function merged)

### From core/templates/core/ to dashboard/templates/dashboard/
- `dashboard.html` → `dashboard/templates/dashboard/dashboard.html`
- `dashboard_master.html` → `dashboard/templates/dashboard/dashboard_master.html`
- `contacts.html` → `dashboard/templates/dashboard/contacts.html`
- `xero_modals.html` → `dashboard/templates/dashboard/xero_modals.html`

## Files Modified

### 1. `dev_app/settings/base.py`
- Added `'dashboard'` to `INSTALLED_APPS` (after 'core')

### 2. `dev_app/urls.py`
- Added dashboard app at root level: `path('', include(('dashboard.urls', 'dashboard'), namespace='dashboard'))`
- Moved core app to `/core/` prefix: `path('core/', include(('core.urls', 'core'), namespace='core'))`

### 3. `core/urls.py`
- Removed `dashboard_view` import and path
- Removed all contact management paths (moved to dashboard app)
- Kept Xero instance management and OAuth paths

### 4. `dashboard/views.py`
Contains 7 functions:
1. `dashboard_view` - Main dashboard homepage
2. `verify_contact_details` - Save verified contact details
3. `pull_xero_contacts` - Pull contacts from Xero API
4. `get_contacts_by_instance` - Get ACTIVE contacts with verified status
5. `create_contact` - Create contact in Xero + local DB
6. `update_contact_details` - Update bank details, email, ABN
7. `update_contact_status` - Archive/unarchive contacts

- Imports from: `core.models` (Contacts, SPVData, XeroInstances)
- Imports helpers from: `core.views.xero` (get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors)

### 5. `dashboard/urls.py`
URL patterns with `app_name = 'dashboard'`:
- `''` → dashboard_view (homepage at root)
- `pull_xero_contacts/<int:instance_pk>/`
- `get_contacts_by_instance/<int:instance_pk>/`
- `create_contact/<int:instance_pk>/`
- `update_contact_details/<int:instance_pk>/<int:contact_pk>/`
- `update_contact_status/<int:instance_pk>/<int:contact_pk>/`
- `verify_contact_details/<int:contact_pk>/`

### 6. `dashboard/templates/dashboard/dashboard.html`
- Updated `{% extends "dashboard/dashboard_master.html" %}`
- Updated includes to `{% include 'dashboard/xero_modals.html' %}` and `{% include 'dashboard/contacts.html' %}`
- Still uses `{% static 'core/...' %}` for shared static files

### 7. `core/static/core/js/xero.js`
Updated Xero instance management URLs to use `/core/` prefix:
- `/core/get_xero_instances/`
- `/core/create_xero_instance/`
- `/core/delete_xero_instance/<pk>/`
- `/core/test_xero_connection/<pk>/`

### 8. `core/templates/core/components/reusable_contacts_modal.html`
Updated OAuth authorization URLs:
- `/core/xero_oauth_authorize/<instance_pk>/` (3 occurrences)

## URL Routing Changes

### Root Level (/) - Now Dashboard App
- `/` → `dashboard:dashboard` (dashboard_view)
- `/pull_xero_contacts/<pk>/` → `dashboard:pull_xero_contacts`
- `/get_contacts_by_instance/<pk>/` → `dashboard:get_contacts_by_instance`
- `/create_contact/<pk>/` → `dashboard:create_contact`
- `/update_contact_details/<pk>/<pk>/` → `dashboard:update_contact_details`
- `/update_contact_status/<pk>/<pk>/` → `dashboard:update_contact_status`
- `/verify_contact_details/<pk>/` → `dashboard:verify_contact_details`

### Core App (/core/) - Xero Management
- `/core/get_xero_instances/` → `core:get_xero_instances`
- `/core/create_xero_instance/` → `core:create_xero_instance`
- `/core/delete_xero_instance/<pk>/` → `core:delete_xero_instance`
- `/core/test_xero_connection/<pk>/` → `core:test_xero_connection`
- `/core/xero_oauth_authorize/<pk>/` → `core:xero_oauth_authorize`
- `/core/xero_oauth_callback/` → `core:xero_oauth_callback`
- `/core/developer/` → `core:homepage` (old developer homepage)

## Files NOT Moved (Still in core)
- `core/views/xero.py` - Xero instance management + helper functions
- `core/views/xero_oauth.py` - OAuth2 authorization flow
- `core/templates/core/components/reusable_contacts_modal.html` - Shared component
- `core/templates/core/components/reusable_form.html` - Shared component
- `core/templates/core/components/reusable_navbar.html` - Shared component
- `core/templates/core/components/reusable_table.html` - Shared component
- `core/static/core/` - All static files (CSS, JS, images) remain in core for sharing

## Dependencies

### dashboard app depends on:
- **core.models**: Contacts, SPVData, XeroInstances
- **core.views.xero**: Helper functions (get_xero_auth, format_bank_details, parse_xero_validation_errors, handle_xero_request_errors)
- **core templates**: Shared components (reusable_contacts_modal, reusable_form, reusable_navbar, reusable_table)
- **core static files**: CSS, JS, images

## Functionality Preserved
✅ Dashboard loads at root `/` URL (localhost:8000/)
✅ All contact management functions work from dashboard app
✅ Xero instance management works from core app
✅ OAuth2 authorization flow works (redirects to /core/xero_oauth_authorize/)
✅ All JavaScript fetch calls updated to correct endpoints
✅ All template includes reference correct paths
✅ Static files still load from core (shared across apps)

## Testing Commands
```bash
# Syntax check
python3 -m py_compile dashboard/views.py dashboard/urls.py

# Django check
python3 manage.py check

# Run development server
python3 manage.py runserver
```

## Browser Testing
1. Visit `http://localhost:8000/` → Should load dashboard
2. Click "Contacts" → Should open contacts modal
3. Click "Xero" → Should open Xero instances modal
4. Test Xero connection → Should hit `/core/test_xero_connection/`
5. Pull contacts → Should hit `/pull_xero_contacts/`
6. Update contact → Should hit `/update_contact_details/`

## Migration Benefits
1. **Cleaner separation**: Dashboard functionality isolated in its own app
2. **Follows PROJECT_TYPE pattern**: Same structure as development, precast, pods, etc.
3. **Scalable**: Easy to add more dashboard-specific features
4. **Maintainable**: Contact management code in one place
5. **Root-level access**: Dashboard at `/` for immediate access
