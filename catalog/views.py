import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, F, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils.html import strip_tags

from core import seo
from pricing.models import PricingSettings, Size

from .models import Attribute, AttributeTerm, Brand, Category, Product, ProductTag, Review, Variation

SORTS = {
    "new": ("-published_at", "جدیدترین"),
    "popular": ("-views", "پربازدیدترین"),
    "rating": ("-rating_avg", "بیشترین امتیاز"),
    "cheap": ("min_price", "ارزان‌ترین"),
    "expensive": ("-max_price", "گران‌ترین"),
}


def card_queryset(qs):
    return qs.select_related("image", "brand").only(
        "title", "slug", "album_id", "min_price", "max_price", "stock_status", "sale_status", "rating_avg", "rating_count",
        "image__file", "image__alt", "image__width", "image__height", "brand__name", "published_at",
    )


def paged_url(base, page, query):
    url = base + (f"page/{page}/" if page > 1 else "")
    return url + (f"?{query}" if query else "")


def product_listing(request, base_qs, *, page, path, meta, heading, intro="", crumbs=(), archive=None, template="catalog/product_list.html",
                    extra=None):
    page = int(page or 1)
    base_qs = base_qs.published()
    qs = base_qs
    g = request.GET
    active = {}

    if g.get("size"):
        qs = qs.filter(variations__size__slug=g["size"], variations__is_available=True)
        active["size"] = g["size"]
    for attr in ("reeds-per-meter", "picks-per-meter", "background-color"):
        val = g.get(attr)
        if val:
            qs = qs.filter(specs__attribute__slug=attr, specs__slug=val)
            active[attr] = val
    if g.get("brand"):
        qs = qs.filter(brand__slug=g["brand"])
        active["brand"] = g["brand"]
    if g.get("instock"):
        qs = qs.exclude(stock_status="outofstock")
        active["instock"] = "1"
    for key, lookup in (("min", "min_price__gte"), ("max", "min_price__lte")):
        if g.get(key, "").isdigit():
            qs = qs.filter(**{lookup: int(g[key])})
            active[key] = g[key]
    sort = g.get("sort") if g.get("sort") in SORTS else "new"
    order = SORTS[sort][0]
    # کالاهای موجود همیشه بالاتر (instock < onbackorder < outofstock)
    qs = qs.distinct().order_by("stock_status", order)

    paginator = Paginator(card_queryset(qs), settings.PRODUCTS_PER_PAGE)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        raise Http404
    if page > 1 and not paginator.count:
        raise Http404

    query = g.urlencode()
    ids = base_qs.values("pk")
    facets = {
        "sizes": Size.objects.filter(variations__product__in=ids, is_active=True).exclude(type="custom")
        .annotate(n=Count("variations__product", distinct=True)).order_by("sort_order"),
        "reeds": AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", products__in=ids)
        .annotate(n=Count("products", distinct=True)).order_by("order", "name"),
        "colors": AttributeTerm.objects.filter(attribute__slug="background-color", products__in=ids)
        .annotate(n=Count("products", distinct=True)).order_by("-n")[:30],
        "brands": Brand.objects.filter(products__in=ids).annotate(n=Count("products", distinct=True)).order_by("-n"),
    }
    if "override" in meta:
        m = {"robots": "", **meta["override"],
             "canonical": settings.SITE_URL + path + (f"page/{page}/" if page > 1 else "")}
        if page > 1:
            m["title"] = f"{m['title']} {seo.page_label(page)}"
    else:
        m = seo.build(**meta, page=page)
    if active or g.get("sort"):
        m["robots"] = "noindex,follow"
    ctx = {
        "meta": m, "heading": heading, "intro": intro if page == 1 else "", "crumbs": crumbs, "archive": archive,
        "page_obj": page_obj, "products": page_obj.object_list, "facets": facets, "active": active,
        "sort": sort, "sorts": [(k, v[1]) for k, v in SORTS.items()], "base_path": path,
        "prev_url": paged_url(path, page - 1, query) if page_obj.has_previous() else "",
        "next_url": paged_url(path, page + 1, query) if page_obj.has_next() else "",
        "page_links": [(n, paged_url(path, n, query)) if n != "…" else (n, "") for n in
                       page_obj.paginator.get_elided_page_range(page, on_each_side=2, on_ends=1)],
    }
    ctx.update(extra or {})
    return render(request, template, ctx)


def shop(request, page=1, page_obj_cms=None):
    from blog.models import Page

    cms = page_obj_cms or Page.objects.filter(template="shop").first()
    meta = {"obj": cms, "kind": "page", "path": "/store/"} if cms else {"kind": "home"}
    return product_listing(
        request, Product.objects.all(), page=page, path="/store/", meta=meta,
        heading=cms.title if cms else "فروشگاه", intro=cms.content if cms else "",
        crumbs=[("فروشگاه", "/store/")],
    )


def category_detail(request, path, page=1):
    slugs = path.strip("/").split("/")
    cat = get_object_or_404(Category, slug=slugs[-1])
    if cat.path != "/".join(slugs):
        raise Http404
    crumbs = [(c.name, c.get_absolute_url()) for c in cat.ancestors()] + [(cat.name, cat.get_absolute_url())]
    qs = Product.objects.filter(categories__in=cat.descendant_ids())
    return product_listing(
        request, qs, page=page, path=cat.get_absolute_url(), meta={"obj": cat, "kind": "product_cat"},
        heading=cat.name, intro=cat.description, crumbs=crumbs, archive=cat,
    )


def tag_detail(request, slug, page=1):
    tag = get_object_or_404(ProductTag, slug=slug)
    return product_listing(
        request, tag.products.all(), page=page, path=tag.get_absolute_url(), meta={"obj": tag, "kind": "product_tag"},
        heading=tag.name, intro=tag.description, crumbs=[(tag.name, tag.get_absolute_url())], archive=tag,
    )


def brand_detail(request, slug, page=1):
    brand = get_object_or_404(Brand, slug=slug)
    return product_listing(
        request, brand.products.all(), page=page, path=brand.get_absolute_url(), meta={"obj": brand, "kind": "product_brand"},
        heading=brand.name, intro=brand.description, crumbs=[("برندها", "/store/"), (brand.name, brand.get_absolute_url())], archive=brand,
    )


def attribute_term_detail(request, term, page=1):
    return product_listing(
        request, term.products.all(), page=page, path=term.get_absolute_url(),
        meta={"obj": term, "kind": f"pa_{term.attribute.slug}"},
        heading=f"{term.attribute.label} {term.name}", intro=term.description,
        crumbs=[(f"{term.attribute.label} {term.name}", term.get_absolute_url())], archive=term,
    )


def search(request, page=1):
    q = (request.GET.get("q") or "").strip()[:100]
    qs = Product.objects.filter(Q(title__icontains=q) | Q(sku__iexact=q) | Q(english_name__icontains=q)) if q else Product.objects.none()
    resp = product_listing(
        request, qs, page=request.GET.get("p", 1), path="/search/", meta={"kind": "home"},
        heading=f"نتیجهٔ جستجو برای «{q}»" if q else "جستجو", crumbs=[("جستجو", "/search/")],
    )
    return resp


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("image", "brand", "primary_category", "album__base_size"), slug=slug
    )
    if product.status != Product.Status.PUBLISH and not request.user.is_staff:
        raise Http404
    variations = list(product.variations.select_related("size").prefetch_related("attributes__attribute").order_by("size__sort_order", "menu_order"))
    specs = product.specs.select_related("attribute").order_by("attribute__order", "order")
    gallery = [product.image] if product.image_id else []
    gallery += [pi.media for pi in product.images.select_related("media") if pi.media_id != product.image_id]
    cat = product.primary_category or product.categories.first()
    crumbs = []
    if cat:
        crumbs = [(c.name, c.get_absolute_url()) for c in cat.ancestors()] + [(cat.name, cat.get_absolute_url())]
    crumbs.append((product.title, product.get_absolute_url()))
    reviews = product.reviews.filter(is_approved=True, parent=None).prefetch_related(
        Prefetch("replies", queryset=Review.objects.filter(is_approved=True))
    ).order_by("-created_at")[:30]
    related = card_queryset(
        Product.objects.published().filter(categories=cat).exclude(pk=product.pk).exclude(stock_status="outofstock")
        .order_by("-views")
    )[:8] if cat else []
    Product.objects.filter(pk=product.pk).update(views=F("views") + 1)

    m = seo.build(product, "product", extra={"wc_price": f"{product.min_price:,}" if product.min_price else ""})
    ctx = {
        "meta": m, "product": product, "variations": variations, "specs": specs, "gallery": gallery,
        "crumbs": crumbs, "reviews": reviews, "related": related, "pricing": PricingSettings.load(),
        "faqs": product.faqs.filter(is_active=True),
        "jsonld": json.dumps(product_jsonld(product, variations, gallery, crumbs), ensure_ascii=False),
    }
    if product.is_purchasable and product.min_price:
        from installments.services import teaser

        ctx["inst_teaser"] = teaser(product.min_price)
    return render(request, "catalog/product_detail.html", ctx)


def product_jsonld(product, variations, gallery, crumbs):
    site = settings.SITE_URL
    priced = [v for v in variations if v.price]
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.title,
        "url": site + product.get_absolute_url(),
        "description": seo.plain(product.short_description or product.content, 300),
        "image": [m.absolute_url for m in gallery[:5]],
        "sku": product.sku or str(product.pk),
    }
    if product.brand_id:
        data["brand"] = {"@type": "Brand", "name": product.brand.name}
    if priced:
        # قیمت‌ها به ریال (IRR) برای سازگاری با گوگل
        prices = [v.price * 10 for v in priced]
        data["offers"] = {
            "@type": "AggregateOffer", "priceCurrency": "IRR",
            "lowPrice": min(prices), "highPrice": max(prices), "offerCount": len(priced),
            "availability": "https://schema.org/InStock" if product.in_stock else "https://schema.org/OutOfStock",
        }
    if product.rating_count:
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": float(product.rating_avg), "reviewCount": product.rating_count}
    breadcrumb = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": site + u} for i, (n, u) in enumerate(crumbs)],
    }
    return [data, breadcrumb]
