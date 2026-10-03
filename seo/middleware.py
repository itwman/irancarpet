import re

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
        self.log(request, source)
        return response

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
