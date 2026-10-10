"""ثبت بازدید و رویدادها، منبع ورود، و کلیک پیوند شخصی کمپین پیامکی.

کوکی‌ها (همه httponly، بدون اطلاعات شخصی):
  icv  شناسهٔ تصادفی مرورگر (برای شمردن بازدیدکنندهٔ یکتا)، ۴۰۰ روز
  ics  منبع نشست جاری، ۳۰ دقیقه (با هر بازدید تمدید می‌شود)
  ica  آخرین منبع غیرمستقیم، ۳۰ روز (برای نسبت دادن سفارش)
  icc  کلیک پیوند شخصی کمپین پیامکی، ۷ روز
"""
import json
import logging
import secrets
import threading
import time
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .sources import classify, utm_from

log = logging.getLogger(__name__)
SALT = "ic-stats"
SESSION_SECONDS = 30 * 60
ATTR_DAYS = 30
CLICK_DAYS = 7
SKIP = ("/panel/", "/api/", "/static/", "/media/", "/wp-content/", "/app-img/", "/pay/", "/t/", "/s/", "/robots.txt", "/sitemap")
MAX_PER_MIN = 60      # هر مرورگر در هر دقیقه (بیشتر از این ربات است)
MAX_PER_MIN_IP = 600  # هر نشانی اینترنتی (کاربران موبایل اپراتورها نشانی مشترک دارند)

_RL = {"min": 0, "seen": {}}
_RL_LOCK = threading.Lock()


def _limited(key, limit=MAX_PER_MIN):
    now = int(time.time() // 60)
    with _RL_LOCK:
        if _RL["min"] != now:
            _RL["min"], _RL["seen"] = now, {}
        n = _RL["seen"].get(key, 0) + 1
        _RL["seen"][key] = n
    return n > limit


def _ip(request):
    return (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()


def is_bot(request):
    from affiliate.track import is_bot as _b

    return _b(request)


def device_of(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    if "iPad" in ua or "Tablet" in ua or ("Android" in ua and "Mobile" not in ua):
        return "t"
    if "Mobi" in ua or "iPhone" in ua or "Android" in ua:
        return "m"
    return "d"


def own_hosts():
    hosts = {(urlsplit(settings.SITE_URL).hostname or "").lower()}
    hosts |= {h.lower() for h in getattr(settings, "ALLOWED_HOSTS", []) if h and not h.startswith(".") and h != "*"}
    try:
        from affiliate.track import short_hosts

        hosts |= set(short_hosts())
    except Exception:  # noqa: BLE001
        pass
    return {h[4:] if h.startswith("www.") else h for h in hosts if h}


def _read(request, name, max_age):
    raw = request.COOKIES.get(name)
    if not raw:
        return None
    try:
        return signing.loads(raw, salt=SALT, max_age=max_age)
    except Exception:  # noqa: BLE001
        return None


def _set(response, name, value, max_age):
    response.set_cookie(name, signing.dumps(value, salt=SALT, compress=True), max_age=max_age, httponly=True,
                        secure=not settings.DEBUG, samesite="Lax")


def _src(d):
    return {"s": d.get("s") or "direct", "n": d.get("n") or "", "m": d.get("m") or "", "u": d.get("u") or "",
            "c": d.get("c"), "l": d.get("l")}


def _excluded(request):
    user = getattr(request, "user", None)
    return bool(user is not None and user.is_authenticated and user.is_staff)


# ------------------------------------------------------------------ کلیک پیوند شخصی کمپین (?sl=)
class CampaignClickMiddleware:
    """?sl=کد پیوند شخصی: کلیک انسانی ثبت و کوکی کمپین گذاشته می‌شود، بعد همان صفحه بدون sl باز می‌شود."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get("sl") if request.method == "GET" else None
        if code and not request.path.startswith(SKIP):
            return self.handle(request, code)
        return self.get_response(request)

    def handle(self, request, code):
        from crm.models import ShortLink

        q = request.GET.copy()
        q.pop("sl", None)
        resp = HttpResponseRedirect(request.path + ("?" + q.urlencode() if q else ""))
        resp["X-Robots-Tag"] = "noindex"
        link = ShortLink.objects.filter(code=(code or "").strip().lower()[:12], campaign__isnull=False).first()
        if link is None or is_bot(request) or _excluded(request):
            return resp
        now = timezone.now()
        if not _limited("sl:" + _ip(request), MAX_PER_MIN_IP):
            upd = {"clicks": link.clicks + 1}
            if not link.first_click_at:
                upd["first_click_at"] = now
            ShortLink.objects.filter(pk=link.pk).update(**upd)
        _set(resp, "icc", {"c": link.campaign_id, "l": link.pk, "t": int(time.time())}, CLICK_DAYS * 86400)
        return resp


# ------------------------------------------------------------------ نشست و منبع
def resolve_source(request, page_url="", referrer="", start_session=True):
    """(منبع نشست، نشست تازه است؟، منبع برای نسبت دادن سفارش)"""
    sess = _read(request, "ics", SESSION_SECONDS)
    query = urlsplit(page_url).query if page_url else ""
    utm = utm_from(query)
    click = _read(request, "icc", CLICK_DAYS * 86400)
    fresh_click = bool(click and time.time() - int(click.get("t", 0)) < SESSION_SECONDS)
    new_src = None
    if utm["source"]:
        new_src = {"s": "utm", "n": utm["source"], "m": utm["medium"], "u": utm["campaign"]}
    elif fresh_click and not (sess and sess.get("s") == "sms" and sess.get("l") == click.get("l")):
        new_src = {"s": "sms", "n": "پیامک", "c": click.get("c"), "l": click.get("l")}
    if new_src is None and sess is not None:
        return _src(sess), False, None
    if new_src is None:
        if not start_session:
            return _src({}), False, None
        kind, name = classify(referrer, own_hosts())
        if kind == "internal":
            kind, name = "direct", ""
        if kind == "direct":
            try:
                from affiliate.track import read_cookie

                a, ts = read_cookie(request)
                if a and ts and time.time() - ts < SESSION_SECONDS:
                    kind, name = "affiliate", a.code
            except Exception:  # noqa: BLE001
                pass
        new_src = {"s": kind, "n": name}
    if new_src["s"] != "sms" and click:  # کلیک کمپین در ۷ روز گذشته: کمپین با سفارش همراه می‌ماند
        new_src.setdefault("c", click.get("c"))
        new_src.setdefault("l", click.get("l"))
    return _src(new_src), True, _src(new_src)


def attribution(request):
    """منبع برای سفارش: منبع نشست اگر مستقیم نیست، وگرنه آخرین منبع غیرمستقیم ۳۰ روز گذشته."""
    sess = _read(request, "ics", SESSION_SECONDS) or {}
    if sess and sess.get("s") not in (None, "", "direct"):
        out = _src(sess)
    else:
        out = _src(_read(request, "ica", ATTR_DAYS * 86400) or sess or {})
    click = _read(request, "icc", CLICK_DAYS * 86400)
    if click and not out.get("c"):
        out["c"], out["l"] = click.get("c"), click.get("l")
    return out


def _visitor(request):
    v = request.COOKIES.get("icv") or ""
    if len(v) == 16 and v.isalnum():
        return v, False
    return secrets.token_hex(8), True


def record(request, kind, path, product_id=None, page_url="", referrer="", response=None):
    """یک Hit می‌سازد و کوکی‌ها را روی response می‌گذارد."""
    from .models import Hit

    visitor, new = _visitor(request)
    src, entry, attr = resolve_source(request, page_url, referrer, start_session=(kind == Hit.Kind.VIEW))
    now = timezone.now()
    Hit.objects.create(at=now, day=timezone.localdate(now), kind=kind, path=path[:255], product_id=product_id,
                       visitor=visitor, entry=entry and kind == Hit.Kind.VIEW, new=new, src=src["s"][:10],
                       src_name=(src["n"] or "")[:60], medium=(src["m"] or "")[:40], utm_campaign=(src["u"] or "")[:80],
                       campaign_id=src.get("c") or None, link_id=src.get("l") or None, device=device_of(request))
    if response is not None:
        if new:
            response.set_cookie("icv", visitor, max_age=400 * 86400, httponly=True, secure=not settings.DEBUG, samesite="Lax")
        _set(response, "ics", src, SESSION_SECONDS)
        if attr and attr["s"] != "direct":
            _set(response, "ica", attr, ATTR_DAYS * 86400)
    return src


def _same_origin(request):
    origin = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER") or ""
    host = (urlsplit(origin).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    req_host = request.get_host().split(":")[0].lower()
    req_host = req_host[4:] if req_host.startswith("www.") else req_host
    return bool(host) and host == req_host


@csrf_exempt
@require_POST
def beacon(request):
    """POST /t/ با {p: مسیر و پرسمان، r: ارجاع‌دهنده، pid: شناسهٔ فرش}؛ پاسخ ۲۰۴."""
    resp = HttpResponse(status=204)
    if len(request.body or b"") > 2048 or not _same_origin(request) or is_bot(request) or _excluded(request):
        return resp
    v = request.COOKIES.get("icv") or ""
    if (v and _limited("v:" + v[:16])) or _limited("b:" + _ip(request), MAX_PER_MIN_IP):
        return resp
    try:
        d = json.loads(request.body.decode("utf-8", "ignore") or "{}")
    except ValueError:
        return resp
    page = str(d.get("p") or "")[:600]
    path = unquote(urlsplit(page).path or "/")
    if not path.startswith("/") or path.startswith(SKIP):
        return resp
    try:
        pid = int(d.get("pid") or 0) or None
    except (TypeError, ValueError):
        pid = None
    try:
        record(request, "v", path, pid, page_url=page, referrer=str(d.get("r") or "")[:500], response=resp)
    except Exception:  # noqa: BLE001
        log.exception("stats beacon")
    return resp


def event(request, kind, product_id=None, path=""):
    """رویداد سمت سرور (افزودن به سبد، ثبت سفارش)؛ هرگز خطا به کاربر نمی‌رساند."""
    if request is None or is_bot(request) or _excluded(request):
        return None
    try:
        return record(request, kind, path or request.path, product_id)
    except Exception:  # noqa: BLE001
        log.exception("stats event")
        return None


def attach_order(request, order, source=""):
    """منبع ورود سفارش (برای گزارش فروش هر منبع و هر کمپین)."""
    from shop.models import Order

    try:
        if source == "app":
            a = {"s": "app", "n": "اپلیکیشن", "m": "", "u": "", "c": None}
        else:
            a = attribution(request)
        Order.objects.filter(pk=order.pk).update(src=a["s"][:10], src_name=(a["n"] or "")[:60],
                                                 utm_campaign=(a["u"] or "")[:80], sms_campaign_id=a.get("c") or None)
        if source != "app":
            event(request, "o", path="/checkout/")
    except Exception:  # noqa: BLE001
        log.exception("stats order")
