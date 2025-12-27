# PO (Purchase Orders) Module

## Data Flow

| File | Responsibility |
|------|----------------|
| `views/pos.py` | Single source of truth for column config & all CRUD operations |
| `templates/core/po.html` | Self-contained - includes layout, loads JS, all PO logic |
| `templates/core/components/allocations_layout.html` | Reusable HTML structure (tables, viewers, CSS) |
| `static/core/js/allocations_layout.js` | Reusable JS behavior (populate, select, CRUD events) |

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  User clicks "POs" tab in Construction section                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  projects_scripts.html: loadSharedPOSection()                   │
│  - MINIMAL: Just AJAX fetch, no logic                           │
│  - GET /core/po/?project_pk=X                                   │
│  - Inserts response HTML into #constructionContentArea          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  pos.py: po_view()                                              │
│  - Accepts project_pk query parameter                           │
│  - Gets xero_instance_pk from project                           │
│  - Defines main_table_columns (headers, widths)                 │
│  - render('core/po.html', context)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  po.html (SELF-CONTAINED)                                       │
│  - {% include allocations_layout.html with columns... %}        │
│  - <script src="allocations_layout.js">                         │
│  - Sets window.poProjectPk, window.poXeroInstancePk             │
│  - $(document).ready() AUTO-INITIALIZES:                        │
│      └─ AllocationsManager.init({sectionId: 'po'})              │
│      └─ loadPOSuppliers()                                       │
│  - All event handlers defined WITHIN this file                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  allocations_layout.html                                        │
│  - Renders table structure with section_id='po' prefix          │
│  - Creates #poMainTableBody, #poPdfViewer, etc.                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  allocations_layout.js                                          │
│  - AllocationsManager.init() stores config                      │
│  - populateMainTable() renders supplier rows                    │
│  - selectRow() triggers generatePODocument() for preview        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Gold Standard Pattern

| Aspect | Implementation |
|--------|----------------|
| **Entry point** | `po.html` auto-initializes on document ready |
| **projects_scripts.html** | Minimal AJAX fetch only (~10 lines) |
| **Global variables** | None required - uses URL params |
| **Template** | Self-contained with all logic |

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/core/po/` | GET | Render template with column config |
| `/core/get_po_suppliers/{pk}/` | GET | Fetch suppliers with quotes for project |
| `/core/get_po_status/{pk}/` | GET | Get sent status for all suppliers |
| `/core/generate_po/` | POST | Generate PO PDF for supplier |
| `/core/send_po_email/` | POST | Send PO email to supplier |
| `/core/preview_po/` | POST | Generate PO preview HTML |
| `/core/update_po_contact/` | POST | Update supplier contact info |

---

## Functions in pos.py

| Function | Purpose |
|----------|---------|
| `po_view` | Render template with column config, accepts project_pk |
| `get_po_suppliers` | Fetch suppliers with quote data for project |
| `get_po_status` | Get sent/PDF status for all suppliers |
| `generate_po` | Generate PO PDF document |
| `send_po_email` | Send PO email to supplier |
| `preview_po` | Generate PO preview HTML |
| `update_po_contact` | Update supplier contact details |
| `get_po_table_data_for_bill` | Get PO claim data for bill viewer |

---

## Functions in po.html (Self-Contained)

| Function | Purpose |
|----------|---------|
| `loadPOSuppliers()` | Fetch and populate supplier table |
| `generatePODocument()` | Generate PO preview on row select |
| `handleUpdateClick()` | Enable inline editing of contact fields |
| `handleSaveClick()` | Save contact updates to Xero |
| `handleCancelClick()` | Cancel edit, restore original values |
| `handleEmailClick()` | Send PO email to supplier |

---

## Key Features

- **No allocations table** - PO uses `hide_allocations=True`
- **PDF preview** - Generated on-the-fly when row selected
- **Inline editing** - Update → Save/Cancel pattern for contact fields
- **Email integration** - Send PO directly from UI
- **Construction mode** - Shows Qty/Unit/Rate columns for construction projects
