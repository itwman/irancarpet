"""پیشنهاد فرش در مقاله‌ها و جستجوی مقاله‌ها.

- نوع مقاله: «خرید» (قیمت، خرید، اقساط، شانه، سایز…) یا «دانستنی» (تاریخچه، شعر، نساجی…)؛
  پایان مقالهٔ دانستنی به‌جای فروش مستقیم، دعوت به همکاری در فروش است.
- فرش‌های پیشنهادی از روی موضوع مقاله: شانه‌ای که بیشتر آمده، رنگ زمینه و سایز عنوان؛ اگر کم بود، پربازدیدها.
- جستجوی مقاله‌ها جدا از جستجوی فرش است و فارسی را مثل جستجوی فرش نرمال می‌کند.
"""
import re
from collections import Counter

from django.core.cache import cache
from django.db.models import Max
from django.utils.html import strip_tags

from catalog.search import GENERIC, norm, tokens

BUY_RE = re.compile(r"خرید|قیمت|اقساط|قسطی|ارزان|فروش|سفارش|شانه|متری|کناره|پادری|قالیچه|فرش\s+(?:گرد|سجاده)|بهترین\s+فرش")
REEDS_RE = re.compile(r"\b(500|700|1000|1200|1500)\s*شانه")
SIZE_RE = re.compile(r"\b(6|9|12)\s*متری")


def intent(post):
    return "buy" if BUY_RE.search(post.title or "") or BUY_RE.search(norm(post.title)) else "learn"


def _topic(post):
    title = norm(post.title)
    body = norm(strip_tags((post.content or "")[:8000]))
    reeds = [m for m in REEDS_RE.findall(title)] or [m for m, _ in Counter(REEDS_RE.findall(body)).most_common(1)]
    size = SIZE_RE.findall(title)
    return (reeds[0] if reeds else None), (size[0] if size else None), title


def _color_term(title):
    from catalog.models import AttributeTerm

    key = "rec:colors"
    colors = cache.get(key)
    if colors is None:
        colors = [(t.pk, norm(t.name)) for t in AttributeTerm.objects.filter(attribute__slug__in=["background-color", "رنگ-زمینه"])
                  if len(norm(t.name)) >= 2]
        cache.set(key, colors, 3600)
    padded = f" {title} "
    best = None
    for pk, name in colors:
        if f" {name} " in padded and (best is None or len(name) > len(best[1])):
            best = (pk, name)
    return best[0] if best else None


def products_for(post, n=4):
    """[Product] برای کارت‌ها؛ هر مقاله یک ساعت کش می‌شود."""
    key = f"rec:p:{post.pk}:{int(post.modified_at.timestamp())}:{n}"
    ids = cache.get(key)
    if ids is None:
        ids = _pick(post, n)
        cache.set(key, ids, 3600)
    if not ids:
        return []
    from catalog.models import Product
    from catalog.views import card_queryset

    by = {p.pk: p for p in card_queryset(Product.objects.filter(pk__in=ids))}
    return [by[i] for i in ids if i in by]


def _pick(post, n):
    from catalog.models import AttributeTerm, Product, Variation

    reeds, size, title = _topic(post)
    base = (Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False, seller__isnull=True,
                                                                                    min_price__gt=0))
    filters = []
    if reeds:
        term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter").filter(slug=reeds).first() or \
            AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", name=reeds).first()
        if term:
            filters.append(("specs", term.pk))
    color = _color_term(title)
    if color:
        filters.append(("specs", color))
    if size:
        filters.append(("size", f"{size}-meter"))
    picked = []
    # همهٔ شرط‌ها، بعد بدون آخری، …، و در آخر پربازدیدترین‌ها
    for k in range(len(filters), -1, -1):
        qs = base
        for kind, val in filters[:k]:
            if kind == "specs":
                qs = qs.filter(specs=val)
            else:
                qs = qs.filter(pk__in=Variation.objects.filter(size__slug=val, is_available=True).values("product_id"))
        for pk in qs.exclude(pk__in=picked).order_by("-views").values_list("pk", flat=True)[: n - len(picked)]:
            picked.append(pk)
        if len(picked) >= n:
            break
    return picked[:n]


def reeds_of(post):
    return _topic(post)[0]


# ------------------------------------------------------------------ جستجوی مقاله‌ها
def _index():
    from .models import Post

    stamp = Post.objects.published().aggregate(m=Max("modified_at"))["m"]
    key = f"rec:idx:{int(stamp.timestamp()) if stamp else 0}"
    idx = cache.get(key)
    if idx is None:
        idx = [(p.pk, norm(p.title), norm(p.excerpt), norm(strip_tags(p.content or ""))[:20000])
               for p in Post.objects.published().only("pk", "title", "excerpt", "content")]
        cache.set(key, idx, 3600)
    return idx


def search_posts(query, limit=None):
    """[pk] مقاله‌ها به ترتیب نزدیکی: عبارت کامل در عنوان، همهٔ کلمه‌ها در عنوان، در خلاصه، در متن."""
    toks = [t for t in tokens(query) if len(t) >= 2]
    if not toks:
        return []
    phrase = norm(query)
    must = [t for t in toks if t not in GENERIC] or toks  # «فرش»، «قیمت» و… به‌تنهایی نتیجه نمی‌آورند
    scored = []
    for pk, title, excerpt, body in _index():
        if not all(t in title or t in excerpt or t in body for t in must):
            continue
        score = 0
        if phrase and phrase in title:
            score += 100
        in_title = sum(1 for t in toks if t in title)
        in_body = sum(1 for t in toks if t in body or t in excerpt)
        if in_title == len(toks):
            score += 40
        score += in_title * 10
        if in_body == len(toks):
            score += 8 + min(body.count(toks[0]), 10)
        elif in_body:
            score += in_body
        scored.append((score, pk))
    scored.sort(key=lambda x: -x[0])
    out = [pk for _, pk in scored]
    return out[:limit] if limit else out


def posts_by_ids(ids):
    from .models import Post

    by = {p.pk: p for p in Post.objects.filter(pk__in=ids).select_related("image")}
    return [by[i] for i in ids if i in by]
