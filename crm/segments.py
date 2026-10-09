"""باشگاه مشتریان: هر شمارهٔ موبایل یک مشتری است (سفارش‌های وردپرس و سایت تازه با هم) و خودکار در گروه‌ها می‌نشیند.

گروه‌ها (یک مشتری می‌تواند در چند گروه باشد):
  vip         وفادار: جمع خرید یا تعداد سفارش پرداخت‌شده از حد تنظیمات بیشتر
  new         تازه: اولین خرید در ۶۰ روز اخیر
  active      فعال: آخرین خرید در ۶ ماه اخیر
  at_risk     در خطر ریزش: آخرین خرید ۶ تا ۱۲ ماه پیش
  lost        از دست رفته: آخرین خرید بیش از یک سال پیش
  unpaid      سفارش داده ولی هیچ‌وقت پرداخت نکرده
  registered  ثبت‌نام کرده ولی هیچ سفارشی ندارد
"""
from collections import OrderedDict

from django.core.cache import cache
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone

SEGMENTS = OrderedDict([
    ("vip", "وفادار"), ("new", "تازه"), ("active", "فعال"), ("at_risk", "در خطر ریزش"), ("lost", "از دست رفته"),
    ("unpaid", "سفارش بی‌پرداخت"), ("registered", "ثبت‌نام بدون سفارش"),
])
JMONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
HINTS = {
    "vip": "جمع خرید یا تعداد سفارش بالا (حدش در تنظیمات)", "new": "اولین خرید در ۶۰ روز اخیر", "active": "آخرین خرید در ۶ ماه اخیر",
    "at_risk": "آخرین خرید ۶ تا ۱۲ ماه پیش؛ بهترین زمان کد تخفیف", "lost": "بیش از یک سال بی‌خرید",
    "unpaid": "سفارش ثبت کرده ولی هیچ‌وقت پرداخت نکرده", "registered": "با موبایل ثبت‌نام کرده ولی سفارشی نداده",
}
PAID_Q = Q(status__in=["deposit_paid", "paid", "processing", "shipped", "completed"]) | Q(paid_amount__gt=0, status__in=["on_hold"])


def customers():
    """{موبایل: {name, city, paid_orders, total, first, last, orders, last_order}} — ۱۰ دقیقه کش."""
    from accounts.utils import normalize_mobile
    from shop.models import Order

    key = "crm:customers"
    hit = cache.get(key)
    if hit is not None:
        return hit
    out = {}
    rows = (Order.objects.exclude(mobile="").values("mobile")
            .annotate(orders=Count("pk"), last_order=Max("created_at"),
                      paid_orders=Count("pk", filter=PAID_Q), total=Sum("items_total", filter=PAID_Q),
                      first=Min("created_at", filter=PAID_Q), last=Max("created_at", filter=PAID_Q)))
    for r in rows:
        m = normalize_mobile(r["mobile"])
        if not m:
            continue
        c = out.setdefault(m, {"mobile": m, "orders": 0, "paid_orders": 0, "total": 0, "first": None, "last": None, "last_order": None})
        c["orders"] += r["orders"]
        c["paid_orders"] += r["paid_orders"]
        c["total"] += r["total"] or 0
        for k, fn in (("first", min), ("last", max), ("last_order", max)):
            if r[k]:
                c[k] = fn(c[k], r[k]) if c[k] else r[k]
    names = {}
    for mobile, first, last, city in Order.objects.exclude(mobile="").order_by("created_at").values_list("mobile", "first_name", "last_name", "city"):
        names[normalize_mobile(mobile)] = (first, f"{first} {last}".strip(), city)
    for m, c in out.items():
        c["name"], c["full_name"], c["city"] = names.get(m, ("", "", ""))
    cache.set(key, out, 600)
    return out


def registered_only():
    """موبایل‌های ثبت‌نام‌کرده‌ای که هیچ سفارشی ندارند."""
    from accounts.models import Profile
    from accounts.utils import normalize_mobile

    buyers = customers()
    out = []
    for m, first in Profile.objects.exclude(mobile=None).filter(user__is_active=True, user__is_staff=False).values_list(
            "mobile", "user__first_name"):
        m = normalize_mobile(m)
        if m and m not in buyers:
            out.append({"mobile": m, "name": first or "", "full_name": first or "", "city": "", "orders": 0, "paid_orders": 0,
                        "total": 0, "first": None, "last": None, "last_order": None})
    return out


def segments_of(c, now=None, settings_obj=None):
    from .models import CrmSettings

    s = settings_obj or CrmSettings.load()
    now = now or timezone.now()
    out = []
    if not c["paid_orders"]:
        return ["unpaid"] if c["orders"] else ["registered"]
    if c["total"] >= s.vip_total or c["paid_orders"] >= s.vip_orders:
        out.append("vip")
    days = (now - c["last"]).days if c["last"] else 9999
    if c["first"] and (now - c["first"]).days <= 60:
        out.append("new")
    if days <= 180:
        out.append("active")
    elif days <= 365:
        out.append("at_risk")
    else:
        out.append("lost")
    return out


def audience(segment, inactive_days=180, custom="", album=None):
    """[{mobile, name, ...}] گیرنده‌های یک کمپین."""
    import re

    from accounts.utils import normalize_mobile

    from .models import CrmSettings

    if segment == "custom":
        seen, out = set(), []
        for x in re.split(r"[\n\r,،;]+", custom or ""):
            m = normalize_mobile(x.replace(" ", ""))
            if m and m not in seen:
                seen.add(m)
                c = customers().get(m)
                out.append(c or {"mobile": m, "name": "", "full_name": ""})
        return out
    if segment == "registered":
        return registered_only()
    if segment == "album":
        from .interest import album_audience

        return album_audience(album) if album else []
    s, now = CrmSettings.load(), timezone.now()
    out = []
    for c in customers().values():
        segs = segments_of(c, now, s)
        if segment == "buyers" and c["paid_orders"]:
            out.append(c)
        elif segment == "inactive" and c["paid_orders"] and c["last"] and (now - c["last"]).days >= inactive_days:
            out.append(c)
        elif segment in segs:
            out.append(c)
    return sorted(out, key=lambda c: -(c["total"] or 0))


def counts():
    from .models import CrmSettings

    s, now = CrmSettings.load(), timezone.now()
    out = {k: 0 for k in SEGMENTS}
    for c in customers().values():
        for seg in segments_of(c, now, s):
            out[seg] += 1
    out["registered"] = len(registered_only())
    return out
