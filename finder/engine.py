"""موتور فرش‌یاب: فهمیدن جملهٔ مشتری و پیدا کردن فرش‌های مناسب.

قاعدهٔ ترکیب نیازها: نیازهای یک گروه با «یا» و گروه‌های مختلف با «و» ترکیب می‌شوند.
یعنی «قرمز یا آبی» و «سنتی» → فرش سنتی که قرمز یا آبی باشد.
"""
import re
from dataclasses import dataclass, field

from django.core.cache import cache
from django.db.models import Min, Q

from catalog.models import AttributeTerm, Category, Product, Variation

from .models import Need, split_words

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
MILLION = 1_000_000


def normalize(text):
    t = (text or "").translate(FA_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    t = t.replace("‌", " ").replace("ـ", "").lower()
    t = re.sub(r"(\d)[,٬](\d{3})", r"\1\2", t)
    t = re.sub(r"(\d)[/٫](\d)", r"\1.\2", t)
    return re.sub(r"\s+", " ", t).strip()


# ------------------------------------------------------------------ قاعدهٔ هر نیاز
def _cat_ids(cats):
    ids = set()
    for c in cats:
        ids.update(c.descendant_ids())
    return ids


def need_q(need):
    """شرط Q روی محصول برای یک نیاز (با زیرپرس‌وجو تا ترکیب «یا»/«و» درست بماند)."""
    pos = Q(pk__in=[])
    cats = list(need.categories.all())
    if cats:
        pos |= Q(pk__in=Product.objects.filter(categories__in=_cat_ids(cats)).values("pk"))
    terms = list(need.terms.values_list("pk", flat=True))
    words = split_words(need.term_keywords)
    if words:
        tq = Q()
        for w in words:
            tq |= Q(name__icontains=w)
        qs = AttributeTerm.objects.filter(tq)
        if need.term_attribute_id:
            qs = qs.filter(attribute_id=need.term_attribute_id)
        terms += list(qs.values_list("pk", flat=True))
    if terms:
        pos |= Q(pk__in=Product.objects.filter(specs__in=terms).values("pk"))
    for w in split_words(need.title_keywords):
        pos |= Q(title__icontains=w)
    neg = Q()
    ex = list(need.exclude_categories.all())
    if ex:
        neg |= Q(pk__in=Product.objects.filter(categories__in=_cat_ids(ex)).values("pk"))
    for w in split_words(need.exclude_keywords):
        neg |= Q(title__icontains=w)
    return pos & ~neg if neg else pos


def has_rules(need):
    return bool(need.title_keywords.strip() or need.term_keywords.strip() or need.categories.exists() or need.terms.exists())


def active_needs(with_empty=False):
    """نیازهای فعال. نیازِ بی‌قاعده فقط برای فهم جمله لازم است (تا «غیر برجسته» با «برجسته» اشتباه نشود)."""
    key = "finder:needs"
    data = cache.get(key)
    if data is None:
        data = list(Need.objects.filter(is_active=True).prefetch_related("categories", "terms", "exclude_categories"))
        for n in data:
            n.usable = has_rules(n)
        cache.set(key, data, 300)
    return data if with_empty else [n for n in data if n.usable]


def clear_cache(*a, **kw):
    cache.delete("finder:needs")


# ------------------------------------------------------------------ فهم جمله
@dataclass
class Wish:
    needs: list = field(default_factory=list)      # Need
    sizes: list = field(default_factory=list)      # Size
    size_label: str = ""
    min_price: int = 0
    max_price: int = 0
    reeds: list = field(default_factory=list)      # AttributeTerm
    words: str = ""                                 # باقی جمله که فهمیده نشد

    def chips(self):
        """آنچه فهمیده شد، برای نمایش به مشتری."""
        out = [{"type": "need", "id": n.pk, "label": n.title, "group": n.group, "swatch": n.swatch} for n in self.needs]
        out += [{"type": "reeds", "id": t.pk, "label": f"{t.name} شانه"} for t in self.reeds]
        if self.sizes:
            out.append({"type": "size", "id": self.sizes[0].pk, "label": self.size_label or self.sizes[0].label})
        if self.min_price and self.max_price:
            out.append({"type": "price", "label": f"بین {money_label(self.min_price)} تا {money_label(self.max_price)}"})
        elif self.max_price:
            out.append({"type": "price", "label": f"تا {money_label(self.max_price)}"})
        elif self.min_price:
            out.append({"type": "price", "label": f"از {money_label(self.min_price)}"})
        return out


def money_label(n):
    if n % MILLION == 0:
        return f"{n // MILLION:,} میلیون تومان"
    if n >= MILLION:
        return f"{n / MILLION:.1f}".rstrip("0").rstrip(".") + " میلیون تومان"
    return f"{n:,} تومان"


NUM = r"(\d+(?:\.\d+)?)"
UNIT = r"\s*(میلیون|ملیون|میلیونی|م\b|تومن|تومان|هزار)?"


def _amount(num, unit):
    v = float(num)
    if unit and unit.startswith("هزار"):
        return int(v * 1000)
    if unit in ("تومن", "تومان") and v >= 100_000:
        return int(v)
    if unit or v < 2000:  # «۴۰» در جملهٔ قیمت یعنی ۴۰ میلیون
        return int(v * MILLION)
    return int(v)


def parse_price(t):
    """(کمترین، بیشترین) و جملهٔ بدون بخش قیمت."""
    lo = hi = 0
    m = re.search(rf"(?:بین|از)\s*{NUM}{UNIT}\s*(?:تا|و|الی|-)\s*{NUM}{UNIT}", t)
    if m:
        u = m.group(2) or m.group(4)
        lo, hi = _amount(m.group(1), u), _amount(m.group(3), m.group(4) or u)
        return lo, hi, t.replace(m.group(0), " ")
    m = re.search(rf"(?:زیر|کمتر از|ارزانتر از|ارزان تر از|تا سقف|سقف|تا|حداکثر|نهایتا|ماکزیمم|ماکسیمم|نهایت)\s*{NUM}{UNIT}", t)
    if m and (m.group(2) or "میلیون" in t or "تومن" in t or "تومان" in t or float(m.group(1)) < 2000):
        # «تا ۶ متری» قیمت نیست
        after = t[m.end():m.end() + 6]
        if not after.strip().startswith("متر"):
            hi = _amount(m.group(1), m.group(2))
            t = t.replace(m.group(0), " ")
    m = re.search(rf"(?:بالای|بیشتر از|بیش از|حداقل|از)\s*{NUM}{UNIT}", t)
    if m and m.group(2):
        lo = _amount(m.group(1), m.group(2))
        t = t.replace(m.group(0), " ")
    m = re.search(rf"(?:حدود|حدودا|در حد|تقریبا|حول و حوش)\s*{NUM}{UNIT}", t)
    if m and (m.group(2) or float(m.group(1)) < 2000) and not (lo or hi):
        v = _amount(m.group(1), m.group(2))
        lo, hi = int(v * 0.8), int(v * 1.15)
        t = t.replace(m.group(0), " ")
    if not (lo or hi):
        m = re.search(rf"{NUM}\s*(میلیون|ملیون|تومن|تومان)", t)
        if m:
            hi = _amount(m.group(1), m.group(2))
            t = t.replace(m.group(0), " ")
    return lo, hi, t


def _sizes():
    from pricing.models import Size

    return list(Size.objects.filter(is_active=True).exclude(type="custom").order_by("sort_order", "pk"))


def parse_size(t):
    sizes = _sizes()
    m = re.search(rf"{NUM}\s*(?:در|x|×|\*)\s*{NUM}(?:\s*متر)?", t)
    if m:
        a, b = sorted([float(m.group(1)), float(m.group(2))])
        hit = [s for s in sizes if s.width and s.length and abs(float(min(s.width, s.length)) - a) < .26
               and abs(float(max(s.width, s.length)) - b) < .26]
        if hit:
            return hit, hit[0].label, t.replace(m.group(0), " ")
    m = re.search(rf"{NUM}\s*متر(?:ی|ه)?", t)
    if m:
        area = float(m.group(1))
        hit = [s for s in sizes if s.area and s.type == "rect" and abs(float(s.area) - area) <= max(.6, area * .08)]
        if not hit:
            hit = [s for s in sizes if s.area and abs(float(s.area) - area) <= max(.6, area * .08)]
        if hit:
            return hit, f"{m.group(1)} متری", t.replace(m.group(0), " ")
    return [], "", t


def parse_reeds(t):
    out = []
    for m in re.finditer(r"(\d{3,4})\s*شانه", t):
        term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", name=m.group(1)).first() or \
            AttributeTerm.objects.filter(attribute__label="شانه", name=m.group(1)).first()
        if term:
            out.append(term)
        t = t.replace(m.group(0), " ")
    return out, t


STOP = set("فرش یا یک یه خیلی ولی اما مثل یکی چیزی دوست می میخوام میخواهم می‌خواهم میخام خواهم خوام دارم دنبال برای برام واسه با و که به از در رو را تا باشه باشد بشه "
           "هست هستم لطفا لطفاً سلام ممنون ای ی های ها اتاق خونه خانه پذیرایی مدل طرح نقشه رنگ رنگی زمینه شانه متری متر "
           "قیمت تومان تومن میلیون ارزون".split())


def understand(text, needs=None):
    """جملهٔ مشتری → Wish"""
    t = " " + normalize(text) + " "
    w = Wish()
    w.min_price, w.max_price, t = parse_price(t)
    w.sizes, w.size_label, t = parse_size(t)
    w.reeds, t = parse_reeds(t)
    by_kw = {}
    for n in needs if needs is not None else active_needs(with_empty=True):
        for kw in n.keyword_list + [n.title]:
            k = normalize(kw)
            if k and n not in by_kw.setdefault(k, []):
                by_kw[k].append(n)
    found = []
    for k in sorted(by_kw, key=lambda x: -len(x)):  # «غیر برجسته» پیش از «برجسته»
        pat = rf"(?<![\w]){re.escape(k)}(?![\w])"
        if re.search(pat, t):
            t = re.sub(pat, " ", t)
            found += [n for n in by_kw[k] if n not in found]
    w.needs = [n for n in found if getattr(n, "usable", True)]
    rest = [x for x in re.split(r"\s+", t) if x and x not in STOP and not x.isdigit() and len(x) > 1]
    w.words = " ".join(rest)
    return w


# ------------------------------------------------------------------ جستجو
def _base():
    from catalog.models import BLOCKED_SALE_STATUSES

    return Product.objects.published().exclude(stock_status="outofstock").exclude(sale_status__in=BLOCKED_SALE_STATUSES)


def apply(wish, use_words=True):
    qs = _base()
    groups = {}
    for n in wish.needs:
        groups.setdefault(n.group, []).append(n)
    for items in groups.values():
        q = Q(pk__in=[])
        for n in items:
            q |= need_q(n)
        qs = qs.filter(q)
    for t in wish.reeds:
        qs = qs.filter(pk__in=Product.objects.filter(specs=t).values("pk"))
    if wish.sizes:
        vq = Variation.objects.filter(size__in=wish.sizes, is_available=True, final_price__gt=0)
        if wish.max_price:
            vq = vq.filter(final_price__lte=wish.max_price)
        if wish.min_price:
            vq = vq.filter(final_price__gte=wish.min_price)
        qs = qs.filter(pk__in=vq.values("product_id"))
    else:
        if wish.max_price:
            qs = qs.filter(min_price__gt=0, min_price__lte=wish.max_price)
        if wish.min_price:
            qs = qs.filter(max_price__gte=wish.min_price)
    if use_words and wish.words and not (wish.needs or wish.reeds or wish.sizes):
        wq = Q()
        for x in wish.words.split()[:5]:
            wq &= Q(title__icontains=x)
        qs = qs.filter(wq)
    return qs


SORTS = {"best": ("-views",), "cheap": ("min_price",), "expensive": ("-min_price",), "new": ("-published_at",)}


def search(wish, sort="best"):
    """(کوئری‌ست، پیام نرم‌شدن یا "")؛ اگر چیزی پیدا نشد، شرط‌ها کم‌کم سبک می‌شوند."""
    order = SORTS.get(sort, SORTS["best"])
    qs = apply(wish)
    if qs.exists():
        return qs.order_by(*order), ""
    tries = []
    if wish.max_price:
        tries.append((Wish(**{**wish.__dict__, "max_price": int(wish.max_price * 1.25)}), "کمی بالاتر از بودجه‌ات"))
    for g, label in (("use", "کاربرد"), ("style", "سبک"), ("feel", "جنس و ضخامت"), ("color", "رنگ")):
        if any(n.group == g for n in wish.needs):
            w2 = Wish(**{**wish.__dict__, "needs": [n for n in wish.needs if n.group != g]})
            tries.append((w2, f"بدون شرط {label}"))
    if wish.sizes:
        tries.append((Wish(**{**wish.__dict__, "sizes": [], "min_price": 0, "max_price": 0}), "در سایزهای دیگر"))
    for w2, msg in tries:
        qs = apply(w2)
        if qs.exists():
            return qs.order_by(*order), f"دقیقاً با همهٔ خواسته‌هایت پیدا نکردیم؛ نزدیک‌ترین‌ها ({msg}):"
    return _base().none(), ""


def size_prices(product_ids, sizes):
    """قیمت سایز خواسته‌شده برای هر محصول."""
    if not sizes:
        return {}
    rows = (Variation.objects.filter(product_id__in=product_ids, size__in=sizes, is_available=True, final_price__gt=0)
            .values("product_id").annotate(p=Min("final_price")))
    return {r["product_id"]: r["p"] for r in rows}


def why(product_ids, needs):
    """برای هر محصول، کدام نیازها را دارد (برای برچسب «چرا این فرش؟»)."""
    out = {pk: [] for pk in product_ids}
    for n in needs:
        for pk in Product.objects.filter(pk__in=product_ids).filter(need_q(n)).values_list("pk", flat=True):
            out[pk].append(n.title)
    return out


def need_count(need):
    return _base().filter(need_q(need)).count()
