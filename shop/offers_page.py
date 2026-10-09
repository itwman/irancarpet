"""صفحهٔ «فرصت‌های ویژهٔ خرید» (فرش جشنواره‌ای، زیر قیمت و استوک): همهٔ تک‌تخته‌های انبار با فیلتر سایز و شانه، مرتب‌سازی و صفحه‌بندی."""
import json
import re

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import redirect, render
from django.utils import timezone

from .offers import live_offers

PATH = "/فرش-جشنواره-ای/"
PER_PAGE = 24
SORTS = {"off": "بیشترین تخفیف", "soon": "زودتر تمام می‌شود", "cheap": "ارزان‌ترین", "new": "تازه‌ترین"}
FAQ = [
    ("فرش جشنواره‌ای یعنی چه؟",
     "فرش جشنواره‌ای همان فرش نو و درجه یکی است که برای مدت محدود یا تا تمام شدن موجودی با تخفیف فروخته می‌شود. "
     "در ایران کارپت این فرش‌ها تک‌تخته‌های موجود در انبار کاشان هستند که با قیمتی کمتر از قیمت روز همان سایز عرضه می‌شوند."),
    ("فرش زیر قیمت و استوک ایراد دارد؟",
     "نه. این فرش‌ها نو و بی‌استفاده‌اند. معمولاً از سفارش‌های لغوشده، تخته‌های باقی‌ماندهٔ یک جفت یا رنگ‌هایی که دیگر بافته "
     "نمی‌شوند به دست می‌آیند. برای همین فقط یک یا چند تخته از هر کدام هست."),
    ("فرق فرصت ویژه با فرش‌های لیست قیمت چیست؟",
     "فرش‌های لیست قیمت پس از سفارش بافته می‌شوند و حدود ۱۴ روز کاری زمان می‌برند. فرصت‌های ویژه آماده در انبارند و "
     "بلافاصله بسته‌بندی و ارسال می‌شوند."),
    ("چرا قیمت ویژه فقط برای تعداد مشخصی است؟",
     "از هر نقشه فقط همین چند تخته موجود است. اگر بیشتر از تعداد موجود بخواهید، بقیه با قیمت روز بافته می‌شوند."),
    ("تخفیف تا کی می‌ماند؟",
     "بعضی فرصت‌ها شمارندهٔ معکوس دارند و بعضی تا فروش آخرین تخته باقی‌اند. فرصت‌های پرطرفدار معمولاً چند روزه تمام می‌شوند."),
]


def _reeds(o):
    if not hasattr(o, "_reeds"):
        o._reeds = ""
        for t in o.product.specs.all():
            if t.attribute.slug == "reeds-per-meter":
                o._reeds = re.sub(r"\D", "", (t.name or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
                break
    return o._reeds


def _sorted(items, sort):
    far = timezone.now() + timezone.timedelta(days=3650)
    if sort == "soon":
        return sorted(items, key=lambda o: (o.ends_at or far, o.remaining))
    if sort == "cheap":
        return sorted(items, key=lambda o: o.price)
    if sort == "new":
        return sorted(items, key=lambda o: o.created_at, reverse=True)
    return sorted(items, key=lambda o: (-o.off_percent, o.price))


def offers_page(request):
    from django.db.models import Prefetch

    from catalog.models import AttributeTerm

    from .models import SpecialOffer

    offers = live_offers()
    ids = [o.pk for o in offers]
    terms = Prefetch("product__specs", queryset=AttributeTerm.objects.select_related("attribute"))
    by_id = {o.pk: o for o in SpecialOffer.objects.filter(pk__in=ids).select_related("product__image", "size").prefetch_related(terms)}
    offers = [by_id[o.pk] for o in offers if o.pk in by_id and o.is_live]

    sizes = sorted({(o.size.slug, o.size.label, o.size.sort_order) for o in offers}, key=lambda s: s[2])
    reeds = sorted({_reeds(o) for o in offers if _reeds(o)}, key=int)
    size, reed = request.GET.get("size", ""), request.GET.get("reeds", "")
    sort = request.GET.get("sort") if request.GET.get("sort") in SORTS else "off"
    items = [o for o in offers if (not size or o.size.slug == size) and (not reed or _reeds(o) == reed)]
    items = _sorted(items, sort)
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    pag = Paginator(items, PER_PAGE)
    try:
        page_obj = pag.page(page)
    except EmptyPage:
        return redirect(PATH)

    def url(**kw):
        q = {"size": size, "reeds": reed, "sort": "" if sort == "off" else sort, "page": ""}
        q.update(kw)
        qs = "&".join(f"{k}={v}" for k, v in q.items() if v and not (k == "page" and str(v) == "1"))
        return PATH + (f"?{qs}" if qs else "")

    site = settings.SITE_URL
    best = max((o.off_percent for o in offers), default=0)
    filtered = bool(size or reed or sort != "off")
    title = "فرش جشنواره‌ای و زیر قیمت؛ فرش استوک کاشان با تخفیف"
    meta = {
        "title": f"{title} | ایران کارپت" + (f" — صفحهٔ {page}" if page > 1 else ""),
        "description": (f"{len(offers)} فرش ماشینی نو و آمادهٔ ارسال از انبار کاشان با تا {best}٪ تخفیف: فرش جشنواره‌ای، زیر قیمت و استوک "
                        "۷۰۰ تا ۱۵۰۰ شانه. تعداد محدود، ارسال فوری.") if offers else
                       "فرش جشنواره‌ای، زیر قیمت و استوک ایران کارپت: تک‌تخته‌های نو و آمادهٔ ارسال انبار کاشان با تخفیف.",
        "canonical": site + (PATH if page == 1 else f"{PATH}?page={page}"),
        "robots": "noindex,follow" if filtered else "",
    }
    jsonld = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": title, "url": site + PATH, "inLanguage": "fa-IR",
         "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": [
             {"@type": "ListItem", "position": i + 1, "url": site + o.product.get_absolute_url(), "name": o.product.title}
             for i, o in enumerate(page_obj.object_list)]}},
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                                            for q, a in FAQ]},
    ]}
    return render(request, "shop/offers.html", {
        "meta": meta, "jsonld": json.dumps(jsonld, ensure_ascii=False), "crumbs": [("فرصت‌های ویژهٔ خرید", PATH)],
        "offers": page_obj.object_list, "page_obj": page_obj, "total": len(offers), "count": len(items), "best": best,
        "sizes": [(s, label, url(size="" if size == s else s, page="")) for s, label, _ in sizes], "size": size,
        "reeds_opts": [(r, url(reeds="" if reed == r else r, page="")) for r in reeds], "reed": reed,
        "sorts": [(k, v, url(sort="" if k == "off" else k, page="")) for k, v in SORTS.items()], "sort": sort,
        "clear_url": PATH if (size or reed) else "", "faq": FAQ, "first_page": page == 1 and not filtered,
        "prev_url": url(page=page - 1) if page_obj.has_previous() else "",
        "next_url": url(page=page + 1) if page_obj.has_next() else "",
        "page_links": [(n, url(page=n) if n != "…" else "") for n in pag.get_elided_page_range(page, on_each_side=2, on_ends=1)],
    })
