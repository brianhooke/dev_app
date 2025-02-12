from django import template
import locale
import json

register = template.Library()

@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def max_value(value1, value2):
    return max(value1, value2)

@register.filter
def numberformat(value, decimal_pos=2):
    locale.setlocale(locale.LC_ALL, '')  # Use '' for auto, or force e.g. to 'en_US.UTF-8'
    return locale.format_string(f"%%.%df" % decimal_pos, value, grouping=True)

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