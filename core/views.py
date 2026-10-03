import re

from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render

from blog import views as blog_views
from blog.models import Page, Post
from catalog import views as catalog_views
from catalog.models import Attribute, AttributeTerm, Category, Product

from . import seo

PAGED = re.compile(r"^(?P<path>.*?)/?page/(?P<page>\d+)$")


def home(request):
    page = Page.objects.filter(template="home").first()
    cats = Category.objects.filter(parent=None).select_related("image").order_by("order")[:12]
    products = catalog_views.card_queryset(Product.objects.published().exclude(stock_status="outofstock").order_by("-published_at"))[:12]
    popular = catalog_views.card_queryset(Product.objects.published().exclude(stock_status="outofstock").order_by("-views"))[:12]
    reeds = sorted(
        (t for t in AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", products__isnull=False).distinct() if t.name.strip().isdigit()),
        key=lambda t: int(t.name),
    )
    posts = Post.objects.published().select_related("image")[:4]
    org = {
        "@context": "https://schema.org", "@type": "OnlineStore", "name": "ایران کارپت",
        "url": settings.SITE_URL + "/", "logo": settings.SITE_URL + "/static/img/logo.svg",
    }
    import json

    return render(request, "home.html", {
        "meta": seo.build(kind="home"), "page": page, "categories": cats, "products": products,
        "popular": popular, "reeds": reeds, "posts": posts, "jsonld": json.dumps(org, ensure_ascii=False),
    })


def resolve(request, path):
    """مسیرهای یک‌بخشی و چندبخشی: مقاله، برگه، آرشیو ویژگی (مثل /reeds-per-meter/1200/)."""
    page_num = 1
    m = PAGED.match(path)
    if m:
        path, page_num = m.group("path"), int(m.group("page"))
        if page_num < 2:
            return HttpResponsePermanentRedirect(f"/{path}/" if path else "/")
    slugs = [s for s in path.split("/") if s]
    if not slugs:
        raise Http404

    if len(slugs) == 1 and page_num == 1:
        post = Post.objects.filter(slug=slugs[0]).select_related("image", "primary_category").first()
        if post:
            return blog_views.post_detail(request, post)

    if len(slugs) == 2:
        attr = Attribute.objects.filter(slug=slugs[0], is_public=True).first()
        if attr:
            term = AttributeTerm.objects.filter(attribute=attr, slug=slugs[1]).first()
            if term:
                return catalog_views.attribute_term_detail(request, term, page_num)

    # ساختار قدیمی وردپرس: /1396/09/21/slug/
    if len(slugs) == 4 and all(x.isdigit() for x in slugs[:3]):
        post = Post.objects.filter(slug=slugs[3]).first() or (
            Post.objects.filter(wp_id=int(slugs[3])).first() if slugs[3].isdigit() else None)
        if post:
            return HttpResponsePermanentRedirect(post.get_absolute_url())

    page = _page_by_path(slugs)
    if page:
        if page.template == "shop":
            return catalog_views.shop(request, page_num, page)
        if page.template == "home":
            return HttpResponsePermanentRedirect("/")
        if page_num == 1:
            return blog_views.page_detail(request, page)
    raise Http404


def _page_by_path(slugs):
    candidates = Page.objects.filter(slug=slugs[-1]).select_related("parent__parent")
    for p in candidates:
        if p.path == "/".join(slugs):
            return p
    return None


def gone(request, *args, **kwargs):
    return HttpResponse("410 Gone", status=410, content_type="text/plain; charset=utf-8")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /panel/",
        "Disallow: /search/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /my-account/",
        "Disallow: /*?*",
        "",
        f"Sitemap: {settings.SITE_URL}/sitemap_index.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def not_found(request, exception=None):
    products = catalog_views.card_queryset(Product.objects.published().exclude(stock_status="outofstock").order_by("-views"))[:8]
    return render(request, "404.html", {"meta": {"title": "صفحه پیدا نشد", "robots": "noindex"}, "products": products}, status=404)


def server_error(request):
    return render(request, "500.html", status=500)


def dev_media(request, path):
    """فقط در حالت DEBUG: اگر فایل محلی نبود، از سایت اصلی خوانده شود."""
    from pathlib import Path

    from django.http import HttpResponseRedirect
    from django.views.static import serve

    local = Path(settings.MEDIA_ROOT) / path
    if not local.exists():
        import urllib.request
        from urllib.parse import quote

        try:
            url = f"{settings.SITE_URL}/wp-content/uploads/{quote(path)}"
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dev"}), timeout=20).read()
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(data)
        except Exception:  # noqa: BLE001
            return HttpResponseRedirect(f"{settings.SITE_URL}/wp-content/uploads/{path}")
    return serve(request, path, document_root=settings.MEDIA_ROOT)
