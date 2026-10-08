"""صفحه‌های سایت: «در ایران کارپت بفروشید»، پنل فروشنده و صفحهٔ عمومی هر فروشگاه."""
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits, normalize_mobile
from affiliate.models import clean_sheba, valid_sheba
from catalog.models import Product
from shop.models import Order

from . import orders as O
from . import products as P
from .models import MarketSettings, Seller, SellerOrder

LOGIN = "/my-account/login/"
META = {"robots": "noindex, nofollow"}


def _provinces():
    from shop.views import PROVINCES as PV

    return PV


def _seller(request):
    return getattr(request.user, "seller", None) if request.user.is_authenticated else None


def seller_required(fn):
    """فقط فروشندهٔ ثبت‌نام‌شده؛ کارهای فروش فقط برای فروشندهٔ فعال یا تعطیل موقت."""
    @login_required(login_url=LOGIN)
    def wrap(request, *a, **kw):
        s = _seller(request)
        if s is None:
            return redirect("/sell/")
        if s.status not in (Seller.Status.ACTIVE, Seller.Status.PAUSED) and request.path != "/seller/":
            return redirect("/seller/")
        request.seller = s
        return fn(request, *a, **kw)
    wrap.__name__ = fn.__name__
    return wrap


def _ctx(request, title, tab, **kw):
    s = request.seller
    pending_orders = s.orders.filter(status=SellerOrder.Status.NEW).count()
    return {"meta": {**META, "title": title}, "seller": s, "tab": tab, "pending_orders": pending_orders, "ms": MarketSettings.load(), **kw}


# ------------------------------------------------------------------ معرفی و ثبت‌نام
def _clean_slug(v):
    v = slugify(latin_digits(v or "").strip().lower(), allow_unicode=False)[:60]
    return v if re.match(r"^[a-z0-9][a-z0-9-]{2,59}$", v or "") else ""


def landing(request):
    ms = MarketSettings.load()
    if not ms.enabled:
        raise Http404
    s = _seller(request)
    errors, data = {}, {}
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{LOGIN}?next=/sell/%23join")
        if s is not None:
            return redirect("/seller/")
        if not ms.signup_open:
            raise Http404
        keys = ("name", "slug", "kind", "owner_name", "national_id", "phone", "province", "city", "address", "about", "sheba",
                "account_holder")
        data = {k: (request.POST.get(k) or "").strip() for k in keys}
        if len(data["name"]) < 3:
            errors["name"] = "نام فروشگاه را بنویسید."
        elif Seller.objects.filter(name__iexact=data["name"]).exists():
            errors["name"] = "این نام قبلاً ثبت شده است."
        slug = _clean_slug(data["slug"]) or _clean_slug(re.sub(r"[^a-z0-9]+", "-", data["slug"].lower()))
        if data["slug"] and not slug:
            errors["slug"] = "فقط حروف کوچک انگلیسی، عدد و خط تیره (۳ تا ۶۰ حرف)."
        if slug and Seller.objects.filter(slug=slug).exists():
            errors["slug"] = "این نشانی گرفته شده است."
        if len(data["owner_name"]) < 3:
            errors["owner_name"] = "نام و نام خانوادگی را بنویسید."
        nid = latin_digits(data["national_id"])
        if data["kind"] == Seller.Kind.COMPANY:
            if not re.match(r"^\d{11}$", nid):
                errors["national_id"] = "شناسهٔ ملی شرکت ۱۱ رقم است."
        elif not _valid_melli(nid):
            errors["national_id"] = "کد ملی ۱۰ رقمی درست نیست."
        if not data["city"]:
            errors["city"] = "شهری که از آن ارسال می‌کنید را بنویسید."
        sheba = clean_sheba(data["sheba"])
        if sheba and not valid_sheba(sheba):
            errors["sheba"] = "شماره شبا درست نیست (IR و ۲۴ رقم)."
        if not request.POST.get("terms"):
            errors["terms"] = "برای ثبت‌نام، قوانین فروشندگان را بپذیرید."
        if not errors:
            from accounts.views import profile_of

            mobile = normalize_mobile(getattr(profile_of(request.user), "mobile", "") or request.user.username)
            base = slug or _clean_slug(f"shop-{request.user.pk}") or f"shop-{request.user.pk}"
            Seller.objects.create(
                user=request.user, name=data["name"][:80], slug=base, kind=data["kind"] if data["kind"] in Seller.Kind.values else "person",
                owner_name=data["owner_name"][:120], national_id=nid[:11], mobile=mobile, phone=latin_digits(data["phone"])[:20],
                province=data["province"][:60], city=data["city"][:80], address=data["address"][:1000], about=data["about"][:3000],
                sheba=sheba, account_holder=data["account_holder"][:120] or data["owner_name"][:120])
            try:
                from shop.notify import admin_text

                admin_text(f"درخواست تازهٔ فروشندگی: «{data['name']}» از {data['city']}. پنل ← فروشندگان.")
            except Exception:  # noqa: BLE001
                pass
            return redirect("/seller/")
    return render(request, "market/landing.html", {
        "meta": {"title": "در ایران کارپت بفروشید", "description":
                 "فرش و کالاهای مرتبط خود را در ایران کارپت بفروشید: پرداخت امن، تسویهٔ منظم و دسترسی به خریداران فرش سراسر ایران."},
        "ms": ms, "s": s, "errors": errors, "data": data, "terms": ms.terms_list(), "provinces": _provinces(),
        "commission": ms.default_commission,
    })


def _valid_melli(c):
    if not re.match(r"^\d{10}$", c or "") or len(set(c)) == 1:
        return False
    total = sum(int(c[i]) * (10 - i) for i in range(9)) % 11
    return int(c[9]) == (total if total < 2 else 11 - total)


# ------------------------------------------------------------------ داشبورد
@seller_required
def dashboard(request):
    s = request.seller
    if s.status not in (Seller.Status.ACTIVE, Seller.Status.PAUSED):
        return render(request, "market/status.html", {"meta": {**META, "title": "پنل فروشنده"}, "seller": s, "ms": MarketSettings.load()})
    since = timezone.now() - timezone.timedelta(days=30)
    sold = s.orders.exclude(status__in=[SellerOrder.Status.WAITING, SellerOrder.Status.CANCELLED])
    month = sold.filter(paid_at__gte=since).aggregate(t=Sum("items_total"), n=Count("pk"))
    prods = Product.objects.filter(seller=s)
    return render(request, "market/dashboard.html", _ctx(
        request, "پنل فروشنده", "home",
        bal=O.balances(s), month_total=month["t"] or 0, month_count=month["n"],
        new_orders=s.orders.filter(status__in=[SellerOrder.Status.NEW, SellerOrder.Status.ACCEPTED]).select_related("order")[:10],
        counts={"live": prods.filter(status="publish").count(), "pending": prods.filter(review_status="pending").count(),
                "rejected": prods.filter(review_status="rejected").count(),
                "out": prods.filter(status="publish", stock_status="outofstock").count()},
    ))


@seller_required
@require_POST
def toggle_pause(request):
    s = request.seller
    if s.status == Seller.Status.ACTIVE:
        s.status = Seller.Status.PAUSED
        messages.success(request, "فروشگاه موقتاً تعطیل شد و کالاهایتان از سایت برداشته شد.")
    elif s.status == Seller.Status.PAUSED:
        s.status = Seller.Status.ACTIVE
        messages.success(request, "فروشگاه دوباره باز شد.")
    s.save(update_fields=["status"])
    P.set_visibility(s)
    return redirect("/seller/")


# ------------------------------------------------------------------ کالاها
@seller_required
def product_list(request):
    s = request.seller
    if request.method == "POST":
        n = P.quick_update(s, request.POST)
        messages.success(request, f"{n} قیمت/موجودی به‌روز شد." if n else "تغییری نبود.")
        return redirect(request.get_full_path())
    qs = Product.objects.filter(seller=s).select_related("image", "primary_category").prefetch_related("variations__size").order_by("-pk")
    f = request.GET.get("f", "")
    if f == "pending":
        qs = qs.filter(review_status="pending")
    elif f == "rejected":
        qs = qs.filter(review_status="rejected")
    elif f == "out":
        qs = qs.filter(stock_status="outofstock")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(sku=q))
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "market/products.html", _ctx(request, "کالاهای من", "products", page=page, f=f, q=q))


@seller_required
def product_edit(request, pk=None):
    s = request.seller
    product = get_object_or_404(Product, pk=pk, seller=s) if pk else None
    errors = {}
    if request.method == "POST":
        product, errors, changed = P.save_product(s, request.POST, request.FILES, product)
        if not errors:
            if changed and product.review_status == "pending":
                messages.success(request, "ذخیره شد و برای بررسی فرستاده شد؛ بعد از تأیید در سایت منتشر می‌شود.")
            else:
                messages.success(request, "ذخیره شد.")
            return redirect(f"/seller/products/{product.pk}/")
    form = _product_form(request.POST if errors else None, product)
    return render(request, "market/product_edit.html", _ctx(
        request, "ویرایش کالا" if product else "افزودن کالا", "products", product=product, errors=errors, form=form,
        attrs=P.spec_attributes(), cats=P.categories(), sizes=P.sizes(), max_images=P.MAX_IMAGES,
    ))


def _product_form(post, p):
    from content.render import to_text
    from core.templatetags.fa import toman

    if post is not None:
        vs = []
        for i, vid in enumerate(post.getlist("v_id")):
            g = lambda k: (post.getlist(k)[i] if i < len(post.getlist(k)) else "")  # noqa: E731
            vs.append({"id": vid, "size": g("v_size"), "label": g("v_label"), "price": g("v_price"), "sale": g("v_sale"),
                       "qty": g("v_qty"), "pair": g("v_pair") == "1"})
        return {"title": post.get("title", ""), "category": post.get("category", ""), "short": post.get("short", ""),
                "description": post.get("description", ""), "specs": {k[5:]: v for k, v in post.items() if k.startswith("spec_")},
                "variations": vs or [{}], "images": list(p.images.select_related("media").order_by("order", "pk")) if p else []}
    if p is None:
        return {"variations": [{}], "specs": {}, "images": []}
    return {
        "title": p.title, "category": str(p.primary_category_id or ""), "short": to_text(p.short_description),
        "description": to_text(p.content), "specs": {str(t.attribute_id): str(t.pk) for t in p.specs.all()},
        "variations": [{"id": v.pk, "size": str(v.size_id or ""), "label": v.sku if not v.size_id else "",
                        "price": toman(v.manual_price) if v.manual_price else "", "sale": toman(v.sale_price) if v.sale_price else "", "qty": "" if v.stock_qty is None else v.stock_qty, "pair": bool(v.pair_only)}
                       for v in p.variations.order_by("menu_order", "pk")] or [{}],
        "images": list(p.images.select_related("media").order_by("order", "pk")),
    }


@seller_required
@require_POST
def product_hide(request, pk):
    p = get_object_or_404(Product, pk=pk, seller=request.seller)
    if p.status == Product.Status.PUBLISH:
        Product.objects.filter(pk=p.pk).update(status=Product.Status.PRIVATE)
        messages.success(request, "کالا از سایت برداشته شد.")
    elif p.review_status == "approved" and request.seller.is_active:
        Product.objects.filter(pk=p.pk).update(status=Product.Status.PUBLISH)
        messages.success(request, "کالا دوباره در سایت نمایش داده می‌شود.")
    return redirect("/seller/products/")


# ------------------------------------------------------------------ سفارش‌ها
@seller_required
def order_list(request):
    s = request.seller
    qs = s.orders.exclude(status=SellerOrder.Status.WAITING).select_related("order").annotate(n=Count("items"))
    f = request.GET.get("f", "open")
    if f == "open":
        qs = qs.filter(status__in=[SellerOrder.Status.NEW, SellerOrder.Status.ACCEPTED])
    elif f in SellerOrder.Status.values:
        qs = qs.filter(status=f)
    page = Paginator(qs.order_by("-created_at"), 25).get_page(request.GET.get("page"))
    return render(request, "market/orders.html", _ctx(request, "سفارش‌ها", "orders", page=page, f=f,
                                                      statuses=[x for x in SellerOrder.Status.choices if x[0] != "waiting"]))


@seller_required
def order_detail(request, pk):
    s = request.seller
    so = get_object_or_404(SellerOrder.objects.select_related("order"), pk=pk, seller=s)
    if so.status == SellerOrder.Status.WAITING:
        raise Http404
    if request.method == "POST":
        act = request.POST.get("act")
        ok = False
        if act == "accept":
            ok = O.accept(so)
            msg = "سفارش پذیرفته شد؛ آن را آماده و ارسال کنید."
        elif act == "ship":
            code = (request.POST.get("tracking_code") or "").strip()
            if len(code) < 4:
                messages.error(request, "کد رهگیری یا شمارهٔ بارنامه را بنویسید.")
                return redirect(request.path)
            ok = O.ship(so, code, request.POST.get("carrier") or "")
            msg = "ارسال ثبت شد و کد رهگیری برای مشتری پیامک شد."
        elif act == "cancel":
            reason = (request.POST.get("reason") or "").strip()
            if len(reason) < 5:
                messages.error(request, "دلیل لغو را بنویسید.")
                return redirect(request.path)
            ok = O.cancel(so, reason)
            msg = "سفارش لغو شد و به ایران کارپت اطلاع داده شد."
        (messages.success if ok else messages.error)(request, msg if ok else "این کار در وضعیت فعلی سفارش ممکن نیست.")
        return redirect(request.path)
    return render(request, "market/order_detail.html", _ctx(
        request, f"سفارش {so.order.number}", "orders", so=so, o=so.order,
        items=so.items.select_related("product", "variation"),
        carriers=["پست پیشتاز", "تیپاکس", "باربری", "پیک", "چاپار", "ماهکس"],
    ))


# ------------------------------------------------------------------ مالی و تنظیمات
@seller_required
def finance(request):
    s = request.seller
    rows = s.orders.exclude(status__in=[SellerOrder.Status.WAITING]).select_related("order").order_by("-created_at")
    page = Paginator(rows, 30).get_page(request.GET.get("page"))
    return render(request, "market/finance.html", _ctx(request, "مالی و تسویه", "finance", bal=O.balances(s), page=page,
                                                       payouts=s.payouts.all()[:30]))


@seller_required
def shop_settings(request):
    s = request.seller
    errors = {}
    if request.method == "POST":
        d = {k: (request.POST.get(k) or "").strip() for k in ("about", "phone", "province", "city", "address", "shipping", "prep_days",
                                                              "return_policy", "sheba", "account_holder")}
        sheba = clean_sheba(d["sheba"])
        if sheba and not valid_sheba(sheba):
            errors["sheba"] = "شماره شبا درست نیست (IR و ۲۴ رقم)."
        if not d["city"]:
            errors["city"] = "شهر ارسال لازم است."
        days = P._int(d["prep_days"])
        if days is None or not (0 <= days <= 60):
            errors["prep_days"] = "زمان آماده‌سازی را به روز بنویسید (۰ تا ۶۰)."
        logo = request.FILES.get("logo")
        if logo and not errors:
            try:
                s.logo = P.save_image(logo)
            except ValueError as e:
                errors["logo"] = str(e)
        if not errors:
            s.about, s.phone, s.province, s.city, s.address = d["about"][:3000], latin_digits(d["phone"])[:20], d["province"][:60], d["city"][:80], d["address"][:1000]
            s.shipping = d["shipping"] if d["shipping"] in Seller.Shipping.values else s.shipping
            s.prep_days, s.return_policy = days, d["return_policy"][:300]
            s.sheba, s.account_holder = sheba, d["account_holder"][:120]
            s.save()
            messages.success(request, "تنظیمات فروشگاه ذخیره شد.")
            return redirect("/seller/settings/")
    return render(request, "market/settings.html", _ctx(request, "تنظیمات فروشگاه", "settings", errors=errors, provinces=_provinces()))


# ------------------------------------------------------------------ صفحهٔ عمومی فروشگاه
def store(request, slug):
    s = get_object_or_404(Seller, slug=slug)
    if s.status not in (Seller.Status.ACTIVE, Seller.Status.PAUSED):
        raise Http404
    from catalog.views import card_queryset

    qs = card_queryset(Product.objects.published().filter(seller=s).order_by("-published_at"))
    page = Paginator(qs, settings.PRODUCTS_PER_PAGE).get_page(request.GET.get("page"))
    stats = s.orders.filter(status=SellerOrder.Status.DELIVERED).count()
    return render(request, "market/store.html", {
        "meta": {"title": f"فروشگاه {s.name} در ایران کارپت", "description": (s.about or f"کالاهای {s.name} از {s.city}")[:160]},
        "store": s, "page": page, "delivered": stats,
    })


# ------------------------------------------------------------------ مشتری: تأیید تحویل
@login_required(login_url=LOGIN)
@require_POST
def customer_received(request, number, pk):
    order = get_object_or_404(Order, number=number, user=request.user)
    so = get_object_or_404(SellerOrder, pk=pk, order=order)
    if O.deliver(so):
        messages.success(request, "ممنون؛ تحویل ثبت شد.")
    return redirect(order.get_absolute_url())
