"""فید ترب — همان خروجی افزونهٔ وردپرسی (مسیر /wp-json/torob/products/)

در سایت قبلی، محصول آلبومی یک ردیف با قیمت سایز پایه (۱۲ متری) داشت و
page_unique همان شناسهٔ محصول در وردپرس بود؛ همین حفظ می‌شود تا ترب محصولات را از نو نشناسد.
"""
import re
from decimal import Decimal
from html import unescape
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import strip_tags

from catalog.models import Product, ProductImage


NEW_ID_OFFSET = 1_000_000_000   # محصولات تازه (بدون شناسهٔ وردپرس)
CACHE_KEY, CACHE_TTL = "torob_rows", 300


def wp_url(path):
    """مثل وردپرس: حروف فارسی به‌صورت درصدی با حروف کوچک (‎%d9%81…)."""
    return re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), quote(path, safe="/-_.~"))


def unique_of(p):
    return p.wp_id or NEW_ID_OFFSET + p.pk


def product_by_unique(u):
    if u >= NEW_ID_OFFSET:
        return Product.objects.filter(pk=u - NEW_ID_OFFSET).first()
    return Product.objects.filter(wp_id=u).first()


def base_queryset(s):
    qs = Product.objects.published().exclude(pk__in=s.excluded.values("pk"))
    if s.only_album:
        qs = qs.filter(album__isnull=False)
    return qs


def rows(s):
    ids = cache.get(CACHE_KEY)
    if ids is None:
        ids = list(base_queryset(s).exclude(min_price=None).exclude(min_price=0).order_by("-published_at", "-pk")
                   .values_list("pk", flat=True))
        cache.set(CACHE_KEY, ids, CACHE_TTL)
    return ids


def adjust(raw, s):
    p = Decimal(raw) / max(1, s.price_divisor)
    if s.decrease_rate:
        p -= p * s.decrease_rate / 100
    if s.tax_percent:
        p += p * s.tax_percent / 100
    if s.round_to:
        p = (p / s.round_to).quantize(Decimal(1)) * s.round_to
    return int(max(Decimal(0), p).quantize(Decimal(1)))


def _price(p):
    """(قیمت فعلی، قیمت قبل از تخفیف) — محصول آلبومی: سایز پایه؛ بقیه: ارزان‌ترین سایز موجود."""
    vs = [v for v in p.variations.all() if v.is_available and v.price]
    if p.album_id:
        vs = [v for v in vs if v.size_id == p.album.base_size_id] or vs
    if not vs:
        return None, None
    v = min(vs, key=lambda x: x.price)
    return v.price, (v.final_price if v.on_sale else None)


def _category(p):
    c = p.primary_category or max(p.categories.all(), key=lambda x: len(x.ancestors()), default=None)
    if not c:
        return ""
    return " > ".join([a.name for a in c.ancestors()] + [c.name])


def _text(html, limit=500):
    t = re.sub(r"\s+", " ", unescape(strip_tags(html or ""))).strip()
    return t[:limit] + "…" if len(t) > limit else t


def _spec(p, s):
    spec = {}
    for t in p.specs.select_related("attribute").order_by("attribute__order", "order"):
        label = t.attribute.label
        spec[label] = f"{spec[label]}، {t.name}" if label in spec else t.name
    sizes = [v.size.label for v in p.variations.all() if v.size_id and v.is_available]
    if sizes:
        spec["اندازه"] = "، ".join(sizes)
    return spec


def format_row(p, s):
    current, old = _price(p)
    if not current:
        return None
    site = settings.SITE_URL
    imgs = [pi.media for pi in ProductImage.objects.filter(product=p).select_related("media").order_by("order")]
    main = p.image or (imgs[0] if imgs else None)
    links = []
    for m in [p.image] + imgs:
        if m and m.absolute_url and m.absolute_url not in links:
            links.append(m.absolute_url)
    links = [site + wp_url(u[len(site):]) if u.startswith(site) else u for u in links]
    guarantee = ""
    if s.guarantee_attr:
        guarantee = "، ".join(p.specs.filter(attribute__slug=s.guarantee_attr).values_list("name", flat=True))
    title = p.title + (f" - {s.title_suffix}" if s.title_suffix else "")
    return {
        "title": title,
        "subtitle": "",
        "page_unique": unique_of(p),
        "product_group_id": "",
        "current_price": adjust(current, s),
        "old_price": adjust(old, s) if old and old > current else 0,
        "availability": "instock" if p.is_purchasable else "outofstock",
        "category_name": _category(p),
        "image_link": (site + wp_url(main.url)) if main and main.url else "",
        "image_links": links,
        "page_url": site + wp_url(p.get_absolute_url()),
        "short_desc": _text(p.short_description or p.content),
        "spec": _spec(p, s),
        "guarantee": guarantee,
        "registry": s.registry_text,
        "date": timezone.localtime(p.published_at).strftime("%Y-%m-%d %H:%M:%S") if p.published_at else "",
    }


def _load(ids):
    by = {p.pk: p for p in Product.objects.filter(pk__in=ids).select_related(
        "album", "image", "primary_category__parent__parent").prefetch_related("variations", "categories")}
    return [by[i] for i in ids if i in by]


def page(n, s):
    ids = rows(s)
    per = max(1, s.per_page)
    chunk = ids[(n - 1) * per: n * per]
    items = [r for r in (format_row(p, s) for p in _load(chunk)) if r]
    return {"count": len(ids), "max_pages": -(-len(ids) // per), "products": items}


def single(p, s):
    items = []
    if p and base_queryset(s).filter(pk=p.pk).exists():
        r = format_row(p, s)
        if r:
            items.append(r)
    return {"count": len(items), "max_pages": 1, "products": items}


def product_by_url(url):
    path = unquote(urlsplit(url).path or "")
    q = dict(parse_qsl(urlsplit(url).query))
    m = re.match(r"^/product/([^/]+)/?$", path)
    if m:
        return Product.objects.filter(slug=m.group(1)).first()
    if q.get("p", "").isdigit():
        return Product.objects.filter(wp_id=int(q["p"])).first()
    return None

