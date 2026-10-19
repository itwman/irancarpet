"""تگ‌های کمکی برای قالب‌های جدا (مثل قالب فرشستان) که به دادهٔ صفحهٔ اول وابسته نیستند.

    {% load shop_theme %}
    {% reeds_categories as rc %}      دسته‌هایی مثل «فرش ۷۰۰ شانه» با تعداد محصول
    {% color_categories as cc %}      دسته‌های «فرش زمینه …» با رنگ نمونه و تعداد
    {% latest_products 8 as items %}  تازه‌ترین فرش‌های موجود و عکس‌دار
    {{ "سرمه ای"|swatch }}            کد رنگ نمونه برای نام رنگ فارسی
    {% jyear %}                       سال شمسی جاری با ارقام فارسی
"""
import re

from django import template
from django.core.cache import cache
from django.db.models import Count, Q

register = template.Library()

COLORS = {
    "آبی": "#4A78A8", "اقیانوسی": "#1F5F7A", "بنفش": "#6B4C8A", "بژ": "#D9C4A3", "ترمه": "#6E2A2E", "تیتانیومی": "#8A8D8F",
    "دلفینی": "#6F8796", "دودی": "#6B6764", "روناسی": "#A3312A", "زغالی": "#3E3B39", "سبز آبی": "#3E8A86", "سبز": "#4E7A55",
    "سربی": "#5E6366", "سرمه": "#2E3A5C", "سفید": "#F4F1EA", "سیلور": "#CFCBC4", "شکلاتی": "#5A3A2A", "کرم صدفی": "#EFE4D2",
    "صدفی": "#EDE3D3", "طوسی": "#9A9690", "فیلی": "#8E8A84", "قهوه": "#6E4B33", "لاکی": "#8E2B2B", "قرمز": "#9B2C2C",
    "متالیک": "#9AA0A3", "مشکی": "#1E1C1B", "موشی": "#7D7770", "موکا": "#8B6A55", "نسکافه": "#A47E5E", "نقره": "#C3C5C7",
    "کاربنی": "#3B3D40", "کرم": "#E9DCC4", "یاسی": "#B9A3C9", "گردویی": "#6B4A32", "طلایی": "#C8A45C",
}
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def swatch(name):
    n = (name or "").replace("ي", "ی").replace("‌", " ")
    for key in sorted(COLORS, key=len, reverse=True):
        if key in n:
            return COLORS[key]
    return "#D9C4A3"


def _cat_counts():
    from catalog.models import Category

    data = cache.get("theme_cat_counts")
    if data is None:
        qs = (Category.objects.filter(parent=None)
              .annotate(n=Count("products", filter=Q(products__status="publish"), distinct=True)).filter(n__gt=0))
        data = [(c.pk, c.name, c.get_absolute_url(), c.n) for c in qs]
        cache.set("theme_cat_counts", data, 600)
    return data


@register.simple_tag
def reeds_categories():
    out = []
    for _pk, name, url, n in _cat_counts():
        m = re.search(r"(\d{3,4})\s*شانه", name.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        if m:
            out.append({"reeds": int(m.group(1)), "name": name, "url": url, "count": n})
    return sorted(out, key=lambda x: x["reeds"])


@register.simple_tag
def color_categories(limit=12):
    out = []
    for _pk, name, url, n in _cat_counts():
        if "زمینه" in name:
            color = name.split("زمینه", 1)[1].strip()
            out.append({"name": color, "url": url, "count": n, "hex": swatch(color)})
    return sorted(out, key=lambda x: -x["count"])[:limit]


@register.simple_tag
def latest_products(n=8):
    from catalog.models import Product

    key = f"theme_latest_{n}"
    ids = cache.get(key)
    if ids is None:
        ids = list(Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False)
                   .order_by("-published_at", "-pk").values_list("pk", flat=True)[: int(n)])
        cache.set(key, ids, 600)
    items = {p.pk: p for p in Product.objects.filter(pk__in=ids).select_related("image", "brand")}
    return [items[i] for i in ids if i in items]


@register.simple_tag
def jyear():
    import jdatetime

    return str(jdatetime.date.today().year).translate(_FA)


# ---------------------------------------------------------------- برای قالب «خانهٔ ایرانی» فرشستان
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


@register.filter
def rug_name(title):
    """«فرش طرح زرین سیلور 700 شانه برجسته تمام آکریلیک» ← «زرین سیلور» (نام کوتاه نقشه برای تیترهای درشت)"""
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    m = re.search(r"(?:نقشه|طرح)\s+(.+)$", t)
    rest = m.group(1) if m else re.sub(r"^(?:تابلو\s*فرش|فرش)\s+", "", t)
    rest = re.split(r"\s*[\d۰-۹]{3,4}\s*شانه|\s+(?:سایز|کد|تمام|بافت)\s|\s*[-–(]", rest, maxsplit=1)[0].strip()
    rest = re.sub(r"\s+زمینه\s+", " ", rest)
    words = rest.split()
    return " ".join(words[:4]) if words else t


@register.filter
def rug_crop(media):
    """کادر خود فرش در عکس محصول (درصد x، y، پهنا، بلندی و نسبت ابعاد) تا حاشیهٔ سفید، نوار تماس و لوگوی عکس بریده شود.

    یک بار از روی فایل حساب و کنار تصویرهای کوچک (app-thumbs/crop) نگه داشته می‌شود. اگر عکس خودش فقط فرش باشد
    یا تشخیص مطمئن نباشد، کل عکس برمی‌گردد (crop=False).
    """
    import json
    import os
    from pathlib import Path

    from django.conf import settings

    f = getattr(media, "file", None)
    if not f:
        return None
    full = {"x": 0, "y": 0, "w": 100, "h": 100, "crop": False}
    w0, h0 = getattr(media, "width", None), getattr(media, "height", None)
    full["ar"] = round(w0 / h0, 4) if w0 and h0 else 0.6667
    root = Path(settings.MEDIA_ROOT)
    src = root / f.name
    side = root / "app-thumbs" / "crop" / (f.name + ".json")
    try:
        mt = int(os.path.getmtime(src))
    except OSError:
        return full
    try:
        data = json.loads(side.read_text())
        if data.get("mt") == mt:
            return data
    except (OSError, ValueError):
        pass
    data = _detect_rug(src) or {}
    out = {**full, **data, "mt": mt}
    try:
        side.parent.mkdir(parents=True, exist_ok=True)
        tmp = side.with_suffix(".tmp")
        tmp.write_text(json.dumps(out))
        tmp.replace(side)
    except OSError:
        pass
    return out


def _detect_rug(path):
    """بزرگ‌ترین بازهٔ پیوستهٔ ستون‌ها و ردیف‌های «غیرسفید» = خود فرش (نوار باریک کنار عکس و لوگو کنار گذاشته می‌شوند)."""
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.draft("RGB", (320, 320))
            im = im.convert("RGB")
            im.thumbnail((240, 240))
            W, H = im.size
            px = im.load()
    except Exception:  # noqa: BLE001 — عکس خراب نباید صفحه را از کار بیندازد
        return None
    ar = round(W / H, 4)
    if W < 40 or H < 40:
        return {"ar": ar}
    ink = [[0] * W for _ in range(H)]
    for y in range(H):
        row = ink[y]
        for x in range(W):
            r, g, b = px[x, y]
            row[x] = 0 if (min(r, g, b) > 228 and max(r, g, b) - min(r, g, b) < 26) else 1

    def run(vals, th):
        best, cur, start = (0, 0), 0, 0
        for i, v in enumerate(vals + [0]):
            if v > th:
                if cur == 0:
                    start = i
                cur += 1
            else:
                if cur > best[1] - best[0]:
                    best = (start, start + cur)
                cur = 0
        return best

    cols = [sum(ink[y][x] for y in range(H)) / H for x in range(W)]
    x0, x1 = run(cols, 0.55)
    if x1 - x0 < W * 0.25:
        return {"ar": ar}
    span = x1 - x0
    rows = [sum(ink[y][x0:x1]) / span for y in range(H)]
    y0, y1 = run(rows, 0.6)
    if y1 - y0 < H * 0.25:
        return {"ar": ar}
    if (x1 - x0) * (y1 - y0) > W * H * 0.93:
        return {"ar": ar}

    # لوگوی قرمز فروشگاه که روی لبهٔ بالای فرش افتاده: ردیف‌های بالایی که پیکسل قرمز تند دارند کنار می‌روند
    def red(x, y):
        r, g, b = px[x, y]
        return r > 150 and g < 95 and b < 95

    limit = y0 + int((y1 - y0) * 0.14)
    last = None
    for y in range(y0, limit):
        if sum(1 for x in range(x0, x1) if red(x, y)) >= 3:
            last = y
    if last is not None:
        y0 = last + 5  # خط دور لوگو هم کنار برود
    # یک پیکسل به داخل تا لبهٔ سفید دیده نشود
    x0, y0, x1, y1 = x0 + 1, y0 + 1, x1 - 1, y1 - 1
    return {"x": round(x0 / W * 100, 2), "y": round(y0 / H * 100, 2), "w": round((x1 - x0) / W * 100, 2),
            "h": round((y1 - y0) / H * 100, 2), "ar": round((x1 - x0) / (y1 - y0), 4), "crop": True}


def _cached_ids(key, build):
    ids = cache.get(key)
    if ids is None:
        ids = build()
        cache.set(key, ids, 600)
    return ids


@register.simple_tag
def best_products(n=5):
    """پربازدیدترین فرش‌های موجود و عکس‌دار (برای «شاه‌نشین» صفحهٔ اول)."""
    from catalog.models import Product

    ids = _cached_ids(f"theme_best_{n}", lambda: list(
        Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False)
        .order_by("-views", "-pk").values_list("pk", flat=True)[: int(n)]))
    items = {p.pk: p for p in Product.objects.filter(pk__in=ids).select_related("image", "brand")}
    return [items[i] for i in ids if i in items]


@register.simple_tag
def arch_categories(n=7):
    """دسته‌های اصلی (به‌جز دسته‌های «زمینه …») با تعداد و عکس پربازدیدترین فرش هر دسته؛ پرتعدادترین در وسط.

    خروجی: {"arches": [...n تا به ترتیب نمایش], "more": [بقیهٔ دسته‌ها]}
    """
    from catalog.models import Category, Product
    from core.models import Media

    def build():
        cats = [c for c in _cat_counts() if "زمینه" not in c[1]]
        cats.sort(key=lambda c: -c[3])
        out = []
        for pk, name, url, cnt in cats:
            img = None
            if len(out) < int(n):
                c = Category.objects.filter(pk=pk).first()
                ids = c.descendant_ids() if c else [pk]
                img = (Product.objects.published().filter(categories__in=ids, image__isnull=False)
                       .exclude(stock_status="outofstock").order_by("-views", "-pk").values_list("image_id", flat=True).first())
            out.append((pk, name, url, cnt, img))
        return out

    data = _cached_ids(f"theme_arches_{n}", build)
    imgs = Media.objects.in_bulk([d[4] for d in data if d[4]])
    items = []
    for pk, name, url, cnt, img in data:
        short = re.sub(r"^فرش\s+", "", name)
        m = re.search(r"(\d{3,4})\s*شانه", name.translate(_EN))
        items.append({"name": name, "short": short, "url": url, "count": cnt, "image": imgs.get(img),
                      "reeds": int(m.group(1)) if m else None})
    top = items[: int(n)]
    if top:
        top[0]["mid"] = True
    order = []
    for i, it in enumerate(top):  # پرتعدادترین وسط، بقیه یکی راست یکی چپ
        if i % 2:
            order.insert(0, it)
        else:
            order.append(it)
    # در RTL اولین خانهٔ شبکه سمت راست است؛ ترتیب بالا تقارن را نگه می‌دارد
    return {"arches": order, "more": items[int(n):]}


@register.simple_tag
def product_total():
    from catalog.models import Product

    n = cache.get("theme_product_total")
    if n is None:
        n = Product.objects.published().count()
        cache.set("theme_product_total", n, 600)
    return n


@register.simple_tag
def jtoday():
    """«دوشنبه ۲۷ مهر ۱۴۰۵»"""
    import jdatetime
    from django.utils import timezone

    d = jdatetime.date.fromgregorian(date=timezone.localdate())
    days = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    return f"{days[d.weekday()]} {d.day} {months[d.month - 1]} {d.year}".translate(_FA)


@register.filter
def size_name(label):
    """«۹ متری مستطیل (۳.۵ × ۲.۵)» ← «۹ متری مستطیل» (ابعاد جدا نوشته می‌شود)"""
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(label or "")).strip() or label


@register.filter
def rug_style(media):
    """متغیرهای CSS کادر فرش برای style=""؛ مثل «--ar:0.7217;--cx:20;--cy:9.58;--cw:63.75;--ch:88.33»"""
    from django.utils.safestring import mark_safe

    c = rug_crop(media) if media else None
    if not c:
        return mark_safe("--ar:0.6667")
    s = f"--ar:{c['ar']:.4f}"
    if c.get("crop"):
        s += f";--cx:{c['x']:g};--cy:{c['y']:g};--cw:{c['w']:g};--ch:{c['h']:g}"
    return mark_safe(s)


@register.filter
def rug_data(media):
    """همان کادر به شکل «x,y,w,h,ar» برای data-crop (اسکریپت ذره‌بین و نقشهٔ اتاق)"""
    c = rug_crop(media) if media else None
    if not c:
        return "0,0,100,100,0.6667"
    return f"{c['x']:g},{c['y']:g},{c['w']:g},{c['h']:g},{c['ar']:.4f}"
