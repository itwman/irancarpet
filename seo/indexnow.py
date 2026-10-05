"""IndexNow: خبر دادن فوری تغییر صفحه‌ها به Bing، Yandex و... (ChatGPT برای جستجو از Bing استفاده می‌کند).

نشانی‌ها در هر پروسه جمع می‌شوند و چند ثانیه بعد یک‌جا فرستاده می‌شوند تا تغییر گروهی قیمت‌ها
صدها درخواست جدا نسازد. هر نشانی تا ۳۰ دقیقه دوباره فرستاده نمی‌شود.
"""
import hashlib
import json
import logging
import threading
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

log = logging.getLogger(__name__)

ENDPOINT = "https://api.indexnow.org/indexnow"
DELAY = 20  # ثانیه
DEDUPE = 30 * 60
BATCH = 10_000

_pending = set()
_lock = threading.Lock()
_timer = None


def active():
    """فقط روی سایت اصلی (نه حالت توسعه، آزمایشی یا تست)."""
    if settings.DEBUG or getattr(settings, "STAGING", False) or getattr(settings, "TESTING", False):
        return False
    return settings.SITE_URL.startswith("https://")


def _abs(url):
    return url if url.startswith("http") else settings.SITE_URL + url


def queue(*urls):
    """نشانی‌ها (نسبی یا کامل) را برای ارسال در چند ثانیهٔ بعد صف کن."""
    global _timer
    urls = {_abs(u) for u in urls if u}
    if not urls or not active():
        return
    with _lock:
        _pending.update(urls)
        if _timer is None:
            _timer = threading.Timer(DELAY, flush)
            _timer.daemon = True
            _timer.start()


def flush():
    global _timer
    with _lock:
        urls, _timer = sorted(_pending), None
        _pending.clear()
    fresh = [u for u in urls if cache.add("inx:" + hashlib.md5(u.encode()).hexdigest(), 1, DEDUPE)]
    if fresh:
        try:
            submit(fresh)
        except Exception:  # noqa: BLE001 — ارسال نباید هیچ‌وقت سایت را از کار بیندازد
            log.exception("IndexNow")


# هر موتوری که IndexNow را بپذیرد، نشانی‌ها را با بقیه (Bing، Yandex، Naver، Seznam، Yep) هم به اشتراک می‌گذارد.
# api.indexnow.org مال مایکروسافت است و ممکن است درخواست سرورهای ایران را رد کند (403)؛ پس اگر نشد، بعدی‌ها امتحان می‌شوند.
ENDPOINTS = [
    ("IndexNow (Bing)", ENDPOINT),
    ("Yandex", "https://yandex.com/indexnow"),
    ("Naver", "https://searchadvisor.naver.com/indexnow"),
    ("Seznam", "https://search.seznam.cz/indexnow"),
]
CODES = {400: "درخواست نادرست", 403: "رد شد (403)", 422: "نشانی‌ها با دامنهٔ سایت نمی‌خوانند", 429: "درخواست زیاد؛ بعداً دوباره"}


def _post(url, body):
    """(کد، متن کوتاه پاسخ)"""
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "irancarpet.net"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        try:
            txt = e.read(400).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            txt = ""
        return e.code, " ".join(txt.split())[:120]
    except Exception as e:  # noqa: BLE001
        return 0, e.__class__.__name__


def submit(urls):
    """ارسال مستقیم؛ خروجی: (موفق؟، پیام)."""
    from .models import SeoSettings

    s = SeoSettings.load()
    if not s.indexnow_enabled:
        return False, "غیرفعال است"
    host = urlparse(settings.SITE_URL).netloc
    urls = [_abs(u) for u in urls]
    ok, msg, sent = True, "", 0
    endpoints = list(ENDPOINTS)
    for i in range(0, len(urls), BATCH):
        part = urls[i:i + BATCH]
        body = json.dumps({"host": host, "key": s.indexnow_key, "keyLocation": f"{settings.SITE_URL}/{s.indexnow_key}.txt",
                           "urlList": part}).encode()
        tried, accepted = [], False
        for name, url in list(endpoints):
            code, detail = _post(url, body)
            if code in (200, 202):
                sent += len(part)
                msg, accepted = f"پذیرفته شد از راه {name} (کد {code})", True
                endpoints = [(name, url)] + [e for e in endpoints if e[1] != url]  # دستهٔ بعد اول همین را امتحان کند
                break
            label = CODES.get(code, f"کد {code}") if code else f"اتصال برقرار نشد ({detail})"
            tried.append(f"{name}: {label}" + (f" «{detail}»" if code and detail else ""))
            if code in (400, 422):  # ایراد از خود درخواست است؛ موتور دیگر هم همین را می‌گوید
                break
        if not accepted:
            ok, msg = False, " | ".join(tried)
            break
    type(s).objects.filter(pk=s.pk).update(
        indexnow_last_at=timezone.now(), indexnow_last_status=f"{msg} — {sent} نشانی"[:300],
        indexnow_total=F("indexnow_total") + sent)
    log.info("IndexNow %s: %s", sent, msg)
    return ok, msg


def all_urls():
    """همهٔ نشانی‌های سایت‌مپ + صفحهٔ اول."""
    from .sitemaps import sections

    out = ["/"]
    for qs, _paged in sections().values():
        for obj in qs.iterator(chunk_size=500) if hasattr(qs, "iterator") else qs:
            try:
                out.append(obj.get_absolute_url())
            except Exception:  # noqa: BLE001
                continue
    return list(dict.fromkeys(out))
