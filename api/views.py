"""API اپلیکیشن ایران کارپت — /api/app/v1/

احراز هویت با سرآیند «Authorization: Token <کلید>»؛ کوکی و CSRF استفاده نمی‌شود.
همهٔ مبلغ‌ها تومان است.
"""
import json
import logging
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate
from django.core import signing
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import OtpCode
from accounts.utils import latin_digits, normalize_mobile
from catalog.models import AttributeTerm, Brand, Category, Product, ProductImage, Review, Variation
from catalog.views import SORTS, card_queryset
from core.models import SiteSettings
from pricing.models import Size
from shop import gateways
from shop.models import Order, ShopSettings
from shop.views import PROVINCES

from . import serializers as S
from .models import ApiToken, AppNotification, AppSettings, Device, Wishlist

log = logging.getLogger(__name__)
PER_PAGE = 20
PAY_SALT = "app-pay"


# ------------------------------------------------------------------ پایه
def ok(data, status=200):
    return JsonResponse(data, status=status, safe=False, json_dumps_params={"ensure_ascii": False})


def fail(message, status=400, **extra):
    return ok({"error": message, **extra}, status=status)


def payload(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body or b"{}")
        except ValueError:
            return {}
    return request.POST.dict()


def endpoint(methods=("GET",), login=False):
    def deco(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return fail("روش درخواست مجاز نیست.", 405)
            request.api_user = None
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Token "):
                tok = ApiToken.lookup(auth[6:].strip())
                if tok:
                    request.api_user = tok.user
                    if (timezone.now() - tok.last_used).total_seconds() > 3600:
                        ApiToken.objects.filter(pk=tok.pk).update(last_used=timezone.now())
            _touch_device(request)
            if login and request.api_user is None:
                return fail("ابتدا وارد شوید.", 401)
            return view(request, *args, **kwargs)
        return wrapper
    return deco


def _touch_device(request):
    iid = (request.headers.get("X-Install-Id") or "")[:64]
    if not iid:
        return
    defaults = {"app_version": (request.headers.get("X-App-Version") or "")[:20],
                "model": (request.headers.get("X-Device-Model") or "")[:100], "last_seen": timezone.now()}
    if request.api_user:
        defaults["user"] = request.api_user
    try:
        Device.objects.update_or_create(install_id=iid, defaults=defaults)
    except Exception:  # noqa: BLE001  (دو درخواست هم‌زمان)
        pass


def _int(v, default=0):
    try:
        return int(latin_digits(str(v)))
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ تنظیمات و صفحهٔ اول
@endpoint()
def config(request):
    app, site, shop = AppSettings.load(), SiteSettings.load(), ShopSettings.load()
    return ok({
        "latest_version": app.latest_version, "min_version": app.min_version,
        "update_url": app.update_url, "update_note": app.update_note,
        "site_name": site.site_name, "phone": site.phone, "whatsapp": site.whatsapp, "email": site.email,
        "shop": {"deposit_percent": shop.deposit_percent, "free_shipping_min": shop.free_shipping_min,
                 "allow_full": shop.allow_full, "allow_deposit": shop.allow_deposit, "note": S.plain(shop.checkout_note)},
        "gateways": [{"key": g.key, "name": gateways.GATEWAY_NAMES.get(g.key, g.key)} for g in gateways.enabled(shop)],
        "sorts": [{"key": k, "label": v[1]} for k, v in SORTS.items()],
        "provinces": PROVINCES,
    })


@endpoint()
def home(request):
    from core.views import HOME_REEDS

    base = card_queryset(Product.objects.published().exclude(stock_status="outofstock").filter(image__isnull=False))
    reeds = []
    for r in HOME_REEDS:
        term = AttributeTerm.objects.filter(attribute__slug="reeds-per-meter", slug=r).first()
        if term:
            items = list(base.filter(specs=term).order_by("-views")[:10])
            if items:
                reeds.append({"term_id": term.pk, "slug": term.slug, "name": term.name, "products": [S.card(p) for p in items]})
    site = SiteSettings.load()
    cats = Category.objects.filter(parent=None).select_related("image").order_by("order")[:16]
    stats = Review.objects.filter(parent=None, is_approved=True, rating__gt=0).values("rating")
    n = stats.count()
    return ok({
        "notice": AppSettings.load().home_notice,
        "trust_points": [{"title": t[0], "subtitle": t[1]} for t in (site.trust_points or []) if t],
        "categories": [{"id": c.pk, "name": c.name, "image": S.thumb_url(c.image, 240)} for c in cats],
        "reeds": reeds,
        "newest": [S.card(p) for p in base.order_by("-published_at")[:10]],
        "popular": [S.card(p) for p in base.order_by("-views")[:10]],
        "rating": {"count": n, "avg": round(sum(x["rating"] for x in stats) / n, 1) if n else 0},
    })


@endpoint()
def categories(request):
    rows = list(Category.objects.select_related("image").order_by("order", "name"))
    by_parent = {}
    for c in rows:
        by_parent.setdefault(c.parent_id, []).append(c)
    own = {}
    for cid, pid in Product.categories.through.objects.filter(product__status="publish").values_list("category_id", "product_id"):
        own.setdefault(cid, set()).add(pid)

    def tree(pid):
        out = []
        for c in by_parent.get(pid, []):
            children, ids = tree(c.pk)
            ids = ids | own.get(c.pk, set())
            out.append(({"id": c.pk, "name": c.name, "count": len(ids), "image": S.thumb_url(c.image, 240),
                         "children": children}, ids))
        return [x for x, _ in out], set().union(*[i for _, i in out]) if out else set()

    return ok(tree(None)[0])


# ------------------------------------------------------------------ محصولات
def filtered_products(g):
    qs = Product.objects.published()
    q = (g.get("q") or "").strip()[:100]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(sku__iexact=latin_digits(q)) | Q(english_name__icontains=q))
    if g.get("category"):
        cat = Category.objects.filter(pk=_int(g["category"])).first()
        qs = qs.filter(categories__in=cat.descendant_ids()) if cat else qs.none()
    if g.get("tag"):
        qs = qs.filter(tags__pk=_int(g["tag"]))
    if g.get("brand"):
        qs = qs.filter(brand__pk=_int(g["brand"]))
    for key in ("reeds", "color", "term"):
        vals = [x for x in (g.getlist(key) if hasattr(g, "getlist") else [g.get(key)]) if x]
        for val in vals:
            qs = qs.filter(specs__pk=_int(val))
    if g.get("size"):
        qs = qs.filter(variations__size__pk=_int(g["size"]), variations__is_available=True)
    if g.get("instock"):
        qs = qs.exclude(stock_status="outofstock")
    if g.get("min"):
        qs = qs.filter(min_price__gte=_int(g["min"]))
    if g.get("max"):
        qs = qs.filter(min_price__lte=_int(g["max"]))
    if g.get("ids"):
        qs = qs.filter(pk__in=[_int(x) for x in g["ids"].split(",") if x.strip()][:50])
    sort = g.get("sort") if g.get("sort") in SORTS else "new"
    return qs.distinct().order_by("stock_status", SORTS[sort][0])


@endpoint()
def products(request):
    qs = card_queryset(filtered_products(request.GET))
    page = max(1, _int(request.GET.get("page"), 1))
    p = Paginator(qs, PER_PAGE)
    try:
        items = p.page(page).object_list if p.count else []
    except EmptyPage:
        items = []
    return ok({"count": p.count, "page": page, "pages": p.num_pages if p.count else 0,
               "results": [S.card(x) for x in items]})


@endpoint()
def filters(request):
    ids = filtered_products(request.GET).values("pk")
    terms = lambda slug, n=40: [  # noqa: E731
        {"id": t.pk, "name": t.name, "count": t.n}
        for t in AttributeTerm.objects.filter(attribute__slug=slug, products__in=ids).annotate(n=Count("products", distinct=True))
        .order_by("order", "name")[:n]]
    return ok({
        "reeds": terms("reeds-per-meter"),
        "colors": sorted(terms("background-color", 60), key=lambda x: -x["count"]),
        "sizes": [{"id": s.pk, "name": s.label, "count": s.n} for s in Size.objects.filter(
            variations__product__in=ids, is_active=True).exclude(type="custom").annotate(
            n=Count("variations__product", distinct=True)).order_by("sort_order")],
        "brands": [{"id": b.pk, "name": b.name, "count": b.n} for b in Brand.objects.filter(products__in=ids)
                   .annotate(n=Count("products", distinct=True)).order_by("-n")[:40]],
    })


@endpoint()
def product(request, pk):
    p = (Product.objects.published().select_related("image", "brand", "album", "primary_category")
         .prefetch_related("categories", "tags").filter(pk=pk).first())
    if not p:
        return fail("این محصول پیدا نشد.", 404)
    gallery = [pi.media for pi in ProductImage.objects.filter(product=p).select_related("media").order_by("order")]
    if p.image and p.image not in gallery:
        gallery.insert(0, p.image)
    variations = list(p.variations.select_related("size").prefetch_related("attributes").order_by("size__sort_order", "menu_order"))
    specs = {}
    for t in p.specs.select_related("attribute").order_by("attribute__order", "order"):
        specs.setdefault(t.attribute.label, []).append(t.name)
    reviews = Review.objects.filter(product=p, parent=None, is_approved=True).order_by("-created_at")[:20]
    faqs = p.faqs.filter(is_active=True).order_by("order")
    related = []
    if p.primary_category_id or p.categories.exists():
        cat = p.primary_category or p.categories.first()
        related = list(card_queryset(Product.objects.published().filter(categories=cat).exclude(pk=p.pk)
                                     .exclude(stock_status="outofstock").order_by("-views"))[:10])
    Product.objects.filter(pk=p.pk).update(views=p.views + 1)
    data = S.product_detail(p, gallery, variations, [{"name": k, "value": "، ".join(v)} for k, v in specs.items()],
                            reviews, faqs, related)
    data["in_wishlist"] = bool(request.api_user and Wishlist.objects.filter(user=request.api_user, product=p).exists())
    return ok(data)


# ------------------------------------------------------------------ ورود
@endpoint(methods=("POST",))
def auth_otp(request):
    from accounts.views import _dev_codes, send_code

    mobile = normalize_mobile(payload(request).get("mobile"))
    if not mobile:
        return fail("شمارهٔ موبایل را درست وارد کنید؛ مثل ۰۹۱۲۱۲۳۴۵۶۷.")
    err = send_code(request, mobile)
    if err:
        return fail(err, 429)
    from accounts.views import user_for_mobile

    data = {"sent": True, "mobile": mobile, "is_new": user_for_mobile(mobile) is None, "resend_after": 60}
    if _dev_codes():
        data["dev_code"] = request.session.get("dev_otp")
    return ok(data)


def _login_payload(user, device):
    from accounts.views import profile_of

    return {"token": ApiToken.issue(user, device), "user": _me(user, profile_of(user))}


def _me(user, profile):
    return {"first_name": user.first_name, "last_name": user.last_name, "email": user.email, "mobile": profile.mobile or "",
            "province": profile.province, "city": profile.city, "address": profile.address, "postal_code": profile.postal_code}


@endpoint(methods=("POST",))
def auth_verify(request):
    from accounts.views import create_customer, user_for_mobile

    d = payload(request)
    mobile = normalize_mobile(d.get("mobile"))
    code = latin_digits(str(d.get("code", ""))).strip()
    otp = OtpCode.objects.filter(mobile=mobile, used=False).order_by("-created_at").first() if mobile else None
    if not (otp and otp.verify(code)):
        return fail("کد درست نیست یا منقضی شده است.")
    user = user_for_mobile(mobile) or create_customer(mobile, d.get("name", ""))
    return ok(_login_payload(user, d.get("device", "")))


@endpoint(methods=("POST",))
def auth_password(request):
    d = payload(request)
    user = authenticate(request, username=latin_digits(str(d.get("identifier", ""))).strip(), password=d.get("password", ""))
    if not user:
        return fail("موبایل/ایمیل یا رمز درست نیست.", 401)
    return ok(_login_payload(user, d.get("device", "")))


@endpoint(methods=("POST",), login=True)
def auth_logout(request):
    key = request.headers.get("Authorization", "")[6:].strip()
    tok = ApiToken.lookup(key)
    if tok:
        tok.delete()
    return ok({"ok": True})


@endpoint(methods=("GET", "POST"), login=True)
def me(request):
    from accounts.views import profile_of

    u = request.api_user
    p = profile_of(u)
    if request.method == "POST":
        d = payload(request)
        for f in ("first_name", "last_name"):
            if f in d:
                setattr(u, f, str(d[f]).strip()[:150])
        if "email" in d:
            u.email = str(d["email"]).strip()[:254]
        u.save()
        for f in ("province", "city", "address"):
            if f in d:
                setattr(p, f, str(d[f]).strip()[:500])
        if "postal_code" in d:
            p.postal_code = latin_digits(str(d["postal_code"])).replace(" ", "")[:10]
        p.save()
    return ok(_me(u, p))


# ------------------------------------------------------------------ سبد و سفارش
class _Line:
    """سطر سبد (هم‌شکل shop.cart.Line)."""

    def __init__(self, v, qty):
        from shop.cart import Cart

        self.variation, self.product = v, v.product
        self.qty = Cart.fix_qty(v, qty)
        self.unit_price = v.price or 0
        self.problem = ""
        if not self.product.is_purchasable or not v.is_available:
            self.problem = "این سایز الان موجود نیست."
        elif not self.unit_price:
            self.problem = "قیمت این سایز استعلامی است."

    @property
    def total(self):
        return self.unit_price * self.qty

    @property
    def size_label(self):
        v = self.variation
        parts = [v.size.label] if v.size else []
        parts += [a.name for a in v.attributes.all()]
        return "، ".join(parts) or v.sku


def _summary(items):
    qty = {}
    for it in items or []:
        vid, q = _int(it.get("variation")), _int(it.get("qty"), 1)
        if vid and q > 0:
            qty[vid] = qty.get(vid, 0) + q
    vs = {v.pk: v for v in Variation.objects.filter(pk__in=list(qty)[:50]).select_related("product__image", "product__album", "size")
          .prefetch_related("attributes")}
    lines = [_Line(vs[k], q) for k, q in qty.items() if k in vs]
    good = [x for x in lines if not x.problem]
    return {"lines": lines, "total": sum(x.total for x in good), "has_problem": any(x.problem for x in lines)}


def _summary_json(summary, shop, mode="full"):
    total = summary["total"]
    return {
        "lines": [{"variation": x.variation.pk, "product_id": x.product.pk, "title": x.product.title, "size": x.size_label,
                   "image": S.thumb_url(x.product.image, 240), "unit_price": x.unit_price, "qty": x.qty, "total": x.total,
                   "pair_only": x.variation.is_pair_only, "problem": x.problem} for x in summary["lines"]],
        "total": total, "has_problem": summary["has_problem"],
        "deposit": shop.deposit_amount(total), "remaining_after_deposit": total - shop.deposit_amount(total),
        "free_shipping": total >= shop.free_shipping_min, "free_shipping_min": shop.free_shipping_min,
        "shipping": {m: shop.shipping_for(m, total) for m in ("full", "deposit")},
    }


@endpoint(methods=("POST",))
def cart_quote(request):
    return ok(_summary_json(_summary(payload(request).get("items")), ShopSettings.load()))


@endpoint(methods=("POST",), login=True)
def order_create(request):
    from shop.views import create_order

    d = payload(request)
    shop = ShopSettings.load()
    summary = _summary(d.get("items"))
    if not summary["lines"]:
        return fail("سبد خرید خالی است.")
    form = {k: str(d.get(k) or "").strip() for k in
            ("first_name", "last_name", "mobile", "email", "province", "city", "address", "postal_code", "note", "payment_mode", "gateway")}
    form["mobile"] = normalize_mobile(form["mobile"]) or form["mobile"]
    form["postal_code"] = latin_digits(form["postal_code"]).replace(" ", "")
    errors = {}
    for f, label in (("first_name", "نام"), ("last_name", "نام خانوادگی"), ("province", "استان"), ("city", "شهر"), ("address", "آدرس")):
        if not form[f]:
            errors[f] = f"{label} را وارد کنید."
    if form["province"] and form["province"] not in PROVINCES:
        errors["province"] = "استان را از فهرست انتخاب کنید."
    if not normalize_mobile(form["mobile"]):
        errors["mobile"] = "شمارهٔ موبایل درست نیست."
    if form["postal_code"] and not (form["postal_code"].isdigit() and len(form["postal_code"]) == 10):
        errors["postal_code"] = "کد پستی باید ۱۰ رقم باشد."
    modes = [m for m in ("full", "deposit") if getattr(shop, f"allow_{m}")]
    if form["payment_mode"] not in modes:
        errors["payment_mode"] = "نوع پرداخت را انتخاب کنید."
    if not any(g.key == form["gateway"] for g in gateways.enabled(shop)):
        errors["gateway"] = "درگاه پرداخت را انتخاب کنید."
    if summary["has_problem"]:
        errors["cart"] = "بعضی کالاهای سبد الان قابل خرید نیستند؛ آن‌ها را از سبد حذف کنید."
    if errors:
        return fail("لطفاً خطاها را برطرف کنید.", errors=errors)
    order = create_order(request.api_user, form, summary, shop)
    return ok({"order": S.order_row(order, items=True), "pay_url": _pay_url(request, order, form["gateway"])})


def _pay_url(request, order, gateway):
    token = signing.dumps({"o": order.number, "g": gateway}, salt=PAY_SALT)
    return request.build_absolute_uri(f"/api/app/v1/pay/{token}/")


@endpoint(login=True)
def orders(request):
    qs = Order.objects.filter(user=request.api_user).prefetch_related("items").order_by("-created_at")[:100]
    return ok([S.order_row(o) for o in qs])


@endpoint(methods=("GET", "POST"), login=True)
def order(request, number):
    o = Order.objects.filter(user=request.api_user, number=number).prefetch_related("items__product__image", "payments").first()
    if not o:
        return fail("سفارش پیدا نشد.", 404)
    data = S.order_row(o, items=True)
    if request.method == "POST":   # پرداخت دوباره
        gw = payload(request).get("gateway") or ""
        if not o.can_pay:
            return fail("این سفارش قابل پرداخت نیست.")
        if not any(g.key == gw for g in gateways.enabled(ShopSettings.load())):
            return fail("درگاه پرداخت را انتخاب کنید.")
        data["pay_url"] = _pay_url(request, o, gw)
    return ok(data)


def pay(request, token):
    """صفحه‌ای که اپ در مرورگر باز می‌کند و مشتری را به درگاه بانک می‌برد."""
    from shop.views import start_payment

    try:
        d = signing.loads(token, salt=PAY_SALT, max_age=60 * 60)
    except signing.BadSignature:
        raise Http404
    o = Order.objects.filter(number=d["o"]).first()
    gw = next((g for g in gateways.enabled(ShopSettings.load()) if g.key == d["g"]), None)
    if not o or not gw:
        raise Http404
    if not o.can_pay:
        return render(request, "api/return.html", {"order": o, "paid": o.is_paid, "message": "", "meta": {"robots": "noindex"}})
    return start_payment(request, o, gw, source="app")


def app_return(request, number):
    """بعد از بانک: برگشت به اپ با پیوند irancarpet://"""
    o = Order.objects.filter(number=number).first()
    if not o:
        raise Http404
    return render(request, "api/return.html", {
        "order": o, "paid": request.GET.get("paid") == "1" and o.is_paid, "message": request.GET.get("msg", "")[:200],
        "meta": {"robots": "noindex", "title": "بازگشت به اپ"},
    })


@endpoint(methods=("POST",))
def track(request):
    d = payload(request)
    mobile = normalize_mobile(d.get("mobile"))
    num = _int(d.get("number"))
    o = Order.objects.filter(number=num, mobile=mobile).prefetch_related("items").first() if mobile and num else None
    if not o:
        return fail("سفارشی با این شماره و موبایل پیدا نشد.", 404)
    return ok(S.order_row(o))


# ------------------------------------------------------------------ علاقه‌مندی و اعلان
@endpoint(methods=("GET", "POST"), login=True)
def wishlist(request):
    u = request.api_user
    if request.method == "POST":
        d = payload(request)
        ids = [_int(x) for x in (d.get("add") or [])] + ([_int(d["product"])] if d.get("product") else [])
        for pid in ids:
            if Product.objects.filter(pk=pid).exists():
                Wishlist.objects.get_or_create(user=u, product_id=pid)
        rm = [_int(x) for x in (d.get("remove") or [])]
        if rm:
            Wishlist.objects.filter(user=u, product_id__in=rm).delete()
    ids = list(Wishlist.objects.filter(user=u).order_by("-created_at").values_list("product_id", flat=True))
    items = {p.pk: p for p in card_queryset(Product.objects.filter(pk__in=ids))}
    return ok({"ids": ids, "products": [S.card(items[i]) for i in ids if i in items]})


@endpoint()
def notifications(request):
    since = request.GET.get("since")
    qs = AppNotification.objects.filter(is_active=True, created_at__lte=timezone.now()).select_related("image")
    if since:
        try:
            from datetime import datetime

            qs = qs.filter(created_at__gt=datetime.fromisoformat(since))
        except ValueError:
            pass
    return ok([{
        "id": n.id, "title": n.title, "body": n.body, "kind": n.kind, "image": S.thumb_url(n.image, 480),
        "product_id": n.product_id, "category_id": n.category_id, "url": n.url, "created_at": n.created_at.isoformat(),
    } for n in qs[:20]])


# ------------------------------------------------------------------ تصویر کوچک
def thumb(request, w, path):
    """نسخهٔ webp کوچک یک تصویر از پوشهٔ آپلود؛ بار اول ساخته و نگه داشته می‌شود."""
    from PIL import Image

    if w not in S.THUMB_SIZES or ".." in path:
        raise Http404
    root = Path(settings.MEDIA_ROOT)
    src = root / path
    out = root / "app-thumbs" / str(w) / (path + ".webp")
    if not out.exists():
        if not src.is_file():
            raise Http404
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((w, w * 2))
                tmp = out.with_suffix(".tmp")
                im.save(tmp, "WEBP", quality=82, method=4)
                tmp.replace(out)
        except OSError:
            raise Http404
    resp = FileResponse(open(out, "rb"), content_type="image/webp")
    resp["Cache-Control"] = "public, max-age=2592000, immutable"
    return resp
