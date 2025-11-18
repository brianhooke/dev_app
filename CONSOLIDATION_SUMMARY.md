# Views Consolidation Summary

## Changes Made

### 1. Created SERVICES_ORDER.txt Template
- **Location:** `/SERVICES_ORDER.txt`
- **Purpose:** Defines standard ordering for documenting functions across all PROJECT TYPE views.py files
- **Services Order:**
  1. SELF (App-Specific Views)
  2. Contacts
  3. Bills
  4. Quotes
  5. POs (Purchase Orders)
  6. Claims
  7. Xero

### 2. Consolidated dashboard/bills.py into dashboard/views.py
- **Moved Function:** `send_bill()` from `dashboard/bills.py` → `dashboard/views.py`
- **Updated Imports:** Added required models (Invoices, Projects, Invoice_allocations) and libraries
- **Deleted File:** `dashboard/bills.py` (no longer needed)

### 3. Updated dashboard/views.py Header
- **New Structure:** Follows SERVICES_ORDER.txt template
- **Current Functions by Service:**
  - **Dashboard View:** (1 function)
    1. dashboard_view - Main dashboard homepage
  
  - **Contacts Views:** (6 functions)
    2. verify_contact_details - Save verified contact details
    3. pull_xero_contacts - Pull from Xero API
    4. get_contacts_by_instance - Get active contacts
    5. create_contact - Create in Xero + DB
    6. update_contact_details - Update bank/email/ABN
    7. update_contact_status - Archive/unarchive
  
  - **Bills Views:** (1 function)
    8. send_bill - Smart endpoint (Inbox→Direct or Direct→Xero)
  
  - **Quotes Views:** (none)
  - **PO Views:** (none)
  - **Claims Views:** (none)
  - **Xero Views:** (none)

### 4. Updated dashboard/urls.py
- **Removed Import:** `from . import views, bills` → `from . import views`
- **Updated Route:** `bills.send_bill` → `views.send_bill`
- **Path:** `/send_bill/` now routes to `views.send_bill`

## Benefits

1. **Consistency:** All PROJECT TYPE apps will follow the same documentation structure
2. **Maintainability:** Single views.py file per app is easier to maintain
3. **Scalability:** Clear template for adding new PROJECT TYPEs (Quotes, POs, Claims apps)
4. **Discoverability:** Functions organized by service with numbered list
5. **Future-Proof:** Even empty services are listed, showing what's available

## Next Steps for Other Apps

When creating or updating other PROJECT TYPE apps (e.g., quotes_app, pos_app, claims_app):

1. Consult `SERVICES_ORDER.txt`
2. Copy the template structure
3. List ALL services in order, even if "(none)"
4. Number functions sequentially across all services
5. Include helper function notes if applicable

## Example for Future quotes_app/views.py:

```python
"""
Quotes app views.

Quotes App View:
1. quotes_dashboard - Main quotes dashboard

Contacts Views:
(none)

Bills Views:
(none)

Quotes Views:
2. create_quote - Create new quote
3. update_quote - Update existing quote
4. get_quote_allocations - Fetch quote allocations

PO Views:
(none)

Claims Views:
(none)

Xero Views:
(none)
"""
```

## Files Modified

1. `/SERVICES_ORDER.txt` - Created
2. `/CONSOLIDATION_SUMMARY.md` - Created (this file)
3. `/dashboard/views.py` - Updated header + added send_bill function
4. `/dashboard/urls.py` - Updated imports and routing
5. `/dashboard/bills.py` - Deleted

## Testing Required

- ✅ Verify `/send_bill/` endpoint still works
- ✅ Check Bills - Inbox → Bills - Direct workflow
- ✅ Check Bills - Direct → Xero workflow
- ✅ Ensure no import errors on server restart
