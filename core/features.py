"""روشن/خاموش کردن بخش‌های اختیاری سایت (برای اجرای همین کد روی سایت‌های دیگر مثل فرشستان).

فهرست بخش‌های خاموش در «تنظیمات سایت ← بخش‌های خاموش» پنل است؛ نشانی‌های آن بخش‌ها ۴۰۴ می‌دهند.
روی ایران کارپت این فهرست خالی است و هیچ چیزی عوض نمی‌شود.
"""
from django.core.cache import cache
from django.http import Http404

FEATURES = {
    "affiliate": ("affiliate/", "my-account/affiliate/"),
    "market": ("sell/", "seller/", "vendor/"),
    "finder": ("farsh-yab/",),
    "farshplus": ("farshplus-gift/",),
    "app": ("api/app/v1/", "app-img/", "app/return/"),
    "torob": ("wp-json/torob/", "wp-json/emalls_ext/"),
    "manix": ("wp-json/wc/v3/",),
}


def disabled():
    v = cache.get("features_off")
    if v is None:
        try:
            from .models import SiteSettings

            raw = SiteSettings.objects.filter(pk=1).values_list("features_off", flat=True).first() or ""
        except Exception:  # noqa: BLE001
            raw = ""
        v = sorted({x.strip().lower() for x in raw.replace("،", ",").split(",") if x.strip()})
        cache.set("features_off", v, 300)
    return v


def is_on(name):
    return name not in disabled()


class FeatureGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        off = disabled()
        if off:
            path = request.path_info.lstrip("/")
            for name in off:
                if any(path.startswith(p) for p in FEATURES.get(name, ())):
                    raise Http404
        return self.get_response(request)
