# Dashboard App - Refactoring Opportunities

## Summary
Found 7 major refactoring opportunities to reduce code duplication, improve maintainability, and simplify the codebase.

---

## 1. 🔴 HIGH PRIORITY: Duplicate Method Check Pattern

**Issue:** 5 functions have identical code for checking POST method at the end:
```python
return JsonResponse({
    'status': 'error',
    'message': 'Only POST method is allowed'
}, status=405)
```

**Locations:**
- `verify_contact_details` (line 232-235)
- `pull_xero_contacts` (line 370-373)
- `create_contact` (line 552-555)
- `update_contact_details` (line 638-641)
- `update_contact_status` (line 706-709)

**Solution:** Use `@require_http_methods(["POST"])` decorator (already imported!)
- Already used on `send_bill` function
- Removes need for manual method checking
- Django returns proper 405 status automatically

**Refactor:**
```python
# BEFORE:
@csrf_exempt
def verify_contact_details(request, contact_pk):
    if request.method == 'POST':
        # ... logic ...
    return JsonResponse({'status': 'error', 'message': 'Only POST method is allowed'}, status=405)

# AFTER:
@csrf_exempt
@require_http_methods(["POST"])
def verify_contact_details(request, contact_pk):
    # ... logic (no need for method check!)
```

**Impact:** 
- Remove ~25 lines of duplicate code
- More consistent with `send_bill` function
- Clearer intent with decorator

---

## 2. 🔴 HIGH PRIORITY: Duplicate Xero API Headers

**Issue:** Same headers constructed 5 times for Xero API calls

**Locations:**
- `pull_xero_contacts` (lines 256-260)
- `create_contact` (lines 495-499)
- `update_contact_details` (lines 596-600)
- `update_contact_status` (lines 677-681)
- `send_bill` (lines 861-865)

**Solution:** Create helper function in `core.views.xero` (where other helpers live):

```python
# In core/views/xero.py:
def build_xero_headers(access_token, tenant_id, content_type='application/json'):
    """Build standard Xero API request headers."""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Xero-tenant-id': tenant_id
    }
    if content_type:
        headers['Content-Type'] = content_type
    return headers

# In dashboard/views.py:
from core.views.xero import build_xero_headers

# Usage:
headers = build_xero_headers(access_token, tenant_id)  # For POST/PUT
headers = build_xero_headers(access_token, tenant_id, None)  # For GET (no Content-Type)
```

**Impact:**
- Remove ~20 lines of duplicate code
- Single source of truth for Xero headers
- Easier to update if Xero API changes

---

## 3. 🟡 MEDIUM PRIORITY: Bank Details Parsing Logic

**Issue:** Bank details parsing logic (lines 286-301) is specific to `pull_xero_contacts` but could be useful elsewhere.

**Current Location:**
- `pull_xero_contacts` only

**Solution:** Move to `core.views.xero` as helper (similar to `format_bank_details`):

```python
# In core/views/xero.py:
def parse_bank_details(bank_account_details):
    """
    Parse Xero bank account details into BSB and account number.
    Returns (bsb, account_number) tuple.
    """
    bank_bsb = ''
    bank_account_number = ''
    
    if bank_account_details:
        cleaned = bank_account_details.replace(' ', '').replace('-', '')
        if len(cleaned) >= 6:
            bank_bsb = cleaned[:6]
            bank_account_number = cleaned[6:]
        else:
            bank_account_number = cleaned
    
    return bank_bsb, bank_account_number

# Usage:
bank_bsb, bank_account_number = parse_bank_details(xero_contact.get('BankAccountDetails', ''))
```

**Impact:**
- Reusable for other Xero integrations
- Pairs nicely with existing `format_bank_details` helper
- ~10 lines saved if used in multiple places

---

## 4. 🟡 MEDIUM PRIORITY: Contact Field Update Pattern

**Issue:** Verbose field-by-field comparison in `pull_xero_contacts` (lines 311-333)

**Current Code (23 lines):**
```python
updated = False
if existing_contact.name != name:
    existing_contact.name = name
    updated = True
if existing_contact.email != email:
    existing_contact.email = email
    updated = True
# ... 5 more fields ...
```

**Solution:** Use dictionary-based update:

```python
def update_model_fields(instance, field_updates):
    """Update model instance fields if values differ. Returns True if any changed."""
    updated = False
    for field_name, new_value in field_updates.items():
        if getattr(instance, field_name) != new_value:
            setattr(instance, field_name, new_value)
            updated = True
    return updated

# Usage:
updated = update_model_fields(existing_contact, {
    'name': name,
    'email': email,
    'status': status,
    'bank_details': bank_details,
    'bank_bsb': bank_bsb,
    'bank_account_number': bank_account_number,
    'tax_number': tax_number,
})
```

**Impact:**
- ~15 lines saved
- More maintainable (add fields without code duplication)
- Reusable for other models

---

## 5. 🟢 LOW PRIORITY: Error Response Patterns

**Issue:** Similar error response patterns repeated throughout

**Patterns:**
```python
# Pattern 1: Missing fields
return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)

# Pattern 2: Not found
return JsonResponse({'status': 'error', 'message': 'X not found'}, status=404)

# Pattern 3: Success
return JsonResponse({'status': 'success', 'message': '...'})
```

**Solution:** Create response helpers:

```python
def error_response(message, status=400):
    """Standard error response."""
    return JsonResponse({'status': 'error', 'message': message}, status=status)

def success_response(message, **extra_data):
    """Standard success response with optional extra data."""
    response = {'status': 'success', 'message': message}
    response.update(extra_data)
    return JsonResponse(response)

# Usage:
return error_response('Invoice not found', 404)
return success_response('Contact created successfully', contact={'pk': 123, ...})
```

**Impact:**
- Cleaner, more consistent responses
- Easier to add logging/monitoring hooks
- ~30-50 lines saved across file

---

## 6. 🟢 LOW PRIORITY: Common Try-Except Patterns

**Issue:** Similar try-except blocks for object retrieval

**Pattern:**
```python
try:
    invoice = Invoices.objects.get(invoice_pk=invoice_pk)
except Invoices.DoesNotExist:
    return JsonResponse({'status': 'error', 'message': 'Invoice not found'}, status=404)
```

**Solution:** Django's `get_object_or_404` could be adapted:

```python
from django.shortcuts import get_object_or_404

# OR create JSON-aware version:
def get_object_or_json_error(model, error_message, **kwargs):
    """Get object or return JSON error response."""
    try:
        return model.objects.get(**kwargs), None
    except model.DoesNotExist:
        return None, JsonResponse({'status': 'error', 'message': error_message}, status=404)

# Usage:
invoice, error = get_object_or_json_error(Invoices, 'Invoice not found', invoice_pk=invoice_pk)
if error:
    return error
```

**Impact:**
- Slightly cleaner code
- May not be worth the abstraction complexity

---

## 7. 🟢 LOW PRIORITY: Template JavaScript Patterns

**Issue:** In `contacts.html`, BSB and ABN formatting logic is duplicated (lines 151-186)

**Locations:**
- Format BSB for display (lines 151-156 and 170-175)
- Format ABN for display (lines 159-167 and 178-186)

**Solution:** Create JavaScript utility functions:

```javascript
// At top of script section:
function formatBSB(bsb) {
    if (!bsb) return '';
    const cleaned = bsb.replace(/\s/g, '').replace(/-/g, '');
    return cleaned.length === 6 
        ? cleaned.substring(0, 3) + '-' + cleaned.substring(3) 
        : cleaned;
}

function formatABN(abn) {
    if (!abn) return '';
    const cleaned = abn.replace(/\s/g, '');
    return cleaned.length === 11
        ? cleaned.substring(0, 2) + ' ' + cleaned.substring(2, 5) + ' ' + 
          cleaned.substring(5, 8) + ' ' + cleaned.substring(8)
        : abn;
}

// Usage:
let formattedBsb = formatBSB(contact.bank_bsb);
let formattedVerifiedBsb = formatBSB(contact.verified_bank_bsb);
```

**Impact:**
- ~20 lines saved in template
- Reusable if other templates need formatting
- More testable

---

## Implementation Priority

### Phase 1 (Quick Wins - 30 mins):
1. ✅ Add `@require_http_methods(["POST"])` to 5 functions
2. ✅ Create `build_xero_headers()` helper in core/views/xero.py
3. ✅ Update all 5 Xero API calls to use new helper

**Expected Savings:** ~45 lines, significantly cleaner code

### Phase 2 (Medium Effort - 1 hour):
4. ✅ Create `parse_bank_details()` helper
5. ✅ Create `update_model_fields()` helper
6. ✅ Refactor `pull_xero_contacts` to use new helpers

**Expected Savings:** ~25 lines, more reusable code

### Phase 3 (Nice to Have - 30 mins):
7. ✅ Create error/success response helpers
8. ✅ Add JavaScript formatting functions in templates

**Expected Savings:** ~50 lines, more consistent

---

## Total Potential Impact

- **Lines Removed:** ~120 lines
- **Maintainability:** Significantly improved
- **Reusability:** 4-5 new helper functions for future use
- **Consistency:** Standardized patterns across app
- **Time to Implement:** ~2-2.5 hours total

---

## Recommended Next Steps

1. **Review this document** - Agree on priority/approach
2. **Phase 1 implementation** - Start with high priority items
3. **Test thoroughly** - Especially Xero API integration
4. **Update SERVICES_ORDER.txt** - Add note about using helpers
5. **Apply learnings** - Use these patterns in future PROJECT TYPE apps

---

## Notes

- All helpers should go in `core.views.xero` to match existing pattern
- Keep `dashboard/views.py` lean by using helpers from core
- These refactorings don't change functionality, only structure
- Each phase can be committed separately for easy rollback
