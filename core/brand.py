"""نام و دامنهٔ برند سایت — برای اجرای همین کد روی چند سایت (ایران کارپت، فرشستان و...).

نام برند از «تنظیمات سایت» در پنل خوانده می‌شود (فیلد brand_name) و دامنه از SITE_URL.
روی ایران کارپت مقدار پیش‌فرض دقیقاً «ایران کارپت» و «irancarpet.net» است؛ پس خروجی هیچ صفحه‌ای عوض نمی‌شود.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache

DEFAULT_BRAND = "ایران کارپت"


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


def clear():
    cache.delete_many(["brand_name", "features_off"])
