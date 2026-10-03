import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from core import seo

from .models import BlogCategory, BlogTag, Post


def _paged(request, qs, page, path, meta, heading, intro="", crumbs=()):
    page = int(page or 1)
    paginator = Paginator(qs.select_related("image"), settings.POSTS_PER_PAGE)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
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
    return _paged(request, Post.objects.published(), page, "/blog/", {"kind": "home"}, "مجله ایران کارپت",
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
        "author": {"@type": "Organization", "name": "ایران کارپت"},
        "publisher": {"@type": "Organization", "name": "ایران کارپت"},
    }
    return render(request, "blog/post_detail.html", {
        "meta": seo.build(post, "post"), "post": post, "crumbs": crumbs, "related": related,
        "comments": post.comments.filter(is_approved=True, parent=None).prefetch_related("replies"),
        "jsonld": json.dumps(jsonld, ensure_ascii=False),
    })


def page_detail(request, page):
    if page.status != "publish" and not request.user.is_staff:
        raise Http404
    return render(request, "blog/page_detail.html", {
        "meta": seo.build(page, "page"), "page": page,
        "crumbs": [(p.title, p.get_absolute_url()) for p in _ancestors(page)] + [(page.title, page.get_absolute_url())],
    })


def _ancestors(page):
    out, node = [], page.parent
    while node is not None and len(out) < 10:
        out.insert(0, node)
        node = node.parent
    return out
