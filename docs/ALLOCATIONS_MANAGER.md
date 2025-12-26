# AllocationsManager Documentation

A reusable JavaScript module for managing data tables with allocations, used across Quotes, Bills, and PO sections.

**File:** `core/static/core/js/allocations_manager.js`

---

## 1. Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `deleteRowBtn` | `false` | Show delete button in main table rows |
| `saveRowBtn` | `false` | Show save/update button in main table rows |
| `constructionMode` | `false` | Enable qty/unit/rate columns for allocations |
| `gstField` | `false` | Show GST inputs in allocations |
| `confirmDelete` | `true` | Show confirmation dialog before delete |
| `reloadAfterSave` | `false` | Reload table data after successful save |
| `reloadAfterDelete` | `true` | Reload table data after successful delete |

### Feature Flags by Section

| Section | deleteRowBtn | saveRowBtn | constructionMode | gstField |
|---------|-------------|-----------|-----------------|----------|
| **Quotes** | ✅ | ✅ | dynamic* | ❌ |
| **Bills** | ❌ | ❌ | dynamic* | ✅ |
| **PO** | ❌ | ❌ | ❌ | ❌ |

*dynamic = determined at runtime by `isConstructionProject()` check

---

## 2. Public API Functions

### Core
| Function | Purpose |
|----------|---------|
| `init(config)` | Initialize a section with config |
| `getConfig(sectionId)` | Get current config for a section |
| `getState(sectionId)` | Get current state (selectedRowPk, isNewMode, editMode) |

### Main Table
| Function | Purpose |
|----------|---------|
| `loadData(sectionId, params)` | Load data from API and populate main table |
| `populateMainTable(sectionId, items)` | Render items into main table |
| `selectRow(sectionId, row)` | Select a row and load its allocations |

### Allocations Table
| Function | Purpose |
|----------|---------|
| `loadAllocations(sectionId, pk)` | Load allocations from API for a given PK |
| `populateAllocationsTable(sectionId, allocations)` | Render allocations into table |
| `addAllocationRow(sectionId)` | Add empty editable row to allocations table |
| `updateStillToAllocate(sectionId)` | Recalculate "Still to Allocate" footer value |
| `getAllocations(sectionId)` | Get allocation data from current table rows |

### Mode Control
| Function | Purpose |
|----------|---------|
| `setNewMode(sectionId, isNew)` | Toggle "new item" mode |
| `setEditMode(sectionId, isEdit)` | Toggle edit mode |

### Button Helpers
| Function | Purpose |
|----------|---------|
| `createSaveButton(item, cfg)` | Create save button for new items |
| `createUpdateButton(item, cfg)` | Create update button for existing items |
| `createDeleteButton(item, cfg)` | Create delete button for main table rows |
| `createAllocationDeleteButton(alloc, cfg)` | Create delete button for allocation rows |

### Direct Actions
| Function | Purpose |
|----------|---------|
| `saveItem(sectionId, data)` | Save/update an item via API |
| `deleteItem(sectionId, itemPk, row)` | Delete an item via API |

### Row Builders
| Function | Purpose |
|----------|---------|
| `createEditableAllocationRow(options)` | Create editable allocation row with inputs, dropdowns, auto-save |

---

## 3. DOM Element Naming Convention

AllocationsManager expects HTML elements with IDs following this pattern:

| Element | ID Pattern | Example (sectionId='quote') |
|---------|------------|----------------------------|
| Main table container | `{sectionId}TableContainer` | `quoteTableContainer` |
| Main table | `{sectionId}MainTable` | `quoteMainTable` |
| Main table body | `{sectionId}MainTableBody` | `quoteMainTableBody` |
| Main table footer | `{sectionId}MainTableFooter` | `quoteMainTableFooter` |
| Allocations table | `{sectionId}AllocationsTable` | `quoteAllocationsTable` |
| Allocations table body | `{sectionId}AllocationsTableBody` | `quoteAllocationsTableBody` |
| Allocations title | `{sectionId}AllocationsTitle` | `quoteAllocationsTitle` |
| Allocations footer | `{sectionId}AllocationsFooter` | `quoteAllocationsFooter` |
| Add allocation button | `{sectionId}AddAllocationBtn` | `quoteAddAllocationBtn` |
| Save allocations button | `{sectionId}SaveAllocationsBtn` | `quoteSaveAllocationsBtn` |
| PDF viewer iframe | `{sectionId}PdfViewer` | `quotePdfViewer` |
| Viewer placeholder | `{sectionId}ViewerPlaceholder` | `quoteViewerPlaceholder` |
| Title actions area | `{sectionId}TitleActions` | `quoteTitleActions` |

---

## 4. Window Variables

| Variable | Used By | Purpose |
|----------|---------|---------|
| `window.projectPk` | All sections | Current project primary key |
| `window.billCostingItems` | Bills | Costing items for bill allocation dropdowns |
| `window.quotesCostingItems` | Quotes | Costing items for quote allocation dropdowns |
| `window.currentSelectedBill` | Bills | Currently selected bill data |
| `window.adjustAllocationsHeight[sectionId]` | All | Height adjustment function for allocations table |

---

## 5. CSS Classes

### Applied by AllocationsManager
| Class | Applied To | Purpose |
|-------|-----------|---------|
| `.selected-row` | `<tr>` | Highlights selected row in main table |

### Expected in Allocation Rows
| Class | Element | Purpose |
|-------|---------|---------|
| `.allocation-item-select` | `<select>` | Item dropdown |
| `.allocation-net-input` | `<input>` | Net amount input |
| `.allocation-gst-input` | `<input>` | GST amount input |
| `.allocation-qty-input` | `<input>` | Quantity input (construction) |
| `.allocation-rate-input` | `<input>` | Rate input (construction) |
| `.allocation-unit-input` | `<input hidden>` | Unit value |
| `.allocation-unit-display` | `<span>` | Unit display text |
| `.allocation-amount-display` | `<span>` | Calculated amount display |
| `.allocation-notes-input` | `<input>` | Notes input |
| `.delete-allocation-btn` | `<button>` | Delete button |

---

## 6. Config Structure Reference

```javascript
AllocationsManager.init({
    sectionId: 'quote',
    
    features: {
        deleteRowBtn: true,
        saveRowBtn: true,
        constructionMode: false,
        gstField: false,
        confirmDelete: true,
        reloadAfterSave: false,
        reloadAfterDelete: true
    },
    
    mainTable: {
        emptyMessage: 'No quotes found.',
        showFooter: true,
        footerTotals: [{ colIndex: 2, valueKey: 'total_cost' }],
        renderRow: function(item, index, cfg) { return $('<tr>...'); },
        onRowSelect: function(row, pk, cfg) { ... }
    },
    
    allocations: {
        emptyMessage: 'No allocations.',
        editable: true,
        showStillToAllocate: true,
        renderRow: function(alloc, cfg) { return $('<tr>...'); },
        renderEditableRow: function(alloc, cfg, onChange) { return $('<tr>...'); },
        onUpdate: function(sectionId, totals) { ... }
    },
    
    api: {
        loadAllocations: '/core/get_allocations/{pk}/',
        save: '/core/update_item/',
        delete: '/core/delete_item/{pk}/'
    },
    
    callbacks: {
        onSave: function(data, cfg) { return true; },      // return false to cancel
        onDelete: function(pk, cfg) { return true; },      // return false to cancel
        onSaveSuccess: function(response, cfg) { ... },
        onDeleteSuccess: function(response, pk, cfg) { ... },
        preparePayload: function(data, cfg) { return data; }
    },
    
    data: {
        pkField: 'quotes_pk'
    }
});
```

---

## 7. Related Files

| File | Purpose |
|------|---------|
| `core/static/core/js/allocations_manager.js` | The module itself |
| `core/templates/core/components/reusable_allocations_section.html` | HTML template for tables layout |
| `core/templates/core/components/data_table_styles.html` | CSS styles for tables |
| `core/templates/core/includes/projects_scripts.html` | Page-specific initialization and custom renderers |
