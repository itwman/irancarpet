"""گزارش‌های پنل: بازدید و منبع ورود، و بازخورد هر کمپین پیامکی.

روزهای نزدیک (LIVE_DAYS روز اخیر) از ریز بازدیدها (Hit) و روزهای قدیمی‌تر از جدول‌های روزانه خوانده می‌شوند.
نتیجه ۱۰ دقیقه کش می‌شود تا باز کردن پنل بار سرور نشود.
"""
from collections import defaultdict

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import SRC_LABELS, DailyPage, DailyProduct, DailyStat, DailyTotal, Hit
from .sources import medium_label

LIVE_DAYS = 40
V, C, O = Q(kind="v"), Q(kind="c"), Q(kind="o")
CACHE_SECONDS = 600


def split(start, end):
    """[start, end] ← (بازهٔ جدول‌های روزانه، بازهٔ ریز)"""
    boundary = timezone.localdate() - timezone.timedelta(days=LIVE_DAYS)
    old = (start, min(end, boundary - timezone.timedelta(days=1))) if start < boundary else None
    live = (max(start, boundary), end) if end >= boundary else None
    return old, live


def _pct(a, b):
    return round(a * 100 / b) if b else 0


def _rate(a, b):
    """درصد با یک رقم اعشار (برای نرخ تبدیل که معمولاً زیر ۵٪ است)."""
    if not b:
        return 0
    v = round(a * 100 / b, 1)
    return int(v) if v == int(v) else v


def _placed():
    from shop.coupons import PLACED

    return PLACED


def traffic(start, end):
    key = f"stats:traffic:{start}:{end}"
    out = cache.get(key)
    if out is None:
        out = _traffic(start, end)
        cache.set(key, out, CACHE_SECONDS if end < timezone.localdate() else 120)
    return out


def _traffic(start, end):
    from catalog.models import Product
    from shop.models import Order, OrderItem

    old, live = split(start, end)
    t = dict(views=0, visits=0, visitors=0, new_visitors=0, mobile=0, carts=0, orders=0)
    days = defaultdict(lambda: {"views": 0, "visits": 0, "visitors": 0})
    src = defaultdict(lambda: {"views": 0, "visits": 0, "visitors": 0, "carts": 0, "orders_hit": 0})
    utm = defaultdict(lambda: {"visits": 0, "views": 0, "carts": 0})
    pages = defaultdict(lambda: {"views": 0, "visitors": 0, "entries": 0})
    prods = defaultdict(lambda: {"views": 0, "visitors": 0, "carts": 0})
    if old:
        for r in DailyTotal.objects.filter(day__range=old):
            for k in t:
                t[k] += getattr(r, k)
            days[r.day].update(views=r.views, visits=r.visits, visitors=r.visitors)
        for r in DailyStat.objects.filter(day__range=old):
            s = src[(r.src, r.src_name)]
            s["views"] += r.views
            s["visits"] += r.visits
            s["visitors"] += r.visitors
            s["carts"] += r.carts
            s["orders_hit"] += r.orders
            if r.src == "utm":
                u = utm[(r.src_name, r.medium, r.utm_campaign)]
                u["visits"] += r.visits
                u["views"] += r.views
                u["carts"] += r.carts
        for r in DailyPage.objects.filter(day__range=old).values("path").annotate(v=Sum("views"), u=Sum("visitors"), e=Sum("entries")):
            p = pages[r["path"]]
            p["views"] += r["v"]
            p["visitors"] += r["u"]
            p["entries"] += r["e"]
        for r in DailyProduct.objects.filter(day__range=old).values("product_id").annotate(v=Sum("views"), u=Sum("visitors"), c=Sum("carts")):
            p = prods[r["product_id"]]
            p["views"] += r["v"]
            p["visitors"] += r["u"]
            p["carts"] += r["c"]
    if live:
        qs = Hit.objects.filter(day__range=live)
        a = qs.aggregate(views=Count("pk", filter=V), visits=Count("pk", filter=V & Q(entry=True)),
                         visitors=Count("visitor", filter=V, distinct=True),
                         new_visitors=Count("visitor", filter=V & Q(new=True), distinct=True),
                         mobile=Count("pk", filter=V & Q(device="m")), carts=Count("pk", filter=C), orders=Count("pk", filter=O))
        for k in t:
            t[k] += a[k] or 0
        for r in qs.filter(V).values("day").annotate(views=Count("pk"), visits=Count("pk", filter=Q(entry=True)),
                                                     visitors=Count("visitor", distinct=True)):
            days[r["day"]].update(views=r["views"], visits=r["visits"], visitors=r["visitors"])
        for r in qs.values("src", "src_name").annotate(views=Count("pk", filter=V), visits=Count("pk", filter=V & Q(entry=True)),
                                                       visitors=Count("visitor", filter=V, distinct=True),
                                                       carts=Count("pk", filter=C), orders=Count("pk", filter=O)):
            s = src[(r["src"], r["src_name"])]
            s["views"] += r["views"]
            s["visits"] += r["visits"]
            s["visitors"] += r["visitors"]
            s["carts"] += r["carts"]
            s["orders_hit"] += r["orders"]
        for r in qs.filter(src="utm").values("src_name", "medium", "utm_campaign").annotate(
                views=Count("pk", filter=V), visits=Count("pk", filter=V & Q(entry=True)), carts=Count("pk", filter=C)):
            u = utm[(r["src_name"], r["medium"], r["utm_campaign"])]
            u["visits"] += r["visits"]
            u["views"] += r["views"]
            u["carts"] += r["carts"]
        for r in qs.filter(V).values("path").annotate(v=Count("pk"), u=Count("visitor", distinct=True),
                                                      e=Count("pk", filter=Q(entry=True))).order_by("-v")[:300]:
            p = pages[r["path"]]
            p["views"] += r["v"]
            p["visitors"] += r["u"]
            p["entries"] += r["e"]
        for r in qs.exclude(product_id=None).values("product_id").annotate(
                v=Count("pk", filter=V), u=Count("visitor", filter=V, distinct=True), c=Count("pk", filter=C)):
            p = prods[r["product_id"]]
            p["views"] += r["v"]
            p["visitors"] += r["u"]
            p["carts"] += r["c"]

    # فروش هر منبع از خود سفارش‌ها (وضعیت امروز سفارش، نه لحظهٔ ثبت)
    orders = Order.objects.filter(created_at__date__range=(start, end), status__in=_placed())
    by_src = {(r["src"] or "", r["src_name"] or ""): r for r in orders.values("src", "src_name").annotate(n=Count("pk"), s=Sum("items_total"))}
    rows = []
    for (s, name), v in src.items():
        o = by_src.pop((s, name), {"n": 0, "s": 0})
        rows.append({"src": s, "label": SRC_LABELS.get(s, s), "name": name, **v, "orders": o["n"], "revenue": o["s"] or 0,
                     "conv": _rate(o["n"], v["visits"])})
    for (s, name), o in by_src.items():  # سفارش‌هایی که بازدیدشان در بازه نبود (یا پیش از راه‌اندازی آمار)
        rows.append({"src": s or "unknown", "label": SRC_LABELS.get(s, "پیش از راه‌اندازی آمار" if not s else s), "name": name,
                     "views": 0, "visits": 0, "visitors": 0, "carts": 0, "orders_hit": 0, "orders": o["n"], "revenue": o["s"] or 0,
                     "conv": 0})
    rows.sort(key=lambda r: (-r["visits"], -r["revenue"]))
    groups = defaultdict(lambda: {"visits": 0, "orders": 0, "revenue": 0})
    for r in rows:
        g = groups[(r["src"], r["label"])]
        g["visits"] += r["visits"]
        g["orders"] += r["orders"]
        g["revenue"] += r["revenue"]
    total_visits = sum(g["visits"] for g in groups.values())
    group_rows = sorted(({"src": k[0], "label": k[1], **g, "share": _pct(g["visits"], total_visits)} for k, g in groups.items()),
                        key=lambda g: (-g["visits"], -g["revenue"]))

    # روزانه (برای نمودار)
    series, d = [], start
    peak = max([v["visits"] for v in days.values()] or [0]) or 1
    while d <= end:
        v = days.get(d, {"views": 0, "visits": 0, "visitors": 0})
        series.append({"day": d, **v, "h": round(v["visits"] * 100 / peak)})
        d += timezone.timedelta(days=1)

    top_prods = sorted(prods.items(), key=lambda kv: -kv[1]["views"])[:30]
    titles = {p.pk: p for p in Product.objects.filter(pk__in=[k for k, _ in top_prods]).only("title", "slug")}
    sold = {r["product_id"]: r["n"] for r in OrderItem.objects.filter(
        order__created_at__date__range=(start, end), order__status__in=_placed(),
        product_id__in=[k for k, _ in top_prods]).values("product_id").annotate(n=Sum("quantity"))}
    product_rows = [{"p": titles.get(pid), "pid": pid, **v, "sold": sold.get(pid, 0), "cart_rate": _pct(v["carts"], v["visitors"])}
                    for pid, v in top_prods]
    utm_rows = sorted(({"source": k[0], "medium": k[1], "medium_label": medium_label(k[1]), "campaign": k[2], **v}
                       for k, v in utm.items()), key=lambda r: -r["visits"])
    utm_orders = {(r["src_name"], r["utm_campaign"]): r for r in orders.filter(src="utm").values("src_name", "utm_campaign")
                  .annotate(n=Count("pk"), s=Sum("items_total"))}
    for r in utm_rows:
        o = utm_orders.get((r["source"], r["campaign"]), {"n": 0, "s": 0})
        r["orders"], r["revenue"] = o["n"], o["s"] or 0
    page_rows = sorted(({"path": k, **v} for k, v in pages.items()), key=lambda r: -r["views"])[:40]
    revenue = orders.aggregate(n=Count("pk"), s=Sum("items_total"))
    return {
        "t": {**t, "mobile_pct": _pct(t["mobile"], t["views"]), "new_pct": _pct(t["new_visitors"], t["visitors"]),
              "pages_per_visit": round(t["views"] / t["visits"], 1) if t["visits"] else 0,
              "orders_placed": revenue["n"], "revenue": revenue["s"] or 0, "conv": _rate(revenue["n"], t["visits"])},
        "series": series, "groups": group_rows, "sources": rows[:60], "utm": utm_rows[:40], "pages": page_rows,
        "products": product_rows, "referrals": [r for r in rows if r["src"] == "referral"][:30],
        "approx_visitors": bool(old),
    }


# ------------------------------------------------------------------ کمپین پیامکی
def campaign(c):
    key = f"stats:camp:{c.pk}:{c.sent}"
    out = cache.get(key)
    if out is None:
        out = _campaign(c)
        cache.set(key, out, CACHE_SECONDS)
    return out


def _campaign(c):
    from accounts.models import Profile
    from crm.campaigns import link_target, results
    from crm.contact import sms_parts
    from crm.models import ShortLink, SmsLog
    from shop.models import Order

    start = c.started_at or c.created_at
    week = start + timezone.timedelta(days=7)
    logs = SmsLog.objects.filter(campaign=c)
    ok = set(logs.filter(ok=True).values_list("mobile", flat=True))
    failed = logs.filter(ok=False).values("mobile").distinct().count()
    parts = sum(sms_parts(t) for t in logs.filter(ok=True).values_list("text", flat=True)[:20000])
    placed = _placed()
    from crm.segments import customers

    buyers_before = {m for m, x in customers().items() if m in ok and x.get("first") and x["first"] < start}
    links = {link.mobile: link for link in ShortLink.objects.filter(campaign=c)}
    personal = bool(links)
    clicked = {m for m, link in links.items() if link.clicks}
    shared_hits = 0
    if not personal and ("{link}" in (c.text or "") or c.offer_id):
        try:
            target = link_target(c)
            shared_hits = sum(ShortLink.objects.filter(campaign__isnull=True, target=target,
                                                       created_at__lte=week).values_list("hits", flat=True))
        except Exception:  # noqa: BLE001
            shared_hits = 0

    # بازدیدها پس از کلیک
    days_old = DailyStat.objects.filter(campaign_id=c.pk).aggregate(v=Sum("views"), s=Sum("visits"), cart=Sum("carts"))
    live = Hit.objects.filter(campaign_id=c.pk, day__gte=timezone.localdate() - timezone.timedelta(days=LIVE_DAYS))
    rolled_live = DailyStat.objects.filter(campaign_id=c.pk, day__gte=timezone.localdate() - timezone.timedelta(days=LIVE_DAYS))
    rl = rolled_live.aggregate(v=Sum("views"), s=Sum("visits"), cart=Sum("carts"))
    lv = live.aggregate(v=Count("pk", filter=V), s=Count("pk", filter=V & Q(entry=True)), cart=Count("pk", filter=C),
                        prod=Count("pk", filter=V & Q(product_id__isnull=False)))
    views = (days_old["v"] or 0) - (rl["v"] or 0) + lv["v"]
    visits = (days_old["s"] or 0) - (rl["s"] or 0) + lv["s"]
    carts = (days_old["cart"] or 0) - (rl["cart"] or 0) + lv["cart"]

    attributed = Order.objects.filter(sms_campaign_id=c.pk, status__in=placed)
    att = attributed.aggregate(n=Count("pk"), s=Sum("items_total"))
    att_pending = Order.objects.filter(sms_campaign_id=c.pk).exclude(status__in=placed).count()
    week_orders = Order.objects.filter(mobile__in=ok, created_at__gte=start, created_at__lt=week, status__in=placed)
    wk = week_orders.aggregate(n=Count("pk"), s=Sum("items_total"))
    week_buyers = set(week_orders.values_list("mobile", flat=True))
    code_n, code_sum = results(c) if c.discount else (0, 0)

    def seg(ms):
        n = len(ms)
        cl = len(ms & clicked)
        b = len(ms & week_buyers)
        return {"n": n, "clicked": cl, "click_rate": _rate(cl, n), "bought": b, "buy_rate": _rate(b, n)}

    names = {p.mobile: (p.user.get_full_name() if p.user_id else "") for p in
             Profile.objects.filter(mobile__in=list(clicked | week_buyers)[:3000]).select_related("user")}
    order_names = {o["mobile"]: f'{o["first_name"]} {o["last_name"]}'.strip() for o in
                   Order.objects.filter(mobile__in=list(clicked | week_buyers)[:3000]).values("mobile", "first_name", "last_name")}
    people = []
    for m in sorted(clicked | week_buyers, key=lambda m: (m not in week_buyers, -(links[m].clicks if m in links else 0)))[:300]:
        link = links.get(m)
        people.append({"mobile": m, "name": names.get(m) or order_names.get(m) or "", "clicks": link.clicks if link else 0,
                       "first": link.first_click_at if link else None, "bought": m in week_buyers, "old": m in buyers_before})
    return {
        "sent": len(ok), "failed": failed, "parts": parts, "personal": personal, "shared_hits": shared_hits,
        "clicked": len(clicked), "click_rate": _rate(len(clicked), len(ok)), "views": views, "visits": visits, "carts": carts,
        "att_orders": att["n"], "att_sum": att["s"] or 0, "att_pending": att_pending,
        "week_orders": wk["n"], "week_sum": wk["s"] or 0, "week_buyers": len(week_buyers), "week_until": week,
        "code_orders": code_n, "code_sum": code_sum,
        "old": seg(ok & buyers_before), "new": seg(ok - buyers_before), "people": people,
        "funnel": [("پیامک رسیده به sms.ir", len(ok)), ("کلیک (بدون ربات)", len(clicked)), ("افزودن به سبد", carts),
                   ("خرید پس از کلیک", att["n"])] if personal else [],
    }
