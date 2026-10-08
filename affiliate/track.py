"""ردیابی پیوند همکار: پیوند کوتاه (crpt.ir)، ?ref= در هر صفحه، کوکی ماندگار و ثبت سفارش به نام همکار."""
import hashlib
import logging
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone

from .models import Affiliate, AffiliateSettings, Click, Commission, CustomerRef, Link

log = logging.getLogger(__name__)
COOKIE = "icref"
SALT = "affiliate-ref"
SKIP = ("/panel/", "/api/", "/static/", "/wp-content/", "/app-img/", "/pay/", "/media/")
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|skype|discord|embedly|"
                  r"curl|wget|python|headless|lighthouse|pingdom|monitor", re.I)


def clear_cache():
    _HOSTS["at"] = 0.0
    cache.delete_many(["aff:tiers", "aff:settings"])
    cache.set("aff:ver", int(time.time() * 1000))


def conf():
    s = cache.get("aff:settings")
    if s is None:
        s = AffiliateSettings.load()
        cache.set("aff:settings", s, 300)
    return s


def by_code(code):
    """همکار فعال با این کد (یا None)."""
    code = (code or "").strip().lower()[:20]
    if not re.match(r"^[a-z0-9_]{3,20}$", code):
        return None
    key = f"aff:code:{cache.get('aff:ver', 0)}:{code}"
    pk = cache.get(key)
    if pk is None:
        a = Affiliate.objects.filter(code=code, status=Affiliate.Status.ACTIVE).only("pk").first()
        pk = a.pk if a else 0
        cache.set(key, pk, 300)
    return Affiliate.objects.filter(pk=pk).first() if pk else None


# ------------------------------------------------------------------ نشانی‌ها
def short_base(s=None):
    s = s or conf()
    dom = (s.short_domain or "").strip().strip("/")
    return f"https://{dom}" if dom else settings.SITE_URL


def general_link(a):
    base = short_base()
    return f"{base}/{a.code}" if base != settings.SITE_URL else f"{base}/?ref={a.code}"


def product_link(a, product):
    base = short_base()
    return f"{base}/{a.code}/{product.pk}" if base != settings.SITE_URL else f"{base}{product.get_absolute_url()}?ref={a.code}"


def page_link(a, link):
    base = short_base()
    return f"{base}/{a.code}/{link.slug}" if base != settings.SITE_URL else f"{base}{link.path}?ref={a.code}"


def local_path(url):
    """نشانی کامل یا مسیر سایت ← مسیر داخلی (یا None اگر از سایت دیگری است)."""
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith("/"):
        parts = urlsplit(url)
    else:
        if "://" not in url:
            url = "https://" + url
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        site = (urlsplit(settings.SITE_URL).hostname or "").lower()
        if host not in {site, "www." + site}:
            return None
    path = parts.path or "/"
    if path.startswith(SKIP) or path.startswith("/my-account") or path.startswith("/checkout"):
        return None
    q = [(k, v) for k, v in parse_qsl(parts.query) if k not in ("ref", "utm_source")]
    return (path + ("?" + urlencode(q) if q else ""))[:400]


# ------------------------------------------------------------------ دامنهٔ کوتاه
_HOSTS = {"at": 0.0, "hosts": set()}


def short_hosts():
    """دامنه‌های کوتاه (از تنظیمات سرور و پنل)؛ در حافظهٔ همان پردازه ۵ دقیقه نگه داشته می‌شود تا هر درخواست سراغ پایگاه داده نرود."""
    if time.time() - _HOSTS["at"] > 300:
        hosts = {h.lower() for h in getattr(settings, "SHORT_HOSTS", [])}
        try:
            dom = (conf().short_domain or "").strip().lower()
        except Exception:  # noqa: BLE001
            dom = ""
        if dom:
            hosts |= {dom, "www." + dom}
        _HOSTS.update(at=time.time(), hosts=hosts)
    return _HOSTS["hosts"]


def short_redirect(request):
    """crpt.ir/<کد> ← صفحهٔ اول؛ crpt.ir/<کد>/<شمارهٔ فرش> ← صفحهٔ فرش؛ crpt.ir/<کد>/x<شناسه> ← صفحهٔ دلخواه."""
    from catalog.models import Product

    site = settings.SITE_URL
    if request.path == "/robots.txt":
        return HttpResponse("User-agent: *\nAllow: /\n", content_type="text/plain")
    parts = [p for p in request.path.split("/") if p]
    if not parts:
        return HttpResponseRedirect(site + "/")
    a = by_code(parts[0])
    if a is None:
        return HttpResponseRedirect(site + "/")
    target = "/"
    if len(parts) > 1:
        x = parts[1]
        if x.isdigit():
            p = Product.objects.filter(pk=int(x)).only("slug").first()
            if p:
                target = p.get_absolute_url()
        elif x.startswith("x") and re.match(r"^x[0-9a-z]{1,10}$", x):
            link = Link.objects.filter(pk=int(x[1:], 36), affiliate=a).first()
            if link:
                target = link.path
    sep = "&" if "?" in target else "?"
    return HttpResponseRedirect(f"{site}{target}{sep}ref={a.code}")


# ------------------------------------------------------------------ کوکی
def read_cookie(request):
    """(همکار، زمان کلیک) از کوکی، اگر هنوز معتبر است."""
    raw = request.COOKIES.get(COOKIE)
    if not raw:
        return None, None
    try:
        val = signing.loads(raw, salt=SALT)
        code, ts = val["c"], int(val["t"])
    except Exception:  # noqa: BLE001
        return None, None
    if time.time() - ts > conf().attribution_days * 86400:
        return None, None
    a = by_code(code)
    return (a, ts) if a else (None, None)


def ref_from_request(request):
    a, ts = read_cookie(request)
    return {"affiliate": a, "ts": ts} if a else None


def _visitor(request):
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
    ua = request.META.get("HTTP_USER_AGENT", "")[:200]
    return hashlib.sha256(f"{ip}|{ua}|{settings.SECRET_KEY[:8]}".encode()).hexdigest()[:16]


def is_bot(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    return not ua or bool(BOTS.search(ua))


def record_click(request, a, path):
    from catalog.models import Product

    visitor = _visitor(request)
    key = f"aff:click:{a.pk}:{visitor}:{hashlib.md5(path.encode()).hexdigest()[:8]}"
    if not cache.add(key, 1, 1800):  # هر بازدیدکننده در نیم ساعت یک بار
        return
    product = None
    m = re.match(r"^/product/([^/]+)/", path)
    if m:
        from urllib.parse import unquote

        product = Product.objects.filter(slug=unquote(m.group(1))).only("pk").first()
    ref = request.META.get("HTTP_REFERER", "")
    host = re.sub(r"^https?://(www\.)?", "", ref).split("/")[0][:100]
    try:
        Click.objects.create(affiliate=a, product=product, path=path[:300], visitor=visitor, referer=host)
    except Exception:  # noqa: BLE001
        log.exception("affiliate click")


def bind_user(user, a, ts):
    """مشتری واردشده: همکار به حسابش هم وصل می‌شود (آخرین پیوند حساب است)."""
    if not user or not user.is_authenticated or a.user_id == user.pk:
        return
    clicked = timezone.datetime.fromtimestamp(ts, tz=timezone.get_fixed_timezone(0))
    expires = clicked + timezone.timedelta(days=conf().attribution_days)
    cur = CustomerRef.objects.filter(user=user).first()
    if cur and cur.clicked_at >= clicked:
        return
    CustomerRef.objects.update_or_create(user=user, defaults={"affiliate": a, "clicked_at": clicked, "expires_at": expires})


class ShortHostMiddleware:
    """درخواست‌های دامنهٔ کوتاه (crpt.ir) پیش از هر چیز به سایت اصلی هدایت می‌شوند."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.META.get("HTTP_HOST", "").split(":")[0].lower()
        if host and host in short_hosts():
            try:
                return short_redirect(request)
            except Exception:  # noqa: BLE001
                log.exception("short link")
                return HttpResponseRedirect(settings.SITE_URL + "/")
        return self.get_response(request)


class RefMiddleware:
    """?ref=کد در هر صفحه: کلیک ثبت و کوکی ماندگار گذاشته می‌شود، بعد به همان صفحه بدون ref برمی‌گردد."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get("ref") if request.method == "GET" else None
        if code and not request.path.startswith(SKIP):
            resp = self.handle(request, code)
            if resp is not None:
                return resp
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and COOKIE in request.COOKIES:
            raw = request.COOKIES[COOKIE]
            sess = getattr(request, "session", None)
            if sess is not None and sess.get("aff_bound") != raw:
                a, ts = read_cookie(request)
                if a:
                    try:
                        bind_user(user, a, ts)
                    except Exception:  # noqa: BLE001
                        log.exception("affiliate bind")
                sess["aff_bound"] = raw
        return response

    def handle(self, request, code):
        s = conf()
        q = request.GET.copy()
        q.pop("ref", None)
        clean = request.path + ("?" + q.urlencode() if q else "")
        a = by_code(code) if s.enabled else None
        resp = HttpResponseRedirect(clean)
        resp["X-Robots-Tag"] = "noindex"
        if a is None:
            return resp
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.pk == a.user_id:
            return resp  # همکار پیوند خودش را باز کرده
        if not is_bot(request):
            record_click(request, a, request.path)
            now = int(time.time())
            resp.set_cookie(COOKIE, signing.dumps({"c": a.code, "t": now}, salt=SALT), max_age=s.attribution_days * 86400,
                            secure=not settings.DEBUG, httponly=True, samesite="Lax")
            if user is not None and user.is_authenticated:
                bind_user(user, a, now)
        return resp


# ------------------------------------------------------------------ سفارش
def attach(order, ref=None):
    """هنگام ثبت سفارش: اگر با کد تخفیف همکار، کوکی پیوند یا حساب واردشده با پیوند آمده، پورسانتش ثبت می‌شود."""
    from shop.models import Order

    from .commission import order_base, period_of, recalc, status_for

    s = AffiliateSettings.load()
    if not s.enabled:
        return None
    a, source = None, ""
    if order.coupon_code:
        a = Affiliate.objects.filter(coupon__code=order.coupon_code, status=Affiliate.Status.ACTIVE).first()
        source = Commission.Source.COUPON
    if a is None and ref and ref.get("affiliate"):
        a, source = ref["affiliate"], Commission.Source.LINK
    if a is None and order.user_id:
        cr = (CustomerRef.objects.filter(user_id=order.user_id, expires_at__gt=timezone.now(), affiliate__status=Affiliate.Status.ACTIVE)
              .select_related("affiliate").first())
        if cr:
            a, source = cr.affiliate, Commission.Source.ACCOUNT
    if a is None:
        return None
    from accounts.utils import normalize_mobile

    if a.user_id == order.user_id or normalize_mobile(a.mobile) == normalize_mobile(order.mobile):
        return None  # خرید خود همکار
    if s.new_customers_only and order.user_id and Order.objects.filter(
            user_id=order.user_id, status__in=Order.PAID_STATUSES).exclude(pk=order.pk).exists():
        return None
    c, _ = Commission.objects.get_or_create(order=order, defaults={
        "affiliate": a, "source": source, "base": order_base(order), "status": status_for(order),
        "period": period_of(order.created_at, s)})
    recalc(a, c.period, s)
    return c
