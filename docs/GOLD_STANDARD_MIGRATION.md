# Gold Standard Migration Plan

## What is the Gold Standard?

The **Quotes** section is our gold standard for code that uses `allocations_layout.html/js`:

1. **Self-named .py file** - All server-side functions in `views/quotes.py`
2. **Minimal template** - `quotes.html` follows DRY, lets allocations_layout do heavy lifting
3. **Self-contained** - Only interacts with its own files + `allocations_layout.html/js`
4. **URL parameter** - Receives `project_pk` via URL, no global window variables needed

---

## PO Migration Task List

### Current State
- View: `views/pos.py` ✓ (already has `po_view`)
- Template: `po.html` (uses allocations_layout) ✓
- JS Logic: Mixed between `projects_scripts.html` and `po.html`
- Data Flow: Uses `window.poSectionProject` global variable

### Goal
`projects_scripts.html` should ONLY contain a simple AJAX fetch to load `po.html`.
ALL section-specific logic (AllocationsManager init, data loading, event handlers) should be in `po.html`.

### Tasks

#### Phase 1: Make po.html Self-Contained
- [ ] Update `po_view` to accept `project_pk` query parameter
- [ ] Move `initPOAllocationsManager()` config INTO `po.html`
- [ ] Move `loadPOSuppliers()` logic INTO `po.html`
- [ ] Move PO Email button handler INTO `po.html`
- [ ] Move PO Update button handler INTO `po.html`
- [ ] Have `po.html` auto-load data on ready using `project_pk` from context

#### Phase 2: Simplify projects_scripts.html
- [ ] Replace `loadSharedPOSection()` with simple AJAX fetch + HTML insert
- [ ] Remove `window.poSectionProject` global variable
- [ ] Remove `window.poSectionContentAreaId` global variable
- [ ] Remove `window.poSectionStatus` global variable

#### Phase 3: Consolidate Python Functions
- [ ] Audit all PO-related endpoints in `urls.py`
- [ ] Ensure all PO functions are in `views/pos.py`
- [ ] Update imports in `urls.py` if any functions moved

#### Phase 4: Cleanup & Documentation
- [ ] Verify `projects_scripts.html` only has ~5 lines for PO section
- [ ] Test all PO functionality end-to-end
- [ ] Create `docs/pos.md` with code flow documentation

---

## Bills Migration Task List - ✅ COMPLETE

### Final State
- View: `views/bills.py` ✓ - accepts `project_pk` and `template` query parameters
- Template: `bills_project.html` ✓ - self-contained, 1000+ lines with all logic
- JS Logic: All in `bills_project.html` ✓
- Data Flow: Uses URL params, falls back to `window.currentConstructionProject` ✓

### Completed Tasks

#### Phase 1: Make bills_project.html Self-Contained ✅
- [x] Update `bills_view` to accept `project_pk` query parameter
- [x] Move `initBillsAllocationsManager()` config INTO `bills_project.html`
- [x] Move bill loading logic INTO `bills_project.html`
- [x] Move all Bills event handlers INTO `bills_project.html`
- [x] Have `bills_project.html` auto-load data on ready using `project_pk` from context
- [x] Remove global window variable dependencies (uses fallback pattern)

#### Phase 2: Simplify projects_scripts.html ✅
- [x] Replace Bills loading with simple AJAX fetch + HTML insert (~15 lines)
- [x] Both unallocated and allocated bills use minimal AJAX pattern
- [x] Template type passed via URL parameter

### Functions Moved to bills_project.html
**Unallocated Bills:**
- `loadUnallocatedBills()`
- `populateUnallocatedBillsTable()`
- `selectBillRow()`
- `loadBillAllocations()`
- `updateBillStillToAllocate()`
- `addNewAllocationRow()`
- `allocateBill()`
- `recalculateFooterTotals()`

**Allocated Bills:**
- `loadAllocatedBills()`
- `populateAllocatedBillsTable()`
- `selectAllocatedBillRow()`
- `loadAllocatedBillAllocations()`
- `updateAllocatedSaveButtonState()`
- `enableEditMode()`
- `saveAllocatedBill()`
- `unallocateBill()`
- `approveBill()`
- `removeAllocatedBillRow()`
- `showPOTableForBill()`
- `renderPOTableInViewer()`

### Future Improvements (Optional)
- [ ] Audit all Bills-related endpoints in `urls.py`
- [ ] Evaluate if Inbox bills need separate template (`bills_inbox.html`)
- [ ] Create `docs/bills.md` with code flow documentation

---

## Priority Order

1. **PO Phase 1-2** - Simpler, good practice run
2. **PO Phase 3-4** - Complete PO migration
3. **Bills Phase 1** - URL parameter change
4. **Bills Phase 2-5** - Full Bills migration (more complex)

---

## Success Criteria

For each section (Quotes, PO, Bills):

| Criteria | Description |
|----------|-------------|
| Single .py file | All server-side code in one named file |
| Minimal .html | Template delegates to allocations_layout |
| No global vars | Uses URL params, not window.* variables |
| Self-contained | Only touches own files + allocations_layout |
| Documented | Has matching docs/*.md file |
