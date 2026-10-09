"""صفحه‌های عمومی رشد فروش: پرداخت سریع از پیامک، ثبت نظر از پیامک، «خبرم کن»، ثبت نظر از صفحهٔ فرش."""
from django.contrib import messages
from django.core import signing
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits, normalize_mobile
from catalog.models import Product

from .jobs import QUICKPAY_SALT, REVIEW_SALT
from .models import ProductAlert

META = {"robots": "noindex,nofollow"}


def _order_from(token, salt, days):
    from shop.models import Order

    try:
        number = signing.loads(token, salt=salt, max_age=days * 86400)
    except signing.BadSignature:
        raise Http404
    return get_object_or_404(Order.objects.prefetch_related("items"), number=number)


# ------------------------------------------------------------------ پرداخت سریع (پیوند پیامک)
def quickpay(request, token):
    from shop import gateways, paymode
    from shop.models import ShopSettings
    from shop.views import start_payment

    order = _order_from(token, QUICKPAY_SALT, 30)
    gws = gateways.enabled(ShopSettings.load())
    if request.method == "POST" and order.can_pay:
        gw = next((g for g in gws if g.key == request.POST.get("gateway")), None)
        if gw:
            paymode.switch(order, request.POST.get("mode"))
            return start_payment(request, order, gw, source="quickpay")
        messages.error(request, "درگاه پرداخت را انتخاب کنید.")
    return render(request, "growth/quickpay.html", {
        "meta": {**META, "title": f"پرداخت سفارش {order.number}"}, "order": order, "gateways": gws,
        "paid": request.GET.get("paid") == "1", "modes": paymode.options(order), "due": paymode.due_word(order),
    })


# ------------------------------------------------------------------ ثبت نظر از پیامک
def review_invite(request, token):
    from catalog import reviews

    order = _order_from(token, REVIEW_SALT, 60)
    seen, items = set(), []
    for it in order.items.all():
        if it.product_id and it.product_id not in seen:
            seen.add(it.product_id)
            items.append(it)
    done = request.GET.get("done") == "1"
    if request.method == "POST":
        n = 0
        name = f"{order.first_name} {order.last_name[:1]}.".strip()
        for it in items:
            pid = it.product_id
            rating = latin_digits(request.POST.get(f"rating_{pid}", "0"))
            text = (request.POST.get(f"text_{pid}") or "").strip()
            photos = request.FILES.getlist(f"photos_{pid}")
            if not (rating.isdigit() and int(rating)) and not text and not photos:
                continue
            reviews.create(it.product, user=order.user, name=name, mobile=order.mobile, rating=int(rating or 0) if rating.isdigit() else 0,
                           text=text or "—", photos=photos, order=order)
            n += 1
        if n:
            return redirect(request.path + "?done=1")
        messages.error(request, "دست‌کم برای یک فرش امتیاز یا نظر بدهید.")
    from crm.models import CrmSettings

    cs = CrmSettings.load()
    return render(request, "growth/review_invite.html", {
        "meta": {**META, "title": "نظر شما دربارهٔ فرش"}, "order": order, "items": items, "done": done,
        "reward": cs.review_reward_amount if cs.review_reward_enabled else 0,
    })


# ------------------------------------------------------------------ ثبت نظر از صفحهٔ فرش
@require_POST
def product_review(request, slug):
    from catalog import reviews

    product = get_object_or_404(Product.objects.published(), slug=slug)
    back = product.get_absolute_url() + "#reviews"
    if not request.user.is_authenticated:
        return redirect(f"/my-account/login/?next={back}")
    if not cache.add(f"rv:{request.user.pk}:{product.pk}", 1, 120):
        messages.info(request, "نظر شما ثبت شده است.")
        return redirect(back)
    rating = latin_digits(request.POST.get("rating", "0"))
    text = (request.POST.get("text") or "").strip()
    if len(text) < 5 and not (rating.isdigit() and int(rating)):
        messages.error(request, "امتیاز بدهید یا چند کلمه بنویسید.")
        return redirect(back)
    from accounts.views import profile_of

    reviews.create(product, user=request.user, name=request.user.get_full_name() or "مشتری ایران کارپت",
                   mobile=profile_of(request.user).mobile or "", rating=int(rating) if rating.isdigit() else 0,
                   text=text or "—", photos=request.FILES.getlist("photos"))
    messages.success(request, "ممنون! نظر شما بعد از بررسی نمایش داده می‌شود.")
    return redirect(back)


# ------------------------------------------------------------------ «خبرم کن»
def create_alert(product, kind, mobile, user=None, source="web", ip=""):
    """(ok، پیام)"""
    if kind not in ("stock", "price"):
        return False, "نوع درخواست درست نیست."
    mobile = normalize_mobile(mobile or "")
    if not mobile:
        return False, "شمارهٔ موبایل درست نیست."
    if not _rate_ok(ip or mobile):
        return False, "درخواست‌های زیادی فرستاده‌اید؛ کمی بعد دوباره امتحان کنید."
    ProductAlert.objects.get_or_create(product=product, mobile=mobile, kind=kind, sent_at=None,
                                       defaults={"user": user, "price_at": product.min_price, "source": source})
    if kind == "stock":
        return True, "وقتی این فرش موجود شد، با پیامک خبرتان می‌کنیم."
    return True, "اگر قیمت این فرش کم شد، با پیامک خبرتان می‌کنیم."


def _rate_ok(key):
    k = f"alert-rate:{key}"
    n = cache.get(k, 0)
    if n >= 15:
        return False
    cache.set(k, n + 1, 3600)
    return True


@require_POST
def alert(request):
    product = get_object_or_404(Product.objects.published(), pk=latin_digits(request.POST.get("product", "0")) or 0)
    user = request.user if request.user.is_authenticated else None
    mobile = request.POST.get("mobile")
    if user and not mobile:
        from accounts.views import profile_of

        mobile = profile_of(user).mobile or user.username
    ok, msg = create_alert(product, request.POST.get("kind"), mobile, user, "web", request.META.get("REMOTE_ADDR", ""))
    (messages.success if ok else messages.error)(request, msg)
    return redirect(product.get_absolute_url())
