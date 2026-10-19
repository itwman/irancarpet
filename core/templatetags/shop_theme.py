"""تگ‌های کمکی برای قالب‌های جدا (مثل قالب فرشستان) که به دادهٔ صفحهٔ اول وابسته نیستند.

    {% load shop_theme %}
    {% reeds_categories as rc %}      دسته‌هایی مثل «فرش ۷۰۰ شانه» با تعداد محصول
    {% color_categories as cc %}      دسته‌های «فرش زمینه …» با رنگ نمونه و تعداد
    {% latest_products 8 as items %}  تازه‌ترین فرش‌های موجود و عکس‌دار
    {{ "سرمه ای"|swatch }}            کد رنگ نمونه برای نام رنگ فارسی
    {% jyear %}                       سال شمسی جاری با ارقام فارسی
"""
import re

from django import template
from django.core.cache import cache
from django.db.models import Count, Q

register = template.Library()

COLORS = {
    "آبی": "#4A78A8", "اقیانوسی": "#1F5F7A", "بنفش": "#6B4C8A", "بژ": "#D9C4A3", "ترمه": "#6E2A2E", "تیتانیومی": "#8A8D8F",
    "دلفینی": "#6F8796", "دودی": "#6B6764", "روناسی": "#A3312A", "زغالی": "#3E3B39", "سبز آبی": "#3E8A86", "سبز": "#4E7A55",
    "سربی": "#5E6366", "سرمه": "#2E3A5C", "سفید": "#F4F1EA", "سیلور": "#CFCBC4", "شکلاتی": "#5A3A2A", "کرم صدفی": "#EFE4D2",
    "صدفی": "#EDE3D3", "طوسی": "#9A9690", "فیلی": "#8E8A84", "قهوه": "#6E4B33", "لاکی": "#8E2B2B", "قرمز": "#9B2C2C",
    "متالیک": "#9AA0A3", "مشکی": "#1E1C1B", "موشی": "#7D7770", "موکا": "#8B6A55", "نسکافه": "#A47E5E", "نقره": "#C3C5C7",
    "کاربنی": "#3B3D40", "کرم": "#E9DCC4", "یاسی": "#B9A3C9", "گردویی": "#6B4A32", "طلایی": "#C8A45C",
}
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def swatch(name):
    n = (name or "").replace("ي", "ی").replace("‌", " ")
    for key in sorted(COLORS, key=len, reverse=True):
        if key in n:
            return COLORS[key]
    return "#D9C4A3"


def _cat_counts():
    from catalog.models import Category

    data = cache.get("theme_cat_counts")
    if data is None:
        qs = (Category.objects.filter(parent=None)
              .annotate(n=Count("products", filter=Q(products__status="publish"), distinct=True)).filter(n__gt=0))
        data = [(c.pk, c.name, c.get_absolute_url(), c.n) for c in qs]
        cache.set("theme_cat_counts", data, 600)
    return data


@register.simple_tag
def reeds_categories():
    out = []
    for _pk, name, url, n in _cat_counts():
        m = re.search(r"(\d{3,4})\s*شانه", name.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if m:
            out.append({"reeds": int(m.group(1)), "name": name, "url": url, "count": n})
    return sorted(out, key=lambda x: x["reeds"])


@register.simple_tag
def color_categories(limit=12):
    out = []
    for _pk, name, url, n in _cat_counts():
        if "زمینه" in name:
            color = name.split("زمینه", 1)[1].strip()
            out.append({"name": color, "url": url, "count": n, "hex": swatch(color)})
    return sorted(out, key=lambda x: -x["count"])[:limit]


@register.simple_tag
def latest_products(n=8):
    from catalog.models import Product

    key = f"theme_latest_{n}"
    ids = cache.get(key)
    if ids is None:
        ids = list(Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False)
                   .order_by("-published_at", "-pk").values_list("pk", flat=True)[: int(n)])
        cache.set(key, ids, 600)
    items = {p.pk: p for p in Product.objects.filter(pk__in=ids).select_related("image", "brand")}
    return [items[i] for i in ids if i in items]


@register.simple_tag
def jyear():
    import jdatetime

    return str(jdatetime.date.today().year).translate(_FA)
