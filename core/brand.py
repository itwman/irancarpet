"""نام و دامنهٔ برند سایت — برای اجرای همین کد روی چند سایت (ایران کارپت، فرشستان و...).

نام برند از «تنظیمات سایت» در پنل خوانده می‌شود (فیلد brand_name) و دامنه از SITE_URL.
روی ایران کارپت مقدار پیش‌فرض دقیقاً «ایران کارپت» و «irancarpet.net» است؛ پس خروجی هیچ صفحه‌ای عوض نمی‌شود.
"""
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache

DEFAULT_BRAND = "ایران کارپت"
_NAME_RE = re.compile(r"ایران[ \u200c]?کارپت")


def name():
    """نام کوتاه برند، مثل «ایران کارپت» یا «فرشستان»."""
    v = cache.get("brand_name")
    if v is None:
        try:
            from .models import SiteSettings

            v = (SiteSettings.objects.filter(pk=1).values_list("brand_name", flat=True).first() or "").strip()
        except Exception:  # noqa: BLE001 — پیش از migrate یا در آزمون‌ها
            v = ""
        v = v or DEFAULT_BRAND
        cache.set("brand_name", v, 300)
    return v


def domain():
    """دامنهٔ اصلی سایت بدون www، مثل irancarpet.net"""
    host = urlsplit(settings.SITE_URL).hostname or ""
    return host[4:] if host.startswith("www.") else host


def fix(text):
    """«ایران کارپت» و irancarpet.net در متن‌های ثابت را با نام و دامنهٔ همین سایت عوض می‌کند (روی ایران کارپت بی‌اثر)."""
    if not text:
        return text
    n, d = name(), domain()
    if n != DEFAULT_BRAND:
        text = _NAME_RE.sub(n, text)
    if d and d != "irancarpet.net":
        text = text.replace("irancarpet.net", d)
    return text


def is_main():
    """همین سایت ایران کارپت است (یا نسخهٔ آزمایشی آن)؟ روی فرشستان و هر سایت دیگر False."""
    d = domain()
    return not d or d == "irancarpet.net" or d.endswith(".irancarpet.net") or d in ("localhost", "127.0.0.1", "testserver")


# نوع پاسخ‌هایی که نگهبان برند بازبینی می‌کند (صفحه، JSON اپ، نقشهٔ سایت، خوراک، llms.txt)
_TEXT_TYPES = ("text/", "application/json", "application/xml", "application/rss+xml", "application/atom+xml",
               "application/ld+json", "application/manifest+json")
# پنل مدیریت و خوراک همگام‌سازی نام ایران کارپت را لازم دارند (منبع کاتالوگ)
_SKIP_PATHS = ("/panel/", "/admin/", "/api/mirror/")


class BrandGuardMiddleware:
    """فرشستان و هر سایت دیگری روی همین کد: هیچ «ایران کارپت» یا irancarpet.net به بازدیدکننده نمی‌رسد.

    تور ایمنی آخر است؛ ریشه‌ها (متن‌های دیتابیس) را دستور brand_clean پاک می‌کند. روی ایران کارپت هیچ کاری نمی‌کند."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if is_main() or request.path.startswith(_SKIP_PATHS) or getattr(response, "streaming", False):
            return response
        ctype = (response.get("Content-Type") or "").lower()
        if not ctype.startswith(_TEXT_TYPES) or response.has_header("Content-Disposition"):
            return response
        charset = getattr(response, "charset", None) or "utf-8"
        try:
            body = response.content.decode(charset)
        except (UnicodeDecodeError, LookupError):
            return response
        if "ایران" not in body and "irancarpet" not in body and "\\u0627\\u06cc\\u0631\\u0627\\u0646" not in body:
            return response
        fixed = fix(body)
        if "\\u0627\\u06cc\\u0631\\u0627\\u0646" in fixed:   # JSON با ensure_ascii
            import json

            n = json.dumps(name())[1:-1]
            for old in ("ایران کارپت", "ایران\u200cکارپت"):
                fixed = fixed.replace(json.dumps(old)[1:-1], n)
        if fixed != body:
            response.content = fixed.encode(charset)
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        return response


def clear():
    cache.delete_many(["brand_name", "features_off"])
