
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render

from blog.models import Post
from catalog.models import Product
from seo.models import NotFoundLog
from shop.models import Order

from ..auth import staff_required


@staff_required
def home(request):
    from .. import dash

    p = dash.period(request.GET.get("p"))
    manager = request.user.is_superuser
    sales = dash.sales(p)
    ctx = {
        "p": p, "periods": dash.PERIODS, "manager": manager, "todo": dash.todo(manager), "camps": dash.campaigns(manager),
        "cust": dash.customers(p), "best": dash.best_sellers(p),
        "orders_n": sales["cur"]["orders"], "orders_d": sales["d"]["orders"],
        "recent": Order.objects.order_by("-created_at")[:6], "top404": NotFoundLog.objects.order_by("-hits")[:4],
        "counts": {"products": Product.objects.filter(status="publish").count(), "posts": Post.objects.count()},
    }
    if manager:
        ctx["sales"] = sales
        ctx["money"] = {k: dash.short_money(sales["cur"][k]) for k in ("sales", "received", "avg")}
        ctx["money_series"] = dash.money_series(p)
        ctx["money_total"] = sum(x["value"] for x in ctx["money_series"])
    return render(request, "dashboard/home.html", ctx)


@staff_required
def home_traffic(request):
    """بخش بازدید پیشخوان (جدا بار می‌شود تا صفحه زود باز شود)."""
    import logging

    from .. import dash

    p = dash.period(request.GET.get("p"))
    try:
        tr = dash.traffic(p)
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("dash traffic")
        tr = None
    return render(request, "dashboard/_dash_traffic.html", {"p": p, "tr": tr, "manager": request.user.is_superuser})


def search(request):

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
