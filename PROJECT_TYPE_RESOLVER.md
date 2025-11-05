# PROJECT_TYPE Resolver Documentation

## Overview

The PROJECT_TYPE resolver mechanism determines which app features and customizations are active for each request. This enables the application to support multiple project types (Development, Construction, Precast, Pods, General) with type-specific behavior.

## Architecture

### 1. Database Model

**Projects Model** (`core/models.py`):
```python
class Projects(models.Model):
    PROJECT_TYPE_CHOICES = [
        ('general', 'General'),
        ('development', 'Development'),
        ('construction', 'Construction'),
        ('precast', 'Precast'),
        ('pods', 'Pods'),
    ]
    
    project_type = models.CharField(
        max_length=20,
        choices=PROJECT_TYPE_CHOICES,
        default='general'
    )
```

**Migration:** `core/migrations/0002_add_project_type_field.py`

### 2. Middleware

**ProjectTypeMiddleware** (`core/middleware.py`):
- Runs on every request
- Resolves the active PROJECT_TYPE
- Attaches `request.project_type` and `request.project` to the request object

**Resolution Strategy:**
1. Check session for stored `project_type`
2. Check if there's a single project in database, use its type
3. Default to `'general'` if no project exists

### 3. Context Processor

**project_type_context** (`core/middleware.py`):
- Makes `project_type` and `project` available in all templates
- Provides `PROJECT_TYPE_CHOICES` for dropdowns/selectors

### 4. Utility Functions

**core/utils/project_type.py** provides:
- `get_project_type(request)` - Get active project type
- `get_project(request)` - Get active project instance
- `set_project_type(request, project_type)` - Set project type in session
- `set_active_project(request, project_pk)` - Set active project
- `get_template_for_project_type(base_template, request)` - Get template path
- `is_project_type(request, project_type)` - Check if current type matches
- `get_available_project_types()` - Get all available types

### 5. Views

**core/views/project_type.py** provides:
- `switch_project_type(request)` - API endpoint to switch PROJECT_TYPE
- `switch_project(request)` - API endpoint to switch active project
- `get_current_project_info(request)` - Get current project info
- `project_selector_view(request)` - UI for project selection

## Usage

### In Views

**Access current PROJECT_TYPE:**
```python
from core.utils import get_project_type

def my_view(request):
    project_type = get_project_type(request)
    # or
    project_type = request.project_type
    
    if project_type == 'construction':
        # Construction-specific logic
        pass
```

**Conditional template selection:**
```python
from core.utils import get_template_for_project_type

def my_view(request):
    template = get_template_for_project_type('dashboard.html', request)
    return render(request, template, context)
```

**Check PROJECT_TYPE:**
```python
from core.utils import is_project_type

def my_view(request):
    if is_project_type(request, 'development'):
        # Development-specific logic
        pass
```

### In Templates

**Access project_type:**
```django
<p>Current project type: {{ project_type }}</p>

{% if project_type == 'construction' %}
    <!-- Construction-specific content -->
{% endif %}
```

**Access project:**
```django
{% if project %}
    <p>Project: {{ project.project }}</p>
    <p>Type: {{ project.project_type }}</p>
{% endif %}
```

**Create PROJECT_TYPE selector:**
```django
<select id="project-type-selector">
    {% for value, label in PROJECT_TYPE_CHOICES %}
        <option value="{{ value }}" {% if value == project_type %}selected{% endif %}>
            {{ label }}
        </option>
    {% endfor %}
</select>
```

### JavaScript API

**Switch PROJECT_TYPE:**
```javascript
fetch('/switch_project_type/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        project_type: 'construction'
    })
})
.then(response => response.json())
.then(data => {
    console.log('Switched to:', data.project_type);
    location.reload(); // Reload to apply changes
});
```

**Switch active project:**
```javascript
fetch('/switch_project/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        project_pk: 123
    })
})
.then(response => response.json())
.then(data => {
    console.log('Switched to project:', data.project_name);
    location.reload();
});
```

**Get current project info:**
```javascript
fetch('/get_current_project_info/')
    .then(response => response.json())
    .then(data => {
        console.log('Current type:', data.project_type);
        console.log('Available types:', data.available_types);
    });
```

## URL Endpoints

All endpoints are namespaced under `core:`:

- `core:switch_project_type` - POST endpoint to switch PROJECT_TYPE
- `core:switch_project` - POST endpoint to switch active project
- `core:get_current_project_info` - GET endpoint for current project info
- `core:project_selector` - UI page for project selection

## Configuration

### Enable Middleware

Add to `settings.py`:
```python
MIDDLEWARE = [
    # ... other middleware
    'core.middleware.ProjectTypeMiddleware',
]
```

### Enable Context Processor

Add to `settings.py`:
```python
TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                # ... other context processors
                'core.middleware.project_type_context',
            ],
        },
    },
]
```

## Session Storage

The resolver stores data in the session:
- `request.session['project_type']` - Active project type
- `request.session['project_pk']` - Active project primary key

## Examples

### Example 1: Conditional View Logic

```python
from core.utils import get_project_type

def invoice_list(request):
    project_type = get_project_type(request)
    
    # Get invoices
    invoices = Invoice.objects.all()
    
    # Apply PROJECT_TYPE-specific filtering
    if project_type == 'construction':
        invoices = invoices.filter(invoice_type='construction')
    elif project_type == 'development':
        invoices = invoices.filter(invoice_type='development')
    
    # Use PROJECT_TYPE-specific template
    template = f'{project_type}/invoices/list.html'
    
    return render(request, template, {'invoices': invoices})
```

### Example 2: Template Inheritance

**Base template** (`core/templates/core/base.html`):
```django
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}My App{% endblock %}</title>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav>
        <span>Project Type: {{ project_type }}</span>
    </nav>
    
    {% block content %}{% endblock %}
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

**PROJECT_TYPE-specific template** (`construction/templates/construction/dashboard.html`):
```django
{% extends "core/base.html" %}

{% block title %}Construction Dashboard{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="{% static 'construction/css/dashboard.css' %}">
{% endblock %}

{% block content %}
    <h1>Construction Dashboard</h1>
    <!-- Construction-specific content -->
{% endblock %}
```

### Example 3: Dynamic Template Selection

```python
from django.template.loader import select_template

def dashboard(request):
    project_type = get_project_type(request)
    
    # Try PROJECT_TYPE-specific template first, fallback to core
    template = select_template([
        f'{project_type}/dashboard.html',
        'core/dashboard.html',
    ])
    
    return render(request, template, context)
```

## Testing

### Test PROJECT_TYPE Resolution

```python
from django.test import TestCase, RequestFactory
from core.models import Projects
from core.middleware import ProjectTypeMiddleware
from core.utils import get_project_type

class ProjectTypeResolverTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ProjectTypeMiddleware(lambda r: None)
    
    def test_default_project_type(self):
        """Should default to 'general' when no project exists."""
        request = self.factory.get('/')
        request.session = {}
        
        self.middleware(request)
        
        self.assertEqual(request.project_type, 'general')
    
    def test_project_type_from_project(self):
        """Should use project's type when project exists."""
        project = Projects.objects.create(
            project='Test Project',
            project_type='construction'
        )
        
        request = self.factory.get('/')
        request.session = {}
        
        self.middleware(request)
        
        self.assertEqual(request.project_type, 'construction')
    
    def test_project_type_from_session(self):
        """Should use session value when set."""
        request = self.factory.get('/')
        request.session = {'project_type': 'development'}
        
        self.middleware(request)
        
        self.assertEqual(request.project_type, 'development')
```

## Migration Guide

### Step 1: Run Migration
```bash
python manage.py migrate core
```

### Step 2: Update Existing Projects
```python
# In Django shell or migration
from core.models import Projects

for project in Projects.objects.all():
    # Set appropriate project_type based on your logic
    project.project_type = 'general'  # or determine from project name/data
    project.save()
```

### Step 3: Enable Middleware and Context Processor
Update `settings.py` as shown in Configuration section.

### Step 4: Test
```bash
python manage.py runserver
# Visit pages and verify project_type is available
```

## Benefits

1. **Flexible Configuration:** Each project can have its own type
2. **Session-Based:** Users can switch between project types
3. **Template Overrides:** PROJECT_TYPE apps can override core templates
4. **Conditional Logic:** Views can implement type-specific behavior
5. **API Support:** JavaScript can switch types dynamically
6. **Testable:** Easy to test with different project types

## Future Enhancements

1. **User Preferences:** Store preferred PROJECT_TYPE per user
2. **URL-Based Resolution:** Determine type from URL path
3. **Multi-Tenancy:** Support multiple organizations with different types
4. **Permission-Based:** Restrict certain types to specific users
5. **Template Loader:** Custom template loader for automatic fallback
