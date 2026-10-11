"""موتور قیمت حدودی فرش با سایز دلخواه.

قاعده‌ها (از روش واقعی بافت):
  - دستگاه هر بار دو تختهٔ یکسان می‌بافد. از تعداد سفارش، جفت‌ها کامل و بدون دوخت بافته می‌شوند؛
    اگر تعداد فرد باشد، آخری دو نیمه بافته و دوخته می‌شود.
  - فرشی که در هیچ جهتی در عرض دستگاه جا نشود، هر عددش دو نیمه و دوخت دارد. اگر نیمه‌اش هم روی دستگاه
    همان شانه جا نشود، با بزرگ‌ترین دستگاه (۴ متر) حساب می‌شود.
  - دو نیمه از کنارهٔ بافت به هم دوخته می‌شوند (زیباتر و دقیق‌تر)؛ ضلعی که نصف می‌شود روی عرض دستگاه می‌رود
    و طول درز همان ضلع دیگر است. روش ارزان‌تر (دوخت از سمت طول بافت) فقط برای مقایسه نشان داده می‌شود و ضمانت ندارد.
  - قیمت هر تکه = کمترین این دو: سهم تکه از عرض دستگاه با نرخ کامل (۱۲ متری ÷ ۱۲)، یا مساحت واقعی با نرخ پرتی (۹ متری ÷ ۹).
    اگر چند تکه کنار هم در عرض دستگاه جا شوند، هر کدام سهم خودش را از عرض می‌پردازد.
  - طراحی یک بار برای هر سفارش (اندازهٔ واقعی فرش)؛ دوخت = طول درز × نرخ دوخت × تعداد فرش‌های دوخت‌دار.
    هر دو حداقلی دارند (تنظیمات): طراحی کمتر از «حداقل هزینهٔ طراحی» و دوخت هر فرش کمتر از «حداقل هزینهٔ دوخت» نمی‌شود.
"""
import math
from dataclasses import dataclass, field
from decimal import Decimal

EPS = 1e-6
REEDS = ("700", "1000", "1200", "1500")


class QuoteError(ValueError):
    pass


@dataclass
class Rates:
    r12: float   # نرخ کامل هر متر مربع
    r9: float    # نرخ با پرتی هر متر مربع
    p12: int
    p9: int
    source: str  # «میانگین ۵ آلبوم فرش ۷۰۰ شانه» یا نام آلبوم
    round_to: int = 10_000


@dataclass
class Plan:
    """یک روش بافت برای یک عدد فرش."""
    across: float
    along: float
    pieces: int        # ۱ = کامل، ۲ = دو نیمه
    seam: float        # طول درز (متر)
    loom: float
    cost: float        # قیمت بافت این یک فرش (بدون طراحی و دوخت)
    full_width: bool   # با نرخ کامل (سهم عرض دستگاه) حساب شده؟
    selvedge: bool = True  # دوخت از کنارهٔ بافت (زیباتر)


@dataclass
class Quote:
    width: float
    length: float
    qty: int
    reeds: str
    loom: float
    rates: Rates
    lines: list = field(default_factory=list)   # [(عنوان، مبلغ)]
    total: int = 0
    whole: Plan = None
    halved: Plan = None
    n_whole: int = 0
    n_halved: int = 0
    notes: list = field(default_factory=list)
    alternative: dict = None   # روش ارزان‌تر بدون ضمانت دوخت
    pair_offer: dict = None    # پیشنهاد جفت


def settings():
    from .models import PricingSettings

    return PricingSettings.load()


def loom_width(reeds, s=None):
    s = s or settings()
    return float(getattr(s, f"loom_{reeds}", None) or 3)


def piece_cost(across, along, loom, rates):
    """(قیمت، با نرخ کامل؟) یک تکه با عرض across روی دستگاه loom."""
    k = max(1, math.floor((loom + EPS) / across))
    full = (loom / k) * along * rates.r12
    waste = across * along * rates.r9
    return (full, True) if full <= waste else (waste, False)


def whole_plan(w, l, loom, rates):
    """بهترین جهت برای بافت کامل (یا None اگر در عرض دستگاه جا نشود)."""
    best = None
    for across, along in ((w, l), (l, w)):
        if across <= loom + EPS:
            cost, full = piece_cost(across, along, loom, rates)
            if best is None or cost < best.cost - EPS:
                best = Plan(across, along, 1, 0, loom, cost, full)
    return best


def halved_plan(w, l, loom, rates, selvedge=True, seam_rate=0, seam_min=0):
    """بهترین برش به دو نیمه (با هزینهٔ دوخت در مقایسه). selvedge: ضلع نصف‌شده روی عرض دستگاه و دوخت از کنارهٔ بافت (زیباتر)."""
    best, best_total = None, None
    for split, other in ((w, l), (l, w)):
        half = split / 2
        if selvedge:
            across, along, seam = half, other, other
        else:
            across, along, seam = other, half, other
        if across > loom + EPS:
            continue
        one, full = piece_cost(across, along, loom, rates)
        cost = one * 2
        total = cost + max(seam * seam_rate, seam_min)
        if best is None or total < best_total - EPS:
            best, best_total = Plan(across, along, 2, seam, loom, cost, full, selvedge), total
    return best


def rates_for(reeds=None, album=None):
    """نرخ‌ها از یک آلبوم (زیر صفحهٔ فرش) یا میانگین آلبوم‌های لیست قیمتِ یک شانه."""
    from .models import Size
    from .pricelist import build

    z12, z9 = Size.objects.filter(slug="12-meter").first(), Size.objects.filter(slug="9-meter").first()
    if not z12 or not z9:
        raise QuoteError("سایزهای ۱۲ و ۹ متری تعریف نشده‌اند.")
    if album is not None:
        p12, p9 = album.size_price(z12), album.size_price(z9)
        if not p12:
            raise QuoteError("قیمت این آلبوم در دسترس نیست.")
        p9 = p9 or album.round_up(album._waste(album.sale_base() * Decimal(9) / album._base_area(), z9))
        return Rates(p12 / float(z12.area or 12), p9 / 9, p12, p9, album.title, album.round_to or 10_000)
    data = build()
    g = next((g for g in data["groups"] if g["reeds"] == str(reeds)), None)
    if not g:
        raise QuoteError("برای این شانه هنوز لیست قیمتی نداریم.")
    pairs = [(al["prices"].get(z12.pk), al["prices"].get(z9.pk)) for al in g["albums"]]
    pairs = [(a, b) for a, b in pairs if a and b]
    if not pairs:
        raise QuoteError("برای این شانه قیمت ۱۲ و ۹ متری ثبت نشده است.")
    p12 = sum(a for a, _ in pairs) / len(pairs)
    p9 = sum(b for _, b in pairs) / len(pairs)
    return Rates(p12 / float(z12.area or 12), p9 / 9, int(p12), int(p9), f"میانگین {len(pairs)} آلبوم فرش {reeds} شانه")


def round_up(x, step):
    step = int(step or 1)
    return int(math.ceil((x - EPS) / step)) * step


def _parse(v):
    try:
        x = float(str(v).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٫،", "0123456789..")).strip())
    except (TypeError, ValueError):
        raise QuoteError("طول و عرض را به متر بنویسید؛ مثل ۲٫۵")
    if x > 40:  # احتمالاً سانتی‌متر نوشته
        x = x / 100
    return round(x, 2)


def quote(width, length, qty=1, reeds="700", album=None, rates=None):
    """قیمت حدودی سفارش. خطای ورودی ← QuoteError با پیام فارسی."""
    from core.templatetags.fa import fa_num

    s = settings()
    if not s.custom_enabled:
        raise QuoteError("محاسبهٔ سایز دلخواه فعلاً خاموش است؛ با ما تماس بگیرید.")
    w, l = _parse(width), _parse(length)
    try:
        qty = max(1, min(int(str(qty).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))), 50))
    except (TypeError, ValueError):
        qty = 1
    reeds = str(reeds) if str(reeds) in REEDS else "700"
    w, l = min(w, l), max(w, l)
    mn, mx = float(s.custom_min_side), float(s.custom_max_length)
    if w < mn - EPS:
        raise QuoteError(f"کمترین اندازهٔ هر ضلع {fa_num(int(round(mn * 100)))} سانتی‌متر است.")
    if l > mx + EPS:
        raise QuoteError(f"بیشترین طول {fa_num(f'{mx:g}')} متر است؛ برای اندازهٔ بزرگ‌تر با ما تماس بگیرید.")
    rates = rates or rates_for(reeds, album)
    loom = loom_width(reeds, s)
    big = float(s.loom_big or 4)
    q = Quote(w, l, qty, reeds, loom, rates)
    whole = whole_plan(w, l, loom, rates)
    seam_min = int(s.seam_min or 0)
    halved = halved_plan(w, l, loom, rates, seam_rate=s.seam_per_m, seam_min=seam_min)
    if halved is None and big > loom:
        loom = big
        q.loom = big
        whole = whole_plan(w, l, loom, rates)
        halved = halved_plan(w, l, loom, rates, seam_rate=s.seam_per_m, seam_min=seam_min)
        q.notes.append(f"به‌خاطر اندازهٔ بزرگ، این فرش با دستگاه {fa_num(f'{big:g}')} متری حساب شد؛ ممکن است در قیمت یا دستگاه بافت تغییری لازم شود "
                       "و کارشناس ما هماهنگ می‌کند.")
    if halved is None:
        raise QuoteError("این اندازه حتی به‌صورت دو تکه هم روی دستگاه جا نمی‌شود؛ برای سفارش با کارشناس تماس بگیرید.")
    if whole is not None:
        n_whole = (qty // 2) * 2
        n_halved = qty % 2
    else:
        n_whole, n_halved = 0, qty
    q.whole, q.halved, q.n_whole, q.n_halved = whole, halved, n_whole, n_halved

    carpets = n_whole * (whole.cost if whole else 0) + n_halved * halved.cost
    area = w * l
    design_raw = area * s.design_per_m2
    design = max(design_raw, int(s.design_min or 0))
    seam_one = max(halved.seam * s.seam_per_m, seam_min)
    seam = n_halved * seam_one
    area_fa = fa_num(f'{area:.2f}'.rstrip('0').rstrip('.'))
    q.lines.append((f"بافت {fa_num(qty)} فرش ({area_fa} متر مربع هر کدام)", carpets))
    q.lines.append((f"طراحی نقشه برای این اندازه ({'حداقل هزینهٔ طراحی' if design > design_raw else area_fa + ' متر مربع'}؛ یک بار)", design))
    if seam:
        what = "حداقل هزینهٔ دوخت" if seam_one > halved.seam * s.seam_per_m else f"{fa_num(f'{halved.seam:g}')} متر"
        q.lines.append((f"دوخت دو نیمه ({what}{' × ' + fa_num(n_halved) + ' فرش' if n_halved > 1 else ''})", seam))
    q.total = round_up(carpets + design + seam, rates.round_to)

    # روش ارزان‌تر بدون ضمانت دوخت
    if n_halved:
        alt = halved_plan(w, l, loom, rates, selvedge=False, seam_rate=s.seam_per_m, seam_min=seam_min)
        if alt:
            alt_total = round_up(n_whole * (whole.cost if whole else 0) + n_halved * alt.cost + design
                                 + n_halved * max(alt.seam * s.seam_per_m, seam_min), rates.round_to)
            if alt_total < q.total:
                q.alternative = {"total": alt_total, "saving": q.total - alt_total, "seam": alt.seam}
    # پیشنهاد جفت
    if n_halved and whole is not None:
        pair_total = round_up((qty + 1) * whole.cost + design, rates.round_to)
        q.pair_offer = {"qty": qty + 1, "total": pair_total, "each": round_up(pair_total / (qty + 1), 1000),
                        "each_now": round_up(q.total / qty, 1000)}
    return q


def describe(q):
    """توضیح روش بافت برای مشتری."""
    from core.templatetags.fa import fa_num

    def m(x):
        return fa_num(f"{x:.2f}".rstrip("0").rstrip("."))

    out = []
    if q.n_whole:
        p = q.whole
        out.append(f"{fa_num(q.n_whole)} عدد کامل و بدون دوخت (دستگاه هر بار دو تخته می‌بافد)؛ "
                   f"{m(p.across)} متر روی عرض دستگاه {m(q.loom)} متری.")
    if q.n_halved:
        p = q.halved
        why = "چون این اندازه در عرض دستگاه جا نمی‌شود" if q.whole is None else "چون دستگاه از هر طرح دو تخته می‌بافد"
        out.append(f"{fa_num(q.n_halved)} عدد به‌صورت دو نیمهٔ {m(p.across)} در {m(p.along)} متر بافته و از کنارهٔ بافت به هم دوخته می‌شود "
                   f"({why}).")
    if q.whole is not None and (q.whole.across, q.whole.along) == (q.length, q.width) and q.width != q.length:
        out.append("ضلع بلندتر روی عرض دستگاه قرار می‌گیرد؛ فرش همان اندازهٔ شماست.")
    return out


def as_dict(q):
    from core.templatetags.fa import toman

    return {
        "ok": True, "width": q.width, "length": q.length, "qty": q.qty, "reeds": q.reeds, "loom": q.loom,
        "total": q.total, "total_fa": toman(q.total), "each_fa": toman(round_up(q.total / q.qty, 1000)) if q.qty > 1 else "",
        "lines": [{"label": a, "amount": toman(round_up(b, 1000))} for a, b in q.lines],
        "how": describe(q), "notes": q.notes, "source": q.rates.source,
        "split": ("" if not q.n_halved else ("length" if abs(q.halved.across * 2 - q.length) < 0.011 else "width")),
        "alternative": {**q.alternative, "total_fa": toman(q.alternative["total"]), "saving_fa": toman(q.alternative["saving"])}
        if q.alternative else None,
        "pair": {**q.pair_offer, "total_fa": toman(q.pair_offer["total"]), "each_fa": toman(q.pair_offer["each"]),
                 "each_now_fa": toman(q.pair_offer["each_now"])} if q.pair_offer else None,
    }


def block(request, title=""):
    """بلوک [custom_size_calc] برای مقاله‌ها و برگه‌ها."""
    import json

    from django.template.loader import render_to_string

    from .pricelist import build

    s = settings()
    if not s.custom_enabled:
        return ""
    groups = [{"reeds": g["reeds"], "albums": [{"id": a["id"], "title": a["title"]} for a in g["albums"]]}
              for g in build()["groups"] if g["reeds"] in REEDS]
    return render_to_string("blog/blocks/custom_size.html", {
        "groups": groups, "groups_json": json.dumps(groups, ensure_ascii=False), "min_cm": int(round(float(s.custom_min_side) * 100)),
        "max_len": float(s.custom_max_length),
    }, request=request)


def product_reeds(product):
    """شانهٔ فرش: از عنوان، وگرنه از ویژگی «شانه»."""
    import re

    from core.templatetags.fa import reeds_of

    r = reeds_of(product.title or "")
    if r in REEDS:
        return r
    for name in product.specs.filter(attribute__slug="reeds-per-meter").values_list("name", flat=True):
        d = re.sub(r"\D", "", str(name or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if d in REEDS:
            return d
    return ""


def product_block(request, product):
    """ماشین‌حساب جمع‌شده زیر جدول سایزهای صفحهٔ فرش؛ فقط برای فرش موجود فروشگاه با آلبوم و قیمت ۱۲ و ۹ متری."""
    from django.template.loader import render_to_string

    s = settings()
    if not s.custom_enabled or not product.is_purchasable or product.seller_id or not product.album_id:
        return ""
    album = product.album
    if not album.is_active:
        return ""
    reeds = product_reeds(product)
    if not reeds:
        return ""
    try:
        rates_for(album=album)
    except QuoteError:
        return ""
    except Exception:  # noqa: BLE001  (قیمت آلبوم ناقص؛ ماشین‌حساب نشان داده نمی‌شود)
        import logging

        logging.getLogger(__name__).warning("custom calc product %s", product.pk, exc_info=True)
        return ""
    from django.conf import settings as dj_settings

    from core.context_processors import site

    ss = site(request)["site_settings"]
    return render_to_string("blog/blocks/custom_size.html", {
        "product": product, "reeds": reeds, "wa": ss.whatsapp or ss.mobile or "",
        "page_url": dj_settings.SITE_URL.rstrip("/") + product.get_absolute_url(),
        "min_cm": int(round(float(s.custom_min_side) * 100)), "max_len": float(s.custom_max_length),
    }, request=request)
