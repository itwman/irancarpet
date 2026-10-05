"""نسخهٔ وب فرش‌یاب: /farsh-yab/"""
from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import Http404
from django.shortcuts import render

from catalog.views import card_queryset

from . import api, engine


def page(request):
    g = request.GET
    asked = any(g.get(k) for k in ("q", "needs", "size", "max"))
    from django.core.cache import cache

    cfg = cache.get("finder:config")
    if cfg is None:
        import json

        cfg = json.loads(api.config(request).content)
    chosen = {int(x) for x in (g.get("needs") or "").split(",") if x.strip().isdigit()}
    chosen |= {int(x) for x in g.getlist("n") if x.isdigit()}
    ctx = {"cfg": cfg, "chosen": chosen, "q": g.get("q", ""), "size": g.get("size", ""), "max": g.get("max", ""), "asked": asked,
           "meta": {"title": "فرش‌یاب ایران کارپت: فرش مناسب خودت را پیدا کن",
                    "description": "بگو چه فرشی می‌خواهی (ضخیم، قرمز، سنتی، ۶ متری زیر ۴۰ میلیون...) تا از بین فرش‌های ایران کارپت مناسب‌ترین‌ها را ببینی.",
                    "canonical": settings.SITE_URL + "/farsh-yab/", "robots": "noindex,follow" if asked else ""},
           "crumbs": [("فرش‌یاب", "/farsh-yab/")]}
    if asked:
        q = g.copy()
        if chosen:
            q["needs"] = ",".join(map(str, sorted(chosen)))
        wish = api.wish_from(q)
        qs, relaxed = engine.search(wish, g.get("sort", "best"))
        try:
            pnum = max(1, int(g.get("page", "1")))
        except ValueError:
            pnum = 1
        p = Paginator(card_queryset(qs), 24)
        try:
            items = list(p.page(pnum).object_list) if p.count else []
        except EmptyPage:
            raise Http404
        whys = engine.why([x.pk for x in items], wish.needs) if wish.needs else {}
        for x in items:
            x.why = "، ".join(whys.get(x.pk, []))
        prices = engine.size_prices([x.pk for x in items], wish.sizes)
        for x in items:
            if x.pk in prices:
                x.min_price = prices[x.pk]
        ctx.update(products=items, count=p.count, relaxed=relaxed, chips=wish.chips(), page_obj=p.page(pnum) if p.count else None,
                   size_label=wish.size_label)
        if g.get("q") and pnum == 1:
            from growth.search_log import log as log_search

            log_search(g["q"], "finder", 0 if relaxed else p.count)
    return render(request, "finder/page.html", ctx)
