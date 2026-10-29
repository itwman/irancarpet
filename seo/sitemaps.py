"""سایت‌مپ با همان نام فایل‌های Rank Math (sitemap_index.xml، product-sitemap1.xml و...)."""
from django.conf import settings
from django.db.models import Count, Max, Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.html import escape

from blog.models import PAGE_REDIRECTS, BlogCategory, Page, Post
from catalog.models import Attribute, AttributeTerm, Brand, Category, Product, ProductTag

PER_PAGE = 200


def _xml(body):
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?>\n' + body, content_type="application/xml; charset=utf-8")


def _iso(dt):
    return (dt or timezone.now()).astimezone(timezone.get_current_timezone()).isoformat(timespec="seconds")


def sections():
    """نام → (queryset، تابع ساخت آیتم، صفحه‌بندی؟)"""
    out = {
        "post": (Post.objects.published().exclude(robots__contains="noindex").select_related("image").order_by("-modified_at"), True),
        "page": (Page.objects.filter(status="publish").exclude(robots__contains="noindex").exclude(template__in=["cart", "checkout", "account", "tracking", "home"])
                 .exclude(parent=None, slug__in=list(PAGE_REDIRECTS)).order_by("menu_order"), False),
        "product": (Product.objects.published().exclude(robots__contains="noindex").select_related("image").prefetch_related("images__media").order_by("-modified_at"), True),
        "category": (BlogCategory.objects.annotate(n=Count("posts"), lm=Max("posts__modified_at")).filter(n__gt=0), False),
        "product_brand": (Brand.objects.filter(wp_id__isnull=False).annotate(n=Count("products"), lm=Max("products__modified_at")).filter(n__gt=0), False),
        "product_cat": (Category.objects.filter(redirect_url="").annotate(n=Count("products"), lm=Max("products__modified_at")).filter(n__gt=0)
                        .exclude(robots__contains="noindex"), False),
        # برچسب‌های فرش با دست‌کم ۴ فرش منتشرشده (در سرچ کنسول نمایش دارند ولی در سایت‌مپ نبودند)
        "product_tag": (ProductTag.objects.exclude(robots__contains="noindex")
                        .annotate(n=Count("products", filter=Q(products__status="publish"), distinct=True),
                                  lm=Max("products__modified_at", filter=Q(products__status="publish"))).filter(n__gte=4)
                        .order_by("-n"), False),
    }
    from pricing.pricelist import albums_qs

    out["price_list"] = (albums_qs().exclude(slug="").order_by("sort_order", "name"), False)
    from landing.build import live

    out["landing"] = (live().order_by("-count"), True)
    for attr in Attribute.objects.filter(is_public=True).exclude(slug__in=["brand"]):
        out[f"pa_{attr.slug}"] = (AttributeTerm.objects.filter(attribute=attr).annotate(n=Count("products"), lm=Max("products__modified_at"))
                                  .filter(n__gt=0), False)
    return out


DATE_FIELDS = ("lm", "modified_at", "last_updated", "synced_at", "published_at")


def _lastmod(obj):
    """تاریخ واقعی آخرین تغییر؛ برای دسته و برچسب: آخرین تغییر فرش‌هایش. اگر نبود، lastmod نوشته نمی‌شود (نه «همین الان»)."""
    for f in DATE_FIELDS:
        v = getattr(obj, f, None)
        if v:
            return v
    return None


def _section_lastmod(qs, start=None, stop=None):
    """بیشترین تاریخ تغییرِ آیتم‌های همان زیرنقشه."""
    names = set(qs.query.annotations) | {f.name for f in qs.model._meta.get_fields()}
    field = next((f for f in DATE_FIELDS if f in names), None)
    if field is None:
        return None
    part = qs.select_related(None).prefetch_related(None)
    if start is not None:
        part = part[start:stop]
    vals = [v for v in part.values_list(field, flat=True) if v]
    return max(vals) if vals else None


def index(request):
    from django.core.cache import cache

    body = cache.get("sitemap_index")
    if body is None:
        items = []
        for name, (qs, paged) in sections().items():
            count = qs.count()
            if not count:
                continue
            pages = (count - 1) // PER_PAGE + 1 if paged else 1
            for n in range(1, pages + 1):
                fname = f"{name}-sitemap{n if paged else ''}.xml"
                lm = _section_lastmod(qs, (n - 1) * PER_PAGE, n * PER_PAGE) if paged else _section_lastmod(qs)
                items.append(f"<sitemap><loc>{settings.SITE_URL}/{fname}</loc>" + (f"<lastmod>{_iso(lm)}</lastmod>" if lm else "")
                             + "</sitemap>")
        body = '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(items) + "\n</sitemapindex>"
        cache.set("sitemap_index", body, 600)
    return _xml(body)


def section(request, name, num=""):
    secs = sections()
    if name not in secs:
        raise Http404
    qs, paged = secs[name]
    if paged != bool(num):
        raise Http404
    n = int(num or 1)
    objs = list(qs[(n - 1) * PER_PAGE: n * PER_PAGE])
    if not objs:
        raise Http404
    site = settings.SITE_URL
    rows = []
    if name == "page":
        rows.append(f"<url><loc>{site}/</loc></url>")
        rows.append(f"<url><loc>{escape(site + '/فرش-جشنواره-ای/')}</loc></url>")
    for o in objs:
        url = o.get_absolute_url()
        if url == "/":
            continue
        imgs = ""
        if name in ("product", "post"):
            media = [o.image] if getattr(o, "image_id", None) else []
            if name == "product":
                media += [pi.media for pi in o.images.all()][:10]
            imgs = "".join(f"<image:image><image:loc>{escape(m.absolute_url)}</image:loc></image:image>" for m in media if m)
        lm = _lastmod(o)
        rows.append(f"<url><loc>{escape(site + url)}</loc>" + (f"<lastmod>{_iso(lm)}</lastmod>" if lm else "") + imgs + "</url>")
    return _xml(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
        + "\n".join(rows) + "\n</urlset>"
    )
