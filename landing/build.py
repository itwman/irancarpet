"""ساخت و به‌روزرسانی صفحه‌های فرود + دادهٔ هر صفحه (قیمت‌ها، متن خودکار، پرسش‌های متداول)."""
import re

from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from catalog.models import AttributeTerm, Product, Variation
from core.templatetags.fa import fa_num, toman

MIN_PRODUCTS = 4
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


# ------------------------------------------------------------------ نام‌ها
def size_short(size):
    """«۹ متری مستطیل (۳.۵ × ۲.۵)» → «۹ متری مستطیل»"""
    return re.sub(r"\s*\(.*?\)\s*", " ", size.label).strip()


def color_short(need):
    """«کرم و روشن» → «کرم»"""
    return need.title.split(" و ")[0].strip()


def make_title(reeds=None, size=None, color=None, style=None):
    parts = ["فرش"]
    if reeds:
        parts.append(f"{fa_num(reeds.name)} شانه")
    if style:
        parts.append(style.title.split(" و ")[0].split(" (")[0])
    if color:
        parts.append(color_short(color))
    if size:
        parts.append(fa_num(size_short(size)))
    return " ".join(parts)


def make_slug(title):
    s = title.translate(FA).replace("‌", "-")
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_-]+", "-", s).strip("-").lower()


# ------------------------------------------------------------------ فرش‌های هر صفحه
def base_qs():
    from finder.engine import _base

    return _base()


def products_of(lp):
    from finder.engine import need_q

    qs = base_qs()
    if lp.reeds_id:
        qs = qs.filter(pk__in=Product.objects.filter(specs=lp.reeds_id).values("pk"))
    if lp.color_id:
        qs = qs.filter(need_q(lp.color))
    if lp.style_id:
        qs = qs.filter(need_q(lp.style))
    if lp.size_id:
        qs = qs.filter(pk__in=Variation.objects.filter(size_id=lp.size_id, is_available=True, final_price__gt=0).values("product_id"))
    return qs


def price_range(lp, qs=None):
    qs = qs if qs is not None else products_of(lp)
    vq = Variation.objects.filter(product__in=qs.values("pk"), is_available=True, final_price__gt=0)
    if lp.size_id:
        vq = vq.filter(size_id=lp.size_id)
        agg = vq.aggregate(lo=Min("final_price"), hi=Max("final_price"))
        return agg["lo"], agg["hi"]
    agg = qs.filter(min_price__gt=0).aggregate(lo=Min("min_price"), hi=Max("min_price"))
    return agg["lo"], agg["hi"]


def size_table(lp, qs=None):
    """برای صفحه‌های بدون سایز: بازهٔ قیمت هر سایز."""
    if lp.size_id:
        return []
    qs = qs if qs is not None else products_of(lp)
    rows = (Variation.objects.filter(product__in=qs.values("pk"), is_available=True, final_price__gt=0, size__is_active=True,
                                     size__type__in=["rect", "runner", "round"])
            .values("size_id", "size__label", "size__sort_order")
            .annotate(lo=Min("final_price"), hi=Max("final_price"), n=Count("product", distinct=True))
            .order_by("size__sort_order"))
    by_size = {lp2.size_id: lp2 for lp2 in LandingPageQS().filter(reeds_id=lp.reeds_id, color_id=lp.color_id, style_id=lp.style_id,
                                                                  size__isnull=False, is_active=True, count__gte=MIN_PRODUCTS)}
    out = []
    for r in rows:
        link = by_size.get(r["size_id"])
        out.append({"label": r["size__label"], "lo": r["lo"], "hi": r["hi"], "n": r["n"], "url": link.get_absolute_url() if link else ""})
    return out


def LandingPageQS():
    from .models import LandingPage

    return LandingPage.objects.all()


# ------------------------------------------------------------------ متن خودکار
REEDS_NOTE = {
    "500": "فرش ۵۰۰ شانه اقتصادی‌ترین گزینه است؛ برای فضاهای پررفت‌وآمد و خرید با بودجهٔ کم مناسب است.",
    "700": "فرش ۷۰۰ شانه پرز بلندتر و حس ضخیم‌تری زیر پا دارد؛ گزینهٔ خوبی برای کسانی که فرش نرم و گرم می‌خواهند.",
    "1000": "فرش ۱۰۰۰ شانه میان کیفیت و قیمت تعادل خوبی دارد؛ نقش‌ها از ۷۰۰ شانه ریزتر است و پرز هنوز ضخامت مناسبی دارد.",
    "1200": "فرش ۱۲۰۰ شانه نقش‌های ظریف و رنگ‌بندی دقیقی دارد و از پرفروش‌ترین تراکم‌ها برای پذیرایی است.",
    "1500": "فرش ۱۵۰۰ شانه ظریف‌ترین نقش‌ها و بیشترین تراکم را دارد؛ برای فضاهای رسمی و کسانی که جزئیات طرح برایشان مهم است.",
}
COLOR_NOTE = {
    "کرم": "رنگ‌های روشن مثل کرم فضا را بزرگ‌تر و روشن‌تر نشان می‌دهند و با بیشتر مبلمان‌ها هماهنگ‌اند.",
    "قرمز": "فرش لاکی و قرمز حال‌وهوای گرم و اصیل ایرانی دارد و کنار مبلمان کلاسیک جلوه می‌کند.",
    "سرمه‌ای": "سرمه‌ای و آبی رنگ‌هایی آرام و باوقارند و لک‌ها را کمتر نشان می‌دهند.",
    "طوسی": "طوسی و نقره‌ای انتخاب محبوب دکوراسیون‌های امروزی و مینیمال است.",
    "سبز": "فرش سبز طراوت می‌آورد و با چوب و رنگ‌های خاکی خانه هماهنگ است.",
    "قهوه‌ای": "قهوه‌ای و گردویی رنگ‌هایی گرم و کم‌حاشیه‌اند و برای خانه‌های پررفت‌وآمد مناسب‌اند.",
    "صورتی": "صورتی و گلبهی برای اتاق خواب و فضاهای لطیف انتخاب خوبی است.",
    "مشکی": "زمینهٔ تیره نقش‌ها را پررنگ‌تر نشان می‌دهد و کنار مبلمان روشن کنتراست زیبایی می‌سازد.",
}
SIZE_NOTE = {
    "12": "فرش ۱۲ متری (۴ × ۳) رایج‌ترین سایز برای پذیرایی است و معمولاً به‌صورت جفت خریده می‌شود.",
    "9": "فرش ۹ متری برای پذیرایی‌های کوچک‌تر یا نشیمن مناسب است.",
    "6": "فرش ۶ متری (۳ × ۲) برای اتاق خواب و نشیمن کوچک انتخاب رایجی است.",
    "15": "فرش ۱۵ متری (۵ × ۳) برای سالن‌های بزرگ‌تر است.",
    "24": "فرش ۲۴ متری (۶ × ۴) برای سالن‌های بزرگ و یک‌تکه کردن کف است.",
}


def auto_intro(lp, month):
    lo, hi = lp.min_price, lp.max_price
    first = f"<p>{fa_num(lp.count)} طرح {lp.title} در ایران کارپت موجود است"
    if lo and hi:
        first += (f"؛ قیمت {'هر فرش' if lp.size_id else 'از سایز کوچک'} از {toman(lo)} تا {toman(hi)} تومان"
                  if lo != hi else f" با قیمت {toman(lo)} تومان")
    first += f" (لیست قیمت {month}).</p>"
    notes = []
    if lp.reeds_id and lp.reeds.name in REEDS_NOTE:
        notes.append(REEDS_NOTE[lp.reeds.name])
    if lp.color_id and color_short(lp.color) in COLOR_NOTE:
        notes.append(COLOR_NOTE[color_short(lp.color)])
    if lp.size_id:
        area = str(round(float(lp.size.area or 0)))
        if lp.size.type == "rect" and area in SIZE_NOTE:
            notes.append(SIZE_NOTE[area])
    body = f"<p>{' '.join(notes)}</p>" if notes else ""
    return first + body + "<p>همهٔ فرش‌ها مستقیم از کارخانه‌های کاشان ارسال می‌شوند و خرید نقدی و اقساطی ممکن است.</p>"


def faq(lp, month, size_rows):
    out = []
    lo, hi = lp.min_price, lp.max_price
    if lo:
        if lp.size_id:
            out.append({"q": f"قیمت {lp.title} چند است؟",
                        "a": f"در لیست قیمت {month} ایران کارپت، {lp.title} از {toman(lo)} تا {toman(hi)} تومان است."})
        elif size_rows:
            parts = "، ".join(f"{fa_num(r['label'])} از {toman(r['lo'])}" for r in size_rows[:4])
            out.append({"q": f"قیمت {lp.title} چند است؟", "a": f"قیمت بر اساس سایز فرق می‌کند: {parts} تومان (لیست {month})."})
    if lp.count:
        out.append({"q": f"چند طرح {lp.title} موجود است؟",
                    "a": f"الان {fa_num(lp.count)} طرح موجود است و با تغییر موجودی کارخانه‌ها همین صفحه به‌روز می‌شود."})
    try:
        from installments.services import faq_answer

        ans = faq_answer()
        if ans:
            out.append({"q": f"امکان خرید اقساطی {lp.title} هست؟", "a": ans})
    except ImportError:
        pass
    return out


# ------------------------------------------------------------------ ساخت خودکار
def candidates():
    """ترکیب‌هایی که صفحه می‌گیرند: سایز، رنگ، شانه×سایز، شانه×رنگ، رنگ×سایز."""
    from finder.engine import active_needs
    from pricing.models import Size

    reeds = list(AttributeTerm.objects.filter(Q(attribute__slug="reeds-per-meter") | Q(attribute__label="شانه")))
    sizes = list(Size.objects.filter(is_active=True, type__in=["rect", "runner", "round"]).order_by("sort_order"))
    colors = [n for n in active_needs() if n.group == "color"]
    out = [dict(size=s) for s in sizes] + [dict(color=c) for c in colors]
    out += [dict(reeds=r, size=s) for r in reeds for s in sizes]
    out += [dict(reeds=r, color=c) for r in reeds for c in colors]
    out += [dict(color=c, size=s) for c in colors for s in sizes if s.type == "rect"]
    return out


def refresh(lp, save=True):
    qs = products_of(lp)
    lp.count = qs.count()
    lp.min_price, lp.max_price = price_range(lp, qs) if lp.count else (None, None)
    lp.synced_at = timezone.now()
    if save:
        lp.save(update_fields=["count", "min_price", "max_price", "synced_at"])
    return lp


def sync(log=print):
    """صفحه‌های تازه ساخته می‌شوند، آمار همه به‌روز می‌شود؛ متن‌های دستی دست نمی‌خورند."""
    from .models import LandingPage

    existing = {(lp.reeds_id, lp.size_id, lp.color_id, lp.style_id): lp for lp in LandingPage.objects.all()}
    made = 0
    for c in candidates():
        key = (getattr(c.get("reeds"), "pk", None), getattr(c.get("size"), "pk", None), getattr(c.get("color"), "pk", None), None)
        lp = existing.get(key)
        if lp is None:
            lp = LandingPage(reeds=c.get("reeds"), size=c.get("size"), color=c.get("color"))
            refresh(lp, save=False)
            if lp.count < MIN_PRODUCTS:
                continue
            lp.title = make_title(lp.reeds, lp.size, lp.color)
            lp.slug = make_slug(lp.title)
            if LandingPage.objects.filter(slug=lp.slug).exists():
                continue
            lp.save()
            existing[key] = lp
            made += 1
    for lp in LandingPage.objects.all():
        refresh(lp)
    from django.core.cache import cache

    cache.delete("landing:links")
    log(f"صفحه‌های فرود: {made} تازه، {LandingPage.objects.count()} در کل")
    return made


def live():
    from .models import LandingPage

    return LandingPage.objects.filter(is_active=True, count__gte=MIN_PRODUCTS)


def links_for(reeds_id=None, size_id=None, color_id=None, limit=12):
    """پیوندهای داخلی به صفحه‌های فرود مرتبط."""
    qs = live().select_related("size")
    if reeds_id:
        qs = qs.filter(reeds_id=reeds_id)
    if size_id:
        qs = qs.filter(size_id=size_id)
    if color_id:
        qs = qs.filter(color_id=color_id)
    return list(qs.order_by("-count")[:limit])


def product_links(product, limit=6):
    """صفحه‌های فرود مرتبط با یک فرش (شانه، رنگ و سایزهایش) — یک ساعت کش."""
    from django.core.cache import cache

    key = f"landing:p:{product.pk}"
    ids = cache.get(key)
    if ids is None:
        from finder.engine import active_needs, need_q

        reeds = list(product.specs.filter(Q(attribute__slug="reeds-per-meter") | Q(attribute__label="شانه")).values_list("pk", flat=True))
        colors = [n.pk for n in active_needs() if n.group == "color"
                  and Product.objects.filter(pk=product.pk).filter(need_q(n)).exists()]
        sizes = list(product.variations.filter(is_available=True).values_list("size_id", flat=True))
        qs = live().filter(style=None)
        q = Q(pk__in=[])
        for r in reeds:
            q |= Q(reeds_id=r, size_id__in=sizes) | Q(reeds_id=r, color_id__in=colors)
        q |= Q(reeds=None, color_id__in=colors, size_id__in=sizes)
        ids = list(qs.filter(q).order_by("-count").values_list("pk", flat=True)[:limit])
        cache.set(key, ids, 3600)
    from .models import LandingPage

    by = {x.pk: x for x in LandingPage.objects.filter(pk__in=ids)}
    return [by[i] for i in ids if i in by]
