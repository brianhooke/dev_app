from django import template
import json

register = template.Library()


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def max_value(value1, value2):
    return max(value1, value2)


# Removed: numberformat. It called locale.setlocale(LC_ALL, '') on every
# render, which mutates process-global state and races between requests.
# Use Django's built-in {{ value|floatformat:2 }} or the Money helpers in
# core/static/core/js/money.js instead.


@register.filter
def get_dict_value(dictionary, key):
    """Returns the value from the dictionary for the given key."""
    if dictionary and key in dictionary:
        return dictionary.get(key)
    return ''

@register.filter
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None

@register.filter(is_safe=True)
def parse_json(json_string):
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return {}