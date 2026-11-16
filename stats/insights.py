"""گزارش‌های تازهٔ پنل (آبان ۱۴۰۵): سلامت سایت، فرصت‌ها و هشدارهای بازدید، مقایسهٔ دو بازه.

همه از داده‌هایی که سایت خودش جمع می‌کند (آمار بازدید، سفارش‌ها، پیامک‌ها، ۴۰۴ها، جستجوها)؛ به هیچ سرویس خارجی وابسته نیست.
"""
import os
import re
from collections import defaultdict
from datetime import timedelta as td

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone


def _placed():
    from shop.coupons import PLACED

    return PLACED


def _pct(now, before):
    if not before:
        return None
    return round((now - before) * 100 / before)


# ------------------------------------------------------------------ سلامت سایت
def _dir_size(path):
    n = size = 0
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.is_file(follow_symlinks=False):
                    n += 1
                    size += e.stat().st_size
    except OSError:
        pass
    return n, size


def health():
    """هر ردیف: عنوان، عدد، سطح (ok/warn/bad)، توضیح، پیوند پنل."""
    from blog.models import PostRewrite
    from catalog.models import Product, Review
    from crm.models import ContactMessage, SmsLog
    from seo.models import NotFoundLog, Redirect
    from shop.models import Order, Payment

    now = timezone.now()
    week = now - td(days=7)
    pub = Product.objects.published()
    rows = []

    def row(group, title, n, level, hint="", url=""):
        rows.append({"group": group, "title": title, "n": n, "level": level if n else "ok", "hint": hint, "url": url})

    # فرش‌ها
    row("فرش‌ها", "فرش منتشرشده بی‌عکس", pub.filter(image__isnull=True).count(), "bad",
        "در نتیجهٔ گوگل و کارت‌ها بی‌تصویر دیده می‌شود.", "/panel/products/?status=publish")
    row("فرش‌ها", "فرش منتشرشده بی‌قیمت", pub.filter(min_price__isnull=True).exclude(stock_status="outofstock").count(), "bad",
        "موجود ولی بی‌قیمت: مشتری نمی‌تواند بخرد.", "/panel/products/?status=publish")
    dead = pub.filter(album__isnull=True, stock_status="outofstock").count()
    row("فرش‌ها", "فرش قدیمی بی‌آلبوم و ناموجود (هنوز منتشرشده)", dead, "warn",
        "سهم خزیدن گوگل را می‌گیرند؛ فرمان dead_products فهرست و ادغامشان را می‌دهد.", "/panel/products/?stock_status=outofstock&status=publish")
    row("فرش‌ها", "نظرهای در انتظار تأیید", Review.objects.filter(is_approved=False, parent__isnull=True).count(), "warn",
        "نظر تأییدنشده در صفحه و ستاره‌های گوگل دیده نمی‌شود.", "/panel/reviews/?is_approved=0")

    # فروش
    unpaid = Order.objects.filter(status="pending", created_at__gte=week).count()
    row("فروش", "سفارش پرداخت‌نشدهٔ ۷ روز اخیر", unpaid, "warn", "پیامک یادآوری خودکار می‌رود؛ تماس تلفنی اثر بیشتری دارد.",
        "/panel/orders/?status=pending")
    pays = dict(Payment.objects.filter(created_at__gte=week).values_list("status").annotate(n=Count("pk")))
    failed, ok = pays.get("failed", 0) + pays.get("init", 0), pays.get("ok", 0)
    row("فروش", f"پرداخت ناموفق یا رهاشده در درگاه (۷ روز؛ موفق: {ok})", failed,
        "bad" if failed > max(3, ok) else "warn", "اگر ناگهان زیاد شد، درگاه یا قطعی بانک را بررسی کنید.", "/panel/payments/")
    try:
        new_msgs = ContactMessage.objects.filter(status="new").count()
    except Exception:  # noqa: BLE001
        new_msgs = 0
    row("فروش", "پیام «تماس با ما» بی‌پاسخ", new_msgs, "warn", "", "/panel/contact-messages/")

    # پیامک
    sms = SmsLog.objects.filter(created_at__gte=week)
    sms_bad = sms.filter(ok=False).count()
    sms_all = sms.count()
    errors = list(sms.filter(ok=False).exclude(error="").values("error").annotate(n=Count("pk")).order_by("-n")[:3])
    row("پیامک", f"پیامک ناموفق ۷ روز اخیر (از {sms_all})", sms_bad, "bad" if sms_bad > sms_all / 5 else "warn",
        "؛ ".join(f"{e['error'][:60]} ({e['n']})" for e in errors) or "اعتبار پنل sms.ir و شمارهٔ خط را بررسی کنید.", "/panel/sms/")

    # سئو
    nf = NotFoundLog.objects.filter(last_seen__gte=week)
    row("سئو", "نشانی‌های ۴۰۴ دیده‌شده در ۷ روز", nf.count(), "warn",
        "پرتکرارها را در «خطاهای ۴۰۴» به صفحهٔ درست ریدایرکت کنید.", "/panel/notfound/")
    act = Redirect.objects.filter(is_active=True, match=Redirect.Match.EXACT)
    sources = set(act.values_list("source", flat=True))
    chains = [r for r in act.only("source", "target") if Redirect.normalize(r.target) in sources]
    row("سئو", "ریدایرکت زنجیره‌ای (مقصدش خودش ریدایرکت است)", len(chains), "warn",
        "در اجرا خودکار تا مقصد نهایی دنبال می‌شود، ولی بهتر است مقصد را مستقیم کنید.", "/panel/redirects/")
    q = PostRewrite.objects
    ready = q.filter(status__in=["ready", "approved"]).count()
    row("محتوا", "مقالهٔ آماده در صف انتشار", ready, "ok",
        f"در صف نوشتن: {q.filter(status='queued').count()} — نگه‌داشته: {q.filter(hold=True).count()}", "/panel/rewrites/")

    # کش صفحه‌ها
    pages_dir = settings.CACHES.get("pages", {}).get("LOCATION", "")
    if pages_dir and os.path.isdir(pages_dir):
        n, size = _dir_size(pages_dir)
        rows.append({"group": "سرور", "title": f"کش صفحهٔ فرش‌ها: {n:,} فایل", "n": round(size / 1048576), "level": "warn" if size > 1.5e9 else "ok",
                     "hint": "مگابایت. اگر از ۱٫۵ گیگ گذشت، مدت کش کم شود.", "url": ""})
    top404 = list(nf.order_by("-hits")[:12])
    return {"rows": rows, "top404": top404, "chains": chains[:10],
            "bad": sum(1 for r in rows if r["level"] == "bad"), "warn": sum(1 for r in rows if r["level"] == "warn")}


# ------------------------------------------------------------------ فرصت‌ها و هشدارهای بازدید
def opportunities(days=30):
    from catalog.models import Product
    from growth.models import SearchLog
    from shop.models import OrderItem

    from .models import DailyPage, DailyProduct

    today = timezone.localdate()
    start = today - td(days=days - 1)

    # جهش ناگهانی: ۳ روز اخیر در برابر میانگین ۲۸ روز پیش از آن
    recent = dict(DailyProduct.objects.filter(day__gte=today - td(days=2)).values_list("product_id").annotate(v=Sum("views")))
    base = dict(DailyProduct.objects.filter(day__range=(today - td(days=30), today - td(days=3)))
                .values_list("product_id").annotate(v=Sum("views")))
    spikes = []
    for pid, v in recent.items():
        avg3 = base.get(pid, 0) / 28 * 3
        if v >= 15 and v >= 3 * max(avg3, 1):
            spikes.append({"pid": pid, "views": v, "before": round(avg3, 1), "x": round(v / max(avg3, 1), 1), "new": pid not in base})
    spikes.sort(key=lambda r: -r["views"])
    spikes = spikes[:12]

    # پربازدید بی‌فروش در بازه
    views = list(DailyProduct.objects.filter(day__range=(start, today)).values("product_id")
                 .annotate(v=Sum("views"), c=Sum("carts")).filter(v__gte=30).order_by("-v")[:200])
    sold = set(OrderItem.objects.filter(order__created_at__date__range=(start, today), order__status__in=_placed())
               .values_list("product_id", flat=True))
    no_sale = [{"pid": r["product_id"], "views": r["v"], "carts": r["c"]} for r in views if r["product_id"] not in sold][:15]

    ids = {r["pid"] for r in spikes + no_sale}
    prods = {p.pk: p for p in Product.objects.filter(pk__in=ids).only("pk", "title", "slug", "min_price", "stock_status")}
    for r in spikes + no_sale:
        r["p"] = prods.get(r["pid"])

    searches = list(SearchLog.objects.filter(results=0, last_seen__date__gte=start).order_by("-hits")[:20])

    # صفحه‌های فرود و صفحه‌های ورودِ رو به افت (۱۴ روز در برابر ۱۴ روز پیش از آن)
    landing = list(DailyPage.objects.filter(day__range=(start, today), path__startswith="/carpets/").values("path")
                   .annotate(e=Sum("entries"), v=Sum("views")).order_by("-e")[:15])
    now14 = dict(DailyPage.objects.filter(day__gte=today - td(days=13)).values_list("path").annotate(e=Sum("entries")))
    prev14 = dict(DailyPage.objects.filter(day__range=(today - td(days=27), today - td(days=14))).values_list("path").annotate(e=Sum("entries")))
    falling = [{"path": p, "now": now14.get(p, 0), "before": e, "pct": _pct(now14.get(p, 0), e)}
               for p, e in prev14.items() if e >= 20 and now14.get(p, 0) <= e * 0.6]
    falling.sort(key=lambda r: r["now"] - r["before"])
    rising = [{"path": p, "now": e, "before": prev14.get(p, 0), "pct": _pct(e, prev14.get(p, 0))}
              for p, e in now14.items() if e >= 20 and e >= prev14.get(p, 0) * 1.5]
    rising.sort(key=lambda r: r["before"] - r["now"])
    return {"spikes": spikes, "no_sale": no_sale, "searches": searches, "landing": landing,
            "falling": falling[:12], "rising": rising[:12], "days": days}


# ------------------------------------------------------------------ مقایسهٔ دو بازه
REEDS_RX = re.compile(r"([0-9۰-۹]{3,4})\s*شانه")
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _window(start, end):
    from shop.models import Order, OrderItem

    from .models import DailyTotal

    t = DailyTotal.objects.filter(day__range=(start, end)).aggregate(
        visits=Sum("visits"), views=Sum("views"), carts=Sum("carts"))
    orders = Order.objects.filter(created_at__date__range=(start, end), status__in=_placed())
    o = orders.aggregate(n=Count("pk"), s=Sum("items_total"))
    inst = orders.exclude(installment_plan__isnull=True).count()
    items = OrderItem.objects.filter(order__in=orders)
    dims = {k: defaultdict(lambda: {"n": 0, "s": 0}) for k in ("reeds", "size", "brand", "province")}
    for it in items.values("title", "size_label", "quantity", "unit_price", "product__brand__name", "order__province"):
        m = REEDS_RX.search(it["title"] or "")
        keys = {"reeds": f"{m.group(1).translate(FA)} شانه" if m else "سایر",
                "size": (it["size_label"] or "—").split("(")[0].strip()[:40],
                "brand": it["product__brand__name"] or "بی‌برند", "province": it["order__province"] or "—"}
        for d, k in keys.items():
            dims[d][k]["n"] += it["quantity"]
            dims[d][k]["s"] += it["quantity"] * it["unit_price"]
    visits = t["visits"] or 0
    n = o["n"] or 0
    return {"visits": visits, "views": t["views"] or 0, "carts": t["carts"] or 0, "orders": n, "revenue": o["s"] or 0,
            "aov": round((o["s"] or 0) / n) if n else 0, "conv": round(n * 100 / visits, 2) if visits else 0,
            "installments": inst, "dims": dims}


def compare(days=30):
    today = timezone.localdate()
    a = (today - td(days=days - 1), today)
    b = (a[0] - td(days=days), a[0] - td(days=1))
    now, before = _window(*a), _window(*b)
    metrics = []
    for key, label in (("visits", "ورود به سایت"), ("carts", "افزودن به سبد"), ("orders", "سفارش ثبت‌شده"), ("revenue", "فروش (تومان)"),
                       ("aov", "میانگین هر سفارش (تومان)"), ("conv", "نرخ تبدیل (٪)"), ("installments", "سفارش اقساطی")):
        metrics.append({"label": label, "now": now[key], "before": before[key], "pct": _pct(now[key], before[key]), "money": key in ("revenue", "aov")})
    dims = []
    for d, label in (("reeds", "به تفکیک شانه"), ("size", "به تفکیک سایز"), ("brand", "به تفکیک برند"), ("province", "به تفکیک استان")):
        keys = set(now["dims"][d]) | set(before["dims"][d])
        rows = [{"k": k, "now": now["dims"][d][k]["n"], "before": before["dims"][d][k]["n"], "s": now["dims"][d][k]["s"],
                 "pct": _pct(now["dims"][d][k]["n"], before["dims"][d][k]["n"])} for k in keys]
        rows.sort(key=lambda r: (-r["now"], -r["before"]))
        dims.append({"label": label, "rows": rows[:12]})
    return {"a": a, "b": b, "metrics": metrics, "dims": dims, "days": days}
