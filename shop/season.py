"""فصل شلوغ و توقف سفارش (تاریخ‌های شمسی هر سال، از «تنظیمات ← فروش و ارسال»).

- شلوغی (پیش‌فرض اول دی تا پایان بهمن): فقط اطلاعیه؛ آماده شدن فرش بیشتر از معمول طول می‌کشد.
- توقف سفارش (پیش‌فرض اول اسفند تا ۱۵ فروردین): فرش‌هایی که باید بافته شوند سفارش گرفته نمی‌شوند؛
  فرصت‌های ویژه (آماده در انبار) و کالای فروشندگان مارکت‌پلیس همچنان فروخته می‌شوند.
"""
import re

from django.utils import timezone


def parse_md(text):
    m = re.match(r"^\s*(\d{1,2})\s*[-/]\s*(\d{1,2})\s*$", (text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    return (int(m.group(1)), int(m.group(2))) if m else None


def today_md(now=None):
    import jdatetime

    j = jdatetime.date.fromgregorian(date=timezone.localtime(now or timezone.now()).date())
    return j.month, j.day


def in_window(md, start, end):
    if not start or not end:
        return False
    return start <= md <= end if start <= end else (md >= start or md <= end)  # بازه‌ای که از سال می‌گذرد (اسفند تا فروردین)


def state(now=None, shop=None):
    """{"busy": پیام یا ""، "paused": پیام یا ""}"""
    from .models import ShopSettings

    s = shop or ShopSettings.load()
    md = today_md(now)
    return {
        "busy": s.busy_message if s.busy_enabled and in_window(md, parse_md(s.busy_from), parse_md(s.busy_to)) else "",
        "paused": s.pause_message if s.pause_enabled and in_window(md, parse_md(s.pause_from), parse_md(s.pause_to)) else "",
    }


def blocked_lines(lines, now=None, shop=None):
    """سطرهای سبد که در زمان توقف سفارش قابل خرید نیستند (فرش‌هایی که باید بافته شوند)."""
    if not state(now, shop)["paused"]:
        return []
    return [ln for ln in lines if not getattr(ln, "offer", None) and not getattr(ln.product, "seller_id", None)]


def pause_error(lines, now=None, shop=None):
    bad = blocked_lines(lines, now, shop)
    if not bad:
        return ""
    msg = state(now, shop)["paused"]
    return f"{msg} این فرش‌ها را از سبد بردارید: " + "، ".join(ln.product.title[:40] for ln in bad[:3])
