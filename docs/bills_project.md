# Bills Project Module

## Data Flow

| File | Responsibility |
|------|----------------|
| `views/bills.py` | Single source of truth for column config & all CRUD operations |
| `templates/core/bills_project.html` | Self-contained - includes layout, loads JS, all Bills logic |
| `templates/core/components/allocations_layout.html` | Reusable HTML structure (tables, viewers, CSS) |
| `static/core/js/allocations_layout.js` | Reusable JS behavior (populate, select, CRUD events) |

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User clicks "Bills" tab (Unallocated or Allocated)             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  projects_scripts.html: loadConstructionBillsSection()          │
│  - MINIMAL: Just AJAX fetch, no logic                           │
│  - GET /core/bills/?project_pk=X&template=unallocated|allocated │
│  - Inserts response HTML into #constructionContentArea          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  bills.py: bills_view()                                         │
│  - Accepts project_pk and template query parameters             │
│  - Gets xero_instance_pk from project                           │
│  - Defines main_table_columns based on template type            │
│  - Defines allocations_columns                                  │
│  - render('core/bills_project.html', context)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  bills_project.html (SELF-CONTAINED)                            │
│  - {% include allocations_layout.html with columns... %}        │
│  - <script src="allocations_layout.js">                         │
│  - Sets window.billProjectPk, window.billTemplateType           │
│  - $(document).ready() AUTO-INITIALIZES:                        │
│      └─ if (templateType === 'allocated')                       │
│             loadAllocatedBills()                                │
│         else                                                    │
│             loadUnallocatedBills()                              │
│  - All functions defined WITHIN this file                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Two Template Types

| Aspect | Unallocated | Allocated |
|--------|-------------|-----------|
| **URL param** | `template=unallocated` | `template=allocated` |
| **Load function** | `loadUnallocatedBills()` | `loadAllocatedBills()` |
| **API call** | `GET /get_project_bills/{pk}/?status=0` | `GET /get_project_bills/{pk}/?status=1` |
| **Table columns** | Supplier, Bill#, $Net, $GST, Allocate, Del | Supplier, Bill#, $Net, $GST, Progress Claim, Unallocate, Approve, Save |
| **Allocations** | Editable inputs | Read-only display |
| **Row select** | `selectBillRow()` | `selectAllocatedBillRow()` |

---

## Gold Standard Pattern

| Aspect | Implementation |
|--------|----------------|
| **Entry point** | `bills_project.html` auto-initializes on document ready |
| **projects_scripts.html** | Minimal AJAX fetch only (~15 lines) |
| **Global variables** | Uses URL params, fallback to `window.currentConstructionProject` |
| **Template** | Self-contained with all logic (~1000 lines) |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/core/bills/` | GET | Render template with column config |
| `/core/get_project_bills/{pk}/` | GET | Fetch bills for project (status=0 or 1) |
| `/core/get_unallocated_bill_allocations/{pk}/` | GET | Fetch allocations for bill |
| `/core/create_unallocated_invoice_allocation/` | POST | Create allocation row |
| `/core/update_unallocated_invoice_allocation/{pk}/` | POST | Update allocation row |
| `/core/delete_unallocated_invoice_allocation/{pk}/` | POST | Delete allocation row |
| `/core/allocate_bill/{pk}/` | POST | Mark bill as allocated (status 0→1) |
| `/core/unallocate_bill/{pk}/` | POST | Mark bill as unallocated (status 1→0) |
| `/core/approve_bill/{pk}/` | POST | Approve bill (status 1→2 or 102→103) |
| `/core/update_allocated_bill/{pk}/` | POST | Update bill number and GST |
| `/core/get_po_table_data_for_bill/{pk}/` | GET | Get PO claim data for viewer |

---

## Functions in bills_project.html

### Unallocated Bills Functions

| Function | Purpose |
|----------|---------|
| `loadUnallocatedBills()` | Fetch bills with status=0 |
| `populateUnallocatedBillsTable()` | Render editable bill rows |
| `selectBillRow()` | Handle row selection, load PDF |
| `loadBillAllocations()` | Fetch allocations for selected bill |
| `updateBillStillToAllocate()` | Calculate remaining amounts |
| `addNewAllocationRow()` | Create new allocation row |
| `allocateBill()` | Mark bill as allocated |
| `recalculateFooterTotals()` | Update footer totals |

### Allocated Bills Functions

| Function | Purpose |
|----------|---------|
| `loadAllocatedBills()` | Fetch bills with status=1 |
| `populateAllocatedBillsTable()` | Render read-only bill rows |
| `selectAllocatedBillRow()` | Handle row selection, load PDF |
| `loadAllocatedBillAllocations()` | Fetch allocations (read-only) |
| `updateAllocatedSaveButtonState()` | Enable/disable Save button |
| `enableEditMode()` | Convert row to editable |
| `saveAllocatedBill()` | Save bill number and GST |
| `unallocateBill()` | Move bill back to unallocated |
| `approveBill()` | Approve bill for Xero |
| `removeAllocatedBillRow()` | Remove row from table |

### PO Claim Functions

| Function | Purpose |
|----------|---------|
| `showPOTableForBill()` | Load PO data for bill |
| `renderPOTableInViewer()` | Render PO payment schedule table |

### Shared Functions

| Function | Purpose |
|----------|---------|
| `isBillsConstructionProject()` | Check if project is construction type |
| `formatAllocatedMoney()` | Format money with thousand separators |

---

## Key Features

- **Dual template mode** - Same HTML, different data based on `template_type`
- **Auto-initialization** - No external trigger needed
- **Construction mode** - Different allocation columns (Qty/Unit/Rate vs Net/GST)
- **PO Claims** - Special handling for bills with status=102 (progress claims)
- **PDF viewer** - Shows attached PDF or PO payment schedule
- **Inline editing** - For PO claims: Bill# and GST fields
