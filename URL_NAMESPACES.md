# URL Namespace Structure

## Overview

The application now uses Django URL namespaces to organize routes by app. This enables:
- Clear separation of concerns between PROJECT_TYPE apps
- Predictable URL reversing with `{% url 'namespace:name' %}`
- Easier maintenance and debugging
- Future-proof architecture for app-specific customization

## Namespace Structure

### Core App (namespace: `core`)
**URL Prefix:** `/` (root level)

The core app contains all shared business logic and currently handles all existing URLs.

**Example URLs:**
- `/` → `core:homepage`
- `/build/` → `core:build`
- `/drawings/` → `core:drawings`
- `/commit_data/` → `core:commit_data`
- `/upload_invoice/` → `core:upload_invoice`
- `/create_po_order/` → `core:create_po_order`

### PROJECT_TYPE Apps

Each PROJECT_TYPE app has its own namespace and URL prefix:

#### Development App (namespace: `development`)
**URL Prefix:** `/development/`

For development-specific features and overrides.

**Example URLs:**
- `/development/dashboard/` → `development:dashboard` (when implemented)

#### Construction App (namespace: `construction`)
**URL Prefix:** `/construction/`

For construction-specific features and overrides.

**Example URLs:**
- `/construction/dashboard/` → `construction:dashboard` (when implemented)

#### Precast App (namespace: `precast`)
**URL Prefix:** `/precast/`

For precast-specific features and overrides.

**Example URLs:**
- `/precast/dashboard/` → `precast:dashboard` (when implemented)

#### Pods App (namespace: `pods`)
**URL Prefix:** `/pods/`

For pods-specific features and overrides.

**Example URLs:**
- `/pods/dashboard/` → `pods:dashboard` (when implemented)

#### General App (namespace: `general`)
**URL Prefix:** `/general/`

For general project type features and overrides.

**Example URLs:**
- `/general/dashboard/` → `general:dashboard` (when implemented)

## Usage in Templates

### Old Way (without namespaces):
```django
<a href="{% url 'homepage' %}">Home</a>
<a href="{% url 'commit_data' %}">Commit Data</a>
```

### New Way (with namespaces):
```django
<a href="{% url 'core:homepage' %}">Home</a>
<a href="{% url 'core:commit_data' %}">Commit Data</a>
```

## Usage in Views

### Old Way (without namespaces):
```python
from django.urls import reverse
redirect_url = reverse('homepage')
```

### New Way (with namespaces):
```python
from django.urls import reverse
redirect_url = reverse('core:homepage')
```

## Migration Strategy

Currently, all URLs remain in the `core` app with the `core:` namespace. As PROJECT_TYPE-specific logic is migrated:

1. Move PROJECT_TYPE-specific views to respective app's `views.py`
2. Add URL patterns to respective app's `urls.py`
3. Update templates to use new namespaced URLs
4. Update view redirects to use new namespaced URLs

## Benefits

1. **Clear Organization:** Each app's URLs are self-contained
2. **No Name Collisions:** Different apps can have same URL names
3. **Easy Testing:** Can test each app's URLs independently
4. **Future-Proof:** Ready for app-specific customization
5. **Maintainability:** Clear which app owns which URLs

## Current Status

- ✅ All PROJECT_TYPE apps have `urls.py` with `app_name` defined
- ✅ Core app has `app_name = 'core'` defined
- ✅ Main `dev_app/urls.py` includes all apps with namespaces
- ✅ Django check passes with no issues
- ⏳ Templates need updating to use namespaced URLs (Task 6)
- ⏳ Views need updating to use namespaced reverse() (Task 6)

## Testing URL Resolution

To verify URLs resolve correctly:

```python
from django.urls import reverse

# Core URLs
assert reverse('core:homepage') == '/'
assert reverse('core:build') == '/build/'

# PROJECT_TYPE URLs (when implemented)
assert reverse('development:dashboard') == '/development/dashboard/'
assert reverse('construction:dashboard') == '/construction/dashboard/'
```

## Next Steps

1. Update templates to use `{% url 'core:name' %}` syntax
2. Update views to use `reverse('core:name')` syntax
3. Migrate PROJECT_TYPE-specific logic to respective apps
4. Add PROJECT_TYPE-specific URLs to respective `urls.py` files
