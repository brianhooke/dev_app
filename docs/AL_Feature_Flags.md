# AllocationsLayout Feature Flags

Feature flags control behavior per section in `allocations_layout.js`.

---

## Available Flags

| Flag                | Default | Description                                  |
| ------------------- | ------- | -------------------------------------------- |
| `deleteRowBtn`      | `false` | Show delete button in main table rows        |
| `saveRowBtn`        | `false` | Show save/update button in main table rows   |
| `constructionMode`  | `false` | Enable qty/unit/rate columns for allocations |
| `gstField`          | `false` | Show GST inputs in allocations               |
| `confirmDelete`     | `true`  | Show confirmation dialog before delete       |
| `reloadAfterSave`   | `false` | Reload table data after successful save      |
| `reloadAfterDelete` | `true`  | Reload table data after successful delete    |

---

## Feature Flags by Section

| Section    | deleteRowBtn | saveRowBtn | constructionMode | gstField | confirmDelete | reloadAfterSave | reloadAfterDelete |
| ---------- | ------------ | ---------- | ---------------- | -------- | ------------- | --------------- | ----------------- |
| **Quotes** | ✅            | ✅          | dynamic*         | ❌        | ✅             | ❌               | ✅                 |
| **Bills**  | ❌            | ❌          | dynamic*         | ✅        | ✅             | ❌               | ✅                 |
| **PO**     | ❌            | ❌          | ❌                | ❌        | ❌             | ❌               | ❌                 |

*dynamic = determined at runtime by `isConstructionProject()` check

---

## Usage Example

Feature flags are set **in JavaScript** via the `AllocationsManager.init()` call, typically located in:
- `core/templates/core/includes/projects_scripts.html` - for Quotes and Bills within the Projects page
- `core/templates/core/quotes.html` - for standalone Quotes page
- `core/templates/core/includes/bills_scripts.html` - for standalone Bills page

They are **not** stored in the database. Each template hardcodes its own flag values at initialization time.

```javascript
// Example from projects_scripts.html (Quotes section)
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
    // ... rest of config
});
```

---

**Related:** [[ALLOCATIONS_LAYOUT]]
