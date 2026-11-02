"""API پنل فروشندگان برای اپ «ایران کارپت فروشندگان»: خلاصه و آمار، کالا و قیمت، آلبوم، سفارش، پرسش.

ورود همان ورود اپ فروشگاه است (کد پیامکی ← توکن)؛ هر درخواست فقط دادهٔ فروشگاه خود کاربر را می‌بیند.
"""
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from catalog.models import Product, Review, Variation
from market import orders as O
from market import products as P
from market import stats as ST
from market.models import MarketSettings, Seller, SellerOrder
from pricing.models import Album, Size

from .views import _int, endpoint, fail, ok, payload


def _seller(request):
    s = getattr(request.api_user, "seller", None) if request.api_user else None
    if s is None:
        return None, fail("این حساب فروشگاهی در ایران کارپت ندارد. از سایت ← «در ایران کارپت بفروشید» ثبت‌نام کنید.", 403,
                          code="not_seller")
    if s.status not in (Seller.Status.ACTIVE, Seller.Status.PAUSED):
        return None, fail(f"فروشگاه شما «{s.get_status_display()}» است.", 403, code="not_active", status=s.status)
    return s, None


def seller_endpoint(methods=("GET",)):
    def deco(view):
        @endpoint(methods, login=True)
        def wrapper(request, *a, **kw):
            s, err = _seller(request)
            if err:
                return err
            request.seller = s
            return view(request, *a, **kw)
        wrapper.__name__ = view.__name__
        return wrapper
    return deco


def _img(media, w=480):
    from core.templatetags.fa import thumb

    return thumb(media, w) if media else ""


def _seller_json(s):
    return {"id": s.pk, "name": s.name, "slug": s.slug, "url": s.get_absolute_url(), "status": s.status, "logo": _img(s.logo, 240),
            "accent": s.accent_color, "city": s.city, "trusted": s.trusted}


# ------------------------------------------------------------------ خلاصه و آمار
@seller_endpoint()
def summary(request):
    s = request.seller
    rows, sm = ST.summary(s, 7)
    prods = Product.objects.filter(seller=s)
    from market.seller import _open_questions

    return ok({
        "seller": _seller_json(s),
        "week": {k: v for k, v in sm.items()}, "today": {k: rows[-1][k] for k in ("views", "orders", "sales")},
        "series": [{"label": r["label"], "sales": r["sales"], "views": r["views"], "orders": r["orders"]} for r in rows],
        "todo": {"new_orders": s.orders.filter(status=SellerOrder.Status.NEW).count(),
                 "to_ship": s.orders.filter(status=SellerOrder.Status.ACCEPTED).count(),
                 "questions": _open_questions(s).count(), "rejected": prods.filter(review_status="rejected").count(),
                 "out": prods.filter(status="publish", stock_status="outofstock").count()},
        "balance": O.balances(s), "followers": s.followers.count(),
    })


@seller_endpoint()
def stats(request):
    s = request.seller
    n = _int(request.GET.get("d"), 30)
    n = n if n in ST.RANGES else 30
    rows, sm = ST.summary(s, n)
    return ok({
        "days": n, "totals": sm,
        "series": [{"label": r["label"], "sales": r["sales"], "views": r["views"], "store": r["store"], "products": r["products"],
                    "orders": r["orders"]} for r in rows],
        "top_viewed": [{"id": x["product"].pk, "title": x["product"].title, "image": _img(x["product"].image, 240), "views": x["views"]}
                       for x in ST.top_viewed(s, n)],
        "top_sold": [{"id": x["product"].pk, "title": x["product"].title, "image": _img(x["product"].image, 240), "qty": x["qty"]}
                     for x in ST.top_sold(s, n)],
    })


# ------------------------------------------------------------------ کالاها
def _product_json(p, full=False):
    d = {"id": p.pk, "title": p.title, "image": _img(p.image, 240), "status": p.status, "review": p.review_status,
         "review_note": p.review_note, "in_stock": p.stock_status != "outofstock", "min_price": p.min_price,
         "album": {"id": p.album_id, "name": p.album.name} if p.album_id else None, "url": p.get_absolute_url()}
    if full:
        d["variations"] = [{"id": v.pk, "size": v.size.label if v.size_id else v.sku, "size_id": v.size_id, "price": v.manual_price,
                            "sale": v.sale_price, "qty": v.stock_qty, "final": v.final_price, "available": v.is_available}
                           for v in p.variations.all()]
    return d


@seller_endpoint()
def products(request):
    s = request.seller
    qs = Product.objects.filter(seller=s).select_related("image", "album").prefetch_related("variations__size").order_by("-pk")
    f = request.GET.get("f", "")
    if f == "out":
        qs = qs.filter(stock_status="outofstock")
    elif f in ("pending", "rejected"):
        qs = qs.filter(review_status=f)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(sku=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return ok({"items": [_product_json(p, True) for p in page.object_list], "page": page.number, "pages": page.paginator.num_pages,
               "count": page.paginator.count})


@seller_endpoint(("POST",))
def product_stock(request, pk):
    p = get_object_or_404(Product, pk=pk, seller=request.seller)
    on = str(payload(request).get("on")) in ("1", "true", "True")
    Variation.objects.filter(product=p).update(is_available=on)
    if on:
        Variation.objects.filter(product=p, stock_qty=0).update(stock_qty=None)
    p.refresh_price_cache()
    p.refresh_from_db()
    return ok(_product_json(p, True))


@seller_endpoint(("POST",))
def product_prices(request, pk):
    """{"variations": [{"id", "price", "sale", "qty", "available"}]} — قیمت، تخفیف و موجودی هر سایز (بدون بررسی دوباره)."""
    p = get_object_or_404(Product, pk=pk, seller=request.seller)
    rows = payload(request).get("variations") or []
    for r in rows if isinstance(rows, list) else []:
        v = p.variations.filter(pk=_int(r.get("id"))).first()
        if not v:
            continue
        if "available" in r:
            v.is_available = bool(r["available"])
        if not p.album_id:
            price = _int(r.get("price"), None) if r.get("price") not in (None, "") else v.manual_price
            if price and price >= 10_000:
                v.manual_price = price
            sale = _int(r.get("sale"), 0) if "sale" in r else v.sale_price
            v.sale_price = sale if sale and v.manual_price and sale < v.manual_price else None
        if "qty" in r:
            q = r.get("qty")
            v.stock_qty = None if q in (None, "") else max(0, _int(q))
            if v.stock_qty == 0:
                v.is_available = False
        v.save()
    p.refresh_price_cache()
    p.refresh_from_db()
    return ok(_product_json(p, True))


# ------------------------------------------------------------------ آلبوم‌ها
def _album_json(a, rows=False):
    d = {"id": a.pk, "name": a.name, "base_size": a.base_size.label, "base_size_id": a.base_size_id, "base_price": int(a.base_price),
         "products": a.products.count(), "updated": a.last_updated.isoformat()}
    if rows:
        from market.seller import album_rows

        d["sizes"] = [{"id": r["size"].pk, "label": r["size"].label, "on": r["on"] or bool(r["base"]), "base": bool(r["base"]),
                       "manual": r["manual"], "auto": r["auto"]} for r in album_rows(a)]
    return d


@seller_endpoint()
def albums(request):
    return ok({"items": [_album_json(a) for a in Album.all_objects.filter(seller=request.seller).select_related("base_size")]})


@seller_endpoint(("GET", "POST"))
def album(request, pk):
    """POST {"base_price", "prices": {size_id: قیمت یا null}, "sizes": [size_id…]} ← قیمت همهٔ کالاهای آلبوم به‌روز می‌شود."""
    a = get_object_or_404(Album.all_objects.select_related("base_size"), pk=pk, seller=request.seller)
    if request.method == "POST":
        d = payload(request)
        bp = _int(d.get("base_price"), 0)
        if bp and bp < 10_000:
            return fail("قیمت سایز پایه را به تومان بنویسید.")
        if bp:
            a.base_price = Decimal(bp)
        if isinstance(d.get("sizes"), list):
            ids = {_int(x) for x in d["sizes"]} | {a.base_size_id}
            sizes = list(Size.objects.filter(pk__in=ids, is_active=True))
        else:
            sizes = list(a.sizes.all())
        prices = dict(a.size_prices or {})
        for k, v in (d.get("prices") or {}).items():
            if v in (None, "", 0):
                prices.pop(str(k), None)
            elif _int(v) >= 10_000:
                prices[str(_int(k))] = _int(v)
        a.size_prices = {k: v for k, v in prices.items() if int(k) in {z.pk for z in sizes} and int(k) != a.base_size_id}
        a.save()
        a.sizes.set(sizes)
        from pricing.albums import sync_album_variations

        prods = list(a.products.all())
        if prods:
            sync_album_variations(prods)
    return ok(_album_json(a, rows=True))


# ------------------------------------------------------------------ افزودن با عکس
@seller_endpoint(("POST",))
def quick(request):
    s = request.seller
    a = Album.all_objects.filter(pk=_int(request.POST.get("album")), seller=s).first()
    cat = P.Category.objects.filter(pk=_int(request.POST.get("category"))).first()
    files = request.FILES.getlist("photos")
    if not a or not cat or not files:
        return fail("آلبوم، دسته و عکس‌ها لازم است.")
    from market.quick import build

    try:
        created = build(s, a, cat, (request.POST.get("prefix") or a.name).strip()[:120], files[:60], request.POST)
    except ValueError as e:
        return fail(str(e))
    return ok({"created": [_product_json(p) for p in created]}, 201)


@seller_endpoint()
def form_options(request):
    """دسته‌ها و آلبوم‌ها برای فرم افزودن با عکس."""
    return ok({"categories": [{"id": c.pk, "name": c.name, "child": bool(c.parent_id)} for c in P.categories()],
               "albums": [{"id": a.pk, "name": a.name} for a in Album.all_objects.filter(seller=request.seller)]})


# ------------------------------------------------------------------ سفارش‌ها
def _order_json(so, full=False):
    ms = MarketSettings.load()
    d = {"id": so.pk, "number": so.order.number, "status": so.status, "status_label": so.get_status_display(),
         "total": so.items_total, "share": so.seller_amount, "paid_at": so.paid_at.isoformat() if so.paid_at else None,
         "accept_until": (so.paid_at + timezone.timedelta(hours=ms.accept_hours)).isoformat() if so.paid_at else None,
         "tracking_code": so.tracking_code}
    if full:
        o = so.order
        d["customer"] = {"name": o.full_name, "mobile": o.mobile if so.status in (SellerOrder.Status.ACCEPTED, SellerOrder.Status.SHIPPED) else "",
                         "address": f"{o.province}، {o.city}، {o.address}" if so.status != SellerOrder.Status.NEW else f"{o.province}، {o.city}",
                         "postal_code": o.postal_code if so.status != SellerOrder.Status.NEW else ""}
        d["items"] = [{"title": it.title, "size": it.size_label, "qty": it.quantity, "price": it.unit_price} for it in so.items.all()]
    return d


@seller_endpoint()
def orders(request):
    qs = request.seller.orders.exclude(status=SellerOrder.Status.WAITING).select_related("order").order_by("-created_at")
    f = request.GET.get("f", "open")
    if f == "open":
        qs = qs.filter(status__in=[SellerOrder.Status.NEW, SellerOrder.Status.ACCEPTED])
    elif f in SellerOrder.Status.values:
        qs = qs.filter(status=f)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return ok({"items": [_order_json(so) for so in page.object_list], "page": page.number, "pages": page.paginator.num_pages})


@seller_endpoint(("GET", "POST"))
def order(request, pk):
    so = get_object_or_404(SellerOrder.objects.select_related("order"), pk=pk, seller=request.seller)
    if so.status == SellerOrder.Status.WAITING:
        return fail("پیدا نشد.", 404)
    if request.method == "POST":
        d = payload(request)
        act = d.get("act")
        if act == "accept":
            done = O.accept(so)
        elif act == "ship":
            code = str(d.get("tracking_code") or "").strip()
            if len(code) < 4:
                return fail("کد رهگیری یا شمارهٔ بارنامه را بنویسید.")
            done = O.ship(so, code, str(d.get("carrier") or ""))
        elif act == "cancel":
            reason = str(d.get("reason") or "").strip()
            if len(reason) < 5:
                return fail("دلیل لغو را بنویسید.")
            done = O.cancel(so, reason)
        else:
            return fail("کار نامعتبر.")
        if not done:
            return fail("این کار در وضعیت فعلی سفارش ممکن نیست.")
        so.refresh_from_db()
    return ok(_order_json(so, True))


# ------------------------------------------------------------------ پرسش‌ها
@seller_endpoint(("GET", "POST"))
def questions(request):
    s = request.seller
    if request.method == "POST":
        import re

        from accounts.utils import latin_digits

        d = payload(request)
        q = Review.objects.filter(pk=_int(d.get("id")), product__seller=s, parent__isnull=True).first()
        text = str(d.get("answer") or "").strip()
        if not q or len(text) < 2:
            return fail("پرسش یا پاسخ نامعتبر.")
        if re.search(r"(?:09\d{9}|https?://|www\.|@\w{3,})", latin_digits(text)):
            return fail("شمارهٔ تماس، پیوند یا شناسهٔ شبکهٔ اجتماعی در پاسخ مجاز نیست.")
        Review.objects.create(product=q.product, parent=q, author_name=f"فروشگاه {s.name}"[:200], content=text[:2000], is_approved=True,
                              kind=q.kind, user=request.api_user)
        Review.objects.filter(pk=q.pk).update(is_approved=True)
    rows = (Review.objects.filter(product__seller=s, parent__isnull=True, kind="question").select_related("product__image")
            .prefetch_related("replies").order_by("-created_at")[:60])
    return ok({"items": [{"id": r.pk, "text": r.content, "name": r.author_name, "at": r.created_at.isoformat(),
                          "product": {"id": r.product_id, "title": r.product.title, "image": _img(r.product.image, 240)},
                          "answers": [a.content for a in r.replies.all()]} for r in rows]})
