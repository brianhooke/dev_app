# Quotes Module

## Data Flow

| File | Responsibility |
|------|----------------|
| `views/quotes.py` | Single source of truth for column config & all CRUD operations |
| `templates/core/quotes.html` | Glue layer - includes layout, loads JS, calls AllocationsManager.init() |
| `templates/core/components/allocations_layout.html` | Reusable HTML structure (tables, viewers, CSS) |
| `static/core/js/allocations_layout.js` | Reusable JS behavior (populate, select, CRUD events) |

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  REQUEST: /core/quotes/                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  quotes.py: quotes_view()                                       │
│  - Defines main_table_columns (headers, widths)                 │
│  - Defines allocations_columns                                  │
│  - render('core/quotes.html', context)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  quotes.html                                                    │
│  - {% include allocations_layout.html with columns... %}        │
│  - <script src="allocations_layout.js">                         │
│  - AllocationsManager.init({sectionId: 'quote'})                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  allocations_layout.html                                        │
│  - Renders table structure with section_id prefix               │
│  - Loops columns to create <th> headers                         │
│  - Creates #quoteMainTableBody (empty, for JS)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  allocations_layout.js                                          │
│  - AllocationsManager.init() stores config, binds events        │
│  - populateMainTable() renders data rows via custom renderRow() │
│  - selectRow() handles row selection, loads allocations         │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/core/quotes/` | GET | Render template with column config |
| `/core/get_project_quotes/{pk}/` | GET | Fetch all quotes for project |
| `/core/get_allocations_for_quote/{pk}/` | GET | Fetch allocations for selected quote |
| `/core/save_project_quote/` | POST | Create new quote |
| `/core/update_quote/` | POST | Update existing quote |
| `/core/delete_quote/` | POST | Delete quote |
| `/core/create_quote_allocation/` | POST | Create allocation row |
| `/core/update_quote_allocation/{pk}/` | POST | Update allocation row |
| `/core/delete_quote_allocation/{pk}/` | DELETE | Delete allocation row |
| `/core/get_project_contacts/{pk}/` | GET | Fetch contacts for dropdown |

---

## Functions in quotes.py

| Function | Purpose |
|----------|---------|
| `quotes_view` | Render template with column config |
| `get_project_quotes` | Fetch quotes for project |
| `get_quote_allocations_for_quote` | Fetch allocations for quote |
| `save_project_quote` | Create new quote |
| `update_quote` | Update existing quote |
| `delete_quote` | Delete quote |
| `create_quote_allocation` | Create allocation row |
| `update_quote_allocation` | Update allocation row |
| `delete_quote_allocation` | Delete allocation row |
| `get_project_contacts` | Fetch contacts for dropdown |
| `commit_data` | Legacy quote creation |
