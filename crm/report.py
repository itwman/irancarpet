"""گزارش فروش و مشتریان برای پنل."""
from collections import Counter

from django.db.models import Count, Q, Sum
from django.utils import timezone

PAID = ["deposit_paid", "paid", "processing", "shipped", "completed"]
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def _pct(a, b):
    return round(100 * a / b) if b else 0


def build(days=90):
    import jdatetime

    from core.templatetags.fa import fa_num

    from shop.models import Order

    from .campaigns import results
    from .models import Campaign, SmsLog
    from .segments import HINTS, SEGMENTS, counts, customers

    now = timezone.now()
    since = now - timezone.timedelta(days=days) if days else None
    site = Order.objects.filter(wp_id__isnull=True)
    period = site.filter(created_at__gte=since) if since else site

    # قیف سفارش (سفارش‌های همین سایت)
    created = period.count()
    paid_q = period.filter(Q(status__in=PAID) | Q(paid_amount__gt=0))
    paid = paid_q.count()
    shipped = period.filter(status__in=["shipped", "completed"]).count()
    completed = period.filter(status="completed").count()
    pending = period.filter(status="pending").count()
    on_hold = period.filter(status="on_hold").count()
    cancelled = period.filter(status__in=["cancelled", "refunded"]).count()
    revenue = paid_q.aggregate(s=Sum("items_total"))["s"] or 0
    funnel = [("ثبت سفارش", created, 100), ("پرداخت (کامل یا بیعانه)", paid, _pct(paid, created)),
              ("ارسال", shipped, _pct(shipped, created)), ("تحویل", completed, _pct(completed, created))]
    by_mode = list(period.values("payment_mode").annotate(n=Count("pk"), p=Count("pk", filter=Q(status__in=PAID) | Q(paid_amount__gt=0)))
                   .order_by("-n"))
    mode_names = dict(Order._meta.get_field("payment_mode").choices)
    for r in by_mode:
        r["label"] = mode_names.get(r["payment_mode"], r["payment_mode"])
        r["rate"] = _pct(r["p"], r["n"])

    # پیگیری سفارش ناتمام
    reminded = period.filter(reminded_count__gt=0)
    recovered = reminded.filter(Q(status__in=PAID) | Q(paid_amount__gt=0))
    recovered_sum = recovered.aggregate(s=Sum("items_total"))["s"] or 0

    # فروش ماهانه (۱۲ ماه، همهٔ سفارش‌های پرداخت‌شده)
    months = []
    j = jdatetime.date.fromgregorian(date=timezone.localtime(now).date())
    y, m = j.year, j.month
    keys = []
    for _ in range(12):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    keys.reverse()
    allpaid = Order.objects.filter(Q(status__in=PAID) | Q(paid_amount__gt=0), created_at__gte=now - timezone.timedelta(days=380))
    agg = Counter()
    cnt = Counter()
    for created_at, total in allpaid.values_list("created_at", "items_total"):
        jd = jdatetime.date.fromgregorian(date=timezone.localtime(created_at).date())
        agg[(jd.year, jd.month)] += total or 0
        cnt[(jd.year, jd.month)] += 1
    top = max(agg.values(), default=0)
    for k in keys:
        months.append({"label": f"{JMONTHS[k[1] - 1]} {fa_num(str(k[0])[2:])}", "sum": agg[k], "n": cnt[k], "w": _pct(agg[k], top)})

    # مشتریان
    cust = customers()
    buyers_period = [c for c in cust.values() if c["paid_orders"] and c["last"] and (not since or c["last"] >= since)]
    new_buyers = [c for c in buyers_period if c["first"] and (not since or c["first"] >= since)]
    all_buyers = [c for c in cust.values() if c["paid_orders"]]
    repeat = [c for c in all_buyers if c["paid_orders"] >= 2]
    cities = Counter(c["city"] for c in buyers_period if c["city"]).most_common(10)
    top_customers = sorted(all_buyers, key=lambda c: -(c["total"] or 0))[:10]
    seg = counts()

    # کمپین‌ها
    camps = []
    for c in Campaign.objects.all()[:20]:
        n, s = results(c)
        camps.append({"c": c, "orders": n, "sum": s, "rate": _pct(n, c.sent)})
    wb_orders = Order.objects.filter(coupon_code__startswith="WB-", status__in=PAID + ["on_hold"])

    sms = list((SmsLog.objects.filter(created_at__gte=since) if since else SmsLog.objects.all())
               .values("kind").annotate(n=Count("pk"), bad=Count("pk", filter=Q(ok=False))).order_by("-n"))
    kinds = dict(SmsLog.Kind.choices)
    for r in sms:
        r["label"] = kinds.get(r["kind"], r["kind"])

    return {
        "days": days, "funnel": funnel, "created": created, "paid": paid, "pending": pending, "on_hold": on_hold,
        "cancelled": cancelled, "revenue": revenue, "aov": revenue // paid if paid else 0, "conv": _pct(paid, created),
        "by_mode": by_mode, "reminded": reminded.count(), "recovered": recovered.count(), "recovered_sum": recovered_sum,
        "recover_rate": _pct(recovered.count(), reminded.count()), "months": months,
        "buyers": len(buyers_period), "new_buyers": len(new_buyers), "returning": len(buyers_period) - len(new_buyers),
        "all_buyers": len(all_buyers), "repeat": len(repeat), "repeat_rate": _pct(len(repeat), len(all_buyers)),
        "cities": cities, "top_customers": top_customers, "segments": [(k, v, seg.get(k, 0), HINTS.get(k, "")) for k, v in SEGMENTS.items()],
        "campaigns": camps, "winback_orders": wb_orders.count(), "winback_sum": wb_orders.aggregate(s=Sum("items_total"))["s"] or 0,
        "sms": sms,
    }
