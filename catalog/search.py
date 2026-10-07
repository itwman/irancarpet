"""جستجوی فارسیِ مقاوم برای فرش‌ها.

- ی/ي/ى/ئ، ک/ك، ه/ة/ۀ، ا/أ/إ/آ، و/ؤ یکی حساب می‌شوند؛ اعراب و کشیده حذف می‌شود.
- ارقام فارسی، عربی و لاتین یکی‌اند.
- فاصله و نیم‌فاصله مهم نیست: «سرمه ای»، «سرمه‌ای» و «سرمهای» یکی است.
- ترتیب کلمه‌ها مهم نیست و کلمه‌های میانی لازم نیست: «گلریز لاکی» ← «… افشان گلریز زمینه لاکی».
- در عنوان، مشخصات (رنگ، شانه، جنس نخ…)، نام نقشه، آلبوم، برند، دسته‌ها، برچسب‌ها، نام انگلیسی و کد کالا جستجو می‌شود.
- مرتب‌سازی بر اساس نزدیکی: عبارت کامل در عنوان ← همهٔ کلمه‌ها در عنوان ← بقیه؛ بعد پربازدیدترها.
- اگر هیچ فرشی همهٔ کلمه‌ها را نداشت، فرش‌هایی که بیشترِ کلمه‌ها را دارند نشان داده می‌شوند.
"""
import re

from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce

TRANS = str.maketrans({
    "ي": "ی", "ى": "ی", "ئ": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه", "ہ": "ه", "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "‌": " ", "‍": "", "‎": "", "‏": "", "ـ": "",
})
DIACRITICS = re.compile(r"[ً-ٰٟۖ-ۭ]")
PUNCT = re.compile(r"[\-_/\\،,.;:!?()\[\]{}«»\"'٫٬×*+|]+")
GENERIC = {"فرش", "شانه", "زمینه", "نقشه", "طرح", "رنگ", "سایز", "متری", "ماشینی", "خرید", "قیمت"}


def norm(text):
    """متن نرمال با فاصله"""
    s = DIACRITICS.sub("", (text or "").translate(TRANS)).lower()
    s = PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def compact(text):
    return norm(text).replace(" ", "")


def tokens(query):
    out = []
    for t in norm(query).split():
        if len(t) >= 2 or t.isdigit():
            if t not in out:
                out.append(t)
    return out[:8]


# ------------------------------------------------------------------ نمایه
def index_values(p):
    parts = [p.title, p.english_name, p.sku, p.design_name]
    if p.album_id:
        parts += [p.album.name, p.album.title]
    if p.brand_id:
        parts.append(p.brand.name)
    if p.pk:
        parts += [t.name for t in p.specs.all()]
        parts += [c.name for c in p.categories.all()]
        parts += [t.name for t in p.tags.all()]
    return compact(p.title)[:600], "|".join(compact(x) for x in parts if x)[:4000]


def reindex(products):
    from .models import Product

    rows = []
    for p in products:
        p.search_title, p.search_text = index_values(p)
        rows.append(p)
    Product.objects.bulk_update(rows, ["search_title", "search_text"], batch_size=500)
    return len(rows)


def reindex_all():
    from .models import Product

    qs = Product.objects.select_related("album", "brand").prefetch_related("specs", "categories", "tags")
    n, batch = 0, []
    for p in qs.iterator(chunk_size=500):
        batch.append(p)
        if len(batch) >= 500:
            n += reindex(batch)
            batch = []
    return n + reindex(batch)


# ------------------------------------------------------------------ جستجو
def _token_q(t):
    return Q(search_text__contains=t)


def search(qs, query):
    """(queryset مرتب‌شده بر اساس نزدیکی، دقیق بود؟)"""
    toks = tokens(query)
    if not toks:
        return qs.none(), True
    whole = compact(query)
    sku = (query or "").translate(TRANS).strip()
    cond = Q()
    for t in toks:
        cond &= _token_q(t)
    exact = qs.filter(cond | Q(sku__iexact=sku))
    rank = Case(
        When(sku__iexact=sku, then=Value(100)),
        When(search_title__contains=whole, then=Value(50)),
        When(Q(*[Q(search_title__contains=t) for t in toks]), then=Value(30)),
        default=Value(10), output_field=IntegerField(),
    )
    if exact.exists():
        return exact.annotate(_rank=rank), True
    # هیچ فرشی همهٔ کلمه‌ها را نداشت: هرچه کلمه‌های بیشتری (غیر از کلمه‌های عمومی) دارد بالاتر
    useful = [t for t in toks if t not in GENERIC] or toks
    score = sum((Case(When(_token_q(t), then=Value(10)), default=Value(0), output_field=IntegerField()) for t in useful),
                Value(0))
    any_q = Q()
    for t in useful:
        any_q |= _token_q(t)
    return qs.filter(any_q).annotate(_rank=Coalesce(score, Value(0))), False
