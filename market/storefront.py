"""ویترین عمومی هر فروشگاه: کارنامه، قفسه‌ها، فرصت‌های ویژه، نظر خریداران.

همهٔ عددهای کارنامه از دادهٔ واقعی ساخته می‌شوند و هر کدام فقط وقتی نشان داده می‌شود که نمونهٔ کافی داشته باشد
(مثلاً امتیاز با کمتر از ۳ نظر نمی‌آید)، تا فروشگاه تازه با عددهای گمراه‌کننده دیده نشود.
"""
import statistics
from datetime import timedelta

from django.db.models import Avg, Count, Q

from catalog.models import Product, Review

from .models import SellerOrder

MIN_RATINGS = 3
MIN_ORDERS = 5
INDEX_MIN_PRODUCTS = 3  # فروشگاه کم‌کالا برای گوگل noindex است (صفحهٔ کم‌محتوا)


def published(seller):
    return Product.objects.published().filter(seller=seller)


def metrics(seller):
    """[{value, unit, label}] کارنامهٔ فروشگاه."""
    out = []
    r = (Review.objects.filter(product__seller=seller, kind="review", is_approved=True, parent__isnull=True, rating__isnull=False)
         .aggregate(avg=Avg("rating"), n=Count("pk")))
    if r["n"] and r["n"] >= MIN_RATINGS:
        out.append({"key": "rating", "value": round(r["avg"], 1), "unit": "از ۵", "label": f"امتیاز خریداران ({r['n']} نظر)"})
    delivered = seller.orders.filter(status=SellerOrder.Status.DELIVERED).count()
    if delivered:
        out.append({"key": "delivered", "value": delivered, "unit": "", "label": "سفارش تحویل‌شده"})
    shipped = list(seller.orders.filter(shipped_at__isnull=False, paid_at__isnull=False).values_list("paid_at", "shipped_at")[:500])
    if len(shipped) >= MIN_ORDERS:
        limit = timedelta(days=seller.prep_days + 2)  # روزهای کاری ← تقویمی با دو روز تعطیل
        ok = sum(1 for p, s in shipped if s - p <= limit)
        out.append({"key": "ontime", "value": round(ok * 100 / len(shipped)), "unit": "٪", "label": "ارسال سر وقت"})
    accepted = [(a - p).total_seconds() / 3600 for p, a in
                seller.orders.filter(accepted_at__isnull=False, paid_at__isnull=False).values_list("paid_at", "accepted_at")[:500]]
    if len(accepted) >= MIN_ORDERS:
        h = statistics.median(accepted)
        out.append({"key": "accept", "value": max(1, round(h)), "unit": "ساعت", "label": "میانهٔ زمان پذیرش سفارش"})
    return out


def shelves(seller):
    """قفسه‌هایی که دست‌کم یک کالای منتشرشده دارند، با تعداد."""
    rows = (seller.shelves.annotate(n=Count("products", filter=Q(products__status="publish"), distinct=True))
            .filter(n__gt=0).order_by("order", "pk"))
    return list(rows)


def offers(seller):
    from shop.offers import live_offers

    return [o for o in live_offers(sellers=True) if o.product.seller_id == seller.pk and o.price]


def reviews(seller, limit=6):
    return list(Review.objects.filter(product__seller=seller, kind="review", is_approved=True, parent__isnull=True)
                .select_related("product").order_by("-created_at")[:limit])


SORTS = [("new", "تازه‌ترین", ("-published_at", "-pk")), ("popular", "پربازدیدترین", ("-views", "-pk")),
         ("cheap", "ارزان‌ترین", ("min_price", "pk")), ("expensive", "گران‌ترین", ("-min_price", "pk"))]


def product_queryset(seller, shelf=None, sort="new"):
    from catalog.views import card_queryset

    qs = published(seller)
    if shelf is not None:
        qs = qs.filter(shelves=shelf)
    order = dict((k, o) for k, _, o in SORTS).get(sort, SORTS[0][2])
    if sort in ("cheap", "expensive"):
        qs = qs.exclude(min_price=None)
    return card_queryset(qs.order_by(*order))


def store_jsonld(seller, request, metrics_rows):
    from django.conf import settings

    site = settings.SITE_URL
    data = {
        "@context": "https://schema.org", "@type": "Store", "name": seller.name, "url": site + seller.get_absolute_url(),
        "address": {"@type": "PostalAddress", "addressLocality": seller.city, "addressRegion": seller.province or None, "addressCountry": "IR"},
    }
    if seller.tagline or seller.about:
        data["description"] = (seller.tagline or seller.about)[:300]
    if seller.logo_id:
        data["logo"] = site + seller.logo.url
        data["image"] = site + (seller.cover.url if seller.cover_id else seller.logo.url)
    rating = next((m for m in metrics_rows if m["key"] == "rating"), None)
    if rating:
        n = Review.objects.filter(product__seller=seller, kind="review", is_approved=True, parent__isnull=True, rating__isnull=False).count()
        data["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating["value"], "reviewCount": n, "bestRating": 5}
    data["address"] = {k: v for k, v in data["address"].items() if v}
    return data
