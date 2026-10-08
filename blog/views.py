import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core import seo

from .models import BlogCategory, BlogTag, Post
from .tidy import _swap_phones


def _paged(request, qs, page, path, meta, heading, intro="", crumbs=()):
    page = int(page or 1)
    paginator = Paginator(qs.select_related("image"), settings.POSTS_PER_PAGE)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        if page > 1:
            from django.http import HttpResponsePermanentRedirect

            return HttpResponsePermanentRedirect(path)
        raise Http404
    link = lambda n: path + (f"page/{n}/" if n > 1 else "")  # noqa: E731
    return render(request, "blog/post_list.html", {
        "meta": seo.build(**meta, page=page), "heading": heading, "intro": intro if page == 1 else "",
        "crumbs": crumbs, "page_obj": page_obj, "posts": page_obj.object_list,
        "prev_url": link(page - 1) if page_obj.has_previous() else "",
        "next_url": link(page + 1) if page_obj.has_next() else "",
        "page_links": [(n, link(n) if n != "…" else "") for n in paginator.get_elided_page_range(page, on_each_side=2, on_ends=1)],
    })


def blog_index(request, page=1):
    return _paged(request, Post.objects.published(), page, "/blog/", {"kind": "blog"}, "مجله ایران کارپت",
                  crumbs=[("مجله", "/blog/")])


def category_detail(request, path, page=1):
    slugs = path.strip("/").split("/")
    cat = get_object_or_404(BlogCategory, slug=slugs[-1])
    if cat.path != "/".join(slugs):
        raise Http404
    return _paged(request, cat.posts.published(), page, cat.get_absolute_url(), {"obj": cat, "kind": "category"},
                  cat.name, cat.description, [("مجله", "/blog/"), (cat.name, cat.get_absolute_url())])


def tag_detail(request, slug, page=1):
    tag = get_object_or_404(BlogTag, slug=slug)
    return _paged(request, tag.posts.published(), page, tag.get_absolute_url(), {"obj": tag, "kind": "post_tag"},
                  tag.name, tag.description, [("مجله", "/blog/"), (tag.name, tag.get_absolute_url())])


def post_detail(request, post):
    if post.status != "publish" and not request.user.is_staff:
        raise Http404
    Post.objects.filter(pk=post.pk).update(views=F("views") + 1)
    cat = post.primary_category or post.categories.first()
    crumbs = [("مجله", "/blog/")] + ([(cat.name, cat.get_absolute_url())] if cat else []) + [(post.title, post.get_absolute_url())]
    related = Post.objects.published().filter(categories=cat).exclude(pk=post.pk).select_related("image")[:3] if cat else []
    site = settings.SITE_URL
    jsonld = {
        "@context": "https://schema.org", "@type": "BlogPosting", "headline": post.title[:110],
        "datePublished": post.published_at.isoformat(), "dateModified": post.modified_at.isoformat(),
        "mainEntityOfPage": site + post.get_absolute_url(),
        "image": [post.image.absolute_url] if post.image_id else [],
        "author": {"@type": "Organization", "name": "ایران کارپت", "url": site + "/"},
        "publisher": {"@type": "Organization", "name": "ایران کارپت", "url": site + "/",
                      "logo": {"@type": "ImageObject", "url": site + "/static/img/logo.png"}},
        "inLanguage": "fa-IR",
    }
    from . import landing
    from .tidy import tidy

    content = tidy(post.content, post.title, phone=_site_mobile(), self_path=post.get_absolute_url())
    live = landing.has_blocks(content)
    content = landing.render(content, request, title=post.title) if live else content
    if live:
        upd = landing.last_price_update()
        if upd and upd > post.modified_at:  # قیمت‌های زندهٔ صفحه به‌روز شده‌اند
            jsonld["dateModified"] = upd.isoformat()
        faq = landing.faq_jsonld(post.content)
        if faq:
            jsonld = {"@context": "https://schema.org", "@graph": [{k: v for k, v in jsonld.items() if k != "@context"}, faq]}
    meta = seo.build(post, "post")
    meta["description"] = _swap_phones(meta.get("description") or "", _site_mobile())
    if meta.get("description"):
        (jsonld["@graph"][0] if "@graph" in jsonld else jsonld)["description"] = meta["description"]
    side = _side(post, live)
    if side["inline"]:
        content = _insert_inline(content, side["inline"])
    return render(request, "blog/post_detail.html", {
        "meta": meta, "post": post, "crumbs": crumbs, "related": related, **side,
        "comments": post.comments.filter(is_approved=True, parent=None).prefetch_related("replies"),
        "jsonld": json.dumps(jsonld, ensure_ascii=False), "content": content, "live": live,
        "price_updated": landing.last_price_update() if live else None,
    })


def _affiliate_box():
    try:
        from affiliate.models import AffiliateSettings
        from affiliate.views import top_percent

        a = AffiliateSettings.load()
        return {"top": top_percent(), "days": a.attribution_days} if a.enabled else None
    except Exception:  # noqa: BLE001
        return None


def _side(post, live):
    """فرش‌های پیشنهادی، نوع مقاله و کادر همکاری در فروش برای ستون کناری، وسط و پایان مقاله."""
    from django.template.loader import render_to_string

    from . import recommend

    try:
        products = recommend.products_for(post, 11)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("recommend")
        products = []
    kind = recommend.intent(post)
    reeds = recommend.reeds_of(post)
    inline = ""
    # ردیف فرش وسط مقاله فقط در مقاله‌های بلند و بدون جدول قیمت زنده (که خودش پیشنهاد خرید دارد)
    if products[4:7] and not live and len(post.content or "") > 6000:
        inline = render_to_string("blog/_inline_products.html", {"products": products[4:7], "reeds": reeds})
    end = products[7:11] if len(products) >= 9 else products[:4]
    return {"rec_side": products[:4], "rec_products": end, "rec_kind": kind, "rec_reeds": reeds, "aff_box": _affiliate_box(), "inline": inline}


def _insert_inline(content, block):
    """ردیف فرش پیش از تیترِ h2 نزدیک به وسط مقاله؛ اگر h2 کافی نبود، اضافه نمی‌شود."""
    import re

    heads = [m.start() for m in re.finditer(r"<h2\b", content)]
    if len(heads) < 4:
        return content
    mid = len(content) // 2
    at = min(heads[1:-1], key=lambda x: abs(x - mid))
    return content[:at] + block + content[at:]


def blog_search(request):
    from . import recommend

    q = (request.GET.get("q") or "").strip()[:100]
    ids = recommend.search_posts(q) if q else []
    paginator = Paginator(ids, settings.POSTS_PER_PAGE)
    try:
        page_obj = paginator.page(int(request.GET.get("p") or 1))
    except (EmptyPage, ValueError):
        page_obj = paginator.page(1) if ids else None
    posts = recommend.posts_by_ids(list(page_obj.object_list)) if page_obj else []
    from urllib.parse import urlencode

    return render(request, "blog/post_list.html", {
        "meta": {"title": f"جستجوی «{q}» در مقاله‌ها - ایران کارپت" if q else "جستجو در مقاله‌ها - ایران کارپت",
                 "description": "", "robots": "noindex, follow", "canonical": settings.SITE_URL + "/blog/search/"},
        "heading": f"مقاله‌های «{q}»" if q else "جستجو در مقاله‌ها", "q": q, "is_search": True,
        "count": len(ids), "posts": posts, "page_obj": page_obj,
        "crumbs": [("مجله", "/blog/"), ("جستجو", "/blog/search/")],
        "page_links": [(n, "?" + urlencode({"q": q, "p": n})) for n in paginator.page_range] if page_obj and paginator.num_pages > 1 else [],
    })


def page_detail(request, page):
    if page.status != "publish" and not request.user.is_staff:
        raise Http404
    from . import landing
    from .tidy import tidy

    content = tidy(page.content, page.title, phone=_site_mobile(), self_path=page.get_absolute_url())
    live = landing.has_blocks(content)
    meta = seo.build(page, "page")
    meta["description"] = _swap_phones(meta.get("description") or "", _site_mobile())
    return render(request, "blog/page_detail.html", {
        "meta": meta, "page": page, "live": live,
        "content": landing.render(content, request, title=page.title) if live else content,
        "crumbs": [(p.title, p.get_absolute_url()) for p in _ancestors(page)] + [(page.title, page.get_absolute_url())],
    })


def _site_mobile():
    from core.models import SiteSettings

    s = SiteSettings.load()
    return s.mobile or s.phone or ""


def _ancestors(page):
    out, node = [], page.parent
    while node is not None and len(out) < 10:
        out.insert(0, node)
        node = node.parent
    return out
