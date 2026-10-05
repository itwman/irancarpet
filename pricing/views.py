"""صفحهٔ عمومی «لیست قیمت فرش ماشینی» و صفحهٔ هر لیست (آلبوم)."""
import json

from django.conf import settings
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render

from catalog import views as catalog_views
from core import seo
from core.models import SiteSettings
from core.templatetags.fa import fa_num, toman

from . import pricelist
from .models import Album


def _ctx_vars():
    month, year = pricelist.month_year()
    return {"currentmonth": month, "currentyear": year, "currentdate": f"{month} {year}"}


def _crumb_ld(items):
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": settings.SITE_URL + url}
            for i, (name, url) in enumerate([("خانه", "/"), *items])
        ],
    }


def _faq(data, plans_text):
    """پرسش‌های متداول که خودشان از روی قیمت‌های روز ساخته می‌شوند."""
    out = []
    month, year = pricelist.month_year(data["updated"])
    for g in data["groups"]:
        if not g["min_base"] or not g["reeds"]:
            continue
        cheapest = min((a for a in g["albums"] if a["base_price"]), key=lambda a: a["base_price"])
        if g["min_base"] == g["max_base"]:
            ans = f"قیمت فرش ماشینی {fa_num(g['reeds'])} شانه ۱۲ متری در لیست قیمت {month} {year} ایران کارپت {toman(g['min_base'])} تومان است."
        else:
            ans = (f"در لیست قیمت {month} {year} ایران کارپت، فرش ماشینی {fa_num(g['reeds'])} شانه ۱۲ متری از "
                   f"{toman(g['min_base'])} تا {toman(g['max_base'])} تومان است. ارزان‌ترین آن «{fa_num(cheapest['title'])}» است.")
        out.append({"q": f"قیمت فرش {fa_num(g['reeds'])} شانه ۱۲ متری چند است؟", "a": ans})
    if data["updated"]:
        out.append({"q": "قیمت‌های این لیست به‌روز هستند؟",
                    "a": "بله. قیمت‌ها مستقیم از قیمت‌گذاری فروشگاه خوانده می‌شوند و با هر تغییر قیمت کارخانه همین صفحه هم عوض می‌شود. "
                         f"آخرین تغییر: {month} {year}."})
    out.append({"q": "قیمت سایزهای دیگر چطور حساب می‌شود؟",
                "a": "قیمت هر سایز به نسبت متراژ از قیمت ۱۲ متری همان لیست به دست می‌آید؛ برای ۹ متری (۲٫۵ × ۳٫۵) هزینهٔ پرتی هم اضافه می‌شود."})
    if plans_text:
        out.append({"q": "امکان خرید اقساطی فرش هست؟", "a": plans_text})
    return out


def price_list(request, page):
    """برگهٔ «لیست قیمت فرش ماشینی» (قالب price_list). متن برگه از پنل ویرایش می‌شود؛
    جای [icap_price_list] در متن، جدول‌ها قرار می‌گیرند (اگر نبود، بعد از مقدمه)."""
    if page.status != "publish" and not request.user.is_staff:
        raise Http404
    data = pricelist.build()
    content = page.content or ""
    if pricelist.SHORTCODE in content:
        before, _, after = content.partition(pricelist.SHORTCODE)
    else:
        before, after = content, ""
    plans_text, teaser = "", None
    try:
        from installments.services import faq_answer, teaser as inst_teaser

        plans_text = faq_answer()
        bases = [g["min_base"] for g in data["groups"] if g["min_base"]]
        teaser = inst_teaser(min(bases)) if bases else None
    except ImportError:
        pass
    faq = _faq(data, plans_text)
    vars_ = _ctx_vars()
    meta = seo.build(page, "page", extra=vars_)
    s = SiteSettings.load()
    if not page.seo_title:
        meta["title"] = f"{page.title} {vars_['currentdate']} {s.title_separator or '-'} {s.site_name}"
    if not page.seo_description or "[" in (page.seo_description or ""):
        bases = [g for g in data["groups"] if g["min_base"]]
        lo = min((g["min_base"] for g in bases), default=None)
        reeds = "، ".join(fa_num(g["reeds"]) for g in data["groups"] if g["reeds"])
        meta["description"] = (
            f"لیست قیمت فرش ماشینی کاشان، به‌روز {vars_['currentdate']}: قیمت {fa_num(data['albums'])} مدل فرش "
            f"{reeds} شانه در همهٔ سایزها" + (f"؛ ۱۲ متری از {toman(lo)} تومان" if lo else "")
            + ". خرید مستقیم از کارخانه، نقدی و اقساطی."
        )
    graph = [
        _crumb_ld([(page.title, page.get_absolute_url())]),
        {"@type": "ItemList", "name": page.title, "numberOfItems": data["albums"],
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": a["title"], "url": settings.SITE_URL + a["url"]}
                             for i, a in enumerate(a for g in data["groups"] for a in g["albums"])]},
    ]
    if faq:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in faq]})
    from landing.build import live

    size_links = list(live().filter(reeds=None, style=None).order_by("color_id", "-count")[:30])
    return render(request, "pricing/price_list.html", {
        "size_links": size_links,
        "meta": meta, "page": page, "data": data, "before": before, "after": after, "faq": faq, "teaser": teaser,
        "crumbs": [(page.title, page.get_absolute_url())], "month": vars_["currentdate"],
        "jsonld": json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False),
    })


def album_detail(request, slug, page=1):
    album = Album.objects.filter(slug=slug).select_related("base_size").first()
    if album is None:
        # نامک با حروف بزرگ/کوچک یا کد آلبوم
        album = Album.objects.filter(code__iexact=slug).first()
        if album and album.slug:
            return HttpResponsePermanentRedirect(album.get_absolute_url())
        raise Http404
    if not (album.is_active and album.in_price_list) and not request.user.is_staff:
        raise Http404
    from blog.models import Page

    list_page = Page.objects.filter(template="price_list").first()
    list_title = list_page.title if list_page else "لیست قیمت فرش ماشینی"
    rows = pricelist.album_rows(album)
    base = next((r["price"] for r in rows if r["size"].pk == album.base_size_id), None)
    vars_ = _ctx_vars()
    s = SiteSettings.load()
    sep = s.title_separator or "-"
    title = (seo.render(album.seo_title, {**vars_, "title": album.title, "sitename": s.site_name, "sep": sep})
             if album.seo_title else f"قیمت {album.title} {vars_['currentdate']} {sep} {s.site_name}")
    if album.seo_description:
        desc = seo.render(album.seo_description, {**vars_, "title": album.title, "sitename": s.site_name})
    else:
        sizes = "، ".join(f"{r['size'].label} {toman(r['price'])}" for r in rows[:4])
        desc = f"لیست قیمت {album.title} به‌روز {vars_['currentdate']}: {sizes} تومان. خرید مستقیم و اقساطی از ایران کارپت."
    teaser = None
    if base:
        try:
            from installments.services import teaser as inst_teaser

            teaser = inst_teaser(base)
        except ImportError:
            pass
    crumbs = [(list_title, pricelist.PRICE_LIST_PATH), (album.title, album.get_absolute_url())]
    graph = [_crumb_ld(crumbs)]
    meta = {"title": title, "description": seo.plain(desc, 300)}
    return catalog_views.product_listing(
        request, album.products.all(), page=page, path=album.get_absolute_url(),
        meta={"kind": "custom", "override": meta}, heading=f"لیست قیمت {album.title}", intro=album.list_intro,
        crumbs=crumbs, template="pricing/album_detail.html",
        extra={"album": album, "rows": rows, "base": base, "teaser": teaser, "month": vars_["currentdate"],
               "list_url": pricelist.PRICE_LIST_PATH,
               "jsonld": json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)},
    )
