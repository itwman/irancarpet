"""فرش‌هایی که به آلبوم قیمت وصل نیستند (یا آلبومشان غیرفعال است) و حدس آلبوم درست برایشان.

حدس: آلبومی که فرش‌های هم‌برند، هم‌شانه و هم‌جنسِ این فرش در آن هستند. فقط وقتی پیشنهاد می‌شود که
دقیقاً یک آلبوم فعال بخورد؛ اگر یک کارخانه دو آلبوم هم‌شانه داشته باشد (مثلاً دو گروه قیمت)، پیشنهادی داده نمی‌شود.
"""
from django.core.cache import cache
from django.db.models import Q

KEY = "album_suggest_index"


def missing_q(kind="missing"):
    """فرش‌های خود سایت (نه فروشندگان بازارچه) بدون آلبوم یا با آلبوم غیرفعال."""
    none, inactive = Q(album__isnull=True), Q(album__is_active=False)
    q = {"none": none, "inactive": inactive}.get(kind, none | inactive)
    return q & Q(seller__isnull=True)


def _attr_ids():
    from catalog.models import Attribute

    reeds = set(Attribute.objects.filter(Q(slug="reeds-per-meter") | Q(label__contains="شانه")).values_list("pk", flat=True))
    mat = set(Attribute.objects.filter(label__contains="جنس").values_list("pk", flat=True))
    return reeds, mat


def _keys(pid, brand, specs, reeds_ids, mat_ids):
    r = next((t for a, t in specs.get(pid, ()) if a in reeds_ids), None)
    m = next((t for a, t in specs.get(pid, ()) if a in mat_ids), None)
    if not brand or not r:
        return None, None
    return (brand, r, m), (brand, r)


def index():
    """{(برند، شانه، جنس): {آلبوم‌ها}, (برند، شانه): {آلبوم‌ها}} از فرش‌های آلبوم‌های فعال؛ ۵ دقیقه کش."""
    idx = cache.get(KEY)
    if idx is not None:
        return idx
    from catalog.models import Product

    reeds_ids, mat_ids = _attr_ids()
    rows = list(Product.objects.filter(album__is_active=True, seller__isnull=True).exclude(status="trash")
                .values_list("pk", "album_id", "brand_id"))
    specs = _specs([pk for pk, _, _ in rows], reeds_ids | mat_ids)
    idx = {}
    for pk, album, brand in rows:
        k3, k2 = _keys(pk, brand, specs, reeds_ids, mat_ids)
        if k3:
            idx.setdefault(k3, set()).add(album)
            idx.setdefault(k2, set()).add(album)
    cache.set(KEY, idx, 300)
    return idx


def _specs(pids, attr_ids):
    from catalog.models import Product

    out = {}
    for pid, a, t in (Product.specs.through.objects.filter(product_id__in=pids, attributeterm__attribute_id__in=attr_ids)
                      .values_list("product_id", "attributeterm__attribute_id", "attributeterm_id")):
        out.setdefault(pid, []).append((a, t))
    return out


def suggest_ids(products):
    """{شناسهٔ فرش: شناسهٔ آلبوم پیشنهادی} برای فرش‌هایی که پیشنهاد بی‌ابهام دارند."""
    products = [p for p in products if not p.album_id or (p.album and not p.album.is_active)]
    if not products:
        return {}
    idx = index()
    reeds_ids, mat_ids = _attr_ids()
    specs = _specs([p.pk for p in products], reeds_ids | mat_ids)
    out = {}
    for p in products:
        k3, k2 = _keys(p.pk, p.brand_id, specs, reeds_ids, mat_ids)
        if not k3:
            continue
        albums = idx.get(k3) if k3[2] else None
        albums = albums or idx.get(k2) or set()
        if len(albums) == 1:
            out[p.pk] = next(iter(albums))
    return out


def suggestion(p):
    from .models import Album

    a = suggest_ids([p]).get(p.pk)
    return Album.objects.filter(pk=a).first() if a else None
