"""منبع (ایران کارپت): خوراک امن محصولات برای فرشستان و دریافت سفارش‌هایش.

/api/mirror/v1/stock/              فهرست فشردهٔ همهٔ فرش‌های منتشرشدهٔ خود ایران کارپت: قیمت نهایی، موجودی و فرصت‌های ویژه
/api/mirror/v1/products/?ids=1,2   جزئیات کامل (مشخصات، دسته‌ها، عکس‌ها) برای محصولات تازه یا ویرایش‌شده
/api/mirror/v1/orders/             (POST) ثبت یا به‌روزرسانی سفارش فرشستان در پنل ایران کارپت
همه با سرآیند Authorization: Token <کلید اتصال پنل>
"""
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import MirrorSettings

_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _authorized(request):
    s = MirrorSettings.load()
    got = (request.headers.get("Authorization") or "").removeprefix("Token ").strip()
    return s.feed_enabled and s.api_key and got and hmac.compare_digest(got, s.api_key)


def guard(view):
    def wrapped(request, *a, **kw):
        if not _authorized(request):
            return JsonResponse({"ok": False, "error": "دسترسی ندارید"}, status=403)
        return view(request, *a, **kw)
    wrapped.__name__ = view.__name__
    return csrf_exempt(wrapped)


def own_products(picked=True):
    from catalog.models import Product

    # فقط کالای خود سایت (نه فروشندگان بازارچه) و نه کپی‌های همگام‌شده از جای دیگر؛
    # و فقط فرش‌هایی که در پنل برای فرشستان انتخاب شده‌اند (picked=False فقط برای جفت کردن کالاهای قدیمی)
    qs = Product.objects.published().filter(seller__isnull=True, mirror__isnull=True)
    return qs.filter(mirror_pick__isnull=False) if picked else qs


def reeds_of(p, specs=None):
    for t in specs if specs is not None else p.specs.all():
        if t.attribute.slug == "reeds-per-meter" or "شانه" in (t.attribute.label or ""):
            n = re.sub(r"\D", "", (t.name or "").translate(_EN))
            if n:
                return n
    m = re.search(r"(\d{3,4})\s*شانه", (p.title or "").translate(_EN))
    return m.group(1) if m else ""


def color_of(p, specs=None):
    for t in specs if specs is not None else p.specs.all():
        lab = t.attribute.label or ""
        if t.attribute.slug in ("color", "pa_color", "background-color") or "زمینه" in lab:
            return t.name.strip()
    return ""


def _offers(p):
    from shop.models import SpecialOffer

    out = []
    for o in SpecialOffer.objects.filter(product=p, is_active=True).select_related("size"):
        if not o.is_live:
            continue
        out.append([o.pk, o.size.slug, int(o.price), int(o.regular_price), o.remaining,
                    o.ends_at.isoformat() if o.ends_at else "", o.starts_at.isoformat()])
    return out


def compact(p):
    vs = [[v.pk, v.size.slug if v.size_id else "", int(v.final_price or 0), int(v.sale_price or 0) if v.on_sale else 0,
           bool(v.is_available), v.stock_qty, v.pair_only] for v in p.variations.all()]
    specs = list(p.specs.all())
    row = {"id": p.pk, "m": p.modified_at.isoformat(), "t": p.title, "d": p.design_name, "c": color_of(p, specs),
           "r": reeds_of(p, specs), "ss": p.sale_status, "a": p.album_id, "v": vs, "o": _offers(p)}
    row["h"] = hashlib.sha1(json.dumps([row["ss"], row["a"], vs, row["o"]], ensure_ascii=False).encode()).hexdigest()[:16]
    return row


def _qs(ids=None, picked=True):
    from catalog.models import Variation

    qs = own_products(picked).prefetch_related(
        Prefetch("variations", queryset=Variation.objects.select_related("size").order_by("size__sort_order", "menu_order")),
        "specs__attribute")
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    return qs.order_by("pk")


@guard
def stock(request):
    ids = None
    if request.GET.get("ids"):
        ids = [int(x) for x in request.GET["ids"].split(",") if x.strip().isdigit()][:200]
    picked = request.GET.get("all") != "1"
    return JsonResponse({"ok": True, "at": timezone.now().isoformat(), "products": [compact(p) for p in _qs(ids, picked)]},
                        json_dumps_params={"ensure_ascii": False})


def _media(m):
    return {"pk": m.pk, "url": settings.SITE_URL + m.url, "alt": m.alt or "", "w": m.width, "h": m.height}


def full(p):
    row = compact(p)
    cats = list(p.categories.all())
    row.update({
        "slug": p.slug, "english_name": p.english_name, "color_count": p.color_count, "video_url": p.video_url,
        "kind": p.kind, "sku": p.sku, "published_at": p.published_at.isoformat(),
        "brand": {"slug": p.brand.slug, "name": p.brand.name} if p.brand_id else None,
        "categories": [{"slug": c.slug, "name": c.name, "parent": c.parent.slug if c.parent_id else ""} for c in cats],
        "primary_category": p.primary_category.slug if p.primary_category_id else "",
        "specs": [{"attr": t.attribute.slug, "label": t.attribute.label, "slug": t.slug, "name": t.name,
                   "public": t.attribute.is_public, "filter": t.attribute.show_in_filters} for t in p.specs.all()],
        "sizes": [_size_row(v.size) for v in p.variations.all() if v.size_id],
        "images": ([_media(p.image)] if p.image_id else []) +
                  [_media(pi.media) for pi in p.images.select_related("media") if pi.media_id != p.image_id],
    })
    return row


@guard
def products(request):
    ids = [int(x) for x in (request.GET.get("ids") or "").split(",") if x.strip().isdigit()][:60]
    qs = _qs(ids).select_related("brand", "image", "primary_category").prefetch_related("categories__parent")
    return JsonResponse({"ok": True, "products": [full(p) for p in qs]}, json_dumps_params={"ensure_ascii": False})


def _size_row(z):
    return {"slug": z.slug, "label": z.label, "type": z.type, "width": str(z.width), "length": str(z.length),
            "diameter": str(z.diameter), "area": str(z.area), "pair": z.default_pair_only, "waste": z.needs_waste,
            "order": z.sort_order}


@guard
def albums(request):
    """آلبوم‌های قیمت (برای لیست قیمت سایت مقصد): نام، نامک و قیمت نهایی هر سایز."""
    from pricing.models import Album
    from pricing.pricelist import album_rows

    out = []
    for a in Album.objects.filter(mirror_pk__isnull=True).select_related("base_size").prefetch_related("sizes", "even_sizes"):
        rows = album_rows(a) if a.is_active else []
        out.append({"id": a.pk, "name": a.name, "code": a.code, "company": a.company, "public_name": a.public_name,
                    "slug": a.slug, "active": a.is_active, "in_list": a.in_price_list, "order": a.sort_order,
                    "embossed": a.embossed, "updated": a.last_updated.isoformat(), "base_size": _size_row(a.base_size),
                    "rows": [[r["size"].slug, r["price"], r["pair_only"]] for r in rows]
                    + ([[a.base_size.slug, a.size_price(a.base_size), False]] if a.is_m2 and a.is_active else []),
                    "unit": a.unit, "m2": {"widths": a.m2_widths, "min_narrow": str(a.m2_min_narrow), "min_wide": str(a.m2_min_wide),
                                           "max": str(a.m2_max_length), "round": a.m2_round, "note": a.m2_note},
                    "sizes": [_size_row(r["size"]) for r in rows]})
    return JsonResponse({"ok": True, "albums": out}, json_dumps_params={"ensure_ascii": False})


@guard
def pick(request):
    """(POST) انتخاب خودکار فرش‌هایی که با کالای قدیمی فرشستان جفت شده‌اند."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST"}, status=405)
    from .models import MirrorPick

    ids = [int(x) for x in json.loads(request.body or b"{}").get("ids", []) if str(x).isdigit()]
    have = set(MirrorPick.objects.filter(product_id__in=ids).values_list("product_id", flat=True))
    new = [i for i in own_products(picked=False).filter(pk__in=ids).values_list("pk", flat=True) if i not in have]
    MirrorPick.objects.bulk_create([MirrorPick(product_id=i, by_match=True) for i in new])
    return JsonResponse({"ok": True, "added": len(new)})


@guard
def orders(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST"}, status=405)
    from .orders import receive

    try:
        data = json.loads(request.body or b"{}")
        number = receive(data)
    except (ValueError, KeyError) as e:
        return JsonResponse({"ok": False, "error": str(e)[:200]}, status=400)
    return JsonResponse({"ok": True, "number": number})
