"""تصویر هفتگی «قیمت روز فرش»: میانگین قیمت فرش‌های هر آلبوم در سایزهای انتخاب‌شده."""
import io
import re
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, features

from core.templatetags.fa import fa_num, toman

from .fa_text import visual

FONTS = Path(__file__).resolve().parent / "fonts"
RAQM = features.check("raqm")

INK, INK2, MUTED = (34, 38, 90), (75, 79, 126), (108, 111, 152)
PINK, PINK_T, SAFFRON, TEAL = (229, 57, 91), (255, 239, 242), (255, 178, 30), (11, 124, 136)
SOFT, LINE, WHITE = (243, 244, 251), (226, 228, 240), (255, 255, 255)
W, PAD = 1080, 56
MAX_ROWS = 20


def font(size, weight="Regular"):
    return ImageFont.truetype(str(FONTS / f"Vazirmatn-FD-{weight}.ttf"), size,
                              layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)


def text(draw, xy, s, f, fill, anchor="ra"):
    """متن فارسی؛ xy لبهٔ راست (anchor=ra) یا وسط (ma)."""
    s = fa_num(s)
    if RAQM:
        draw.text(xy, s, font=f, fill=fill, anchor=anchor, direction="rtl", language="fa")
    else:
        draw.text(xy, visual(s), font=f, fill=fill, anchor=anchor)


def width(draw, s, f):
    s = fa_num(s)
    if RAQM:
        return draw.textlength(s, font=f, direction="rtl", language="fa")
    return draw.textlength(visual(s), font=f)


def fit(draw, s, f, max_w):
    if width(draw, s, f) <= max_w:
        return s
    while s and width(draw, s + "…", f) > max_w:
        s = s[:-1]
    return s.rstrip() + "…"


def date_label(dt=None):
    import jdatetime

    d = jdatetime.date.fromgregorian(date=timezone.localtime(dt or timezone.now()).date())
    days = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return fa_num(f"{days[d.weekday()]} {d.day} {months[d.month - 1]} {d.year}")


# ------------------------------------------------------------------ داده
def default_sizes():
    from pricing.models import Size

    return list(Size.objects.filter(slug__in=["12-meter", "9-meter", "6-meter"]).order_by("sort_order"))


def _sizes(s):
    sizes = list(s.weekly_sizes.order_by("sort_order")) if s.pk else []
    return (sizes or default_sizes())[:5]


def _avg(values):
    return int(round(sum(values) / len(values), -4)) if values else None


def material(name):
    """«100% آکریلیک هیت ست» ← آکریلیک، «پلی استر» ← پلی‌استر"""
    n = (name or "").replace("\u200c", " ")
    if "پلی" in n or "polyester" in n.lower():
        return "پلی‌استر"
    if "آکریلیک" in n or "اکریلیک" in n or "acryl" in n.lower():
        return "آکریلیک"
    n = re.sub(r"[0-9۰-۹%٪]+", "", n).replace("با ضمانت", "").strip()
    return " ".join(n.split()[:2])


def wanted_reeds(s):
    raw = (getattr(s, "weekly_reeds", "") or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    return [int(x) for x in re.findall(r"\d+", raw)]


def rows_by_reeds(s):
    """میانگین همهٔ فرش‌های هم‌شانه و هم‌جنس (از همهٔ آلبوم‌ها): «فرش ۷۰۰ شانه پلی‌استر» و…"""
    from catalog.models import Attribute, Product, Variation

    sizes = _sizes(s)
    reeds_attr = Attribute.objects.filter(slug="reeds-per-meter").first() or Attribute.objects.filter(label__contains="شانه").first()
    pile_attr = Attribute.objects.filter(label__contains="خاب").first()
    if not reeds_attr:
        return [], sizes
    vs = (Variation.objects.filter(product__status="publish", product__seller__isnull=True, size__in=sizes, is_available=True)
          .exclude(product__sale_status="unavailable").only("product_id", "size_id", "final_price", "sale_price"))
    albums = list(s.weekly_albums.values_list("pk", flat=True)) if s.pk else []
    if albums:
        vs = vs.filter(product__album_id__in=albums)
    vs = list(vs)
    pids = {v.product_id for v in vs}
    spec = {}
    through = Product.specs.through.objects.filter(product_id__in=pids, attributeterm__attribute__in=[reeds_attr] + ([pile_attr] if pile_attr else []))
    for pid, name, attr in through.values_list("product_id", "attributeterm__name", "attributeterm__attribute_id"):
        spec.setdefault(pid, {})["reeds" if attr == reeds_attr.pk else "pile"] = name
    want = wanted_reeds(s)
    groups = {}
    for v in vs:
        sp = spec.get(v.product_id, {})
        digits = re.sub(r"\D", "", (sp.get("reeds") or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if not digits or not v.price:
            continue
        reeds = int(digits)
        if want and reeds not in want:
            continue
        key = (reeds, material(sp.get("pile")))
        groups.setdefault(key, {}).setdefault(v.size_id, []).append(v.price)
    order = {"پلی‌استر": 0, "آکریلیک": 1}
    out = []
    for (reeds, mat), by in sorted(groups.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 2), kv[0][1])):
        prices = [_avg(by.get(z.pk, [])) for z in sizes]
        if any(prices):
            out.append((f"فرش {reeds} شانه {mat}".strip(), prices))
    return out, sizes


def rows(s):
    """[(نام گروه، [میانگین قیمت هر سایز یا None])], سایزها"""
    if getattr(s, "weekly_group", "reeds") == "reeds":
        return rows_by_reeds(s)
    from catalog.models import Variation
    from pricing.models import Album

    sizes = _sizes(s)
    albums = list(s.weekly_albums.order_by("sort_order", "name")) if s.pk else []
    albums = albums or list(Album.objects.filter(is_active=True, in_price_list=True).order_by("sort_order", "name"))
    out = []
    for a in albums:
        vs = (Variation.objects.filter(product__album=a, product__status="publish", product__seller__isnull=True, size__in=sizes, is_available=True)
              .exclude(product__sale_status="unavailable").only("size_id", "final_price", "sale_price"))
        by = {}
        for v in vs:
            if v.price:
                by.setdefault(v.size_id, []).append(v.price)
        prices = [_avg(by.get(z.pk, [])) for z in sizes]
        if any(prices):
            out.append((a.title, prices))
    return out, sizes


def short_size(size):
    return (size.label or "").split("(")[0].strip()


# ------------------------------------------------------------------ تصویر
def border(draw, y, color_a=SAFFRON, color_b=PINK):
    """نوار لوزی‌های کوچک، مثل حاشیهٔ فرش."""
    step, h = 24, 9
    for i, x in enumerate(range(0, W + step, step)):
        c = color_a if i % 2 else color_b
        draw.polygon([(x, y - h), (x + h, y), (x, y + h), (x - h, y)], fill=c)


def render(s, when=None):
    data, sizes = rows(s)
    more = len(data) > MAX_ROWS
    data = data[:MAX_ROWS]
    row_h, head_h, top_h, foot_h = 74, 64, 250, 150
    h = top_h + 70 + head_h + max(len(data), 1) * row_h + 40 + foot_h + (40 if more else 0)
    im = Image.new("RGB", (W, h), WHITE)
    d = ImageDraw.Draw(im)

    # سربرگ
    d.rectangle([0, 0, W, top_h], fill=INK)
    try:
        logo = Image.open(Path(settings.BASE_DIR) / "static" / "img" / "logo.png").convert("RGBA").resize((112, 112))
        tile = Image.new("RGBA", (132, 132), (255, 255, 255, 0))
        ImageDraw.Draw(tile).rounded_rectangle([0, 0, 131, 131], radius=30, fill=WHITE)
        tile.alpha_composite(logo, (10, 10))
        im.paste(tile, (W - PAD - 132, 52), tile)
    except Exception:  # noqa: BLE001
        pass
    right = W - PAD - 132 - 28
    text(d, (right, 62), s.weekly_title or "قیمت روز فرش ماشینی", font(46, "Black"), WHITE)
    text(d, (right, 132), date_label(when), font(30, "Bold"), (255, 205, 214))
    text(d, (right, 180), "ایران کارپت · فرش ماشینی کاشان، بی‌واسطه", font(24), (190, 193, 228))
    border(d, top_h)

    # توضیح
    y = top_h + 34
    text(d, (W - PAD, y), "میانگین قیمت همهٔ طرح‌های هر گروه، به تومان", font(24), MUTED)

    # جدول
    y += 54
    col_w = {1: 260, 2: 230, 3: 210, 4: 168}.get(len(sizes), 140)
    name_w = W - 2 * PAD - col_w * len(sizes)
    d.rounded_rectangle([PAD, y, W - PAD, y + head_h], radius=18, fill=PINK_T)
    text(d, (W - PAD - 24, y + 17), "شانه و جنس نخ" if getattr(s, "weekly_group", "reeds") == "reeds" else "گروه فرش",
         font(26, "Bold"), INK)
    for i, z in enumerate(sizes):
        cx = W - PAD - name_w - col_w * i - col_w / 2
        text(d, (cx, y + 17), short_size(z), font(26, "Bold"), PINK, anchor="ma")
    y += head_h + 8
    fname, fprice = font(29, "Bold"), font(29)
    if not data:
        text(d, (W / 2, y + 18), "هنوز قیمتی برای این سایزها ثبت نشده است.", fname, MUTED, anchor="ma")
        y += row_h
    for k, (name, prices) in enumerate(data):
        if k % 2:
            d.rounded_rectangle([PAD, y, W - PAD, y + row_h - 6], radius=16, fill=SOFT)
        text(d, (W - PAD - 24, y + 18), fit(d, fa_num(name), fname, name_w - 36), fname, INK)
        for i, p in enumerate(prices):
            cx = W - PAD - name_w - col_w * i - col_w / 2
            text(d, (cx, y + 18), toman(p) if p else "—", fprice, INK2 if p else MUTED, anchor="ma")
        y += row_h
    if more:
        text(d, (W - PAD, y + 6), "قیمت همهٔ گروه‌ها و سایزها در سایت", font(24), MUTED)
        y += 40

    # پایین
    fy = h - foot_h
    border(d, fy, PINK, SAFFRON)
    d.rectangle([0, fy + 10, W, h], fill=PINK)
    host = settings.SITE_URL.split("//")[-1].strip("/")
    d.text((PAD, fy + 52), host, font=font(38, "Black"), fill=WHITE, anchor="la")
    text(d, (W - PAD, fy + 46), "خرید نقدی و اقساطی", font(30, "Bold"), WHITE)
    from core.models import SiteSettings

    phone = SiteSettings.load().phone
    text(d, (W - PAD, fy + 92), f"مشاورهٔ خرید: \u2066{phone}\u2069" if phone else "ارسال مستقیم از کاشان", font(24), (255, 225, 231))

    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue(), data, sizes


def save(png, when=None):
    """ذخیره در پوشهٔ رسانه؛ نشانی کامل برمی‌گردد."""
    stamp = timezone.localtime(when or timezone.now()).strftime("%Y%m%d-%H%M")
    name = f"rajyar/pricelist-{stamp}.png"
    if default_storage.exists(name):
        default_storage.delete(name)
    name = default_storage.save(name, ContentFile(png))
    url = default_storage.url(name)
    return url if url.startswith("http") else settings.SITE_URL + url
