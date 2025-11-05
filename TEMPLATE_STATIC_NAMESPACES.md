# Template and Static Asset Namespace Structure

## Overview

Templates and static assets are now organized using Django's recommended namespace pattern. This enables:
- Predictable template overrides by PROJECT_TYPE apps
- No naming conflicts between apps
- Clear ownership of templates and static files
- Easy customization per PROJECT_TYPE

## Directory Structure

### Core App Templates
**Location:** `core/templates/core/`

All core templates are now namespaced under the `core/` directory:
```
core/
├── templates/
│   └── core/
│       ├── base_table.html
│       ├── build.html
│       ├── drawings.html
│       ├── hc_claim_modals.html
│       ├── hc_variation_modals.html
│       ├── homepage.html
│       ├── invoices_modals.html
│       ├── master.html
│       ├── model_viewer.html
│       ├── po_modals.html
│       ├── quotes_modals.html
│       └── view_po_pdf.html
```

### Core App Static Files
**Location:** `core/static/core/`

All core static assets are namespaced under the `core/` directory:
```
core/
├── static/
│   └── core/
│       ├── css/
│       ├── images/
│       ├── main/
│       └── media/
```

### PROJECT_TYPE App Templates

Each PROJECT_TYPE app has its own namespaced template directory:

```
development/
├── templates/
│   └── development/
│       └── (PROJECT_TYPE-specific templates)

construction/
├── templates/
│   └── construction/
│       └── (PROJECT_TYPE-specific templates)

precast/
├── templates/
│   └── precast/
│       └── (PROJECT_TYPE-specific templates)

pods/
├── templates/
│   └── pods/
│       └── (PROJECT_TYPE-specific templates)

general/
├── templates/
│   └── general/
│       └── (PROJECT_TYPE-specific templates)
```

### PROJECT_TYPE App Static Files

Each PROJECT_TYPE app has its own namespaced static directory:

```
development/static/development/
construction/static/construction/
precast/static/precast/
pods/static/pods/
general/static/general/
```

## Usage in Views

### Rendering Templates

**Old Way (without namespaces):**
```python
return render(request, 'homepage.html', context)
```

**New Way (with namespaces):**
```python
return render(request, 'core/homepage.html', context)
```

**PROJECT_TYPE-specific templates:**
```python
# Development-specific template
return render(request, 'development/dashboard.html', context)

# Construction-specific template
return render(request, 'construction/dashboard.html', context)
```

## Usage in Templates

### Extending Base Templates

**In core templates:**
```django
{% extends "core/master.html" %}
```

**In PROJECT_TYPE templates (extending core base):**
```django
{% extends "core/master.html" %}

{% block content %}
    <!-- PROJECT_TYPE-specific content -->
{% endblock %}
```

### Including Templates

**Old Way:**
```django
{% include "invoices_modals.html" %}
```

**New Way:**
```django
{% include "core/invoices_modals.html" %}
```

### Loading Static Files

**Old Way:**
```django
{% load static %}
<link rel="stylesheet" href="{% static 'css/styles.css' %}">
<script src="{% static 'main/invoices.js' %}"></script>
```

**New Way:**
```django
{% load static %}
<link rel="stylesheet" href="{% static 'core/css/styles.css' %}">
<script src="{% static 'core/main/invoices.js' %}"></script>
```

**PROJECT_TYPE-specific static files:**
```django
{% load static %}
<link rel="stylesheet" href="{% static 'construction/css/custom.css' %}">
<script src="{% static 'development/js/dashboard.js' %}"></script>
```

## Template Override Pattern

PROJECT_TYPE apps can override core templates by creating a template with the same name:

**Example: Overriding homepage for Development**

1. Create `development/templates/development/homepage.html`
2. Extend core template and override specific blocks:

```django
{% extends "core/homepage.html" %}

{% block extra_css %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'development/css/custom.css' %}">
{% endblock %}

{% block content %}
    <!-- Development-specific homepage content -->
    {{ block.super }}  {# Include core content if needed #}
{% endblock %}
```

3. Update view to use PROJECT_TYPE template:
```python
def homepage_view(request):
    project_type = get_project_type(request)  # From resolver
    template = f'{project_type}/homepage.html'
    return render(request, template, context)
```

## Static File Collection

When deploying, run `collectstatic` to gather all static files:

```bash
python manage.py collectstatic
```

This will collect static files from all apps into `STATIC_ROOT`, maintaining the namespace structure:
```
static/
├── core/
│   ├── css/
│   ├── main/
│   └── ...
├── development/
│   └── ...
├── construction/
│   └── ...
└── ...
```

## Benefits

1. **No Name Collisions:** Each app's templates/static files are isolated
2. **Clear Ownership:** Easy to see which app owns which template/file
3. **Predictable Overrides:** PROJECT_TYPE apps can override core templates
4. **Easy Testing:** Can test each app's templates independently
5. **Maintainability:** Clear organization makes updates easier

## Migration Checklist

- [x] Create namespaced template directories for all apps
- [x] Move core templates to `core/templates/core/`
- [x] Create namespaced static directories for all apps
- [x] Move core static files to `core/static/core/`
- [x] Update views to reference namespaced template paths
- [ ] Update templates to use namespaced {% extends %} and {% include %}
- [ ] Update templates to use namespaced {% static %} tags
- [ ] Test that all templates render correctly
- [ ] Test that all static files load correctly
- [ ] Run collectstatic and verify output

## Current Status

✅ **Completed:**
- Namespaced directory structure created for all apps
- Core templates moved to `core/templates/core/`
- Core static files moved to `core/static/core/`
- Views updated to reference namespaced template paths
- Django check passes with no issues

⏳ **Next Steps:**
- Update templates to use namespaced paths ({% extends %}, {% include %}, {% static %})
- Test template rendering
- Test static file loading
- Document any PROJECT_TYPE-specific customizations

## Examples

### Creating a PROJECT_TYPE-Specific Template

**File:** `construction/templates/construction/claims_dashboard.html`
```django
{% extends "core/master.html" %}
{% load static %}

{% block title %}Construction Claims Dashboard{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="{% static 'construction/css/claims.css' %}">
{% endblock %}

{% block content %}
    <h1>Construction Claims Dashboard</h1>
    <!-- Construction-specific content -->
{% endblock %}

{% block extra_js %}
    <script src="{% static 'construction/js/claims.js' %}"></script>
{% endblock %}
```

**View:** `construction/views.py`
```python
def claims_dashboard(request):
    context = {
        'claims': get_construction_claims(),
    }
    return render(request, 'construction/claims_dashboard.html', context)
```

### Creating PROJECT_TYPE-Specific Static Files

**File:** `construction/static/construction/css/claims.css`
```css
/* Construction-specific styles */
.claims-table {
    /* Custom styling for construction claims */
}
```

**File:** `construction/static/construction/js/claims.js`
```javascript
// Construction-specific JavaScript
function handleClaimSubmit() {
    // Construction-specific logic
}
```

## Testing

To verify templates and static files work correctly:

1. **Check Django configuration:**
```bash
python manage.py check
```

2. **Test template rendering:**
```bash
python manage.py shell
>>> from django.template.loader import get_template
>>> template = get_template('core/homepage.html')
>>> print(template.origin.name)
```

3. **Collect static files:**
```bash
python manage.py collectstatic --noinput
```

4. **Run development server and verify:**
```bash
python manage.py runserver
# Visit pages and check browser console for 404s
```
