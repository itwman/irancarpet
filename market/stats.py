"""آمار پنل فروشنده: بازدید ویترین و کالاها، فروش و سفارش روزانه، پربازدیدها و پرفروش‌ها.

بازدید فقط بازدید انسانی است (همان فیلتر ربات آمار سایت). روزهای خلاصه‌شده از جدول‌های روزانه و امروز از ریز بازدیدها.
"""
from collections import defaultdict
from datetime import timedelta

import jdatetime
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from catalog.models import Product
from shop.models import OrderItem

from .models import SellerOrder

RANGES = (7, 30, 90)
SOLD = Q(status__in=[SellerOrder.Status.NEW, SellerOrder.Status.ACCEPTED, SellerOrder.Status.SHIPPED, SellerOrder.Status.DELIVERED])


def _days(n, today=None):
    today = today or timezone.localdate()
    return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]


def _store_path(seller):
    return f"/vendor/{seller.slug}/"


def views_by_day(seller, days):
    """{روز: {"store": بازدید ویترین، "products": بازدید صفحهٔ کالاها}}"""
    from stats.models import DailyPage, DailyProduct, Hit, RolledDay

    start = days[0]
    pids = list(Product.objects.filter(seller=seller).values_list("pk", flat=True))
    rolled = set(RolledDay.objects.filter(day__gte=start).values_list("day", flat=True))
    out = defaultdict(lambda: {"store": 0, "products": 0})
    path = _store_path(seller)
    if pids:
        for r in DailyProduct.objects.filter(day__gte=start, day__in=rolled, product_id__in=pids).values("day").annotate(n=Sum("views")):
            out[r["day"]]["products"] += r["n"] or 0
    for r in DailyPage.objects.filter(day__gte=start, day__in=rolled, path__startswith=path).values("day").annotate(n=Sum("views")):
        out[r["day"]]["store"] += r["n"] or 0
    live = Hit.objects.filter(day__gte=start, kind="v").exclude(day__in=rolled)
    for r in live.filter(path__startswith=path).values("day").annotate(n=Count("pk")):
        out[r["day"]]["store"] += r["n"]
    if pids:
        for r in live.filter(product_id__in=pids).values("day").annotate(n=Count("pk")):
            out[r["day"]]["products"] += r["n"]
    return out


def sales_by_day(seller, start):
    rows = (seller.orders.filter(SOLD, paid_at__isnull=False, paid_at__date__gte=start)
            .annotate(d=TruncDate("paid_at", tzinfo=timezone.get_current_timezone()))
            .values("d").annotate(n=Count("pk"), t=Sum("items_total"), net=Sum("seller_amount")))
    return {r["d"]: r for r in rows}


def series(seller, n=30):
    days = _days(n)
    views = views_by_day(seller, days)
    sales = sales_by_day(seller, days[0])
    out = []
    for d in days:
        v, s = views.get(d, {"store": 0, "products": 0}), sales.get(d, {})
        jd = jdatetime.date.fromgregorian(date=d)
        out.append({"day": d, "label": f"{jd.day} {jd.j_months_fa[jd.month - 1]}", "short": str(jd.day),
                    "views": v["store"] + v["products"], "store": v["store"], "products": v["products"],
                    "orders": s.get("n") or 0, "sales": s.get("t") or 0, "net": s.get("net") or 0})
    return out


def chart(rows, key, height=120):
    """ستون‌های نمودار: هر ستون با درصد ارتفاع (برای CSS) و برچسب‌های کم‌شمار زیر محور."""
    top = max([r[key] for r in rows] + [0])
    step = max(1, len(rows) // 7)
    bars = []
    for i, r in enumerate(rows):
        val = r[key]
        bars.append({"pct": round(val * 100 / top) if top else 0, "val": val, "label": r["label"],
                     "tick": r["short"] if (len(rows) - 1 - i) % step == 0 else "", "last": i == len(rows) - 1})
    return {"bars": bars, "top": top, "key": key}


def summary(seller, n=30):
    rows = series(seller, n * 2)
    cur, prev = rows[n:], rows[:n]

    def tot(rs, k):
        return sum(r[k] for r in rs)

    def change(a, b):
        if not b:
            return None
        return round((a - b) * 100 / b)

    data = {}
    for k in ("views", "store", "products", "orders", "sales", "net"):
        a, b = tot(cur, k), tot(prev, k)
        data[k] = {"value": a, "change": change(a, b)}
    v, o = data["views"]["value"], data["orders"]["value"]
    data["conversion"] = round(o * 1000 / v) / 10 if v else None  # ٪ سفارش به ازای بازدید
    return cur, data


def top_viewed(seller, n=30, limit=8):
    from stats.models import DailyProduct, Hit, RolledDay

    start = timezone.localdate() - timedelta(days=n - 1)
    pids = list(Product.objects.filter(seller=seller).values_list("pk", flat=True))
    if not pids:
        return []
    rolled = set(RolledDay.objects.filter(day__gte=start).values_list("day", flat=True))
    cnt = defaultdict(int)
    for r in DailyProduct.objects.filter(day__in=rolled, product_id__in=pids).values("product_id").annotate(n=Sum("views")):
        cnt[r["product_id"]] += r["n"] or 0
    for r in (Hit.objects.filter(day__gte=start, kind="v", product_id__in=pids).exclude(day__in=rolled)
              .values("product_id").annotate(n=Count("pk"))):
        cnt[r["product_id"]] += r["n"]
    best = sorted(cnt.items(), key=lambda x: -x[1])[:limit]
    prods = {p.pk: p for p in Product.objects.filter(pk__in=[k for k, _ in best]).select_related("image")}
    return [{"product": prods[k], "views": v} for k, v in best if k in prods]


def top_sold(seller, n=30, limit=8):
    since = timezone.now() - timedelta(days=n)
    rows = (OrderItem.objects.filter(seller_order__seller=seller, seller_order__paid_at__gte=since)
            .exclude(seller_order__status__in=[SellerOrder.Status.WAITING, SellerOrder.Status.CANCELLED])
            .exclude(product=None)
            .values("product_id").annotate(q=Sum("quantity")).order_by("-q")[:limit])
    prods = {p.pk: p for p in Product.objects.filter(pk__in=[r["product_id"] for r in rows]).select_related("image")}
    return [{"product": prods[r["product_id"]], "qty": r["q"]} for r in rows if r["product_id"] in prods]


def followers_new(seller, n=7):
    return seller.followers.filter(created_at__gte=timezone.now() - timedelta(days=n)).count()
