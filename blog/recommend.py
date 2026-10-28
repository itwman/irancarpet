"""پیشنهاد فرش در مقاله‌ها و جستجوی مقاله‌ها.

- نوع مقاله: «خرید» (قیمت، خرید، اقساط، شانه، سایز…) یا «دانستنی» (تاریخچه، شعر، نساجی…)؛
  پایان مقالهٔ دانستنی به‌جای فروش مستقیم، دعوت به همکاری در فروش است.
- فرش‌های پیشنهادی از روی موضوع مقاله: اول دسته/برچسب انتخاب‌شده در پنل، یا دسته/مجموعه/برچسبی که نامش (یا کلمهٔ
  قانونش، مثل «موکا») در عنوان آمده؛ بعد شانه، رنگ و سایز عنوان برای دقیق‌تر کردن؛ اگر کم بود، شانهٔ متن و پربازدیدها.
  هر نقشه یک بار، تا ستون کناری و ردیف پایین تکراری نباشند.
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


def topic_of(post):
    """(نوع، شیء) موضوع فرشی مقاله: ("cat", Category) یا ("tag", ProductTag) یا (None, None)."""
    from catalog.models import Category, KeywordRule, ProductTag

    if post.rec_category_id:
        return "cat", post.rec_category
    if post.rec_tag_id:
        return "tag", post.rec_tag
    title = post.title or ""
    for r in KeywordRule.matches(title):  # «موکا» ← دستهٔ فرش موکا
        c = next((c for c in r.categories.all() if not c.redirect_url), None)
        if c:
            return "cat", c
        t = next(iter(r.tags.all()), None)
        if t:
            return "tag", t
    best = None
    for c in Category.objects.filter(redirect_url=""):
        for name in filter(None, (c.name, c.collection_label)):
            if KeywordRule.has(name, title) and (best is None or len(name) > best[0]):
                best = (len(name), "cat", c)
    for t in ProductTag.objects.exclude(robots__contains="noindex"):
        if KeywordRule.has(t.name, title) and (best is None or len(t.name) > best[0]):
            best = (len(t.name), "tag", t)
    return (best[1], best[2]) if best else (None, None)


def topic_link(post):
    """{label, heading, url, count} برای سرتیتر و پیوند ردیف پایین مقاله؛ یا None."""
    from core.templatetags.fa import fa_num

    kind, obj = topic_of(post)
    if obj is None:
        return None
    qs = _topic_qs(kind, obj)
    n = qs.count()
    if kind == "cat" and obj.collection_label:
        label = f"فرش {obj.collection_label}"
        return {"heading": f"فرش‌های {obj.collection_label}", "url": obj.get_absolute_url(), "count": n,
                "more": f"همهٔ {fa_num(n)} فرش {obj.collection_label}", "label": label}
    name = obj.name
    return {"heading": name, "url": obj.get_absolute_url(), "count": n, "more": f"همهٔ {fa_num(n)} {name}", "label": name}


def _topic_qs(kind, obj):
    from catalog.models import Product

    base = Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False, seller__isnull=True)
    if kind == "cat":
        return base.filter(categories__in=obj.descendant_ids()).distinct()
    return base.filter(tags=obj).distinct()


def reeds_url(reeds):
    """صفحهٔ واقعی «فرش N شانه» (دسته، وگرنه صفحهٔ شانه)."""
    from catalog.models import AttributeTerm, Category

    if not reeds:
        return ""
    fa = str(reeds).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
    c = Category.objects.filter(redirect_url="", name__in=[f"فرش {reeds} شانه", f"فرش {fa} شانه"]).first()
    if c:
        return c.get_absolute_url()
    t = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", name__in=[str(reeds), fa], attribute__is_public=True).first()
    return t.get_absolute_url() if t else ""


def products_for(post, n=4):
    """[Product] برای کارت‌ها؛ هر مقاله یک ساعت کش می‌شود."""
    key = f"rec2:p:{post.pk}:{int(post.modified_at.timestamp())}:{post.rec_category_id}:{post.rec_tag_id}:{n}"
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
    kind, obj = topic_of(post)
    title_reeds = REEDS_RE.findall(title)
    if obj is not None:
        topic = base.filter(pk__in=_topic_qs(kind, obj).values("pk"))
        filters = []
        if title_reeds:  # فقط شانهٔ عنوان؛ شانه‌ای که در متن آمده موضوع را عوض نمی‌کند
            term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", name=title_reeds[0]).first()
            if term:
                filters.append(("specs", term.pk))
        color = _color_term(title)
        if color:
            filters.append(("specs", color))
        if size:
            filters.append(("size", f"{size}-meter"))
        picked = _relaxed(topic, filters, n, [], one_per_design=True)
        if len(picked) >= n:
            return picked[:n]
        # موضوع تمام شد: بقیه با روش قبلی (شانهٔ متن و پربازدیدها)
        rest = _pick_basic(post, base, reeds, size, title, n - len(picked), exclude=picked)
        return (picked + rest)[:n]
    return _pick_basic(post, base, reeds, size, title, n, exclude=[])


def _relaxed(qs0, filters, n, picked, one_per_design=False):
    """همهٔ شرط‌ها، بعد بدون آخری، …، و در آخر بی‌شرط؛ هر نقشه یک بار (اگر خواسته شود)."""
    from catalog.models import Variation

    picked = list(picked)
    designs = set()
    for k in range(len(filters), -1, -1):
        qs = qs0
        for kind, val in filters[:k]:
            if kind == "specs":
                qs = qs.filter(specs=val)
            else:
                qs = qs.filter(pk__in=Variation.objects.filter(size__slug=val, is_available=True).values("product_id"))
        for pk, design in qs.exclude(pk__in=picked).order_by("-views").values_list("pk", "design_name")[:200]:
            d = (design or "").strip()
            if one_per_design and d and d in designs:
                continue
            designs.add(d)
            picked.append(pk)
            if len(picked) >= n:
                return picked
    return picked


def _pick_basic(post, base, reeds, size, title, n, exclude):
    from catalog.models import AttributeTerm, Product, Variation

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
    picked = list(exclude)
    # همهٔ شرط‌ها، بعد بدون آخری، …، و در آخر پربازدیدترین‌ها
    for k in range(len(filters), -1, -1):
        qs = base
        for kind, val in filters[:k]:
            if kind == "specs":
                qs = qs.filter(specs=val)
            else:
                qs = qs.filter(pk__in=Variation.objects.filter(size__slug=val, is_available=True).values("product_id"))
        for pk in qs.exclude(pk__in=picked).order_by("-views").values_list("pk", flat=True)[: n + len(exclude) - len(picked)]:
            picked.append(pk)
        if len(picked) >= n + len(exclude):
            break
    return [x for x in picked if x not in exclude][:n]


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
