import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits, normalize_mobile
from catalog.models import Variation
from installments.services import active_plans, describe
from installments.views import plans_payload

from . import gateways, notify
from .cart import Cart
from .models import Order, OrderItem, Payment, ShopSettings

log = logging.getLogger(__name__)
META = {"robots": "noindex, nofollow"}
LOGIN = "/my-account/login/"

PROVINCES = [
    "آذربایجان شرقی", "آذربایجان غربی", "اردبیل", "اصفهان", "البرز", "ایلام", "بوشهر", "تهران", "چهارمحال و بختیاری",
    "خراسان جنوبی", "خراسان رضوی", "خراسان شمالی", "خوزستان", "زنجان", "سمنان", "سیستان و بلوچستان", "فارس", "قزوین",
    "قم", "کردستان", "کرمان", "کرمانشاه", "کهگیلویه و بویراحمد", "گلستان", "گیلان", "لرستان", "مازندران", "مرکزی",
    "هرمزگان", "همدان", "یزد",
]


# ------------------------------------------------------------------ سبد
def cart_view(request):
    from installments.services import teaser

    cart = Cart(request)
    summary = _with_coupon(request, cart.summary())
    return render(request, "shop/cart.html", {"meta": {**META, "title": "سبد خرید"}, **summary, "shop": ShopSettings.load(),
                                              "inst_teaser": teaser(summary["total"]) if summary["total"] else None})


def _with_coupon(request, summary):
    """کد تخفیفی که مشتری در سبد زده (در نشست نگه داشته می‌شود)."""
    from .coupons import apply

    user = request.user if request.user.is_authenticated else None
    out = apply(summary, request.session.get("coupon", ""), user)
    out["coupon_code"] = request.session.get("coupon", "")
    return out


@require_POST
def cart_add(request):
    v = Variation.objects.filter(pk=latin_digits(request.POST.get("variation", "0")) or 0).select_related("product", "size").first()
    back = request.META.get("HTTP_REFERER") or "/cart/"
    if not v:
        messages.error(request, "لطفاً یک سایز انتخاب کنید.")
        return redirect(back)
    from .offers import for_variation

    offer = for_variation(v)
    if not offer and not (v.product.is_purchasable and v.is_available and v.price):
        messages.error(request, "این سایز الان قابل خرید نیست.")
        return redirect(v.product.get_absolute_url())
    try:
        qty = int(latin_digits(request.POST.get("qty", "1")))
    except ValueError:
        qty = 1
    cart = Cart(request)
    if offer and request.POST.get("offer"):  # «خرید همین یک تخته»
        total = cart.set(v, 1)
    else:
        total = cart.add(v, qty)
    if offer and total > 1:
        messages.info(request, "قیمت ویژه فقط برای خرید یک تخته از این سایز است؛ با تعداد بیشتر، قیمت معمول حساب می‌شود.")
    if v.is_pair_only and total % 2 == 0 and qty % 2:
        messages.info(request, "این سایز فقط به‌صورت جفت فروخته می‌شود؛ تعداد زوج شد.")
    messages.success(request, f"«{v.product.title}» به سبد اضافه شد.")
    return redirect("/cart/")


@require_POST
def cart_update(request):
    cart = Cart(request)
    rm = request.POST.get("remove")
    if rm:
        cart.remove(rm)
        return redirect("/cart/")
    for line in cart.lines():
        val = request.POST.get(f"qty-{line.variation.pk}")
        if val is not None:
            try:
                cart.set(line.variation, int(latin_digits(val)))
            except ValueError:
                pass
    go = request.POST.get("go")
    if go == "coupon":
        from .coupons import check

        code = (request.POST.get("coupon") or "").strip().upper()
        user = request.user if request.user.is_authenticated else None
        sm = cart.summary()
        c, d, err = check(code, user, sm["total"] - sm.get("offer_total", 0))
        if err:
            messages.error(request, err)
        else:
            request.session["coupon"] = code
            messages.success(request, f"کد {code} اعمال شد: {d:,} تومان تخفیف.")
        return redirect("/cart/")
    if go == "nocoupon":
        request.session.pop("coupon", None)
        return redirect("/cart/")
    if go == "checkout":
        return redirect("/checkout/")
    messages.success(request, "سبد به‌روز شد.")
    return redirect("/cart/")


# ------------------------------------------------------------ تسویه حساب
def account_legacy(request):
    return redirect("/my-account/")


def checkout_legacy(request):
    return HttpResponsePermanentRedirect("/checkout/")


def _initial(user):
    from accounts.views import profile_of

    p = profile_of(user)
    last = Order.objects.filter(user=user).order_by("-created_at").first()
    return {
        "first_name": user.first_name or (last.first_name if last else ""),
        "last_name": user.last_name or (last.last_name if last else ""),
        "mobile": p.mobile or (last.mobile if last else "") or normalize_mobile(user.username),
        "email": user.email,
        "province": p.province or (last.province if last else ""),
        "city": p.city or (last.city if last else ""),
        "address": p.address or (last.address if last else ""),
        "postal_code": p.postal_code or (last.postal_code if last else ""),
        "payment_mode": "full",
    }


@login_required(login_url=LOGIN)
def checkout(request):
    cart = Cart(request)
    summary = _with_coupon(request, cart.summary())
    shop = ShopSettings.load()
    if not summary["lines"]:
        return redirect("/cart/")
    gws = gateways.enabled(shop)
    modes = [m for m in ("full", "deposit") if getattr(shop, f"allow_{m}")]
    plans = active_plans(summary["total"])
    if plans:
        modes.append("installment")
    form = _initial(request.user)
    if request.GET.get("mode") in modes:
        form["payment_mode"] = request.GET["mode"]
    errors = {}
    inst = None
    if request.method == "POST":
        form = {k: (request.POST.get(k) or "").strip() for k in
                ("first_name", "last_name", "mobile", "email", "province", "city", "address", "postal_code", "note", "payment_mode", "gateway")}
        form["mobile"] = normalize_mobile(form["mobile"]) or form["mobile"]
        form["postal_code"] = latin_digits(form["postal_code"]).replace(" ", "")
        for f, label in (("first_name", "نام"), ("last_name", "نام خانوادگی"), ("province", "استان"), ("city", "شهر"), ("address", "آدرس")):
            if not form[f]:
                errors[f] = f"{label} را وارد کنید."
        if not normalize_mobile(form["mobile"]):
            errors["mobile"] = "شمارهٔ موبایل درست نیست."
        if form["postal_code"] and not (form["postal_code"].isdigit() and len(form["postal_code"]) == 10):
            errors["postal_code"] = "کد پستی باید ۱۰ رقم باشد."
        if form["payment_mode"] not in modes:
            errors["payment_mode"] = "نوع پرداخت را انتخاب کنید."
        pay_now = True
        if form["payment_mode"] == "installment":
            from installments.orders import read_request

            plan, q, info, uploads, inst_errors = read_request(request.POST, request.FILES, summary["total"])
            errors.update(inst_errors)
            inst = (plan, q, info, uploads)
            form.update({k: request.POST.get(k, "") for k in request.POST if k.startswith("inst_")})
            pay_now = bool(q and q["down"] and plan.down_timing == plan.DownTiming.CHECKOUT)
        gw = next((g for g in gws if g.key == form["gateway"]), None)
        if pay_now and not gw:
            errors["gateway"] = "درگاه پرداخت را انتخاب کنید."
        if summary["has_problem"]:
            errors["cart"] = "بعضی کالاهای سبد الان قابل خرید نیستند؛ آن‌ها را از سبد حذف کنید."
        if summary["coupon_error"]:
            errors["coupon"] = summary["coupon_error"] + " کد را از سبد حذف کنید یا کد دیگری بزنید."
        if not errors:
            order = create_order(request.user, form, summary, shop, installment=inst)
            request.session.pop("coupon", None)
            if not pay_now:
                Cart(request).clear()
                try:
                    notify.installment_request(order)
                except Exception:  # noqa: BLE001
                    log.exception("notify failed")
                return redirect(order.get_absolute_url() + "?placed=1")
            return start_payment(request, order, gw)
        if errors and form["payment_mode"] == "installment" and inst and inst[3]:
            errors.setdefault("inst_cheque_image", "برای امنیت، تصویر را دوباره انتخاب کنید.")
    total = summary["total"]
    return render(request, "shop/checkout.html", {
        "meta": {**META, "title": "تسویه حساب"}, **summary, "shop": shop, "form": form, "errors": errors,
        "gateways": gws, "modes": modes, "provinces": PROVINCES, "plans": [(p, describe(p)) for p in plans],
        "plans_json": plans_payload(plans),
        "deposit": shop.deposit_amount(total), "remaining": total - shop.deposit_amount(total), "free_shipping": total >= shop.free_shipping_min,
    })


@transaction.atomic
def create_order(user, form, summary, shop, source="web", installment=None):
    from accounts.views import profile_of

    total = summary["total"]
    mode = form["payment_mode"]
    order = Order.objects.create(
        user=user, first_name=form["first_name"][:100], last_name=form["last_name"][:100],
        mobile=normalize_mobile(form["mobile"]), email=form["email"][:254], province=form["province"][:60],
        city=form["city"][:80], address=form["address"], postal_code=form["postal_code"][:10], note=form["note"],
        payment_mode=mode, shipping_mode=shop.shipping_for(mode, total), items_total=total,
        coupon_code=summary["coupon"].code if summary.get("coupon") else "", discount=summary.get("discount") or 0,
        deposit_percent=shop.deposit_percent if mode == "deposit" else 0,
        online_amount=shop.deposit_amount(total) if mode == "deposit" else total,
    )
    if mode == "installment" and installment:
        from installments.orders import apply_to_order, save_uploads

        plan, q, info, uploads = installment
        apply_to_order(order, plan, q, info, save_uploads(order, uploads))
        order.save()
    OrderItem.objects.bulk_create([
        OrderItem(order=order, product=line.product, variation=line.variation, title=line.product.title[:300],
                  size_label=line.size_label[:150], unit_price=line.unit_price, quantity=line.qty,
                  offer=getattr(line, "offer", None))
        for line in summary["lines"] if not line.problem
    ])
    if any(getattr(line, "offer", None) for line in summary["lines"]):
        from .offers import clear

        clear()
    u = user
    u.first_name = u.first_name or form["first_name"][:150]
    u.last_name = u.last_name or form["last_name"][:150]
    u.save(update_fields=["first_name", "last_name"])
    p = profile_of(u)
    p.province, p.city, p.address, p.postal_code = order.province, order.city, order.address, order.postal_code
    p.save()
    return order


def web_return_url(order, source, paid):
    """پرداخت از پیوند پیامک (بدون ورود): برگشت به همان صفحهٔ پرداخت سریع."""
    if source == "quickpay":
        from growth.jobs import quickpay_url

        return quickpay_url(order).replace(settings.SITE_URL, "") + f"?paid={int(paid)}"
    return order.get_absolute_url() + ("?paid=1" if paid else "")


def app_return_url(order, source, paid, msg=""):
    """بازگشت از بانک به همان اپی که سفارش را ثبت کرده (ایران کارپت یا فرش‌یاب)."""
    url = f"/app/return/{order.number}/?paid={int(paid)}"
    if source == "app-finder":
        url += "&app=finder"
    return url + (f"&msg={msg[:120]}" if msg else "")


def start_payment(request, order, gw, source="web"):
    payment = Payment.objects.create(order=order, gateway=gw.key, amount=order.online_amount)
    callback = request.build_absolute_uri(f"/pay/{gw.key}/callback/")
    try:
        action = gw.start(payment, callback)
    except gateways.GatewayError as e:
        payment.status, payment.message = Payment.Status.FAILED, str(e)[:300]
        payment.raw = {**(payment.raw or {}), "source": source}
        payment.save()
        log.warning("payment start failed %s: %s", gw.key, e)
        if source.startswith("app"):
            return redirect(app_return_url(order, source, False))
        messages.error(request, f"اتصال به درگاه ممکن نشد: {e}. می‌توانید دوباره یا با درگاه دیگری پرداخت کنید.")
        return redirect(web_return_url(order, source, False))
    payment.raw = {**(payment.raw or {}), "source": source}
    payment.save()
    if "redirect" in action:
        return redirect(action["redirect"])
    return render(request, "shop/redirect.html", {"meta": {**META, "title": "انتقال به درگاه"}, "action": action, "gateway": gw})


@login_required(login_url=LOGIN)
@require_POST
def order_pay(request, number):
    order = get_object_or_404(Order, number=number, user=request.user)
    if not order.can_pay:
        return redirect(order.get_absolute_url())
    gw = next((g for g in gateways.enabled(ShopSettings.load()) if g.key == request.POST.get("gateway")), None)
    if not gw:
        messages.error(request, "درگاه پرداخت را انتخاب کنید.")
        return redirect(order.get_absolute_url())
    return start_payment(request, order, gw)


@csrf_exempt
def callback(request, gateway):
    gw = gateways.ALL.get(gateway)
    if not gw:
        raise Http404
    params = request.POST if request.method == "POST" else request.GET
    payment = gw.find_payment(params)
    if not payment:
        log.warning("callback without payment %s %s", gateway, dict(params.items()))
        return render(request, "shop/result.html", {"meta": {**META, "title": "نتیجهٔ پرداخت"}, "ok": False,
                                                   "message": "تراکنش پیدا نشد. اگر مبلغی کم شده، تا ۷۲ ساعت به حسابتان برمی‌گردد."})
    order = payment.order
    source = (payment.raw or {}).get("source") or "web"
    app = source.startswith("app")
    if payment.status != Payment.Status.INIT:
        return redirect(app_return_url(order, source, order.is_paid) if app else web_return_url(order, source, order.is_paid))
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status != Payment.Status.INIT:
            return redirect(order.get_absolute_url())
        try:
            res = gw.verify(payment, params)
        except gateways.GatewayError as e:
            res = gateways.Result(False, message=f"خطا در ارتباط با بانک: {e}")
        payment.raw = {**(payment.raw or {}), "callback": res.raw}
        payment.message = (res.message or "")[:300]
        payment.verified_at = timezone.now()
        if res.ok:
            payment.status, payment.ref_id, payment.card = Payment.Status.OK, res.ref_id[:100], res.card[:40]
            payment.save()
            order = Order.objects.select_for_update().get(pk=order.pk)
            order.mark_paid(payment.amount)
        else:
            payment.status = Payment.Status.FAILED
            payment.save()
    if res.ok:
        try:
            notify.order_paid(order, payment.amount)
        except Exception:  # noqa: BLE001
            log.exception("notify failed")
        if app:
            return redirect(app_return_url(order, source, True))
        return redirect(web_return_url(order, source, True))
    if app:
        return redirect(app_return_url(order, source, False, res.message or ""))
    messages.error(request, f"پرداخت انجام نشد. {res.message}")
    return redirect(web_return_url(order, source, False))


def fake_gateway(request, pk):
    if not settings.PAYMENT_FAKE:
        raise Http404
    payment = get_object_or_404(Payment, pk=pk, gateway="fake", status=Payment.Status.INIT)
    return render(request, "shop/fake_gateway.html", {"meta": {**META, "title": "درگاه آزمایشی"}, "payment": payment})


# ---------------------------------------------------------------- سفارش
@login_required(login_url=LOGIN)
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items", "payments"), number=number, user=request.user)
    if request.GET.get("paid") and order.is_paid:
        Cart(request).clear()
    return render(request, "shop/order_detail.html", {
        "meta": {**META, "title": f"سفارش {order.number}"}, "order": order,
        "just_paid": bool(request.GET.get("paid") or request.GET.get("placed")),
        "gateways": gateways.enabled(ShopSettings.load()) if order.can_pay else [], "shop": ShopSettings.load(),
    })


def track_order(request):
    ctx = {"meta": {**META, "title": "پیگیری سفارش"}}
    if request.method == "POST":
        num = latin_digits(request.POST.get("number", "")).strip()
        mobile = normalize_mobile(request.POST.get("mobile"))
        order = Order.objects.filter(number=int(num), mobile=mobile).first() if num.isdigit() and mobile else None
        ctx.update(number=num, mobile=request.POST.get("mobile", ""), searched=True, order=order)
    return render(request, "shop/track.html", ctx)
