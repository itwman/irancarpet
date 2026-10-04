from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from blog.models import Comment, Post
from catalog.models import Product, Review
from core.templatetags.fa import fa_num, jdate
from seo.models import NotFoundLog
from shop.models import Order, Payment

from ..auth import staff_required
from ..registry import GROUPS, REGISTRY


@staff_required
def home(request):
    now = timezone.localtime()
    today = now.date()
    import jdatetime

    jt = jdatetime.date.fromgregorian(date=today)
    month_start = jdatetime.date(jt.year, jt.month, 1).togregorian()  # اول ماه شمسی
    paid = Order.objects.filter(status__in=Order.PAID_STATUSES)
    ok_pay = Payment.objects.filter(status="ok")

    days = 30
    tz = timezone.get_current_timezone()
    start = today - timedelta(days=days - 1)
    # بدون نیاز به جدول‌های منطقهٔ زمانی MySQL: بازه با datetime محاسبه می‌شود
    def at(d):
        return timezone.make_aware(datetime.combine(d, time.min), tz)

    rows = {}
    for dt, amount in ok_pay.filter(verified_at__gte=at(start)).values_list("verified_at", "amount"):
        d = timezone.localtime(dt).date()
        rows[d] = rows.get(d, 0) + amount
    series = []
    mx = max(rows.values(), default=0) or 1
    for i in range(days):
        d = start + timedelta(days=i)
        v = rows.get(d, 0) or 0
        series.append({"label": jdate(d, "%d %B"), "value": v, "h": round(v / mx * 100, 1), "is_today": d == today})

    stats = {
        "today_orders": paid.filter(paid_at__gte=at(today)).count(),
        "today_amount": rows.get(today, 0),
        "month_amount": ok_pay.filter(verified_at__gte=at(month_start)).aggregate(s=Sum("amount"))["s"] or 0,
        "to_ship": Order.objects.filter(status__in=["deposit_paid", "paid", "processing"]).count(),
        "pending": Order.objects.filter(status="pending", created_at__gte=now - timedelta(days=7)).count(),
        "customers_30": get_user_model().objects.filter(date_joined__gte=now - timedelta(days=30)).count(),
        "products": Product.objects.filter(status="publish").count(),
        "out_of_stock": Product.objects.filter(status="publish", stock_status="outofstock").count(),
        "reviews_wait": Review.objects.filter(is_approved=False).count(),
        "comments_wait": Comment.objects.filter(is_approved=False).count(),
        "notfound": NotFoundLog.objects.count(),
    }
    recent = Order.objects.order_by("-created_at")[:8]
    top404 = NotFoundLog.objects.order_by("-hits")[:5]
    return render(request, "dashboard/home.html", {
        "stats": stats, "series": series, "series_total": sum(s["value"] for s in series), "recent": recent, "top404": top404,
        "posts_count": Post.objects.count(),
    })


@staff_required
def search(request):
    from django.contrib.auth import get_user_model

    from ..forms import to_en

    q = (request.GET.get("q") or "").strip()
    qe = to_en(q)
    res = {}
    if len(q) >= 2:
        res["orders"] = Order.objects.filter(Q(mobile__icontains=qe) | Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                                             (Q(number=int(qe)) if qe.isdigit() else Q(pk__in=[])))[:10]
        res["products"] = Product.objects.filter(Q(title__icontains=q) | Q(title__icontains=qe) | Q(sku__icontains=qe)).select_related("image")[:12]
        res["customers"] = get_user_model().objects.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) |
                                                           Q(profile__mobile__icontains=qe) | Q(username__icontains=qe)).select_related("profile")[:10]
        res["posts"] = Post.objects.filter(title__icontains=q)[:8]
    return render(request, "dashboard/search.html", {"q": q, "res": res, "any": any(len(v) for v in res.values())})
