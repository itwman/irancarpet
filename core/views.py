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


HOME_REEDS = ["700", "1000", "1200", "1500"]
ROOM_SIZES = [("6-meter", "۶ متری", "۳ × ۲", 3, 2), ("9-meter", "۹ متری", "۳٫۵ × ۲٫۵", 3.5, 2.5), ("12-meter", "۱۲ متری", "۴ × ۳", 4, 3)]


REVIEW_GOOD = ("عالی", "زیبا", "قشنگ", "کیفیت", "راضی", "ممنون", "خوب", "دوست")
REVIEW_SKIP = ("؟", "?", "موجود", "لینک", "نقص", "ایراد", "مشکل", "دیر", "ولی", "اما")


def _home_data():
    """داده‌های صفحهٔ اصلی (۱۰ دقیقه کش می‌شود)."""
    from django.db.models import Avg, Count

    from catalog.models import Review, Variation

    base = Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False)
    size_slugs = [s[0] for s in ROOM_SIZES]

    groups, showcase = [], []
    for reeds in HOME_REEDS:
        term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", slug=reeds).first()
        if not term:
            continue
        items = list(catalog_views.card_queryset(base.filter(specs=term).order_by("-views"))[:4])
        groups.append({"term": term, "products": items})
        # نمایش در «گره‌ها» و «چیدمان اتاق»: پربازدیدترین محصولی که هر سه سایز را دارد
        for p in base.filter(specs=term).select_related("image").order_by("-views")[:12]:
            prices = {}
            for v in Variation.objects.filter(product=p, is_available=True, size__slug__in=size_slugs).select_related("size"):
                price = v.price
                if price:
                    prices[v.size.slug] = price
            if len(prices) == len(size_slugs):
                showcase.append({
                    "name": p.title, "url": p.get_absolute_url(), "img": p.image.url, "reeds": reeds,
                    "prices": [prices[s] for s in size_slugs],
                })
                break

    reviews = list(
        Review.objects.filter(parent=None, is_approved=True, rating=5, product__status="publish")
        .select_related("product").order_by("-created_at")[:300]
    )
    picked, seen = [], set()
    for r in reviews:
        text = (r.content or "").strip()
        if not (45 <= len(text) <= 200) or not r.author_name or r.author_name in seen or r.product_id in seen:
            continue
        if any(w in text for w in REVIEW_SKIP) or not any(w in text for w in REVIEW_GOOD):
            continue
        if True:
            r.quote = re.sub(r"^سلام[\s،,.!]*", "", text)
            picked.append(r)
            seen.update({r.author_name, r.product_id})
        if len(picked) == 4:
            break

    stats = Review.objects.filter(parent=None, is_approved=True, rating__gt=0).aggregate(avg=Avg("rating"), n=Count("id"))
    return {
        "groups": groups, "showcase": showcase, "reviews": picked,
        "rating_avg": round(stats["avg"] or 0, 1), "rating_count": stats["n"],
        "ready_sizes": Variation.objects.filter(is_available=True, product__status="publish").count(),
    }


def home(request):
    import json

    from django.core.cache import cache

    data = cache.get("home_data")
    if data is None:
        data = _home_data()
        cache.set("home_data", data, 600)
    page = Page.objects.filter(template="home").first()
    posts = Post.objects.published().select_related("image")[:4]
    cats = Category.objects.filter(parent=None).order_by("order")[:12]
    room = {
        "sizes": [{"slug": s[0], "label": s[1], "dim": s[2], "w": s[3], "h": s[4]} for s in ROOM_SIZES],
        "room": [6.5, 4.75],
        "carpets": data["showcase"],
    }
    from core.models import SiteSettings

    site = SiteSettings.load()
    org = {
        "@context": "https://schema.org", "@type": "OnlineStore", "name": "ایران کارپت",
        "url": settings.SITE_URL + "/", "logo": settings.SITE_URL + "/static/img/logo.png",
        "sameAs": [url for key, _, url in site.socials if key != "whatsapp"],
    }
    phones = ["+98" + p[1:] if p.startswith("0") else p for p in (re.sub(r"\D", "", x or "") for x in (site.phone, site.mobile)) if p]
    if phones:
        org["contactPoint"] = [{"@type": "ContactPoint", "telephone": p, "contactType": "sales", "areaServed": "IR",
                                "availableLanguage": "Persian"} for p in phones]
    return render(request, "home.html", {
        "meta": seo.build(kind="home"), "page": page, "posts": posts, "categories": cats,
        "room": room, "jsonld": json.dumps(org, ensure_ascii=False), **data,
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
        if page.template == "price_list" and page_num == 1:
            from pricing.views import price_list

            return price_list(request, page)
        if page.template == "installment" and page_num == 1:
            from installments.views import info_page

            return info_page(request, page)
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
