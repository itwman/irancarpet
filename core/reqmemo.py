"""یادداشت کوتاه‌عمر در طول یک درخواست GET: تنظیمات تک‌ردیفی (load) و فهرست‌های ثابت فقط یک بار از دیتابیس خوانده می‌شوند.

صفحهٔ محصول تنظیمات فروشگاه/قیمت/سایت را از چند جای مختلف می‌خواند؛ بی این یادداشت هر بار یک پرس‌وجو بود.
فقط در درخواست‌های GET/HEAD فعال است (فرم‌های پنل که تنظیمات را تغییر می‌دهند POST‌اند) و بیرون از درخواست
(فرمان‌ها، کارهای زمان‌بندی‌شده) کاری نمی‌کند.
"""
from contextvars import ContextVar

_memo = ContextVar("reqmemo", default=None)


def memo(key, fn):
    d = _memo.get()
    if d is None:
        return fn()
    if key not in d:
        d[key] = fn()
    return d[key]


def load_singleton(cls):
    return memo(f"load:{cls._meta.label}", lambda: cls.objects.get_or_create(pk=1)[0])


class RequestMemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in ("GET", "HEAD"):
            return self.get_response(request)
        token = _memo.set({})
        try:
            return self.get_response(request)
        finally:
            _memo.reset(token)
