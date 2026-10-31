"""اتصال به Shop API ترب: وضعیت فروشگاه و محصولات همان‌طور که ترب می‌بیند، و مقایسه با سایت.

مستند: https://api.torob.com/shop-api/v1/ — توکن در هدر Authorization: Bearer؛ حداکثر ۵ درخواست در ثانیه.
- sync(): وضعیت فروشگاه (/shop/) + همهٔ محصولات (/products/، صفحه‌بندی cursor) یا فقط تغییرهای تازه (updated_since).
- هر محصول ترب با فرش سایت جفت می‌شود (از روی نشانی صفحه، بعد شناسه)؛ قیمت و موجودی‌ای که باید باشد
  با همان قاعدهٔ فید ترب حساب می‌شود و ناهمسانی‌ها (قیمت، موجودی، بی‌جفت، خارج از دسترس) علامت می‌خورند.
- برای محصولاتی که ترب به صفحه‌شان دسترسی ندارد، پاسخ امروز سایت (۲۰۰، ۳۰۱ یا ۴۰۴) هم بررسی می‌شود.
- activate()/deactivate(): فعال و غیرفعال کردن محصولات در ترب.
اطلاعات کلیک‌ها (که آی‌پی کاربران را دارد) و انتقال شارژ عمداً ساخته نشده‌اند.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import TorobProduct, TorobSettings

log = logging.getLogger(__name__)
BASE = "https://api.torob.com/shop-api/v1"
PAGE_SIZE = 500
MAX_PAGES = 60            # حداکثر ۳۰ هزار محصول در یک همگام‌سازی
PRICE_TOLERANCE = 0.01    # اختلاف کمتر از ۱٪ (گرد شدن) ناهمسانی نیست
PROBE_LIMIT = 150         # حداکثر نشانی خارج از دسترس که در هر بار پاسخ سایت برایشان بررسی می‌شود

STATUS_LABELS = {
    "page_deleted_permanent_content": "برای همیشه حذف شده (محتوا)",
    "page_deleted_temporary_content": "موقتاً حذف شده (محتوا)",
    "page_deleted_temporary_technical": "موقتاً حذف شده (فنی)",
    "page_not_active": "غیرفعال",
    "page_not_accessible": "خارج از دسترس",
    "in_progress_add": "در حال افزوده شدن",
    "page_not_available": "ناموجود",
    "base_not_confirmed": "دسته در انتظار تأیید",
    "price_not_valid": "قیمت نامعتبر",
    "base_not_merged": "ادغام نشده",
    "base_image_rejected": "تصویر رد شده",
    "ok": "بدون مشکل",
}
SHOP_STATUS = {"active": "فعال", "blocked": "غیرفعال (دلیل در پنل ترب)", "crawler_check": "در انتظار بررسی فنی سایت",
               "crawler_active": "در حال به‌روز شدن قیمت‌ها"}
PROBLEMS = {"price": "قیمت ناهمسان", "stock": "موجودی ناهمسان", "removed": "حذف‌شده در ترب", "404": "صفحه در دسترس نیست",
            "temp": "خطای موقت دسترسی ترب", "missing": "در سایت پیدا نشد"}
DELETED = ("page_deleted_permanent_content", "page_deleted_temporary_content", "page_deleted_temporary_technical")


class TorobError(Exception):
    pass


def _token(s=None):
    return ((s or TorobSettings.load()).shop_api_token or "").strip()


def _call(method, path, token, params=None, body=None, url=None):
    if not url:
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                time.sleep(0.25)  # سقف ۵ درخواست در ثانیه
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 + attempt * 2)
                continue
            detail = ""
            try:
                detail = json.loads(e.read().decode() or "{}").get("detail", "")
            except Exception:  # noqa: BLE001
                pass
            if e.code == 401:
                raise TorobError("توکن ترب نامعتبر است یا باطل شده؛ در پنل ترب توکن تازه بسازید و اینجا بگذارید.") from e
            raise TorobError(f"خطای ترب ({e.code}) {detail}".strip()) from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise TorobError(f"اتصال به ترب برقرار نشد: {e}") from e
    raise TorobError("ترب پاسخ نداد.")


# ------------------------------------------------------------------ جفت کردن با فرش سایت
class _Matcher:
    """جفت کردن محصول ترب با فرش سایت بدون یک پرس‌وجو برای هر ردیف."""

    def __init__(self):
        from catalog.models import Product

        rows = list(Product.objects.exclude(status="trash").values_list("pk", "slug", "wp_id"))
        self.by_slug = {slug: pk for pk, slug, _ in rows if slug}
        self.by_wp = {wp: pk for pk, _, wp in rows if wp}
        self.pks = {pk for pk, _, _ in rows}

    def __call__(self, item):
        import re

        from . import feed

        url = item.get("page_url") or ""
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.unquote(parts.path or "")
        m = re.match(r"^/product/([^/]+)/?$", path)
        if m and m.group(1) in self.by_slug:
            return self.by_slug[m.group(1)]
        q = dict(urllib.parse.parse_qsl(parts.query))
        if q.get("p", "").isdigit() and int(q["p"]) in self.by_wp:
            return self.by_wp[int(q["p"])]
        head = str(item.get("product_id") or "").split("_")[0]
        if head.isdigit():
            u = int(head)
            if u >= feed.NEW_ID_OFFSET and u - feed.NEW_ID_OFFSET in self.pks:
                return u - feed.NEW_ID_OFFSET
            if u in self.pks:  # ترب فرش‌ها را با شناسهٔ سایت می‌شناسد
                return u
            if u in self.by_wp:
                return self.by_wp[u]
        return None


def _expected(p, s, live_ids):
    """(قیمت، موجود) همان‌طور که فید ترب برای این فرش می‌گوید."""
    from . import feed

    if p.pk not in live_ids:
        return 0, False
    current, _old = feed._price(p)
    if not current:
        return 0, False
    return feed.adjust(current, s), bool(p.is_purchasable)


def _problem(row):
    """دستهٔ مشکل: حذف‌شده و خارج از دسترس اول (قیمت و موجودی‌شان در ترب کهنه است)، بعد بی‌جفت، بعد ناهمسانی."""
    st = row.statuses or []
    if any(x in DELETED for x in st):
        return "removed"
    if "page_not_active" in st:
        return ""
    if "page_not_accessible" in st:
        return "temp" if (row.error_title or "").startswith("-1:") else "404"
    if row.product_id is None:
        return "missing"
    if row.availability != row.site_available:
        return "stock"
    if row.availability and row.site_price and row.price and abs(row.price - row.site_price) > row.site_price * PRICE_TOLERANCE:
        return "price"
    return ""


def _probe(paths):
    """پاسخ امروز سایت برای نشانی‌هایی که ترب به آن‌ها دسترسی ندارد: {path: (کد، مقصد)}."""
    from django.test import Client

    host = urllib.parse.urlsplit(settings.SITE_URL).netloc
    c = Client(HTTP_HOST=host)
    out = {}
    for path in paths:
        try:
            r = c.get(path, secure=settings.SITE_URL.startswith("https"))
            out[path] = (r.status_code, r.get("Location", "") if r.status_code in (301, 302) else "")
        except Exception:  # noqa: BLE001
            log.exception("torob probe %s", path)
            out[path] = (0, "")
    return out


def _aware(v):
    from datetime import timezone as dtz

    d = parse_datetime(v or "") if v else None
    return timezone.make_aware(d, dtz.utc) if d and timezone.is_naive(d) else d


# ------------------------------------------------------------------ همگام‌سازی
def sync(full=False, out=None):
    """وضعیت فروشگاه و محصولات را از ترب می‌گیرد و با سایت مقایسه می‌کند. خروجی: خلاصه برای پیام پنل."""
    from catalog.models import Product

    from . import feed

    s = TorobSettings.load()
    token = _token(s)
    if not token:
        raise TorobError("توکن Shop API ترب در «تنظیمات ← فید ترب و ایمالز» گذاشته نشده.")
    started = timezone.now()
    state = dict(s.shop_state or {})
    try:
        shop = _call("GET", "/shop/", token)
        state.update({"name": shop.get("name", ""), "domain": shop.get("domain", ""), "status": shop.get("shop_status", ""),
                      "summary": shop.get("product_summary") or {}, "shop_at": started.isoformat(), "error": ""})
        body = {}
        since = s.products_synced_at
        if since and not full:
            body["updated_since"] = (since - timedelta(minutes=15)).isoformat()
        url, pages = None, 0
        live_ids = set(feed.rows(s))
        rows = []
        while pages < MAX_PAGES:
            data = _call("POST", "/products/", token, params={"page_size": PAGE_SIZE}, body=body, url=url)
            rows += data.get("results") or []
            pages += 1
            url = data.get("next")
            if not url:
                break
        seen = len(rows)
        match = _Matcher()
        existing = {o.torob_id: o for o in TorobProduct.objects.filter(torob_id__in=[str(i.get("product_id") or "")[:60] for i in rows])}
        new, upd = [], []
        for item in rows:
            tid = str(item.get("product_id") or "")[:60]
            if not tid:
                continue
            statuses = item.get("statuses") or []
            obj = existing.get(tid) or TorobProduct(torob_id=tid)
            obj.page_url = (item.get("page_url") or "")[:1000]
            obj.statuses = statuses
            obj.status = statuses[0] if statuses else "ok"
            obj.price = max(0, int(item.get("price") or 0))
            obj.availability = bool(item.get("availability"))
            obj.error_title = (item.get("error_title") or "")[:200]
            obj.torob_updated_at = _aware(item.get("updated_at"))
            obj.product_id = match(item)
            (upd if obj.pk else new).append(obj)
            existing[tid] = obj
        fields = ["page_url", "statuses", "status", "price", "availability", "error_title", "torob_updated_at", "product"]
        with transaction.atomic():
            TorobProduct.objects.bulk_create(new, batch_size=500)
            TorobProduct.objects.bulk_update(upd, fields, batch_size=500)
        # قیمت و موجودی‌ای که باید باشد، و دستهٔ مشکل: برای همهٔ ردیف‌ها (سایت ممکن است از دفعهٔ قبل عوض شده باشد)
        all_rows = list(TorobProduct.objects.all())
        need = {o.product_id for o in all_rows if o.product_id}
        by = {p.pk: p for p in Product.objects.filter(pk__in=need).select_related("album").prefetch_related("variations")}
        changed = []
        for o in all_rows:
            p = by.get(o.product_id)
            price, avail = _expected(p, s, live_ids) if p else (0, False)
            o.site_price, o.site_available = price, avail
            prob = _problem(o)
            o.problem = prob
            changed.append(o)
        with transaction.atomic():
            TorobProduct.objects.bulk_update(changed, ["site_price", "site_available", "problem"], batch_size=500)
        # نشانی‌های خارج از دسترس: سایت امروز چه جوابی می‌دهد؟
        bad = (list(TorobProduct.objects.filter(problem="404").order_by("-torob_updated_at")[:PROBE_LIMIT])
               + list(TorobProduct.objects.filter(problem="removed").exclude(page_url="").order_by("-torob_updated_at")[:PROBE_LIMIT]))
        paths = {o.pk: urllib.parse.urlsplit(o.page_url).path or "/" for o in bad if o.page_url}
        res = _probe(set(paths.values()))
        for o in bad:
            code, loc = res.get(paths.get(o.pk), (0, ""))
            TorobProduct.objects.filter(pk=o.pk).update(site_status=code, site_location=loc[:1000])
        state["counts"] = counts()
        state["synced_rows"] = seen
        s.products_synced_at = started
    except TorobError as e:
        state["error"] = str(e)
        TorobSettings.objects.filter(pk=s.pk).update(shop_state=state)
        raise
    TorobSettings.objects.filter(pk=s.pk).update(shop_state=state, products_synced_at=s.products_synced_at)
    if out:
        out(f"ترب: {seen} محصول خوانده شد.")
    return state


def counts():
    from django.db.models import Count

    by_problem = dict(TorobProduct.objects.exclude(problem="").values_list("problem").annotate(n=Count("id")))
    return {"total": TorobProduct.objects.count(), **{k: by_problem.get(k, 0) for k in PROBLEMS}}


def due():
    """همگام‌سازی روزانه (از کارهای دوره‌ای): اگر توکن هست و از آخرین بار بیش از ۲۰ ساعت گذشته."""
    s = TorobSettings.load()
    if not _token(s):
        return False
    return not s.products_synced_at or timezone.now() - s.products_synced_at > timedelta(hours=20)


def set_active(torob_ids, active):
    """فعال/غیرفعال کردن در ترب؛ خروجی: تعداد پیدا‌شده."""
    token = _token()
    if not token:
        raise TorobError("توکن Shop API ترب گذاشته نشده.")
    ids = [str(x) for x in torob_ids][:5000]
    if not ids:
        return 0
    data = _call("POST", "/products/activate/" if active else "/products/deactivate/", token, body={"product_ids": ids})
    found = [r["product_id"] for r in data.get("results") or [] if r.get("found")]
    # وضعیت تازهٔ همین محصولات
    fresh = _call("POST", "/products/", token, params={"page_size": PAGE_SIZE}, body={"product_ids": found[:500]}) if found else {}
    for item in fresh.get("results") or []:
        st = item.get("statuses") or []
        TorobProduct.objects.filter(torob_id=str(item.get("product_id"))).update(statuses=st, status=st[0] if st else "ok")
    return len(found)


RUN_KEY = "torob_sync_running"


def start_background(full=False):
    """همگام‌سازی در پس‌زمینه (خواندن کامل چند دقیقه طول می‌کشد و از سقف زمان یک درخواست وب بیشتر است)."""
    import subprocess
    import sys

    from django.core.cache import cache

    if cache.get(RUN_KEY):
        return False
    cache.set(RUN_KEY, timezone.now().isoformat(), 20 * 60)
    cmd = [sys.executable, str(settings.BASE_DIR / "manage.py"), "torob_sync"] + (["--full"] if full else [])
    subprocess.Popen(cmd, cwd=str(settings.BASE_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return True


def running():
    from django.core.cache import cache

    return bool(cache.get(RUN_KEY))
