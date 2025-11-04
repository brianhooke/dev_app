from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter(is_safe=True)
def json_script(value):
    """Safely converts a value to JSON for use in JavaScript."""
    return mark_safe(json.dumps(value))
