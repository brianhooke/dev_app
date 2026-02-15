# Foreign Currency (FX) Bills Implementation Plan

**Created:** 2026-02-14  
**Updated:** 2026-02-14 (Accountant requirements added)  
**Status:** Planning Phase

---

## Accountant's Requirements (AUTHORITATIVE)

1. **Accounts team can select foreign currency in Bills - Inbox**
2. **Project Mgrs allocate in terms of that foreign currency in Bills - Project**
3. **Bills clearly shown as 'unfixed' by rows being ORANGE** in Bills - Inbox / Direct / Approvals / Project before they've been paid
4. **AUD values shown in Contract Budget based on floating exchange rate**
5. **Can see exchange rates for all currencies** that have been applied to unfixed bills in Bills - Inbox
6. **In Bills - Inbox new toggle** to see which bills have unfixed forex amounts
7. **App listens for unfixed amount bills being paid** & Accounts must approve the fixing amount (also in the Bills - Inbox toggle)
8. **Approving the fixing updates the bill to AUD & fixed**

---

## Overview

Add foreign currency support to Bills, allowing users to:
1. Select currency in Inbox section (editable) - Accounts team
2. Allocate bills in foreign currency in bills_project.html - Project Managers
3. Visual orange highlighting for unfixed FX bills across ALL views
4. Contract Budget shows AUD values using floating exchange rate
5. FX rates panel in Inbox to view/manage rates for unfixed bills
6. Toggle in Inbox to filter unfixed FX bills and approve fixing when paid

---

## Files Affected

### Models
- `core/models.py` - Add FX fields to Bills model

### Templates
- `core/templates/core/bills_global.html` - Inbox currency selector, Unfixed toggle, FX rates panel, orange row styling
- `core/templates/core/bills_project.html` - Bills table + Allocations in FOREIGN CURRENCY, orange rows
- `core/templates/core/components/allocations_layout.html` - Column width adjustments, orange row CSS
- `core/templates/core/contract_budget.html` - AUD values with floating exchange rate (NEW SCOPE)

### Views (Python)
- `core/views/bills_global.py` - Column definitions, API endpoints, Xero integration
- `core/views/bills.py` - get_project_bills, get_bills_list responses
- `core/views/xero.py` - Xero payment sync

### JavaScript
- `core/static/core/js/utils.js` - Currency formatting utilities
- `core/static/core/js/allocations_layout.js` - Row rendering

---

## Phase 1: Model Changes

### New Fields in Bills Model (core/models.py ~line 785)

```python
# Foreign Currency fields
currency = models.CharField(max_length=3, default='AUD')  # ISO 4217: AUD, USD, EUR, GBP, NZD, etc.
foreign_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Net amount in foreign currency
foreign_gst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # GST in foreign currency
exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)  # FX rate: 1 foreign = X AUD
is_fx_fixed = models.BooleanField(default=True)  # False for unfixed FX bills, True once payment confirmed
fx_fixed_at = models.DateTimeField(null=True, blank=True)  # When FX was fixed
xero_paid_aud = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Actual AUD from Xero payment
```

### Field Logic
- **AUD bills**: currency='AUD', is_fx_fixed=True (default), foreign_amount=NULL
- **New FX bills**: currency='USD', is_fx_fixed=False, foreign_amount=bill amount
- **Fixed FX bills**: is_fx_fixed=True, total_net/total_gst set to actual AUD

### Migration Notes
- Default currency = 'AUD', is_fx_fixed = True (backward compatible)
- Existing bills: currency='AUD', foreign_amount=NULL, is_fx_fixed=True

---

## Phase 2: Inbox Section (bills_global.html)

### Column Changes
Current columns (11 total):
1. Xero / Project (13%)
2. Supplier (14%)
3. Bill # (10%)
4. $ Gross (9%)
5. $ Net (9%)
6. $ GST (6%)
7. Date (8%)
8. Due (8%)
9. Email (6%)
10. Send (8%)
11. Archive (5%)

New columns (12 total - add Currency before $ Gross):
1. Xero / Project (12%)
2. Supplier (13%)
3. Bill # (9%)
4. **Currency (6%)** ← NEW (dropdown: AUD, USD, EUR, GBP, NZD, SGD)
5. $ Gross (8%)
6. $ Net (8%)
7. $ GST (5%)
8. Date (8%)
9. Due (8%)
10. Email (5%)
11. Send (8%)
12. Archive (5%)

### Currency Dropdown Behavior
- Default: AUD
- Options: AUD, USD, EUR, GBP, NZD, SGD (configurable list)
- When non-AUD selected:
  - Net/GST inputs store `foreign_amount` and `foreign_gst`
  - `total_net` and `total_gst` remain NULL or calculated from estimated rate
  - Gross calculated from foreign values

### renderRow Changes (line ~477)
```javascript
// After Bill # input (column 3), add:
// 4. Currency dropdown
var currencySelect = $('<select>').addClass('form-control form-control-sm currency-select');
['AUD', 'USD', 'EUR', 'GBP', 'NZD', 'SGD'].forEach(function(curr) {
    currencySelect.append($('<option>').val(curr).text(curr));
});
currencySelect.val(bill.currency || 'AUD');
row.append($('<td>').append(currencySelect));
```

### Input Handler Changes (line ~823)
- When currency changes, store to bill.currency
- When Net/GST changes and currency != AUD:
  - Store to foreign_amount/foreign_gst
  - Calculate estimated AUD (if exchange_rate known) or leave blank

---

## Phase 3: Forex Rates Display (Inbox)

### New UI Element
Add "FX Rates" button/section in Inbox that shows:
- List of unique foreign currencies used in Inbox bills
- Current/estimated exchange rate for each
- Input field to manually enter/update rate
- "Apply Rate" button to update estimated AUD for all bills of that currency

### Implementation
```javascript
// New function in bills_global.html
function showForexRatesPanel() {
    // Get unique currencies from Inbox bills
    var currencies = new Set();
    $('#billsInboxMainTableBody tr').each(function() {
        var curr = $(this).find('.currency-select').val();
        if (curr && curr !== 'AUD') currencies.add(curr);
    });
    
    // Display panel with rate inputs
    // ...
}
```

---

## Phase 4: Direct & Approvals Sections (bills_global.html)

### Column Changes
Add Currency column (read-only display) after Bill #:

**Direct columns** (12 total):
1. Xero / Project (11%)
2. Supplier (13%)
3. Bill # (9%)
4. **Currency (5%)** ← NEW (display only)
5. $ Gross (7%)
6. $ Net (7%)
7. $ GST (5%)
8. Date (8%)
9. Due (8%)
10. Email (5%)
11. Approve (9%)
12. Return (6%)

**Approvals columns** (13 total):
1. Project (9%)
2. Xero Instance (9%)
3. Supplier (9%)
4. Bill # (8%)
5. **Currency (4%)** ← NEW (display only)
6. $ Gross (7%)
7. $ Net (7%)
8. $ GST (6%)
9. Date (6%)
10. Due (6%)
11. Send (6%)
12. Mark X (6%)
13. Return (5%)

### Display Format
- AUD bills: show nothing or "AUD"
- Foreign bills: show currency code (e.g., "USD")
- Optional: show both foreign and AUD amounts

---

## Phase 5: bills_project.html Changes (UPDATED per Accountant)

### Key Change: Allocations in FOREIGN CURRENCY
**Project Managers allocate in terms of foreign currency, NOT AUD.**

This means:
- When a bill is USD, the allocation Net/GST inputs are in USD
- The "Still to Allocate" footer shows USD remaining
- AUD equivalent shown separately (calculated from floating rate)

### Main Bills Table Columns
Current (7 columns):
1. Supplier
2. Bill #
3. $ Gross
4. $ Net
5. $ GST
6. Approve
7. Return

New (8 columns):
1. Supplier
2. Bill #
3. **Curr** ← NEW (display: "USD", "EUR", etc. or blank for AUD)
4. $ Gross (in foreign currency if FX bill)
5. $ Net (in foreign currency if FX bill)
6. $ GST (in foreign currency if FX bill)
7. Approve
8. Return

### ORANGE ROW STYLING for Unfixed FX Bills
```css
/* Unfixed FX bill row styling */
#billMainTableBody tr.fx-unfixed {
    background-color: rgba(255, 165, 0, 0.15) !important;  /* Light orange */
}
#billMainTableBody tr.fx-unfixed:hover {
    background-color: rgba(255, 165, 0, 0.25) !important;
}
#billMainTableBody tr.fx-unfixed.selected-row {
    background-color: rgba(255, 165, 0, 0.35) !important;
}
```

### Allocations Table
- **Inputs in FOREIGN CURRENCY** (not AUD)
- Header shows currency: "Net (USD)" instead of "$ Net"
- Footer "Still to Allocate" in foreign currency
- Optional: Show AUD equivalent in parentheses

### Code Changes
- `renderRow` function: Add currency cell, add `fx-unfixed` class if applicable
- Allocation inputs work in foreign currency
- `updateStillToAllocate`: Calculate in foreign currency
- Column widths need recalculation
- `footerTotals` array: Update colIndex values (+1 for all after Bill #)

---

## Phase 6: Xero Integration

### Sending Foreign Currency Bills
Xero API supports `CurrencyCode` field on invoices:

```python
# In _send_bill_to_xero_core (bills_global.py ~line 523)
invoice_payload = {
    "Type": "ACCPAY",
    "Contact": {"ContactID": supplier.xero_contact_id},
    "Date": formatted_date,
    "DueDate": formatted_due_date,
    "InvoiceNumber": invoice.supplier_bill_number or '',
    "LineItems": line_items,
    "Status": "DRAFT",
    "CurrencyCode": invoice.currency or "AUD",  # ← ADD THIS
}

# Line items also need currency handling
for allocation in allocations:
    unit_amount = float(allocation.amount) / qty  # Use foreign_amount if FX bill
    # ...
```

### Notes
- When currency != AUD, amounts sent are in foreign currency
- Xero handles conversion internally
- We get payment info back from Xero with actual AUD paid

---

## Phase 7: Contract Budget Integration (NEW per Accountant)

### Requirement
"AUD values shown in Contract Budget based on floating exchange rate"

### Implementation
- Contract Budget displays costs for projects
- When a project has unfixed FX bills, show AUD equivalent using current exchange rate
- Mark these values as "estimated" or with an indicator
- When FX is fixed, show actual AUD amount

### Code Changes
- `contract_budget.html` or relevant view: Calculate AUD from foreign_amount × exchange_rate
- Add visual indicator for unfixed amounts (e.g., italic, asterisk, or orange text)
- Update totals to include converted amounts

---

## Phase 8: FX Fixing Mechanism (UPDATED per Accountant)

### Terminology Change: "Fixing" not "Locking"
Per Accountant: "Approving the fixing updates the bill to AUD & fixed"

### Detection Flow
1. Bill sent to Xero with foreign currency (is_fx_fixed=False)
2. App listens for bill being paid in Xero (periodic sync or webhook)
3. Xero returns actual AUD amount paid
4. Bill appears in Inbox "Unfixed FX" toggle view
5. Accounts team reviews and approves fixing
6. Bill updated: total_net/total_gst set to actual AUD, is_fx_fixed=True

### Inbox "Unfixed FX" Toggle UI
New toggle in Bills - Inbox header area:
```
[All Bills] [Unfixed FX ●]  ← Toggle switches view
```

When "Unfixed FX" is selected, show:
- Only bills with currency != 'AUD' AND is_fx_fixed = False
- Additional columns: Foreign Amount, Est. AUD, Actual AUD (if paid), Variance
- "Fix" button for each paid bill

### FX Rates Panel (in Unfixed FX view)
Show summary at top:
```
┌─────────────────────────────────────────────────┐
│ Exchange Rates for Unfixed Bills                │
├──────────┬──────────┬───────────────────────────┤
│ Currency │ Rate     │ Bills                     │
├──────────┼──────────┼───────────────────────────┤
│ USD      │ 1.52     │ 3 unfixed                 │
│ EUR      │ 1.65     │ 1 unfixed                 │
│ GBP      │ 1.92     │ 2 unfixed                 │
└──────────┴──────────┴───────────────────────────┘
[Update Rates]
```

### Fixing Approval Table
When a bill is paid in Xero:
```
┌─────────────────────────────────────────────────────────────────────┐
│ Bills Awaiting FX Fixing                                            │
├───────────┬────────┬──────────┬──────────┬──────────┬───────┬──────┤
│ Supplier  │ Bill # │ Foreign  │ Est. AUD │ Actual   │ Var.  │      │
├───────────┼────────┼──────────┼──────────┼──────────┼───────┼──────┤
│ Acme Inc  │ INV123 │ $5,000   │ $7,600   │ $7,650   │ +$50  │ [Fix]│
│           │        │ USD      │          │          │       │      │
└───────────┴────────┴──────────┴──────────┴──────────┴───────┴──────┘
```

### Implementation
```python
# New endpoint: /core/get_unfixed_fx_bills/
def get_unfixed_fx_bills(request):
    """Get FX bills that are unfixed (for Inbox toggle)."""
    bills = Bills.objects.filter(
        currency__in=['USD', 'EUR', 'GBP', 'NZD', 'SGD'],
        is_fx_fixed=False
    ).select_related('contact_pk', 'project')
    # Include payment info from Xero if available
    # ...

# New endpoint: /core/fix_fx_bill/
def fix_fx_bill(request):
    """Fix the AUD amount for a foreign currency bill (Accounts approval)."""
    bill_pk = data.get('bill_pk')
    actual_aud_net = data.get('actual_aud_net')
    actual_aud_gst = data.get('actual_aud_gst')
    
    bill = Bills.objects.get(bill_pk=bill_pk)
    bill.total_net = Decimal(actual_aud_net)
    bill.total_gst = Decimal(actual_aud_gst)
    bill.is_fx_fixed = True
    bill.fx_fixed_at = timezone.now()
    bill.save()
    
    # Also update allocations to AUD? Or keep in foreign currency?
    # Depends on reporting requirements

# New endpoint: /core/sync_xero_payments/
def sync_xero_payments(request):
    """Check Xero for paid invoices and update local records."""
    # Get all unfixed FX bills that have been sent to Xero
    # Query Xero API for payment status
    # Update local records with actual AUD paid
    # ...
```

---

## Phase 8: Column Reference Updates

### Files with hardcoded column indices that need updating:

#### bills_global.html
- Line ~157: `$('#billsApprovalsMainTable colgroup col:nth-child(11)'` - update indices
- Line ~162-175: `sentWidths` array - add currency column
- Line ~286-301: `pendingWidths` array - add currency column
- Line ~296-301: Column width restoration loop

#### bills_project.html
- Line ~87-89: `footerTotals` colIndex values
- Line ~468-473: `recalculateFooterTotals` column indices

---

## Implementation Order

1. **Phase 3: Model changes** - Add fields, create migration
2. **Phase 4: Inbox currency selector** - Basic selection, save to model
3. **Phase 5: Direct/Approvals display** - Read-only currency column
4. **Phase 6: bills_project.html** - Both tables with currency
5. **Phase 7: Forex rates panel** - Rate management UI
6. **Phase 8: Xero CurrencyCode** - Send currency to Xero
7. **Phase 9: FX lock mechanism** - Full workflow
8. **Phase 10: Testing** - All workflows, edge cases

---

## Testing Checklist

### Basic FX Functionality
- [ ] Create AUD bill in Inbox - no FX indication, row NOT orange
- [ ] Create USD bill in Inbox - currency dropdown works
- [ ] USD bill row is ORANGE (unfixed indicator)
- [ ] Change currency mid-flow - values update correctly

### Allocations in Foreign Currency
- [ ] Select USD bill in bills_project.html - allocations in USD
- [ ] "Still to Allocate" shows USD amounts
- [ ] Allocation inputs accept foreign currency values

### Orange Row Styling (All Views)
- [ ] Inbox: Unfixed FX bills have orange rows
- [ ] Direct: Unfixed FX bills have orange rows
- [ ] Approvals: Unfixed FX bills have orange rows
- [ ] bills_project.html: Unfixed FX bills have orange rows

### Inbox Toggle & FX Panel
- [ ] "Unfixed FX" toggle shows in Inbox
- [ ] Toggle filters to show only unfixed FX bills
- [ ] FX rates panel shows currencies and rates
- [ ] Can update exchange rates

### Contract Budget
- [ ] AUD values calculated from floating exchange rate
- [ ] Unfixed amounts marked as estimated

### Xero Integration
- [ ] Send USD bill to Xero - CurrencyCode included
- [ ] Sync detects paid FX bills
- [ ] Actual AUD amount retrieved from Xero

### FX Fixing Workflow
- [ ] Paid FX bills appear in fixing approval list
- [ ] Shows foreign amount, est. AUD, actual AUD, variance
- [ ] "Fix" button works - updates bill to fixed AUD
- [ ] Fixed bill row no longer orange

### General
- [ ] Column widths correct in all views
- [ ] Sorting still works with new columns
- [ ] Footer totals correct (in appropriate currency)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Column index breakage | Systematic search and update of all hardcoded indices |
| Xero API compatibility | Test with Xero sandbox, check CurrencyCode support |
| Migration on prod data | Default currency=AUD, is_fx_locked=True for existing |
| UX complexity | Keep FX fields hidden for AUD bills |

---

## Notes

- All development/testing done locally first
- No push/deploy until explicitly requested
- Follow repo_guide.txt and deployment.txt for deployments
