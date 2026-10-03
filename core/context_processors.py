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
        "site_settings": s,
        "menu_categories": tops[:7],
        "menu_more": tops[7:],
    }
