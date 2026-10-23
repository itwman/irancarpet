"""«حساب من»: پیشخوان مشتری با منوی کناری — سفارش‌ها با مراحل، علاقه‌مندی‌ها، خبرم‌کن‌ها، کدهای تخفیف و اطلاعات حساب."""
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

LOGIN = "/my-account/login/"
META = {"robots": "noindex, nofollow"}

STEPS = ["ثبت سفارش", "پرداخت", "آماده‌سازی", "ارسال", "تحویل"]
# وضعیت ← (مرحلهٔ جاری، همه تمام شده؟)
STEP_OF = {"pending": 1, "on_hold": 1, "deposit_paid": 2, "paid": 2, "processing": 2, "shipped": 3, "completed": 5}


def steps(order):
    """[{label, state: done|now|todo}] برای نوار مراحل سفارش؛ None برای سفارش لغوشده."""
    if order.status in ("cancelled", "refunded"):
        return None
    cur = STEP_OF.get(order.status, 1)
    out = []
    for i, label in enumerate(STEPS):
        if order.is_installment and i == 1:
            label = "تأیید اقساط" if order.status == "on_hold" else "پیش‌پرداخت"
        out.append({"label": label, "state": "done" if i < cur else ("now" if i == cur else "todo")})
    return out


def _profile(user):
    from .views import profile_of

    return profile_of(user)


def _codes(user, mobile):
    from shop.models import Coupon

    now = timezone.now()
    q = Q(for_user=user)
    if mobile:
        q |= Q(for_mobile=mobile)
    return list(Coupon.objects.filter(q, is_active=True).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
                .exclude(owner=user).order_by("-created_at")[:20])


def _club(user):
    try:
        from crm import points
        from crm.club import mobile_of
        from crm.models import CrmSettings

        cs = CrmSettings.load()
        if not (cs.points_enabled or cs.birthday_enabled):
            return None
        m = mobile_of(user)
        bal = points.balance(m, cs) if m and cs.points_enabled else 0
        return {"balance": bal, "value": bal * cs.point_value, "enabled": cs.points_enabled}
    except Exception:  # noqa: BLE001
        return None


def base_ctx(request, section, title):
    """منو و شمارنده‌های همهٔ صفحه‌های حساب."""
    from api.models import Wishlist
    from growth.models import ProductAlert
    from shop.models import Order

    user = request.user
    profile = _profile(user)
    orders = Order.objects.filter(user=user)
    open_orders = orders.exclude(status__in=["completed", "cancelled", "refunded"]).count()
    try:
        from affiliate.models import AffiliateSettings

        aff_on = AffiliateSettings.load().enabled
    except Exception:  # noqa: BLE001
        aff_on = False
    name = user.get_full_name() or user.first_name or ""
    return {
        "meta": {**META, "title": title}, "section": section, "profile": profile, "acc_name": name,
        "acc_initial": (name or "؟")[:1],
        "nav": {
            "orders": orders.count(), "open": open_orders,
            "wishlist": Wishlist.objects.filter(user=user).count(),
            "alerts": ProductAlert.objects.filter(Q(user=user) | Q(mobile=profile.mobile or "-"), sent_at__isnull=True).count(),
            "codes": len(_codes(user, profile.mobile)),
            "affiliate": getattr(user, "affiliate", None) if hasattr(user, "affiliate") else None, "aff_on": aff_on,
            "seller": getattr(user, "seller", None) if hasattr(user, "seller") else None,
        },
    }


# ------------------------------------------------------------------ پیشخوان
@login_required(login_url=LOGIN)
def overview(request):
    if request.method == "POST":  # فرم قدیمی اطلاعات حساب
        return profile(request)
    from api.models import Wishlist
    from shop.models import Order, ShopSettings

    ctx = base_ctx(request, "home", "حساب من")
    user = request.user
    orders = list(Order.objects.filter(user=user).prefetch_related("items__product__image").order_by("-created_at")[:6])
    current = next((o for o in orders if o.status not in ("completed", "cancelled", "refunded")), None)
    shop = ShopSettings.load()
    referral = None
    if shop.referral_enabled:
        from shop.coupons import referral_code

        referral = referral_code(user)
    fav = [w.product for w in Wishlist.objects.filter(user=user, product__status="publish")
           .select_related("product__image").order_by("-created_at")[:4]]
    from shop.cart import Cart

    ctx.update({
        "current": current, "current_steps": steps(current) if current else None, "current_item": current.items.all()[0] if current and current.items.all() else None,
        "recent": [o for o in orders if o is not current][:4], "club": _club(user), "codes": _codes(user, ctx["profile"].mobile)[:3],
        "referral": referral, "shop": shop, "fav": fav, "cart_count": len(Cart(request).summary()["lines"]),
        "member_since": user.date_joined,
    })
    return render(request, "accounts/home.html", ctx)


# ------------------------------------------------------------------ سفارش‌ها
@login_required(login_url=LOGIN)
def orders(request):
    from shop.models import Order

    ctx = base_ctx(request, "orders", "سفارش‌های من")
    rows = []
    for o in Order.objects.filter(user=request.user).prefetch_related("items__product__image").order_by("-created_at")[:100]:
        items = list(o.items.all())
        rows.append({"o": o, "steps": steps(o), "first": items[0] if items else None, "more": max(len(items) - 1, 0)})
    ctx["rows"] = rows
    return render(request, "accounts/orders.html", ctx)


# ------------------------------------------------------------------ علاقه‌مندی‌ها
@login_required(login_url=LOGIN)
def wishlist(request):
    from api.models import Wishlist

    ctx = base_ctx(request, "wishlist", "علاقه‌مندی‌ها")
    ctx["items"] = [w.product for w in Wishlist.objects.filter(user=request.user).select_related("product__image")
                    .order_by("-created_at")]
    return render(request, "accounts/wishlist.html", ctx)


@require_POST
def wishlist_toggle(request, pk):
    """قلب صفحهٔ فرش: افزودن یا برداشتن (JSON)."""
    from api.models import Wishlist
    from catalog.models import Product

    if not request.user.is_authenticated:
        login = f"{LOGIN}?next={request.POST.get('next') or '/'}"
        if request.headers.get("X-Requested-With") == "fetch":
            return JsonResponse({"login": login}, status=401)
        return redirect(login)
    p = get_object_or_404(Product, pk=pk)
    w = Wishlist.objects.filter(user=request.user, product=p).first()
    if w:
        w.delete()
        on = False
    else:
        Wishlist.objects.create(user=request.user, product=p)
        on = True
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"on": on})
    return redirect(request.POST.get("next") or "/my-account/wishlist/")


# ------------------------------------------------------------------ خبرم کن
@login_required(login_url=LOGIN)
def alerts(request):
    from growth.models import ProductAlert

    ctx = base_ctx(request, "alerts", "خبرم کن‌ها")
    m = ctx["profile"].mobile or "-"
    qs = ProductAlert.objects.filter(Q(user=request.user) | Q(mobile=m)).select_related("product__image")
    if request.method == "POST" and (request.POST.get("delete") or "").isdigit():
        qs.filter(pk=int(request.POST["delete"])).delete()
        messages.success(request, "خبرم کن حذف شد.")
        return redirect("/my-account/alerts/")
    ctx["waiting"] = list(qs.filter(sent_at__isnull=True).order_by("-created_at")[:50])
    ctx["done"] = list(qs.filter(sent_at__isnull=False).order_by("-sent_at")[:20])
    return render(request, "accounts/alerts.html", ctx)


# ------------------------------------------------------------------ کدهای تخفیف و دعوت
@login_required(login_url=LOGIN)
def codes(request):
    from shop.models import ShopSettings

    ctx = base_ctx(request, "codes", "کدهای تخفیف و دعوت دوستان")
    shop = ShopSettings.load()
    referral = None
    if shop.referral_enabled:
        from shop.coupons import referral_code

        referral = referral_code(request.user)
    ctx.update({"codes": _codes(request.user, ctx["profile"].mobile), "referral": referral, "shop": shop, "club": _club(request.user)})
    return render(request, "accounts/codes.html", ctx)


# ------------------------------------------------------------------ اطلاعات حساب
@login_required(login_url=LOGIN)
def profile(request):
    from accounts.utils import latin_digits

    from shop.views import PROVINCES

    ctx = base_ctx(request, "profile", "اطلاعات حساب")
    user, p = request.user, ctx["profile"]
    errors = {}
    if request.method == "POST":
        P = request.POST
        user.first_name = P.get("first_name", "").strip()[:150]
        user.last_name = P.get("last_name", "").strip()[:150]
        email = P.get("email", "").strip()
        if email:
            try:
                validate_email(email)
                if get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    errors["email"] = "این ایمیل برای حساب دیگری ثبت شده است."
                else:
                    user.email = email
            except ValidationError:
                errors["email"] = "ایمیل درست نیست."
        else:
            user.email = ""
        pw = P.get("password", "")
        if pw and len(pw) < 8:
            errors["password"] = "رمز باید دست‌کم ۸ حرف باشد."
        postal = latin_digits(P.get("postal_code", "")).replace(" ", "")
        if postal and not (postal.isdigit() and len(postal) == 10):
            errors["postal_code"] = "کد پستی باید ۱۰ رقم باشد."
        if not errors:
            if pw:
                user.set_password(pw)
            user.save()
            p.province, p.city = P.get("province", "").strip()[:60], P.get("city", "").strip()[:80]
            p.address, p.postal_code = P.get("address", "").strip()[:1000], postal
            p.save(update_fields=["province", "city", "address", "postal_code"])
            if pw:
                update_session_auth_hash(request, user)
            messages.success(request, "اطلاعات حساب ذخیره شد.")
            return redirect("/my-account/profile/")
    ctx.update({"errors": errors, "provinces": PROVINCES})
    return render(request, "accounts/profile.html", ctx)
