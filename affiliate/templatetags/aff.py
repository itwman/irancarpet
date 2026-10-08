from django import template

from core.templatetags.fa import fa_num

register = template.Library()


@register.filter
def pct(value):
    """1.50 ← «۱٫۵»، 2.00 ← «۲»"""
    try:
        s = f"{float(value):.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""
    return fa_num(s.replace(".", "٫"))
