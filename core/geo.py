"""خواندن طول و عرض جغرافیایی از متن یا پیوند نقشه (گوگل‌مپ، نشان، بلد)."""
import re
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import unquote

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
NUM = r"-?\d{1,3}\.\d+"


def _norm(text):
    return unquote(str(text or "")).translate(DIGITS).replace("،", ",").strip()


def coord(text):
    """«۳۳٫۹۹۵۶۰۸۹» یا «33.9956089» ← Decimal با ۶ رقم اعشار (حدود ۱۰ سانتی‌متر)."""
    t = _norm(text)
    if not t:
        return None
    m = re.fullmatch(r"\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*", t)
    if not m:
        raise ValueError(t)
    return Decimal(m.group(1)).quantize(Decimal("0.000001"), ROUND_HALF_UP)


def pair(text):
    """«33.99, 51.45» در یک خانه ← (عرض، طول)"""
    m = re.fullmatch(rf"\s*({NUM})\s*[, ]\s*({NUM})\s*", _norm(text))
    return (coord(m.group(1)), coord(m.group(2))) if m else None


def from_url(url):
    """مختصات محل از پیوند نقشه. در گوگل‌مپ آخرین «!3d…!4d…» همان محل انتخاب‌شده است (عدد بعد از @ فقط مرکز نقشه است)."""
    u = _norm(url)
    if not u:
        return None
    hits = re.findall(rf"!3d({NUM})!4d({NUM})", u)
    if hits:
        return coord(hits[-1][0]), coord(hits[-1][1])
    for pat in (rf"[?&](?:q|query|ll|destination)=({NUM}),\s*({NUM})", rf"[?&]lat(?:itude)?=({NUM}).*?[?&](?:lng|lon|longitude)=({NUM})",
                rf"@({NUM}),({NUM})"):
        m = re.search(pat, u)
        if m:
            return coord(m.group(1)), coord(m.group(2))
    return None
