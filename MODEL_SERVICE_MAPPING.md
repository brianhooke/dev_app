# Model to Service Mapping

This document categorizes all Django models by their corresponding SERVICE domain to guide business logic extraction.

## Architecture Overview

```
dev_app/
├── core/                                    # Core app (shared infrastructure)
│   ├── models.py                      # ALL models (shared across PROJECT_TYPEs)
│   ├── services/                            # Business logic by SERVICE (shared)
│   │   ├── __init__.py
│   │   ├── bills.py                         # Supplier bills/invoices (incoming)
│   │   ├── invoices.py                      # HC claims/invoices (outgoing)
│   │   ├── quotes.py                        # Quote business logic
│   │   ├── pos.py                           # PO business logic
│   │   ├── costings.py                      # Costing business logic (NEW)
│   │   ├── contacts.py                      # Contact business logic (NEW)
│   │   └── aggregations.py                  # Dashboard totals (NEW)
│   ├── views/                               # View logic split by feature
│   │   ├── __init__.py
│   │   ├── main.py                          # Main views (homepage, build, etc.)
│   │   └── project_type.py                  # PROJECT_TYPE management views
│   ├── templates/core/                      # Core templates
│   │   ├── master.html
│   │   ├── homepage.html
│   │   ├── build.html
│   │   └── ...
│   ├── static/core/                         # Core static files
│   │   ├── css/
│   │   ├── main/                            # JavaScript files
│   │   └── media/
│   ├── utils/                               # Utility functions
│   │   └── project_type.py
│   ├── middleware.py
│   └── urls.py
│
├── construction/                            # Construction PROJECT_TYPE app
│   ├── models.py                         # Empty (or Construction-specific models)
│   ├── services/                  # Construction-specific business logic (if needed)
│   │   └── __init__.py                      # Usually empty - uses core/services/
│   ├── views/                               # Construction view logic
│   │   ├── __init__.py
│   │   └── main.py                          # Calls core/services/ functions
│   ├── templates/construction/              # Construction templates
│   │   ├── homepage.html
│   │   ├── build.html
│   │   └── ...
│   ├── static/construction/                 # Construction static files
│   │   ├── css/
│   │   └── js/
│   └── urls.py                              # Construction URL patterns
│
├── development/                             # Development PROJECT_TYPE app
│   ├── models.py                            # Empty (or Development-specific models)
│   ├── services/                  # Development-specific business logic (if needed)
│   │   └── __init__.py                      # Usually empty - uses core/services/
│   ├── views/                               # Development view logic
│   │   ├── __init__.py
│   │   └── main.py                          # Calls core/services/ functions
│   ├── templates/development/               # Development templates
│   │   ├── homepage.html
│   │   ├── build.html
│   │   └── ...
│   ├── static/development/                  # Development static files
│   │   ├── css/
│   │   └── js/
│   └── urls.py                              # Development URL patterns
│
├── precast/                            # Precast PROJECT_TYPE app (same structure)
├── pods/                                    # Pods PROJECT_TYPE app (same structure)
└── general/                                 # General PROJECT_TYPE app (same structure)
```

## Key Principles:

1. **Models**: All in `core/models.py` (shared data structure)
2. **Services**: All in `core/services/` (shared business logic)
3. **Views**: Split by PROJECT_TYPE (presentation logic)
4. **Templates**: Split by PROJECT_TYPE (different UI per type)
5. **Static Files**: Split by PROJECT_TYPE (different styling/JS per type)

## Service Categories

### 1. PROJECTS Service (`core/services/projects.py`)
**Models:**
- `Projects` - Project management and PROJECT_TYPE resolution
- `SPVData` - Special Purpose Vehicle data

**Responsibilities:**
- Project CRUD operations
- PROJECT_TYPE determination
- SPV data management

---

### 2. DOCUMENTS Service (`core/services/documents.py`)
**Models:**
- `DesignCategories` - Design document categories
- `PlanPdfs` - Plan/drawing PDFs
- `ReportCategories` - Report categories
- `ReportPdfs` - Report PDFs
- `Models_3d` - 3D model files
- `Letterhead` - Letterhead templates

**Responsibilities:**
- Document upload/retrieval
- Category management
- File storage operations

---

### 3. POS Service (`core/services/pos.py`) ✅ ALREADY EXISTS
**Models:**
- `Po_globals` - Purchase order global settings
- `Po_orders` - Purchase orders
- `Po_order_detail` - Purchase order line items

**Responsibilities:**
- PO creation and management
- PO PDF generation
- PO email sending

**Status:** Already implemented with 5 functions

---

### 4. COSTINGS Service (`core/services/costings.py`) - NEW
**Models:**
- `Categories` - Budget categories
- `Costing` - Line items with budgets

**Responsibilities:**
- Costing queries and transformations
- Category grouping and ordering
- Budget calculations
- Contract budget vs forecast budget
- Cost to Complete (C2C) calculations

**Business Logic in main():**
- Lines 69-81: Costing data transformation
- Lines 126-134: Category totals calculation
- Lines 142-149: Total calculations (contract_budget, uncommitted, committed, etc.)

---

### 5. QUOTES Service (`core/services/quotes.py`) ✅ ALREADY EXISTS
**Models:**
- `Quotes` - Supplier quotes
- `Quote_allocations` - Quote line item allocations

**Responsibilities:**
- Quote management
- Quote allocation calculations
- Committed vs uncommitted tracking

**Status:** Already implemented with 8 functions

---

### 6. BILLS Service (`core/services/bills.py`) ✅ ALREADY EXISTS
**Models:**
- `Invoices` - Supplier bills/invoices (incoming)
- `Invoice_allocations` - Invoice line item allocations

**Responsibilities:**
- Supplier invoice/bill management
- Invoice allocation calculations
- SC invoiced/paid tracking
- Invoice status management

**Status:** Already implemented with 9 functions (renamed from invoices.py)

---

### 7. INVOICES Service (`core/services/invoices.py`) ✅ ALREADY EXISTS
**Models:**
- `HC_claims` - Head contractor claims/invoices (outgoing)
- `HC_claim_allocations` - HC claim line items
- `Hc_variation` - HC variations
- `Hc_variation_allocations` - HC variation line items

**Responsibilities:**
- HC claim/invoice creation and management
- HC claim calculations (previous, this, adjustments)
- Variation management
- Fixed on site tracking

**Status:** Already implemented with 9 functions (renamed from bills.py)

---

### 8. CONTACTS Service (`core/services/contacts.py`) - NEW
**Models:**
- `Contacts` - Suppliers and clients

**Responsibilities:**
- Contact management
- Supplier/client filtering
- Contact queries by division

**Business Logic in main():**
- Lines 84-87: Contact queries (checked vs unfiltered)

---

### 9. AGGREGATIONS Service (`core/services/aggregations.py`) - NEW
**No direct models - operates on aggregated data**

**Responsibilities:**
- Cross-service totals and summaries
- Dashboard data aggregation
- Category-level rollups
- Division-level summaries

**Business Logic in main():**
- Lines 142-149: Total calculations across all costings
- Lines 126-134: Category totals

---

## Business Logic Extraction Plan

### Phase 1: Create New Services (Priority: High)

#### A. Create `core/services/costings.py`
Extract from `main()`:
```python
def get_costings_for_division(division):
    """Get all costings for a division with category metadata."""
    # Lines 69-81 from main()
    
def calculate_category_totals(costings):
    """Calculate totals grouped by category."""
    # Lines 126-134 from main()
    
def calculate_costing_totals(costings):
    """Calculate aggregate totals across all costings."""
    # Lines 142-149 from main()
    
def enrich_costings_with_calculations(costings, committed_values, invoice_sums, paid_sums):
    """Add calculated fields to costings (committed, sc_invoiced, sc_paid, c2c)."""
    # Lines 91-122 from main()
```

#### B. Create `core/services/contacts.py`
Extract from `main()`:
```python
def get_checked_contacts(division):
    """Get checked contacts for a division."""
    # Line 84-85 from main()
    
def get_all_contacts(division):
    """Get all contacts for a division (unfiltered)."""
    # Line 86-87 from main()
```

#### C. Create `core/services/aggregations.py`
Extract from `main()`:
```python
def calculate_dashboard_totals(costings):
    """Calculate all dashboard totals from costings."""
    # Lines 142-149 from main()
    return {
        'total_contract_budget': ...,
        'total_uncommitted': ...,
        'total_committed': ...,
        'total_forecast_budget': ...,
        'total_sc_invoiced': ...,
        'total_fixed_on_site': ...,
        'total_sc_paid': ...,
        'total_c2c': ...,
    }
```

### Phase 2: Refactor `main()` View (Priority: High)

After creating the services, `main()` should become:
```python
def main(request, division):
    # Get base data from services
    costings = costings_service.get_costings_for_division(division)
    contacts_list = contacts_service.get_checked_contacts(division)
    contacts_unfiltered_list = contacts_service.get_all_contacts(division)
    
    # Get quote data
    quote_allocations = quote_service.get_quote_allocations_for_division(division)
    committed_quotes_list = quote_service.get_committed_quotes_list(division)
    
    # Get invoice data
    invoice_allocations_sums = invoice_service.get_invoice_allocations_sums_dict()
    paid_invoice_allocations = invoice_service.get_paid_invoice_allocations_dict()
    
    # Enrich costings with calculations
    costings = costings_service.enrich_costings_with_calculations(
        costings, committed_values, invoice_allocations_sums, paid_invoice_allocations
    )
    
    # Get HC claims data
    hc_claims_list = claims_service.get_hc_claims_list(...)
    
    # Calculate totals
    totals = aggregations_service.calculate_dashboard_totals(costings)
    category_totals = costings_service.calculate_category_totals(costings)
    
    # Render
    return render(request, template, context)
```

### Phase 3: Extract HC Claim Logic (Priority: Medium)

Lines 182-217 in `main()` contain complex HC claim allocation logic that should move to `claims_service`:
```python
def enrich_costings_with_hc_claim_data(costings, current_hc_claim):
    """Add HC claim allocation data to costings."""
    # Lines 182-217 from main()
```

---

## Summary

**Existing Services (4):**
- ✅ `pos.py` - 5 functions
- ✅ `quotes.py` - 8 functions
- ✅ `invoices.py` - 9 functions
- ✅ `bills.py` (claims) - 9 functions

**New Services Needed (3):**
- ⏳ `costings.py` - ~4-5 functions
- ⏳ `contacts.py` - ~2 functions
- ⏳ `aggregations.py` - ~2 functions

**Optional Services (2):**
- 📋 `projects.py` - Project/SPV management
- 📋 `documents.py` - Document/file management

**Total Functions to Extract from main():**
- ~8-10 functions from `main()` view
- ~200-250 lines of business logic

This will reduce `main()` from ~350 lines to ~100 lines of pure view logic.
