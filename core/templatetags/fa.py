from datetime import datetime

import jdatetime
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
jdatetime.set_locale(jdatetime.FA_LOCALE)


@register.filter
def fa_num(value):
    return str(value if value is not None else "").translate(FA_DIGITS)


@register.filter
def jdate(value, fmt="%d %B %Y"):
    if not value:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value)
        j = jdatetime.datetime.fromgregorian(datetime=value)
    else:
        j = jdatetime.date.fromgregorian(date=value)
    return j.strftime(fmt).translate(FA_DIGITS)


@register.filter
def toman(value):
    """۱۲٬۳۴۵٬۰۰۰ تومان"""
    if value in (None, ""):
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", "٬").translate(FA_DIGITS)


@register.simple_tag
def percent_off(sale, regular):
    try:
        return fa_num(round((1 - int(sale) / int(regular)) * 100))
    except (TypeError, ValueError, ZeroDivisionError):
        return ""


@register.simple_tag
def stars(rating):
    try:
        r = float(rating or 0)
    except (TypeError, ValueError):
        r = 0
    full = int(round(r))
    return mark_safe(
        '<span class="stars" aria-label="امتیاز %s از ۵">%s%s</span>'
        % (fa_num(f"{r:.1f}"), "★" * full, '<span class="off">' + "★" * (5 - full) + "</span>")
    )


@register.simple_tag(takes_context=True)
def query_replace(context, *pairs, **kwargs):
    """{% query_replace "size" "6-meter" %} یا {% query_replace sort="new" %} — مقدار خالی یعنی حذف."""
    q = context["request"].GET.copy()
    kwargs.update(dict(zip(pairs[::2], pairs[1::2])))
    for k, v in kwargs.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    q.pop("page", None)
    s = q.urlencode()
    return "?" + s if s else ""


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None
