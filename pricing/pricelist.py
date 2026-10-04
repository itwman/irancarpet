"""داده‌های صفحهٔ عمومی «لیست قیمت فرش ماشینی» (از روی آلبوم‌های قیمت)."""
from django.core.cache import cache
from django.db.models import Count, Max, Q

from core.templatetags.fa import reeds_of

from .models import Album, Size

PRICE_LIST_PATH = "/carpets-price-list/"
SHORTCODE = "[icap_price_list]"
CACHE_SECONDS = 600

JALALI_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def albums_qs():
    """آلبوم‌هایی که در لیست قیمت نمایش داده می‌شوند (فعال، با قیمت و دست‌کم یک فرش منتشرشده)."""
    return (
        Album.objects.filter(is_active=True, in_price_list=True, base_price__gt=0)
        .annotate(n=Count("products", filter=Q(products__status="publish"), distinct=True))
        .filter(n__gt=0)
        .select_related("base_size")
        .prefetch_related("sizes", "even_sizes")
    )


GEN_KEY = "pricelist:gen"


def bump(*args, **kwargs):
    """با هر تغییر آلبوم، سایز یا محصول، کش لیست قیمت کهنه می‌شود."""
    try:
        cache.incr(GEN_KEY)
    except ValueError:
        cache.set(GEN_KEY, 1, None)


def _version():
    agg = Album.objects.aggregate(t=Max("last_updated"), n=Count("id"))
    return f"{cache.get(GEN_KEY, 0)}:{agg['t'] and agg['t'].timestamp()}:{agg['n']}"


def _sizes():
    return list(Size.objects.filter(is_active=True).exclude(type="custom").order_by("sort_order", "pk"))


def album_rows(album, sizes=None):
    """قیمت تک‌تک سایزهای یک آلبوم: [{size, price, per_m2, pair_only}] به ترتیب سایزها."""
    sizes = sizes if sizes is not None else _sizes()
    even = {s.pk for s in album.even_sizes.all()}
    rows = []
    for s in sizes:
        if not album.offers(s):
            continue
        price = album.size_price(s)
        if not price:
            continue
        rows.append({
            "size": s, "price": price, "pair_only": s.pk in even,
            "per_m2": int(round(price / float(s.area))) if s.area else 0,
        })
    return rows


def _album_reeds(album):
    r = reeds_of(album.title) or reeds_of(album.name)
    if r:
        return r
    from catalog.models import AttributeTerm

    term = (AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", products__album=album)
            .annotate(c=Count("products")).order_by("-c").first())
    return term.slug if term and term.slug.isdigit() else ""


def build():
    """گروه‌های لیست قیمت بر اساس شانه، با جدول قیمت هر آلبوم (۱۰ دقیقه کش)."""
    key = f"pricelist:{_version()}"
    data = cache.get(key)
    if data is not None:
        return data
    sizes = _sizes()
    groups = {}
    updated = None
    for a in albums_qs():
        rows = album_rows(a, sizes)
        if not rows:
            continue
        base = next((r["price"] for r in rows if r["size"].pk == a.base_size_id), None)
        item = {
            "id": a.pk, "title": a.title, "url": a.get_absolute_url(), "company": a.company, "count": a.n,
            "base_price": base, "base_label": a.base_size.label, "min_price": min(r["price"] for r in rows),
            "prices": {r["size"].pk: r["price"] for r in rows}, "updated": a.last_updated, "order": a.sort_order,
        }
        reeds = _album_reeds(a)
        g = groups.setdefault(reeds, {"reeds": reeds, "albums": [], "size_ids": set()})
        g["albums"].append(item)
        g["size_ids"].update(item["prices"])
        if not updated or a.last_updated > updated:
            updated = a.last_updated
    out = []
    for reeds, g in sorted(groups.items(), key=lambda kv: (not kv[0], int(kv[0]) if kv[0].isdigit() else 0)):
        g["albums"].sort(key=lambda x: (x["order"], x["base_price"] or x["min_price"]))
        g["sizes"] = [s for s in sizes if s.pk in g["size_ids"]]
        for al in g["albums"]:
            al["cells"] = [al["prices"].get(s.pk) for s in g["sizes"]]
        bases = [x["base_price"] for x in g["albums"] if x["base_price"]]
        g.update(
            title=f"فرش {reeds} شانه" if reeds else "سایر فرش‌ها",
            anchor=f"reeds-{reeds}" if reeds else "others",
            min_base=min(bases) if bases else None, max_base=max(bases) if bases else None,
            count=sum(x["count"] for x in g["albums"]),
        )
        del g["size_ids"]
        out.append(g)
    data = {"groups": out, "updated": updated, "albums": sum(len(g["albums"]) for g in out),
            "products": sum(g["count"] for g in out)}
    cache.set(key, data, CACHE_SECONDS)
    return data


def month_year(dt=None):
    import jdatetime
    from django.utils import timezone

    from core.templatetags.fa import fa_num

    j = jdatetime.date.fromgregorian(date=timezone.localtime(dt or timezone.now()).date())
    return JALALI_MONTHS[j.month - 1], fa_num(j.year)
