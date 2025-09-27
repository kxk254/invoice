
from django import template
import calendar

register = template.Library()

@register.filter
def japan_month_format(value):
    if value:
        return f"{value.year}年{value.month}月分"
    return ""

@register.filter
def japan_day_format(value):
    if value:
        return f"{value.year}年{value.month}月{value.day}日"
    return ""

@register.filter
def year_month(value):
    if value:
        return f"{value.year}{value.month}"
    return ""

@register.filter
def japan_last_day_format(value):
    if value:
        # Get the last day of the month
        last_day = calendar.monthrange(value.year, value.month)[1]
        
        # Return the formatted string with the last day of the month
        return f"{value.year}年{value.month}月{last_day}日"
    return ""

@register.filter
def uppercase(value):
    return value.upper()

@register.filter
def caseclean(value):
    if value is None:
        return ""  # Return actual None if value is None
    return value.upper()

@register.filter
def format_with_000s(value):
    """
    Format the value with commas and append '000'.
    Example: 123 -> 123,000
    """
    try:
        value = int(value)  # Ensure the value is an integer
        formatted_value = f"{value:,}"  # Format with commas and append 000
        return formatted_value
    except (ValueError, TypeError):
        return value  # Return the original value if conversion fails

@register.filter
def format_id(value):
    return f"{value:07}" if value is not None else ""

import base64
@register.filter
def b64encode(value):
    # Ensure the input is bytes, not a string
    if isinstance(value, str):
        value = value.encode('utf-8')  # Convert the string to bytes
    return base64.b64encode(value).decode('utf-8')  # Return the base64 encoded string
