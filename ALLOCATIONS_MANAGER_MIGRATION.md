# AllocationsManager Migration Plan

## Overview

This document outlines the migration from duplicated section-specific JavaScript files to the unified `AllocationsManager` class.

## Rollback Information

**Safe Rollback Commit:** `ca8c3b9` (2025-12-13)
- Refactor Phases 1-3: Dead code removal, duplication fix, file splitting
- Command to rollback: `git checkout ca8c3b9 -- core/static/core/js/`

---

## KEY DISCOVERY: Two Separate Systems

After deep analysis, I found **two completely separate systems** for allocations:

### System 1: Modal-Based (build.html) - ACTIVE & HEAVILY USED
- **Location:** Modals in `build.html` via included templates
- **Templates:** `quotes_modals.html`, `invoices_modals.html`
- **JS Files:** `quotes_1.js`, `quotes_2.js`, `invoices_1-6.js`
- **Pattern:** Create DOM dynamically, populate modals via JS
- **Data:** Global variables (`committedQuotes`, `quote_allocations`, etc.)

### System 2: Standalone Pages - PARTIALLY IMPLEMENTED
- **Location:** Standalone pages accessed via `/quotes/`, `/invoices/`
- **Templates:** `quotes.html`, `invoices.html` using `allocations_layout.html`
- **JS Files:** `allocations_layout.js` (EXISTS BUT UNUSED!)
- **Pattern:** Embedded sections with AllocationsManager API
- **Status:** Templates exist but JS integration incomplete

### Implication

The `AllocationsManager` class was designed for System 2 (standalone pages), but the app primarily uses System 1 (modals). This means:

1. **Option A:** Complete System 2 and phase out System 1 (major change)
2. **Option B:** Extend AllocationsManager to also work with modals
3. **Option C:** Keep System 1 but refactor to reduce duplication

**Recommendation:** Option B - Create a unified approach that works for both

---

## Current Architecture

### Template Layer (Working Well ✅)
- `allocations_layout.html` - Generic template with `section_id` parameter
- Used by: quotes.html, invoices.html, invoices_allocated.html, invoices_approvals.html

### View Layer (Working Well ✅)
- `core/views/main.py` - Passes column configurations per section
- Each section has different columns, widths, and behaviors

### JavaScript Layer (NEEDS MIGRATION ⚠️)

| File | Lines | Section | Status |
|------|-------|---------|--------|
| `quotes_1.js` | 490 | Quotes - New/Update modal | Legacy |
| `quotes_2.js` | 94 | Quotes - Committed list | Legacy |
| `invoices_1.js` | 94 | Invoices - Upload modal | Legacy |
| `invoices_2.js` | 128 | Invoices - Unallocated | Legacy |
| `invoices_3.js` | 52 | Invoices - Helpers | Legacy |
| `invoices_4.js` | 976 | Invoices - Progress Claims | Legacy |
| `invoices_5.js` | 454 | Invoices - Direct Costs | Legacy |
| `invoices_6.js` | 379 | Invoices - Allocated | Legacy |
| `allocations_layout.js` | 579 | Reusable Manager | **UNUSED** |

**Total duplicated code:** ~2,667 lines across quote/invoice files

### Existing AllocationsManager Features (Already Built!)

```javascript
AllocationsManager = {
    init(config)           // Initialize a section
    loadData(sectionId, params)  // Load main table data
    populateMainTable()    // Render main table rows
    selectRow()            // Handle row selection + PDF viewer
    loadAllocations()      // Load allocations for selected item
    populateAllocationsTable()  // Render allocation rows
    addAllocationRow()     // Add editable allocation row
    updateStillToAllocate() // Calculate remaining amount
    getAllocations()       // Gather data for saving
    setNewMode()           // Toggle new item mode
    setEditMode()          // Toggle edit mode
    getConfig()            // Get section config
    getState()             // Get section state
}
```

## Migration Strategy

### Principle: Comment Out, Don't Delete

All existing JavaScript will be commented out, not deleted, so it's available for rollback during bug fixing. The final step after all bugs are fixed will be to remove the commented code.

### Phase 1: Quotes Section (Proof of Concept)

**Files to modify:**
1. `quotes_1.js` - Comment out, add AllocationsManager config
2. `quotes_2.js` - Comment out, integrate with manager
3. `quotes_entry.js` - May need to integrate or keep separate

**Migration approach:**
1. Add AllocationsManager.init() call with quotes-specific config
2. Define custom `renderRow` for main table
3. Define custom `renderEditableRow` for allocations
4. Configure API endpoints
5. Test thoroughly
6. Comment out old code with `/* LEGACY: ... */`

### Phase 2: Invoices Unallocated

**Files to modify:**
- `invoices_1.js`, `invoices_2.js`, `invoices_3.js`

### Phase 3: Invoices Allocated (Read-only)

**Files to modify:**
- `invoices_6.js`

### Phase 4: Progress Claims (Complex)

**Files to modify:**
- `invoices_4.js`, `invoices_5.js`

⚠️ **Note:** Progress claims have complex business logic (previous claims, this claim, variations). May need AllocationsManager extensions.

## Configuration Template

```javascript
// Example: Quotes section configuration
AllocationsManager.init({
    sectionId: 'quote',
    
    mainTable: {
        emptyMessage: 'No quotes found.',
        showFooter: true,
        footerTotals: [
            { colIndex: 2, valueKey: 'total_cost' }
        ],
        renderRow: function(quote, index, cfg) {
            var row = $('<tr>')
                .attr('data-pk', quote.quotes_pk)
                .attr('data-pdf-url', quote.pdf);
            row.append($('<td>').text(quote.supplier_name));
            row.append($('<td>').text('$' + quote.total_cost));
            // ... more columns
            return row;
        },
        onRowSelect: function(row, pk, cfg) {
            // Custom logic when row is selected
        }
    },
    
    allocations: {
        emptyMessage: 'No allocations.',
        editable: true,
        renderEditableRow: function(alloc, cfg, onChange) {
            // Custom editable row rendering
        }
    },
    
    api: {
        loadData: '/get_project_quotes/{pk}/',
        loadAllocations: function(quotePk) {
            return '/get_quote_allocations/' + quotePk + '/';
        },
        saveAllocation: '/commit_data/',
        deleteAllocation: '/delete_quote/'
    }
});
```

## Testing Checklist

For each migrated section:
- [ ] Main table loads correctly
- [ ] Row selection works
- [ ] PDF viewer updates
- [ ] Allocations load for selected item
- [ ] Add allocation row works
- [ ] Delete allocation row works
- [ ] Still to allocate calculation correct
- [ ] Save/commit works
- [ ] Update existing works
- [ ] Delete existing works
- [ ] Validation (button colors) works
- [ ] Modal close/cleanup works

## Rollback Procedure

If issues are found:

1. **Quick rollback (single file):**
   ```bash
   git checkout ca8c3b9 -- core/static/core/js/quotes_1.js
   ```

2. **Full rollback (all JS):**
   ```bash
   git checkout ca8c3b9 -- core/static/core/js/
   ```

3. **Uncomment legacy code:**
   - Find `/* LEGACY:` blocks
   - Remove comment markers
   - Comment out new AllocationsManager code

## Final Cleanup (After All Bugs Fixed)

**DO NOT perform until all sections are migrated and tested:**

1. Search for `/* LEGACY:` in all JS files
2. Remove the entire commented legacy blocks
3. Remove unused helper functions
4. Run full test suite
5. Commit as "Cleanup: Remove legacy allocation JS code"

## Success Metrics

- Reduce ~2,667 lines to ~500 lines (configuration only)
- Single point of maintenance for allocation logic
- Consistent behavior across all sections
- Easier to add new allocation sections in future
