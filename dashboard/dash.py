"""داده‌های پیشخوان: خلاصهٔ فروش، کارهای امروز، کمپین‌ها، مشتریان، فرش‌ها و بازدید.

اصل‌ها:
  - هر عدد با دورهٔ قبلِ هم‌اندازه مقایسه می‌شود.
  - محاسبه‌ها از همان کد گزارش‌های مفصل می‌آیند (stats.reports.traffic) تا دو نسخه از یک عدد نداشته باشیم.
  - همه‌چیز چند دقیقه کش می‌شود؛ بخش بازدید جدا و پس از باز شدن صفحه بار می‌شود.
  - اعداد مالی فقط برای مدیر کل (is_superuser) ساخته و نشان داده می‌شوند.
"""
from datetime import datetime, time, timedelta

import jdatetime
from django.core.cache import cache
from django.db.models import Count, F, Sum
from django.utils import timezone

from core.templatetags.fa import fa_num, jdate

PERIODS = [("today", "امروز"), ("7", "۷ روز"), ("30", "۳۰ روز"), ("month", "این ماه")]
DEFAULT = "7"
CACHE = 300


def period(key):
    """(کلید، برچسب، شروع، پایان، شروع قبلی، پایان قبلی، برچسب مقایسه) — تاریخ‌ها روز محلی و شامل دو سر."""
    key = key if key in dict(PERIODS) else DEFAULT
    today = timezone.localdate()
    if key == "today":
        s = e = today
        ps = pe = today - timedelta(days=1)
        vs = "نسبت به دیروز"
    elif key == "month":
        j = jdatetime.date.fromgregorian(date=today)
        s, e = jdatetime.date(j.year, j.month, 1).togregorian(), today
        n = (e - s).days
        pj = jdatetime.date(j.year - 1, 12, 1) if j.month == 1 else jdatetime.date(j.year, j.month - 1, 1)
        ps = pj.togregorian()
        pe = min(ps + timedelta(days=n), s - timedelta(days=1))
        vs = "نسبت به همین روزهای ماه قبل"
    else:
        n = int(key)
        s, e = today - timedelta(days=n - 1), today
        ps, pe = s - timedelta(days=n), s - timedelta(days=1)
        vs = f"نسبت به {fa_num(n)} روز قبل از آن"
    return {"key": key, "label": dict(PERIODS)[key], "start": s, "end": e, "pstart": ps, "pend": pe, "vs": vs,
            "days": (e - s).days + 1,
            "stats_key": "30" if key == "month" else key, "crm_days": 7 if key in ("today", "7") else 30}


def _at(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def _rng(s, e):
    return _at(s), _at(e + timedelta(days=1))


def delta(cur, prev):
    """تغییر درصدی برای نمایش ▲▼؛ None وقتی دورهٔ قبل صفر است."""
    if not prev:
        return None if not cur else {"new": True}
    p = round((cur - prev) * 100 / prev)
    return {"pct": abs(p), "up": p > 0, "down": p < 0, "flat": p == 0}


def short_money(n):
    """۴۵٫۲ میلیون / ۱٫۳ میلیارد برای کاشی‌ها"""
    n = int(n or 0)
    if n >= 1_000_000_000:
        v, u = n / 1_000_000_000, "میلیارد"
    elif n >= 1_000_000:
        v, u = n / 1_000_000, "میلیون"
    else:
        return fa_num(f"{n:,}".replace(",", "٬")), "تومان"
    s = f"{v:.1f}".rstrip("0").rstrip(".") if v < 100 else f"{v:.0f}"
    return fa_num(s.replace(".", "٫")), u


# ------------------------------------------------------------------ فروش
def _sales(s, e):
    from shop.coupons import PLACED
    from shop.models import Order, Payment

    a, b = _rng(s, e)
    placed = Order.objects.filter(created_at__gte=a, created_at__lt=b, status__in=PLACED)
    agg = placed.aggregate(n=Count("pk"), s=Sum("items_total"))
    paid = Payment.objects.filter(status="ok", verified_at__gte=a, verified_at__lt=b).aggregate(s=Sum("amount"))["s"] or 0
    n, total = agg["n"] or 0, agg["s"] or 0
    return {"orders": n, "sales": total, "received": paid, "avg": round(total / n) if n else 0}


def sales(p):
    key = f"dash:sales:{p['start']}:{p['end']}"
    out = cache.get(key)
    if out is None:
        cur, prev = _sales(p["start"], p["end"]), _sales(p["pstart"], p["pend"])
        out = {"cur": cur, "prev": prev, "d": {k: delta(cur[k], prev[k]) for k in cur}}
        cache.set(key, out, CACHE if p["key"] != "today" else 60)
    return out


def money_series(p):
    """فروش روزانهٔ دوره (برای نمودار مدیر)."""
    from shop.coupons import PLACED
    from shop.models import Order

    s, e = p["start"], p["end"]
    if p["key"] == "today":  # «امروز» یک ستون است؛ ۷ روز آخر نشان داده می‌شود
        s = e - timedelta(days=6)
    a, b = _rng(s, e)
    rows = {}
    for dt, amount in Order.objects.filter(created_at__gte=a, created_at__lt=b, status__in=PLACED).values_list("created_at", "items_total"):
        d = timezone.localtime(dt).date()
        rows[d] = rows.get(d, 0) + (amount or 0)
    return _bars(s, e, rows, lambda v: f"{fa_num(f'{v:,}'.replace(',', '٬'))} تومان")


def _bars(s, e, rows, tip):
    out, d = [], s
    mx = max(rows.values(), default=0) or 1
    today = timezone.localdate()
    while d <= e:
        v = rows.get(d, 0) or 0
        out.append({"day": d, "value": v, "h": round(v * 100 / mx, 1), "today": d == today,
                    "tip": f"{jdate(d, '%A %d %B')}: {tip(v)}"})
        d += timedelta(days=1)
    return out


# ------------------------------------------------------------------ کارهای امروز
def abandoned_carts(days=14):
    """سبدهای مشتریان واردشده که چند ساعت دست نخورده‌اند (سبد مهمان شماره ندارد و این‌جا نیست)."""
    from crm.models import CartSnapshot, CrmSettings

    now = timezone.now()
    hours = CrmSettings.load().cart_hours or 3
    return CartSnapshot.objects.filter(updated_at__lte=now - timedelta(hours=hours), updated_at__gte=now - timedelta(days=days),
                                       user__is_active=True, user__is_staff=False).exclude(data={})


def cart_value(snaps):
    from catalog.models import Variation

    vids = {int(k) for sn in snaps for k in (sn.data or {}) if str(k).isdigit()}
    price = {v.pk: v.price or 0 for v in Variation.objects.filter(pk__in=vids)}
    total = 0
    for sn in snaps:
        for k, q in (sn.data or {}).items():
            if str(k).isdigit():
                try:
                    total += price.get(int(k), 0) * int(q)
                except (TypeError, ValueError):
                    pass
    return total


def todo(manager):
    from blog.models import Comment
    from catalog.models import Product, Review
    from crm.models import ContactMessage
    from seo.models import NotFoundLog
    from shop.models import Order, SpecialOffer

    key = f"dash:todo:{int(manager)}"
    out = cache.get(key)
    if out is not None:
        return out
    now = timezone.now()
    pending = Order.objects.filter(status="pending", created_at__gte=now - timedelta(days=7))
    pend = pending.aggregate(n=Count("pk"), s=Sum("items_total"))
    carts = list(abandoned_carts())
    reminded = sum(1 for c in carts if c.reminded_at)
    offers_soon, offers_done = [], []
    for o in SpecialOffer.objects.filter(is_active=True, starts_at__lte=now).select_related("product", "size"):
        if o.ends_at and o.ends_at <= now:
            continue
        if o.remaining <= 0:
            offers_done.append(o)
        elif o.ends_at and o.ends_at - now < timedelta(hours=48):
            offers_soon.append(o)
    items = [
        {"label": "سفارش منتظر ارسال", "n": Order.objects.filter(status__in=["deposit_paid", "paid", "processing"]).count(),
         "url": "/panel/orders/?status=paid", "hot": True},
        {"label": "اقساطی منتظر بررسی", "n": Order.objects.filter(status="on_hold").count(), "url": "/panel/orders/?status=on_hold", "hot": True},
        {"label": "پرداخت‌نشده (۷ روز)", "n": pend["n"] or 0, "url": "/panel/orders/?status=pending",
         "sub": (f"{short_money(pend['s'])[0]} {short_money(pend['s'])[1]}" if manager and pend["s"] else "شاید نیاز به تماس")},
        {"label": "سبد رهاشده (۱۴ روز)", "n": len(carts), "url": "/panel/abandoned-carts/?age=14",
         "sub": "؛ ".join(x for x in [f"{fa_num(reminded)} پیامک یادآوری گرفته" if reminded else "",
                                      (lambda m: f"حدود {m[0]} {m[1]}")(short_money(cart_value(carts))) if manager and carts else ""] if x)},
        {"label": "پیام تازهٔ «تماس با ما»", "n": ContactMessage.objects.filter(status="new").count(), "url": "/panel/contact-messages/?status=new",
         "hot": True},
        {"label": "نظر منتظر تأیید", "n": Review.objects.filter(is_approved=False).count(), "url": "/panel/reviews/?is_approved=0"},
        {"label": "دیدگاه مجله منتظر تأیید", "n": Comment.objects.filter(is_approved=False).count(), "url": "/panel/comments/?is_approved=0"},
        {"label": "فرصت ویژهٔ رو به پایان (۴۸ ساعت)", "n": len(offers_soon), "url": "/panel/special-offers/?is_active=1",
         "sub": "، ".join(fa_num(o.product.title)[:40] for o in offers_soon[:2])},
        {"label": "فرصت ویژهٔ فروخته‌شده (هنوز فعال)", "n": len(offers_done), "url": "/panel/special-offers/?is_active=1",
         "sub": "می‌توانید غیرفعالش کنید یا تخته اضافه کنید" if offers_done else ""},
        {"label": "فرش منتشرشدهٔ ناموجود", "n": Product.objects.filter(status="publish", stock_status="outofstock").count(),
         "url": "/panel/products/?stock_status=outofstock&status=publish", "quiet": True},
        {"label": "آدرس خراب (۴۰۴)", "n": NotFoundLog.objects.count(), "url": "/panel/notfound/", "quiet": True},
    ]
    for it in items:
        it["urgent"] = bool(it.get("hot") and it["n"])
    out = {"items": items, "open": sum(1 for it in items if it["n"] and not it.get("quiet"))}
    cache.set(key, out, 60)
    return out


# ------------------------------------------------------------------ کمپین‌ها
def campaigns(manager):
    from crm.models import Campaign, ShortLink
    from shop.coupons import PLACED
    from shop.models import Order

    key = f"dash:camp:{int(manager)}"
    out = cache.get(key)
    if out is not None:
        return out
    recent = list(Campaign.objects.exclude(started_at=None).order_by("-started_at")[:4])
    ids = [c.pk for c in recent]
    clicks = dict(ShortLink.objects.filter(campaign_id__in=ids, clicks__gt=0).values("campaign_id")
                  .annotate(n=Count("pk")).values_list("campaign_id", "n"))
    orders = {r["sms_campaign_id"]: r for r in Order.objects.filter(sms_campaign_id__in=ids, status__in=PLACED)
              .values("sms_campaign_id").annotate(n=Count("pk"), s=Sum("items_total"))}
    rows = []
    for c in recent:
        o = orders.get(c.pk, {"n": 0, "s": 0})
        cl = clicks.get(c.pk, 0)
        rows.append({"c": c, "clicks": cl, "click_rate": round(cl * 100 / c.sent, 1) if c.sent else 0,
                     "orders": o["n"], "sum": (o["s"] or 0) if manager else None})
    upcoming = list(Campaign.objects.filter(status__in=["waiting", "sending"]).order_by("next_wave_at", "-pk")[:4])
    drafts = Campaign.objects.filter(status="draft").count()
    out = {"recent": rows, "upcoming": upcoming, "drafts": drafts}
    cache.set(key, out, 120)
    return out


# ------------------------------------------------------------------ مشتریان
def _customers(s, e):
    from django.contrib.auth import get_user_model

    from shop.coupons import PLACED
    from shop.models import Order

    a, b = _rng(s, e)
    joined = get_user_model().objects.filter(date_joined__gte=a, date_joined__lt=b, is_staff=False).count()
    period_orders = Order.objects.filter(created_at__gte=a, created_at__lt=b, status__in=PLACED)
    mobiles = set(period_orders.values_list("mobile", flat=True))
    returning = set(Order.objects.filter(mobile__in=mobiles, created_at__lt=a, status__in=PLACED).values_list("mobile", flat=True))
    cities = list(period_orders.exclude(city="").values("city").annotate(n=Count("pk")).order_by("-n")[:5])
    return {"joined": joined, "buyers": len(mobiles), "new": len(mobiles - returning), "returning": len(mobiles & returning),
            "cities": cities}


def customers(p):
    key = f"dash:cust:{p['start']}:{p['end']}"
    out = cache.get(key)
    if out is None:
        cur, prev = _customers(p["start"], p["end"]), _customers(p["pstart"], p["pend"])
        out = {"cur": cur, "d": {k: delta(cur[k], prev[k]) for k in ("joined", "buyers")}}
        top = max([c["n"] for c in cur["cities"]] or [0]) or 1
        for c in cur["cities"]:
            c["w"] = round(c["n"] * 100 / top)
        cache.set(key, out, CACHE)
    return out


def best_sellers(p, limit=5):
    from shop.coupons import PLACED
    from shop.models import OrderItem

    key = f"dash:best:{p['start']}:{p['end']}"
    out = cache.get(key)
    if out is None:
        a, b = _rng(p["start"], p["end"])
        out = list(OrderItem.objects.filter(order__created_at__gte=a, order__created_at__lt=b, order__status__in=PLACED)
                   .exclude(product_id=None).values("product_id", "product__title", "product__slug")
                   .annotate(q=Sum("quantity"), s=Sum(F("unit_price") * F("quantity"))).order_by("-q", "-s")[:limit])
        cache.set(key, out, CACHE)
    return out


# ------------------------------------------------------------------ بازدید (بخش جدا، پس از باز شدن صفحه)
def traffic(p):
    from stats.reports import traffic as tr

    cur = tr(p["start"], p["end"])
    prev = tr(p["pstart"], p["pend"])
    t, pt = cur["t"], prev["t"]
    s, e = p["start"], p["end"]
    if p["key"] == "today":
        s = e - timedelta(days=6)
        series_src = tr(s, e)["series"]
    else:
        series_src = cur["series"]
    rows = {r["day"]: r["visitors"] for r in series_src}
    visitors = _bars(s, e, rows, lambda v: f"{fa_num(v)} بازدیدکننده")
    placed = t["orders_placed"]
    from shop.models import Order

    a, b = _rng(p["start"], p["end"])
    paid = Order.objects.filter(created_at__gte=a, created_at__lt=b, status__in=Order.PAID_STATUSES).count()
    steps = [("ورود به سایت", t["visits"]), ("افزودن به سبد", t["carts"]), ("ثبت سفارش", placed), ("پرداخت (کامل یا بیعانه)", paid)]
    top = steps[0][1] or 1
    funnel = []
    for i, (label, n) in enumerate(steps):
        prev_n = steps[i - 1][1] if i else None
        funnel.append({"label": label, "n": n, "w": max(round(n * 100 / top, 1), 0.6 if n else 0),
                       "of_prev": round(n * 100 / prev_n, 1) if prev_n else None})
    groups = cur["groups"][:6]
    gmax = max([g["visits"] for g in groups] or [0]) or 1
    for g in groups:
        g["w"] = round(g["visits"] * 100 / gmax)
    cold = [r for r in cur["products"] if r["p"] and r["visitors"] >= 15 and not r["carts"]][:5]
    return {
        "t": t, "d": {"visitors": delta(t["visitors"], pt["visitors"]), "visits": delta(t["visits"], pt["visits"]),
                      "conv": delta(t["conv"], pt["conv"]) if pt["conv"] or t["conv"] else None},
        "visitors_series": visitors, "funnel": funnel, "groups": groups, "cold": cold,
        "hot": [r for r in cur["products"] if r["p"]][:5], "approx": cur["approx_visitors"],
    }
