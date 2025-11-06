# Task 8: Migrate PROJECT_TYPE-Specific Logic - Implementation Plan

## Executive Summary

**Goal:** Move PROJECT_TYPE-specific code from core to respective apps for better separation of concerns.

**Key Finding:** Most code is actually SHARED, not PROJECT_TYPE-specific. Only HC claims/variations are truly construction-specific.

---

## Phase 1: Audit Results

### Models Analysis (22 total models)

**CONSTRUCTION-SPECIFIC (4 models):**
- `HC_claims` - Head contractor claims
- `HC_claim_allocations` - HC claim line items
- `Hc_variation` - HC variations
- `Hc_variation_allocations` - HC variation line items

**DOCUMENT-RELATED (6 models):**
- `DesignCategories`, `PlanPdfs`, `ReportCategories`, `ReportPdfs`, `Models_3d`, `Letterhead`
- Used across all PROJECT_TYPEs (shared)

**SHARED/CORE (12 models):**
- `Projects`, `SPVData` - Global
- `Categories`, `Costing` - Budget/costing (all PROJECT_TYPEs)
- `Quotes`, `Quote_allocations` - Quotes (all PROJECT_TYPEs)
- `Invoices`, `Invoice_allocations` - Supplier bills (all PROJECT_TYPEs)
- `Contacts` - Suppliers/clients (all PROJECT_TYPEs)
- `Po_globals`, `Po_orders`, `Po_order_detail` - Purchase orders (all PROJECT_TYPEs)

### Views Analysis

**Construction-heavy files:**
- `claims.py` - 161 construction terms (HC claims, variations)
- `main.py` - 211 construction terms (dashboard HC claim logic)

**Minimal construction references:**
- `bills.py`, `pos.py`, `quotes.py`, `documents.py` - 6-9 terms each (mostly imports)

### Services Analysis

**Construction-heavy services:**
- `invoices.py` - 222 terms (HC claims/variations logic)
- `bills.py` - 96 terms (HC claim associations)

**Minimal construction references:**
- Other services - 2-4 terms (mostly field names)

---

## Phase 2: Strategic Decision

### Option A: Keep All Models in Core (RECOMMENDED)

**Rationale:**
1. **Most models are shared** - Only 4 of 22 models are construction-specific
2. **Foreign key complexity** - HC_claims references Invoices, Costing, Categories (all core models)
3. **Database table preservation** - No need to rename tables or migrate data
4. **Simpler imports** - One source of truth for all models
5. **Current architecture already works** - Models are PROJECT_TYPE-agnostic by design

**What to move:**
- Views: `claims.py` → `construction/views/claims.py`
- Services: HC claim logic from `invoices.py` → `construction/services/claims.py`
- Templates: HC claim templates → `construction/templates/`
- Static: HC claim JS → `construction/static/`

**What stays in core:**
- ALL models (including HC_claims, HC_claim_allocations, etc.)
- Shared services (bills, quotes, pos, costings, contacts, aggregations)
- Shared views (main dashboard logic)

### Option B: Move Construction Models to Construction App

**Rationale:**
- Pure separation by PROJECT_TYPE
- Construction app is fully self-contained

**Challenges:**
1. **Complex migrations** - Need to preserve table names with db_table
2. **Cross-app foreign keys** - HC_claims references core.Costing, core.Categories
3. **Import updates** - 100+ import statements to update
4. **Testing overhead** - More complex to verify nothing breaks

---

## Phase 3: Recommended Implementation (Option A)

### Step 1: Move Construction Views

```
core/views/claims.py → construction/views/claims.py
```

**Actions:**
- Copy `claims.py` to `construction/views/claims.py`
- Update imports to reference core models
- Update `construction/urls.py` to include claim URLs
- Remove claims.py from core/views/
- Update `core/views/__init__.py` to remove claim imports

### Step 2: Extract Construction Service Logic

**From `core/services/invoices.py`:**
- Extract HC claim functions → `construction/services/claims.py`
- Keep invoice allocation functions in core (used by all PROJECT_TYPEs)

**Functions to move:**
- `get_hc_claims_list()`
- `get_hc_variations_list()`
- `get_hc_variation_allocations_list()`
- `get_current_hc_claim()`
- `get_hc_claim_wip_adjustments()`

**Functions to keep in core:**
- All invoice/bill allocation functions (used by development too)

### Step 3: Update Main Dashboard

**In `core/views/main.py`:**
- Keep HC claim display logic (dashboard shows HC claims)
- Import HC claim service from construction app
- Add conditional logic: only show HC claims if PROJECT_TYPE == 'construction'

### Step 4: Move Templates & Static

```
core/templates/core/hc_claim_modals.html → construction/templates/construction/
core/templates/core/hc_variation_modals.html → construction/templates/construction/
core/static/core/main/hc_claims_*.js → construction/static/construction/js/
core/static/core/main/hc_variations_*.js → construction/static/construction/js/
```

### Step 5: Update URLs

**construction/urls.py:**
```python
from django.urls import path
from . import views

app_name = 'construction'

urlpatterns = [
    path('create-hc-claim/', views.create_hc_claim, name='create_hc_claim'),
    path('update-hc-claim/', views.update_hc_claim_data, name='update_hc_claim'),
    path('send-hc-claim/<int:claim_id>/', views.send_hc_claim_to_xero, name='send_hc_claim'),
    path('create-variation/', views.create_variation, name='create_variation'),
    path('delete-variation/<int:variation_id>/', views.delete_variation, name='delete_variation'),
]
```

### Step 6: Update Imports

**Files to update:**
- `core/views/main.py` - Import construction services
- `core/urls.py` - Include construction URLs conditionally
- Templates - Update URL references to use `construction:` namespace

---

## Phase 4: Testing Checklist

- [ ] HC claim creation works
- [ ] HC claim update works
- [ ] HC claim send to Xero works
- [ ] Variation creation works
- [ ] Variation deletion works
- [ ] Dashboard displays HC claims correctly
- [ ] Non-construction PROJECT_TYPEs don't break
- [ ] All imports resolve correctly
- [ ] All URLs resolve correctly
- [ ] Django check passes
- [ ] No migration errors

---

## Phase 5: Future Considerations

### Development-Specific Features (Future)
When development app needs unique features:
- Create `development/services/` for development-specific logic
- Create `development/views/` for development-specific views
- Keep shared logic in core

### Precast/Pods-Specific Features (Future)
Same pattern as construction:
- Move PROJECT_TYPE-specific views to respective apps
- Keep models in core (unless truly isolated)
- Share services where possible

---

## Estimated Effort

- **Step 1-2:** Move views & services - 2 hours
- **Step 3:** Update main dashboard - 1 hour
- **Step 4:** Move templates & static - 1 hour
- **Step 5:** Update URLs - 30 min
- **Step 6:** Update imports - 1 hour
- **Testing:** 2 hours

**Total: ~7-8 hours**

---

## Risk Assessment

**Low Risk:**
- Moving views (self-contained)
- Moving templates (clear boundaries)
- Moving static files (clear boundaries)

**Medium Risk:**
- Extracting service functions (need to ensure clean separation)
- Updating imports (many files to update)

**High Risk:**
- Moving models (NOT RECOMMENDED - keep in core)

---

## Recommendation

**Proceed with Option A:**
1. Keep ALL models in core (including HC_claims)
2. Move construction-specific VIEWS to construction app
3. Extract construction-specific SERVICE logic to construction/services/
4. Move construction-specific TEMPLATES & STATIC to construction app
5. Update imports and URLs

This provides good separation while avoiding the complexity and risk of moving models between apps.
