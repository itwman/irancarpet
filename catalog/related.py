"""فرش‌های پیشنهادی زیر هر فرش.

ترتیب:
  ۱. فرصت‌های ویژهٔ خرید هم‌رنگ
  ۲. هم‌رنگ، هم‌شانه و هم‌آلبوم
  ۳. هم‌رنگ و هم‌شانه (آلبوم‌های دیگر)
  ۴. هم‌رنگ با شانه‌های دیگر (نزدیک‌ترین شانه اول؛ مثلاً برای ۱۲۰۰: اول ۱۰۰۰، بعد ۱۵۰۰، بعد ۷۰۰)
  ۵. رنگ‌های نزدیک (هم‌خانوادهٔ رنگ در فرش‌یاب، مثل لاکی و قرمز)
  ۶. اگر هنوز کم بود: هم‌آلبوم/هم‌شانه، بعد هم‌دسته
"""
import re

from django.core.cache import cache

from .models import Product

LIMIT = 8


def _num(name):
    d = re.sub(r"\D", "", (name or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    return int(d) if d else None


def _specs(p):
    color, reeds = set(), set()
    for t in p.specs.all():
        label = (t.attribute.label or "").replace("‌", " ")
        if "رنگ" in label and "حاشیه" not in label:
            color.add(t.pk)
        elif "شانه" in label:
            reeds.add(t.pk)
    return color, reeds


def _color_family(p, color_ids):
    """محصولات هم‌خانوادهٔ رنگ (نیازهای رنگی فرش‌یاب که این فرش را دارند)."""
    try:
        from finder.engine import active_needs, need_q
    except Exception:  # noqa: BLE001
        return Product.objects.none()
    from django.db.models import Q

    q = Q(pk__in=[])
    found = False
    for n in active_needs():
        if n.group == "color" and Product.objects.filter(pk=p.pk).filter(need_q(n)).exists():
            q |= need_q(n)
            found = True
    return Product.objects.filter(q) if found else Product.objects.none()


def ranked_ids(p, cat=None):
    key = f"related:{p.pk}:{p.modified_at.timestamp() if p.modified_at else 0}"
    ids = cache.get(key)
    if ids is not None:
        return ids
    base = (Product.objects.published().exclude(pk=p.pk).exclude(stock_status="outofstock").filter(image__isnull=False))
    if p.design_name and p.album_id:  # رنگ‌های دیگر همین نقشه بالای صفحه آمده‌اند
        base = base.exclude(design_name__iexact=p.design_name, album_id=p.album_id)
    color, reeds = _specs(p)
    out, seen = [], {p.pk}

    def add(qs, n=LIMIT * 3):
        for pid in qs.values_list("pk", flat=True)[:n]:
            if pid not in seen:
                seen.add(pid)
                out.append(pid)

    if color:
        same_color = base.filter(specs__in=color).distinct()
        if reeds and p.album_id:
            add(same_color.filter(specs__in=reeds, album_id=p.album_id).order_by("-views"))
        if reeds:
            add(same_color.filter(specs__in=reeds).order_by("-views"))
        # شانه‌های دیگر: نزدیک‌ترین شانه اول
        my = [x for x in (_num(t.name) for t in p.specs.filter(pk__in=reeds)) if x]
        rest = list(same_color.exclude(pk__in=seen).prefetch_related("specs__attribute").order_by("-views")[:120])
        if my:
            def dist(x):
                vals = [_num(t.name) for t in x.specs.all() if "شانه" in (t.attribute.label or "") and _num(t.name)]
                d = min((abs(v - my[0]) for v in vals), default=10_000)
                lower = 0 if vals and vals[0] < my[0] else 1  # در فاصلهٔ برابر، شانهٔ پایین‌تر (ارزان‌تر) اول
                return (d, lower)
            rest.sort(key=dist)
        for x in rest:
            if x.pk not in seen:
                seen.add(x.pk)
                out.append(x.pk)
        fam = _color_family(p, color)
        if fam is not None:
            fam_qs = base.filter(pk__in=fam.values("pk"))
            if p.album_id:
                add(fam_qs.filter(album_id=p.album_id).order_by("-views"))
            add(fam_qs.filter(specs__in=reeds).distinct().order_by("-views") if reeds else fam_qs.order_by("-views"))
            add(fam_qs.order_by("-views"))
    if len(out) < LIMIT:
        if p.album_id:
            add(base.filter(album_id=p.album_id).order_by("-views"))
        if reeds:
            add(base.filter(specs__in=reeds).distinct().order_by("-views"))
        if cat:
            add(base.filter(categories=cat).order_by("-views"))
    ids = out[:LIMIT * 3]
    cache.set(key, ids, 900)
    return ids


def related_products(p, cat=None, limit=LIMIT):
    from shop.offers import live_offers

    from .views import card_queryset

    ids = ranked_ids(p, cat)
    color, _ = _specs(p)
    # فرصت‌های ویژهٔ هم‌رنگ اول
    offers = {}
    for o in live_offers():
        if o.product_id != p.pk:
            offers.setdefault(o.product_id, o)
    offer_ids = []
    if color and offers:
        offer_ids = list(Product.objects.filter(pk__in=list(offers), specs__in=color).distinct().values_list("pk", flat=True))
    order = offer_ids + [i for i in ids if i not in offer_ids]
    order = order[:limit]
    by = {x.pk: x for x in card_queryset(Product.objects.filter(pk__in=order))}
    items = [by[i] for i in order if i in by]
    for x in items:
        x.offer = offers.get(x.pk)
    return items


# ------------------------------------------------------------------ مجموعه (مثل «پالت موکا»)
def collection_for(p, exclude=()):
    """دستهٔ «مجموعه»ای که این فرش در آن است و چند فرش دیگرش با نقشه‌های متفاوت (هر نقشه یک بار).

    خروجی: {cat, label, note, count, items} یا None. فرش‌هایی که در ردیف «مشابه» یا رنگ‌های دیگر همین نقشه آمده‌اند تکرار نمی‌شوند.
    """
    from .models import Category
    from .views import card_queryset

    cat = (Category.objects.filter(products=p, redirect_url="").exclude(collection_label="").order_by("order", "pk").first())
    if cat is None:
        return None
    key = f"coll:{cat.pk}:{p.pk}:{p.modified_at.timestamp() if p.modified_at else 0}"
    hit = cache.get(key)
    if hit is None:
        base = (Product.objects.published().filter(categories__in=cat.descendant_ids(), image__isnull=False)
                .exclude(pk=p.pk).exclude(stock_status="outofstock").distinct())
        count = base.count() + 1
        ids, designs = [], {(p.design_name or "").strip()}
        for pid, design in base.order_by("-views", "-pk").values_list("pk", "design_name")[:200]:
            d = (design or "").strip()
            if d and d in designs:
                continue
            designs.add(d)
            ids.append(pid)
            if len(ids) >= LIMIT * 2:
                break
        hit = {"ids": ids, "count": count}
        cache.set(key, hit, 900)
    skip = set(exclude)
    order = [i for i in hit["ids"] if i not in skip][:LIMIT]
    by = {x.pk: x for x in card_queryset(Product.objects.filter(pk__in=order))}
    return {"cat": cat, "label": cat.collection_label, "note": cat.collection_note, "count": hit["count"],
            "items": [by[i] for i in order if i in by]}
