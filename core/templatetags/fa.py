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
def fa_dec(value):
    """۴٫۶"""
    return fa_num(value).replace(".", "٫")


@register.filter
def jdate(value, fmt="%d %B %Y"):
    if not value:
        return ""
    if isinstance(value, datetime):
        value = timezone.localtime(value)
        j = jdatetime.datetime.fromgregorian(datetime=value, locale=jdatetime.FA_LOCALE)
    else:
        j = jdatetime.date.fromgregorian(date=value, locale=jdatetime.FA_LOCALE)
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


REEDS_RE = __import__("re").compile(r"(\d{3,4})\s*شانه")
REEDS_CLASS = {"700": "r700", "1000": "r1000", "1200": "r1200", "1500": "r1500"}


@register.filter
def reeds_of(title):
    """شانهٔ فرش از روی عنوان: «فرش 1200 شانه …» ← «1200»"""
    m = REEDS_RE.search(str(title or ""))
    return m.group(1) if m else ""


@register.filter
def reeds_class(reeds):
    return REEDS_CLASS.get(str(reeds), "rx")


@register.filter
def short_title(title):
    """«فرش 1200 شانه برجسته نقشه هانا زمینه صدفی» ← «هانا، زمینه صدفی» برای کارت‌های کوچک"""
    import re

    t = str(title or "")
    m = re.search(r"(?:نقشه|طرح)\s+(.+)$", t)
    if not m:
        return t
    rest = m.group(1)
    rest = re.sub(r"\s+زمینه\s+", "، زمینهٔ ", rest, count=1)
    return rest


@register.filter
def wa_link(number):
    import re

    n = re.sub(r"\D", "", str(number or ""))
    if n.startswith("0"):
        n = "98" + n[1:]
    return f"https://wa.me/{n}" if n else ""


@register.filter
def thumb(media, w=480):
    """نشانی نسخهٔ کوچک webp یک تصویر (۲۴۰، ۴۸۰ یا ۹۶۰ پیکسل) برای کارت‌ها؛ تصویر اصلی فقط در صفحهٔ فرش."""
    from urllib.parse import quote

    f = getattr(media, "file", None)
    if not f:
        return getattr(media, "url", "") or ""
    sizes = (240, 480, 960)
    w = min(sizes, key=lambda x: abs(x - int(w or 480)))
    return f"/app-img/{w}/{quote(f.name)}"
