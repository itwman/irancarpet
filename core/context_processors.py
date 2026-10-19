from collections import Counter

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count

from .models import SiteSettings


def _menu():
    from catalog.models import Category, Product

    counts = Counter(dict(
        Product.categories.through.objects.values_list("category_id").annotate(n=Count("id")).values_list("category_id", "n")
    ))
    cats = list(Category.objects.prefetch_related("children").order_by("order", "name"))
    total = Counter()
    for c in cats:
        total[c.parent_id or c.pk] += counts.get(c.pk, 0)
    tops = sorted((c for c in cats if c.parent_id is None and total[c.pk] > 0), key=lambda c: -total[c.pk])
    return tops


def _asset_version():
    """نسخهٔ فایل‌های استاتیک برای شکستن کش مرورگر بعد از هر به‌روزرسانی"""
    import os

    newest = 0
    for base in [str(settings.STATIC_ROOT), *[str(d) for d in settings.STATICFILES_DIRS]]:
        for sub in ("css", "js", "dashboard"):
            d = os.path.join(base, sub)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    try:
                        newest = max(newest, int(os.path.getmtime(os.path.join(d, f))))
                    except OSError:
                        pass
    return format(newest, "x")


ASSET_V = _asset_version()


def _bing():
    v = cache.get("bing_verification")
    if v is None:
        from seo.models import SeoSettings

        v = SeoSettings.objects.filter(pk=1).values_list("bing_verification", flat=True).first() or ""
        cache.set("bing_verification", v, 300)
    return v


def site(request):
    tops = cache.get("menu_categories")
    if tops is None:
        tops = _menu()
        cache.set("menu_categories", tops, 600)
    s = cache.get("site_settings")
    if s is None:
        s = SiteSettings.load()
        cache.set("site_settings", s, 300)
    return {
        "SITE_URL": settings.SITE_URL,
        "ASSET_V": ASSET_V,
        "site_settings": s,
        "menu_categories": tops[:7],
        "menu_more": tops[7:],
        "bing_verification": _bing(),
        "footer_sizes": _footer_sizes(),
        "apps_promo": _apps_promo(request),
        "fp_gift": _fp_gift(),
    }


def _fp_gift():
    """نوار «هدیهٔ فرش پلاس» در فوتر و سبد خرید."""
    v = cache.get("fp_gift")
    if v is None:
        try:
            from farshplus.gift import info

            v = info() or {}
        except Exception:  # noqa: BLE001
            v = {}
        cache.set("fp_gift", v, 300)
    return v or None


def _apps_promo(request):
    """معرفی اپ‌ها در کافه‌بازار؛ داخل خود اپ (وب‌ویو) نشان داده نمی‌شود."""
    ua = request.headers.get("User-Agent", "")
    if "; wv)" in ua or request.headers.get("X-Requested-With", "").startswith(("net.irancarpet", "ir.farshestan")):
        return None
    v = cache.get("apps_promo")
    if v is None:
        try:
            from api.models import AppSettings

            v = AppSettings.load().promo()
        except Exception:  # noqa: BLE001
            v = {}
        cache.set("apps_promo", v, 600)
    return v or None


def _footer_sizes():
    """پیوند صفحه‌های فرود سایز در فوتر (پیوند داخلی برای گوگل)."""
    rows = cache.get("landing:footer")
    if rows is None:
        try:
            from landing.build import live

            rows = [(x.title, x.get_absolute_url()) for x in live().filter(reeds=None, color=None, style=None).order_by("size__sort_order")[:6]]
        except Exception:  # noqa: BLE001
            rows = []
        cache.set("landing:footer", rows, 3600)
    return rows
