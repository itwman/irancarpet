"""فرش متری (کناره، سجاده‌ای): عرض از فهرست، طول دلخواه (تا سانتی‌متر)، قیمت = عرض × طول × قیمت هر متر مربع.

قاعده‌ها از آلبوم «متری» فرش می‌آیند (عرض‌ها، کمترین طول برای عرض باریک و پهن، بیشترین طول، گرد کردن).
قیمت هر متر مربع همان قیمت تنوع «هر متر مربع» فرش است (با سود و گرد کردن آلبوم).
"""
import math
import re
from decimal import Decimal, InvalidOperation

from .models import M2_SLUG, M2_WIDTHS

DEFAULT = {"widths": M2_WIDTHS, "min_narrow": Decimal("2"), "min_wide": Decimal("1.5"), "max_length": Decimal("30"),
           "round": 100_000, "note": ""}
_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")


def num(s):
    """«۱۵٫۴۵»، «15/45»، «15,45» ← Decimal؛ نادرست ← None"""
    s = str(s or "").strip().translate(_EN).replace("/", ".").replace(",", ".").replace("،", ".")
    s = re.sub(r"[^\d.]", "", s)
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


def widths_of(text):
    out = []
    for part in re.split(r"[,،\s]+", str(text or "")):
        d = num(part)
        if d and d not in out:
            out.append(d.quantize(Decimal("0.01")))
    return sorted(out)


def rules(product):
    """قاعده‌های اندازهٔ یک فرش متری، یا None اگر فرش متری نیست."""
    v = variation(product)
    if v is None:
        return None
    a = product.album if product.album_id else None
    src = ({"widths": a.m2_widths, "min_narrow": a.m2_min_narrow, "min_wide": a.m2_min_wide, "max_length": a.m2_max_length,
            "round": a.m2_round, "note": a.m2_note} if a is not None and a.is_m2 else DEFAULT)
    return {"widths": widths_of(src["widths"]) or widths_of(M2_WIDTHS), "min_narrow": Decimal(src["min_narrow"]),
            "min_wide": Decimal(src["min_wide"]), "max_length": Decimal(src["max_length"]), "round": int(src["round"] or 0),
            "note": src["note"], "price": v.price or 0, "variation": v}


def variation(product):
    for v in product.variations.all():
        if v.size_id and v.size.slug == M2_SLUG:
            return v
    return None


def min_length(r, width):
    return r["min_wide"] if width >= 1 else r["min_narrow"]


def check(r, width, length):
    """پیام خطا یا ''"""
    if width is None or width not in r["widths"]:
        return "عرض را از فهرست انتخاب کنید."
    if length is None:
        return "طول را به متر بنویسید؛ مثل ۲٫۳۰"
    lo = min_length(r, width)
    if length < lo:
        return f"کمترین طول برای عرض {fmt(width)} متر، {fmt(lo)} متر است."
    if length > r["max_length"]:
        return f"بیشترین طول {fmt(r['max_length'])} متر است؛ برای طول بیشتر با ما تماس بگیرید."
    if length != length.quantize(Decimal("0.01")):
        return "طول را تا سانتی‌متر بنویسید (دو رقم اعشار)."
    return ""


def area(width, length):
    return (Decimal(width) * Decimal(length)).quantize(Decimal("0.0001"))


def price(per_m2, width, length, step=100_000):
    """قیمت یک تخته: عرض × طول × قیمت هر متر مربع، رو به بالا گرد."""
    raw = Decimal(per_m2 or 0) * area(width, length)
    if not step:
        return int(raw.quantize(Decimal(1)))
    return int(math.ceil(float(raw / Decimal(step)) - 1e-9)) * int(step)


def fmt(d):
    """Decimal ← «۰٫۵»، «۱۵٫۴۵»، «۲»"""
    from core.templatetags.fa import fa_num

    s = f"{Decimal(d):.2f}".rstrip("0").rstrip(".")
    return fa_num(s.replace(".", "٫"))


def label(width, length):
    return f"عرض {fmt(width)} × طول {fmt(length)} متر ({fmt(area(width, length))} متر مربع)"


def key(variation_id, width, length):
    """کلید سبد: «۱۲۳@0.50x15.45»"""
    return f"{variation_id}@{Decimal(width):.2f}x{Decimal(length):.2f}"


def parse_key(k):
    """(شناسهٔ تنوع، عرض، طول) — برای کلید معمولی عرض و طول None است."""
    k = str(k)
    m = re.match(r"^(\d+)@([\d.]+)x([\d.]+)$", k)
    if m:
        return int(m.group(1)), Decimal(m.group(2)), Decimal(m.group(3))
    return (int(k), None, None) if k.isdigit() else (None, None, None)


def payload(r):
    """برای ماشین‌حساب صفحهٔ فرش (JSON)."""
    return {"widths": [float(w) for w in r["widths"]], "min_narrow": float(r["min_narrow"]), "min_wide": float(r["min_wide"]),
            "max": float(r["max_length"]), "round": r["round"], "price": r["price"]}
