import copy
import re
from urllib.parse import unquote, urlsplit

from django.db.models import F
from django.http import HttpResponseGone, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils import timezone

from .models import NotFoundLog, Redirect

SKIP_PREFIXES = ("static/", "wp-content/", "panel/", "media/")


class LegacyQueryMiddleware:
    """آدرس‌های کوئری‌دار وردپرس: ?p=123 ، ?page_id=12 ، ?product=slug ، ?s=..."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        q = request.GET
        if request.method == "GET" and q:
            target = self._resolve(request.path, q)
            if target:
                return HttpResponsePermanentRedirect(target)
        return self.get_response(request)

    def _resolve(self, path, q):
        from blog.models import Page, Post
        from catalog.models import Category, Product

        if path != "/":
            return None
        wp_id = q.get("p") or q.get("page_id") or q.get("post")
        if wp_id and wp_id.isdigit():
            for model in (Product, Post, Page):
                obj = model.objects.filter(wp_id=int(wp_id)).first()
                if obj:
                    return obj.get_absolute_url()
        if q.get("product"):
            obj = Product.objects.filter(slug=q["product"]).first()
            if obj:
                return obj.get_absolute_url()
        if q.get("product_cat"):
            obj = Category.objects.filter(slug=q["product_cat"]).first()
            if obj:
                return obj.get_absolute_url()
        if "s" in q:
            from urllib.parse import urlencode

            return "/search/?" + urlencode({"q": q.get("s", "")})
        return None


class RedirectFallbackMiddleware:
    """اگر پاسخ 404 بود، جدول ریدایرکت‌ها را بررسی و در غیر این صورت 404 را ثبت می‌کند."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        source = Redirect.normalize(request.path)
        if source.startswith(SKIP_PREFIXES):
            return response
        redirect = self.find(source)
        if redirect:
            Redirect.objects.filter(pk=redirect.pk).update(hits=F("hits") + 1, last_hit=timezone.now())
            if redirect.status_code == 410:
                return HttpResponseGone()
            target = redirect.target
            if redirect.match == Redirect.Match.REGEX:
                target = re.sub(redirect.source, redirect.target, source)
            if request.META.get("QUERY_STRING") and "?" not in target:
                target += "?" + request.META["QUERY_STRING"]
            cls = HttpResponsePermanentRedirect if redirect.status_code == 301 else HttpResponseRedirect
            return cls(target)
        if request.method in ("GET", "HEAD"):
            target = self.legacy_target(request, source)
            if target:
                return HttpResponsePermanentRedirect(target)
        self.log(request, source)
        return response

    # نشانی‌های فرعی وردپرس که گوگل هنوز دارد: صفحهٔ دیدگاه، فید، صفحهٔ چندم، پیوند پیوست، ساختار قدیمی post=123
    LEGACY = [
        (re.compile(r"^/post=tag/(.+)$"), r"/tag/\1"),
        (re.compile(r"^/post=\d+/(.+)$"), r"/\1"),
        (re.compile(r"^/product_brand/(.+)$"), r"/brand/\1"),
        (re.compile(r"^/key/(.+)$"), r"/tag/\1"),
        (re.compile(r"^(/.+?)/(?:comment-page-\d+|feed|amp|embed|jpe?g|png|webp|attachment/[^/]+)/?$"), r"\1/"),
        (re.compile(r"^(/.+?)/page/\d+/?$"), r"\1/"),
        # /slug/چیز-اضافه/ ← /slug/ (فقط اگر /slug/ یک نوشته باشد؛ پایین بررسی می‌شود)
        (re.compile(r"^(/[^/]+)/[^/]+/?$"), r"\1/"),
    ]

    def legacy_target(self, request, source):
        """اولین نشانی جایگزینی که واقعاً صفحه دارد (۲۰۰) یا به صفحه‌ای ریدایرکت می‌شود."""
        path = unquote(request.path)
        tried = set()
        for rx, repl in self.LEGACY:
            if not rx.search(path):
                continue
            cand = rx.sub(repl, path, count=1)
            if not cand.endswith("/"):
                cand += "/"
            if cand in tried or cand == path or cand == "/":
                continue
            tried.add(cand)
            if rx is self.LEGACY[-1][0] and not self._is_post(cand):
                continue
            hit = self.find(Redirect.normalize(cand))
            if hit and hit.status_code in (301, 302) and hit.match != Redirect.Match.REGEX:
                return hit.target
            sub = copy.copy(request)
            sub.path = sub.path_info = cand
            sub.GET = request.GET.copy()
            try:
                resp = self.get_response(sub)
            except Exception:  # noqa: BLE001
                continue
            if resp.status_code == 200:
                return cand
            if resp.status_code in (301, 302) and resp.get("Location"):
                loc = resp["Location"]
                return loc if urlsplit(loc).netloc in ("", request.get_host()) else None
        return None

    @staticmethod
    def _is_post(path):
        from blog.models import Post

        return Post.objects.filter(slug=path.strip("/")).exists()

    @staticmethod
    def find(source):
        active = Redirect.objects.filter(is_active=True)
        hit = active.filter(match=Redirect.Match.EXACT, source__in=[source, source + "/"]).first()
        if hit:
            return hit
        for r in active.filter(match=Redirect.Match.START).order_by("-source"):
            if r.source and source.startswith(r.source):
                return r
        for r in active.filter(match=Redirect.Match.REGEX):
            try:
                if re.search(r.source, source):
                    return r
            except re.error:
                continue
        return None

    @staticmethod
    def log(request, source):
        if len(source) > 255:
            return
        updated = NotFoundLog.objects.filter(path=source).update(
            hits=F("hits") + 1, last_seen=timezone.now()
        )
        if not updated:
            NotFoundLog.objects.create(path=source, referrer=(request.META.get("HTTP_REFERER") or "")[:900])


class StagingNoIndexMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        response = self.get_response(request)
        if settings.STAGING:
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
