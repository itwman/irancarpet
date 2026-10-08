"""توضیح متای خودکار و یکتا برای صفحه‌هایی که توضیح سئوی دستی ندارند.

Bing و گوگل توضیح تکراری یا کوتاه را جریمه می‌کنند؛ این توضیح‌ها از داده‌های خود صفحه
(شانه، تراکم، جنس نخ، رنگ، قیمت سایزها، تعداد طرح‌ها) ساخته می‌شوند و ۱۲۰ تا ۱۶۰ حرف‌اند.
توضیحی که در پنل دستی نوشته شده همیشه مقدم است.
"""
from django.core.cache import cache
from django.db.models import Count, Max, Min

from .templatetags.fa import fa_num

MIN_LEN, MAX_LEN = 120, 160
MILLION = 1_000_000


def short_price(n):
    """۴۵٫۵ میلیون"""
    if not n:
        return ""
    if n >= MILLION:
        v = n / MILLION
        txt = f"{v:.1f}".rstrip("0").rstrip(".") if v < 100 else f"{v:.0f}"
        return fa_num(txt.replace(".", "٫")) + " میلیون"
    return fa_num(f"{n:,}").replace(",", "٬")


def fit(parts, tail=(), limit=MAX_LEN):
    """جمله‌ها را تا جایی که از سقف رد نشود کنار هم می‌گذارد؛ بعد اولین جملهٔ پایانی که جا شود."""
    out = ""
    for p in parts:
        if not p:
            continue
        cand = f"{out} {p}".strip() if out else p
        if len(cand) <= limit:
            out = cand
    for t in tail:
        cand = f"{out} {t}".strip()
        if len(cand) <= limit:
            return cand
    return out


def _spec(product, *keys):
    for t in product.specs.all():
        label = (t.attribute.label or "").replace("‌", " ")
        if any(k in label for k in keys):
            return t.name
    return ""


def product(p):
    key = f"autodesc:p:{p.pk}:{p.modified_at.timestamp() if getattr(p, 'modified_at', None) else 0}:{p.min_price}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    reeds, picks = _spec(p, "شانه"), _spec(p, "تراکم")
    pile, color = _spec(p, "خاب"), _spec(p, "رنگ")
    if len(pile) > 22:  # «100% آکریلیک هیت ست شده با ضمانت» ← «100% آکریلیک»
        pile = " ".join(pile.split()[:2])
    if "زمینه" in p.title:
        color = ""
    prices = []
    rows = (p.variations.filter(is_available=True, final_price__gt=0, size__isnull=False)
            .select_related("size").order_by("-size__area")[:6])
    seen = set()
    for v in rows:
        lbl = (v.size.label or "").split("(")[0].strip()
        if lbl and lbl not in seen:
            seen.add(lbl)
            prices.append(f"{lbl} {short_price(v.price)}")
    if prices:
        price_parts = [f"قیمت {'، '.join(prices[:k])} تومان." for k in (2, 1)]
    else:
        price_parts = [f"قیمت از {short_price(p.min_price)} تومان."] if p.min_price else [""]
    head = fa_num(p.title)
    spec_sets = [
        [f"{fa_num(reeds)} شانه" if reeds and "شانه" not in p.title else "", f"تراکم {fa_num(picks)}" if picks else "",
         fa_num(pile), f"زمینهٔ {color}" if color else ""],
    ]
    spec_sets.append(spec_sets[0][:2] + spec_sets[0][3:])   # بدون جنس نخ
    spec_sets.append(spec_sets[0][:2])                        # فقط شانه و تراکم
    spec_sets.append([])
    tail = ["خرید نقدی و اقساطی با ارسال مستقیم از کاشان.", "خرید نقدی و اقساطی از کاشان.", "ارسال به سراسر ایران."]
    if getattr(p, "seller_id", None):  # کالای فروشندهٔ مارکت‌پلیس: ارسال از شهر خود فروشنده، بدون اقساط
        city = p.seller.city
        tail = [f"فروشنده: {p.seller.name}، ارسال از {city}، پرداخت امن در ایران کارپت.", f"ارسال از {city}، پرداخت امن.",
                "ارسال به سراسر ایران."]
    desc = ""
    for specs in spec_sets:
        sp = "، ".join(x for x in specs if x)
        first = f"{head}؛ {sp}." if sp else f"{head}."
        for pr in price_parts:
            cand = f"{first} {pr}".strip()
            if len(cand) <= MAX_LEN:
                desc = fit([cand], tail)
                break
        if desc:
            break
    if not desc:
        desc = fit([f"{head}.", price_parts[-1]], tail)
    cache.set(key, desc, 3600)
    return desc


def listing(obj, products_qs, kind_label="", name=None):
    """دسته، برچسب، برند یا مقدار ویژگی: تعداد طرح و بازهٔ قیمت."""
    name = name or getattr(obj, "name", "") or ""
    if kind_label:
        name = f"{kind_label} {name}".strip()
    key = f"autodesc:l:{obj._meta.label}:{obj.pk}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    agg = products_qs.published().exclude(stock_status="outofstock").aggregate(
        n=Count("pk", distinct=True), lo=Min("min_price"), hi=Max("max_price"))
    n, lo, hi = agg["n"] or 0, agg["lo"], agg["hi"]
    title = name if name.startswith("فرش") else f"فرش {name}"
    parts = [f"خرید {fa_num(title)} از ایران کارپت" + (f"؛ {fa_num(n)} طرح موجود" if n else "") + "."]
    if lo and hi and hi > lo:
        parts.append(f"قیمت از {short_price(lo)} تا {short_price(hi)} تومان.")
    elif lo:
        parts.append(f"قیمت از {short_price(lo)} تومان.")
    tail = ["مقایسهٔ طرح، رنگ و قیمت همهٔ سایزها، خرید نقدی و اقساطی و ارسال مستقیم از کاشان.",
            "خرید نقدی و اقساطی با ارسال مستقیم از کاشان.", "ارسال به سراسر ایران."]
    desc = fit(parts, tail)
    cache.set(key, desc, 3600)
    return desc


def duplicated(model):
    """توضیح‌های سئوی دستی که در چند صفحه از همین نوع تکرار شده‌اند (مثل متن مشترک واردشده از Rank Math)."""
    key = f"autodesc:dup:{model._meta.label}"
    vals = cache.get(key)
    if vals is None:
        vals = set(model.objects.exclude(seo_description="").values("seo_description")
                   .annotate(n=Count("pk")).filter(n__gt=1).values_list("seo_description", flat=True))
        cache.set(key, vals, 3600)
    return vals


def manual_ok(obj):
    """توضیح دستی فقط وقتی به‌کار می‌رود که یکتا باشد و خیلی کوتاه نباشد."""
    d = (obj.seo_description or "").strip()
    if not d:
        return False
    if "%" not in d and len(d) < 70:
        return False
    return d not in duplicated(type(obj))
