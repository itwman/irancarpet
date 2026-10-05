import json

from django.conf import settings
from django.http import Http404

from catalog import views as catalog_views
from core.models import SiteSettings
from core.templatetags.fa import fa_num, toman
from pricing import pricelist

from . import build
from .models import LandingPage


def detail(request, slug, page=1):
    lp = LandingPage.objects.select_related("reeds", "size", "color", "style").filter(slug=slug).first()
    if lp is None or ((not lp.is_active or lp.count == 0) and not request.user.is_staff):
        raise Http404
    month, year = pricelist.month_year()
    when = f"{month} {year}"
    size_rows = build.size_table(lp)
    faqs = build.faq(lp, when, size_rows)
    s = SiteSettings.load()
    sep = s.title_separator or "-"
    title = lp.seo_title or f"قیمت و خرید {lp.title} {when} {sep} {s.site_name}"
    if lp.seo_description:
        desc = lp.seo_description
    else:
        desc = f"{lp.title}: {fa_num(lp.count)} طرح موجود"
        if lp.min_price:
            desc += f"، قیمت از {toman(lp.min_price)} تا {toman(lp.max_price)} تومان"
        desc += f" (به‌روز {when}). خرید مستقیم از کارخانه‌های کاشان، نقدی و اقساطی."
    meta = {"title": title, "description": desc}
    if lp.count < build.MIN_PRODUCTS or not lp.is_active:
        meta["robots"] = "noindex,follow"
    crumbs = [("فرش‌ها", "/store/"), (lp.title, lp.get_absolute_url())]
    related = []
    seen = {lp.pk}
    for kw in ({"reeds_id": lp.reeds_id} if lp.reeds_id else {}, {"size_id": lp.size_id} if lp.size_id else {},
               {"color_id": lp.color_id} if lp.color_id else {}):
        if kw:
            for x in build.links_for(**kw, limit=10):
                if x.pk not in seen:
                    seen.add(x.pk)
                    related.append(x)
    graph = [{
        "@type": "BreadcrumbList",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": settings.SITE_URL + u}
                            for i, (n, u) in enumerate([("خانه", "/"), *crumbs])],
    }]
    if lp.min_price:
        graph.append({"@type": "Product", "name": lp.title, "url": settings.SITE_URL + lp.get_absolute_url(),
                      "offers": {"@type": "AggregateOffer", "priceCurrency": "IRR", "lowPrice": lp.min_price * 10,
                                 "highPrice": lp.max_price * 10, "offerCount": lp.count}})
    if faqs:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faqs]})
    return catalog_views.product_listing(
        request, build.products_of(lp), page=page, path=lp.get_absolute_url(), meta={"kind": "custom", "override": meta},
        heading=lp.title, intro="", crumbs=crumbs, template="landing/detail.html",
        extra={"lp": lp, "lead": lp.intro or build.auto_intro(lp, when), "size_rows": size_rows, "faqs": faqs,
               "related": related[:24], "month": when,
               "jsonld": json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)},
    )


TOOL_SHORTCODE = "[size_tool]"


def size_tool(request, page):
    """برگهٔ «چه سایز فرشی برای اتاق من؟» (قالب size_tool)."""
    from pricing.models import Size

    if page.status != "publish" and not request.user.is_staff:
        raise Http404
    from core import seo

    links = {lp.size_id: lp for lp in build.live().filter(reeds=None, color=None, style=None, size__isnull=False)}
    sizes = []
    for s in Size.objects.filter(is_active=True, type__in=["rect", "runner"]).order_by("sort_order"):
        if not (s.width and s.length):
            continue
        lp = links.get(s.pk)
        sizes.append({"id": s.pk, "label": s.label, "w": float(s.width), "l": float(s.length), "type": s.type,
                      "url": lp.get_absolute_url() if lp else "", "lo": lp.min_price if lp else None, "hi": lp.max_price if lp else None})
    content = page.content or ""
    before, _, after = content.partition(TOOL_SHORTCODE) if TOOL_SHORTCODE in content else (content, "", "")
    faqs = [
        {"q": "فرش چقدر باید از دیوار فاصله داشته باشد؟",
         "a": "معمولاً ۳۰ تا ۶۰ سانتی‌متر از هر دیوار فاصله بگذارید تا کف اطراف فرش دیده شود و اتاق بزرگ‌تر به نظر برسد."},
        {"q": "برای پذیرایی ۵ در ۷ متر چه فرشی بخرم؟",
         "a": "یک جفت فرش ۱۲ متری (هرکدام ۳ در ۴) کنار هم سطحی ۴ در ۶ را می‌پوشاند و حدود نیم متر از هر دیوار فاصله می‌ماند؛ "
              "رایج‌ترین انتخاب برای پذیرایی‌های ایرانی است."},
        {"q": "فرش ۹ متری برای چه اتاقی مناسب است؟",
         "a": "فرش ۹ متری (۲٫۵ در ۳٫۵) برای اتاقی حدود ۳٫۲ در ۴٫۲ متر یا نشیمن کوچک مناسب است."},
    ]
    meta = seo.build(page, "page")
    graph = {"@context": "https://schema.org", "@graph": [
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                                            for f in faqs]},
        {"@type": "WebApplication", "name": page.title, "applicationCategory": "UtilitiesApplication", "operatingSystem": "All",
         "url": settings.SITE_URL + page.get_absolute_url(), "offers": {"@type": "Offer", "price": 0, "priceCurrency": "IRR"}},
    ]}
    from django.shortcuts import render

    return render(request, "landing/size_tool.html", {
        "meta": meta, "page": page, "before": before, "after": after, "faqs": faqs, "crumbs": [(page.title, page.get_absolute_url())],
        "sizes": sizes, "jsonld": json.dumps(graph, ensure_ascii=False),
    })
