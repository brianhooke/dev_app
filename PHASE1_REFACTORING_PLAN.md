# Phase 1 Refactoring - Implementation Plan

## Status: IN PROGRESS

## Changes Completed
1. ✅ Created `build_xero_headers()` in core/views/xero.py
2. ✅ Updated core/views/xero.py header documentation
3. ✅ Added import to dashboard/views.py

## Changes Needed

### Step 1: Update dashboard/views.py header (DONE)
- Added Bills Views section
- Added empty Quotes, PO, Claims, Xero sections
- Updated Note section

### Step 2: For each of 5 functions, make 2 changes:

#### Function 1: verify_contact_details (lines 85-235)
**Change A:** Add `@require_http_methods(["POST"])` decorator ABOVE `@csrf_exempt`
**Change B:** Remove lines 232-235 (the final if/return for POST check)

#### Function 2: pull_xero_contacts (lines 238-373)
**Change A:** Add `@require_http_methods(["POST"])` decorator between `@csrf_exempt` and `@handle_xero_request_errors`
**Change B:** Change line 245 `if request.method == 'POST':` - remove this line and un-indent everything below it
**Change C:** Replace lines 254-260 (headers dict) with: `headers=build_xero_headers(access_token, tenant_id, include_content_type=False),`
**Change D:** Remove lines 370-373 (the final if/return for POST check)

#### Function 3: create_contact (lines 428-555)
**Change A:** Add `@require_http_methods(["POST"])` decorator between `@csrf_exempt` and `@handle_xero_request_errors`
**Change B:** Change line 434 `if request.method == 'POST':` - remove this line and un-indent everything below it
**Change C:** Replace lines 492-499 (headers dict) with: `headers=build_xero_headers(access_token, tenant_id),`
**Change D:** Remove lines 552-555 (the final if/return for POST check)

#### Function 4: update_contact_details (lines 559-641)
**Change A:** Add `@require_http_methods(["POST"])` decorator between `@csrf_exempt` and `@handle_xero_request_errors`
**Change B:** Change line 546 `if request.method == 'POST':` - remove this line and un-indent everything below it
**Change C:** Replace lines 593-600 (headers dict) with: `headers=build_xero_headers(access_token, tenant_id),`
**Change D:** Remove lines 638-641 (the final if/return for POST check)

#### Function 5: update_contact_status (lines 644-709)
**Change A:** Add `@require_http_methods(["POST"])` decorator between `@csrf_exempt` and `@handle_xero_request_errors`
**Change B:** Change line 650 `if request.method == 'POST':` - remove this line and un-indent everything below it
**Change C:** Replace lines 674-681 (headers dict) with: `headers=build_xero_headers(access_token, tenant_id),`
**Change D:** Remove lines 706-709 (the final if/return for POST check)

#### Function 6: send_bill (lines 712-943)
**NO CHANGES NEEDED** - Already uses `@require_http_methods` and has Xero headers inline (will refactor in Phase 2)

## Testing Checklist
After all changes:
- [ ] File has no syntax errors
- [ ] All 5 contact functions use @require_http_methods
- [ ] All 5 Xero API calls use build_xero_headers()
- [ ] No "Only POST method is allowed" checks remain
- [ ] Server starts without errors
- [ ] Test pull contacts
- [ ] Test verify contact
- [ ] Test create contact
- [ ] Test update contact
- [ ] Test Bills - Inbox send
- [ ] Test Bills - Direct send to Xero

## Notes
- Be VERY careful with indentation when removing `if request.method == 'POST':`
- The entire function body below that line needs to be un-indented by 4 spaces
- Use Python auto-format if available after edits
