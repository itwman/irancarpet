"""پروفایل مشتری در پنل: هر شمارهٔ موبایل یک مشتری است (سفارش‌های مهمان، حساب کاربری و سفارش‌های وردپرس با هم)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.utils import normalize_mobile
from dashboard.auth import staff_required

from . import points
from .models import CartSnapshot, CrmSettings, CustomerNote, ProductView, SmsLog
from .segments import JMONTHS, SEGMENTS, segments_of

PAID = {"deposit_paid", "paid", "processing", "shipped", "completed"}


def url(mobile):
    m = normalize_mobile(mobile or "")
    return f"/panel/crm/customer/{m}/" if m else ""


def variants(m):
    return {m, m[1:], "98" + m[1:], "+98" + m[1:]}


def gather(m):
    from catalog.models import Review, Variation
    from shop.coupons import PLACED
    from shop.models import Coupon, Order

    User = get_user_model()
    users = list(User.objects.filter(Q(username__in=variants(m)) | Q(profile__mobile=m)).select_related("profile").distinct())
    orders = list(Order.objects.filter(Q(mobile__in=variants(m)) | Q(user__in=users)).distinct()
                  .prefetch_related("items").order_by("-created_at"))
    paid = [o for o in orders if o.status in PAID or (o.status == "on_hold" and o.paid_amount)]
    total = sum(o.items_total for o in paid)
    c = {"mobile": m, "orders": len(orders), "paid_orders": len(paid), "total": total,
         "first": min((o.created_at for o in paid), default=None), "last": max((o.created_at for o in paid), default=None),
         "last_order": orders[0].created_at if orders else None}
    s = CrmSettings.load()
    segs = segments_of(c, timezone.now(), s) if (orders or users) else []
    latest = orders[0] if orders else None
    user = users[0] if users else None
    profile = getattr(user, "profile", None) if user else None
    name = (f"{latest.first_name} {latest.last_name}".strip() if latest else "") or (user.get_full_name() if user else "")

    codes = list(Coupon.objects.filter(Q(for_mobile=m) | Q(for_user__in=users) | Q(owner__in=users)).order_by("-created_at")[:30])
    used = set(Order.objects.filter(coupon_code__in=[x.code for x in codes], status__in=PLACED).values_list("coupon_code", flat=True))
    now = timezone.now()
    for x in codes:
        x.used = x.code in used
        x.expired = bool(x.ends_at and x.ends_at < now)

    cart = []
    snap = CartSnapshot.objects.filter(user__in=users).order_by("-updated_at").first()
    if snap and snap.data:
        vs = {str(v.pk): v for v in Variation.objects.filter(pk__in=[int(k) for k in snap.data]).select_related("product", "size")}
        cart = [(vs[k], q) for k, q in snap.data.items() if k in vs]

    return {
        "m": m, "c": c, "name": name or "مشتری بی‌نام", "users": users, "acct": user, "cprofile": profile, "orders": orders,
        "latest": latest, "segments": [(k, SEGMENTS[k]) for k in segs if k in SEGMENTS],
        "avg": total // len(paid) if paid else 0,
        "cancelled": sum(1 for o in orders if o.status in ("cancelled", "refunded")),
        "unpaid": sum(1 for o in orders if o.status == "pending"),
        "cities": sorted({o.city for o in orders if o.city}),
        "points": points.balance(m, s) if s.points_enabled else None, "earned": points.earned(m, s) if s.points_enabled else 0,
        "birthday": f"{profile.birth_day} {JMONTHS[profile.birth_month - 1]}" if profile and profile.birth_month and profile.birth_day else "",
        "codes": codes, "cart": cart, "cart_at": snap.updated_at if snap else None,
        "sms": SmsLog.objects.filter(mobile=m).select_related("order", "campaign")[:200],
        "sms_count": SmsLog.objects.filter(mobile=m).count(),
        "reviews": Review.objects.filter(Q(mobile__in=variants(m)) | Q(user__in=users)).select_related("product").order_by("-created_at")[:10],
        "views": ProductView.objects.filter(user__in=users).select_related("product").order_by("-seen_at")[:8],
        "notes": CustomerNote.objects.filter(mobile=m).select_related("author")[:30],
    }


@staff_required
def customer_view(request, mobile):
    from dashboard.models import log

    from .notify import send

    m = normalize_mobile(mobile)
    if not m:
        raise Http404
    if m != mobile:
        return redirect(url(m))
    if request.method == "POST":
        do = request.POST.get("do")
        text = (request.POST.get("text") or "").strip()
        if do == "sms" and text:
            ok = send(m, text[:600], SmsLog.Kind.MANUAL)
            log(request, "action", "باشگاه مشتریان", None, f"پیامک دستی به {m}")
            (messages.success if ok else messages.error)(
                request, "پیامک فرستاده شد." if ok else "sms.ir پیامک را نپذیرفت؛ علت در فهرست پیامک‌ها آمده است.")
        elif do == "note" and text:
            CustomerNote.objects.create(mobile=m, text=text[:2000], author=request.user)
            messages.success(request, "یادداشت ثبت شد.")
        elif do == "del_note":
            CustomerNote.objects.filter(mobile=m, pk=request.POST.get("note") or 0).delete()
        return redirect(url(m) + ("#sms" if do == "sms" else "#notes" if do in ("note", "del_note") else ""))
    ctx = gather(m)
    if not ctx["orders"] and not ctx["users"] and not ctx["sms_count"]:
        raise Http404
    return render(request, "crm/customer.html", ctx)
