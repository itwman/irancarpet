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
        if response.status_code == 301 and request.method in ("GET", "HEAD") and response.get("Location"):
            # ۳۰۱ خود سایت (مثل /x/page/1/ ← /x/) اگر به نشانیِ ریدایرکت‌شوندهٔ دیگری برسد، یک‌جا به مقصد نهایی
            loc = response["Location"]
            if not getattr(request, "_final_probe", False) and urlsplit(loc).netloc in ("", request.get_host()):
                end = self.final(request, loc)
                if end != loc:
                    return HttpResponsePermanentRedirect(end)
            return response
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
            if redirect.status_code == 301:
                return HttpResponsePermanentRedirect(self.final(request, target))
            return HttpResponseRedirect(target)
        if self.GONE.match(unquote(request.path)):
            return HttpResponseGone()
        if request.method in ("GET", "HEAD"):
            target = self.legacy_target(request, source)
            if target:
                return HttpResponsePermanentRedirect(self.final(request, target))
        self.log(request, source)
        return response

    # نشانی‌های قدیمی وردپرس که گوگل هنوز دارد. اول «پیشوند» عوض می‌شود (برند، تاریخ، post=…)، بعد «پسوند» برداشته
    # می‌شود (دیدگاه، فید، صفحهٔ چندم، پیوست). هر نشانی جایگزین فقط وقتی ریدایرکت می‌شود که واقعاً صفحه داشته باشد.
    PREFIX = [
        (re.compile(r"^/post=tag/(.+)$"), r"/tag/\1"),
        (re.compile(r"^/post=\d+/(.+)$"), r"/\1"),
        (re.compile(r"^/product_brand/(.+)$"), r"/brand/\1"),
        (re.compile(r"^/برند/(.+)$"), r"/brand/\1"),
        (re.compile(r"^/key/(.+)$"), r"/tag/\1"),
        (re.compile(r"^/\d{4}/\d{1,2}/\d{1,2}/([^/]+)/?$"), r"/\1/"),  # ساختار تاریخ‌دار قدیمی
        (re.compile(r"^/page/(\d+)/?$"), r"/blog/page/\1/"),           # صفحه‌بندی مقاله‌های صفحهٔ اول وردپرس
    ]
    SUFFIX = [
        (re.compile(r"^(/.+?)/(?:comment-page-\d+|feed|amp|embed|jpe?g|png|webp|attachment/[^/]+)/?$"), r"\1/"),
        (re.compile(r"^(/.+?)/page/\d+/?$"), r"\1/"),
    ]
    POST_PARENT = re.compile(r"^(/[^/]+)/[^/]+/?$")  # /نوشته/چیز-اضافه/ ← /نوشته/ (فقط اگر نوشته باشد)
    GONE = re.compile(r"^/(?:\d{5,}|.*\*.*)/?$")      # فقط‌عدد (لینک اسپم) یا ستاره‌دار: هیچ‌وقت صفحه نبوده‌اند

    def final(self, request, target, hops=3):
        """زنجیرهٔ ریدایرکت یک‌جا: /برند/x/page/1/ → /برند/x/ → /brand/x/ می‌شود یک ۳۰۱ مستقیم به /brand/x/."""
        seen = {request.path}
        for _ in range(hops):
            parts = urlsplit(target)
            if parts.netloc not in ("", request.get_host()) or parts.path in seen:
                return target
            seen.add(parts.path)
            sub = copy.copy(request)
            sub.path = sub.path_info = parts.path
            sub.GET = request.GET.copy()
            sub._final_probe = True
            try:
                resp = self(sub)
            except Exception:  # noqa: BLE001
                return target
            if resp.status_code in (301, 302) and resp.get("Location"):
                target = resp["Location"]
                continue
            return target
        return target

    @staticmethod
    def normalize_path(path):
        """ارقام فارسی ← لاتین، و نیم‌فاصله/فاصله/خط‌تیرهٔ اضافهٔ ابتدا و انتهای هر بخش برداشته می‌شود."""
        path = path.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        parts = [re.sub(r"^[\s\u200c\u200f\-]+|[\s\u200c\u200f\-]+$", "", seg) for seg in path.split("/")]
        return "/".join(parts)

    def _try(self, request, cand):
        """(نشانی نهایی یا None) اگر cand صفحه داشته باشد یا به صفحه‌ای ریدایرکت شود."""
        hit = self.find(Redirect.normalize(cand))
        if hit and hit.status_code in (301, 302) and hit.match != Redirect.Match.REGEX:
            return hit.target
        sub = copy.copy(request)
        sub.path = sub.path_info = cand
        sub.GET = request.GET.copy()
        try:
            resp = self.get_response(sub)
        except Exception:  # noqa: BLE001
            return None
        if resp.status_code == 200:
            return cand
        if resp.status_code in (301, 302) and resp.get("Location"):
            loc = resp["Location"]
            return loc if urlsplit(loc).netloc in ("", request.get_host()) else None
        return None

    def legacy_target(self, request, source):
        """اولین نشانی جایگزینی که واقعاً صفحه دارد (۲۰۰) یا به صفحه‌ای ریدایرکت می‌شود."""
        path = unquote(request.path)
        bases = []

        def add(p):
            if p and not p.endswith("/"):
                p += "/"
            if p and p != "/" and p not in bases:
                bases.append(p)

        add(path)
        add(self.normalize_path(path))
        for b in list(bases):
            for rx, repl in self.PREFIX:
                if rx.search(b):
                    add(rx.sub(repl, b, count=1))
        tried = {path if path.endswith("/") else path + "/"}
        for b in bases:
            cands = [b] + [rx.sub(repl, b, count=1) for rx, repl in self.SUFFIX if rx.search(b)]
            m = self.POST_PARENT.search(b)
            if m and (self._is_post(m.group(1) + "/") or self._is_page(m.group(1) + "/")):
                cands.append(m.group(1) + "/")
            for cand in cands:
                if not cand.endswith("/"):
                    cand += "/"
                if cand in tried or cand == "/":
                    continue
                tried.add(cand)
                target = self._try(request, cand)
                if target:
                    return target
        for b in bases:  # نامک بریده‌شده: فقط اگر دقیقاً یک فرش یا نوشته با همین شروع باشد
            for cand in (rx.sub(repl, b, count=1) for rx, repl in self.SUFFIX if rx.search(b)):
                target = self.truncated(cand)
                if target:
                    return target
            target = self.truncated(b)
            if target:
                return target
        if self._product_exists(path if path.endswith("/") else path + "/"):
            return None  # فرش پیش‌نویس یا در انتظار بررسی: حذف نشده، به جای دیگری فرستاده نمی‌شود
        for b in bases:  # فرش حذف‌شده ← همان نقشه؛ دستهٔ شانهٔ قدیمی ← دستهٔ همان شانه؛ برند با املای نزدیک
            for fn in (self.same_design, self.reeds_page, self.near_brand):
                cand = fn(b)
                if cand and cand not in tried:
                    tried.add(cand)
                    target = self._try(request, cand)
                    if target:
                        return target
        return None

    REEDS = re.compile(r"(?:^|[/-])(500|700|1000|1200|1500)-?(?:reeds?|shane|شانه)(?:[-/]|$)")  # فرش حذف‌شده‌ای که نقشه‌اش هم نیست ← دستهٔ شانه‌اش

    @staticmethod
    def same_design(path):
        """/product/فرش-1200-شانه-گل-برجسته-نقشه-بید-مجنون-زمین/ (حذف‌شده) ← فرش منتشرشدهٔ دیگری از نقشهٔ «بید مجنون»."""
        from django.db.models import Q

        from catalog.models import Product

        m = re.match(r"^/product/[^/]*?نقشه-([^/]+?)/?$", path)
        if not m:
            return None
        words = re.split(r"-زمینه|-حاشیه", m.group(1))[0].split("-")
        reeds = re.search(r"(\d{3,4})-شانه", path)
        for n in range(min(3, len(words)), 0, -1):
            name = " ".join(words[:n])
            if len(name) < 3:
                continue
            qs = Product.objects.published().filter(Q(design_name__iexact=name) | Q(title__contains=f"نقشه {name} "))
            qs = qs.exclude(stock_status="outofstock") if qs.exclude(stock_status="outofstock").exists() else qs
            if reeds:
                hit = qs.filter(title__contains=reeds.group(1)).order_by("-views").first()
                if hit:
                    return hit.get_absolute_url()
            hit = qs.order_by("-views").first()
            if hit:
                return hit.get_absolute_url()
        return None

    def reeds_page(self, path):
        """/product-category/1200-reeds-simple/ یا /carpet-1200-reeds/ ← دستهٔ «فرش ۱۲۰۰ شانه» (یا صفحهٔ شانهٔ ۱۲۰۰)."""
        from catalog.models import AttributeTerm, Category

        if not (path.startswith(("/product-category/", "/product/")) or path.count("/") == 2):
            return None
        m = self.REEDS.search(path)
        if not m:
            return None
        n = m.group(1)
        fa = n.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        cat = Category.objects.filter(redirect_url="", name__in=[f"فرش {n} شانه", f"فرش {fa} شانه"]).first()
        if cat:
            return cat.get_absolute_url()
        term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", name__in=[n, fa]).first()
        return term.get_absolute_url() if term and term.attribute.is_public else None

    @staticmethod
    def near_brand(path):
        """/brand/artamis-carpet/ ← برندی با نامک نزدیک (مثل artemis-carpet)."""
        import difflib

        from catalog.models import Brand

        m = re.match(r"^/brand/([^/]+)/", path)
        if not m:
            return None
        slugs = list(Brand.objects.values_list("slug", flat=True))
        got = difflib.get_close_matches(m.group(1), slugs, n=1, cutoff=0.8)
        return f"/brand/{got[0]}/" if got else None

    @staticmethod
    def truncated(path):
        from blog.models import Page, Post
        from catalog.models import Product

        m = re.match(r"^/product/([^/]+)/?$", path)
        if m:
            qs, prefix = Product.objects.filter(status="publish"), m.group(1)
        else:
            m = re.match(r"^/([^/]+)/?$", path)
            if not m:
                return None
            qs, prefix = None, m.group(1)
        if len(prefix) < 15:
            return None
        if qs is not None:
            hits = list(qs.filter(slug__startswith=prefix).exclude(slug=prefix)[:2])
            return hits[0].get_absolute_url() if len(hits) == 1 else None
        hits = list(Post.objects.filter(status="publish", slug__startswith=prefix).exclude(slug=prefix)[:2])
        if not hits:
            hits = list(Page.objects.filter(status="publish", slug__startswith=prefix).exclude(slug=prefix)[:2])
        return hits[0].get_absolute_url() if len(hits) == 1 else None

    @staticmethod
    def _product_exists(path):
        from catalog.models import Product

        m = re.match(r"^/product/([^/]+)/?$", path)
        return bool(m) and Product.objects.filter(slug=m.group(1)).exists()

    @staticmethod
    def _is_page(path):
        from blog.models import Page

        return Page.objects.filter(parent=None, slug=path.strip("/"), status="publish").exists()

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
