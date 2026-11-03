"""پنل فروشنده (بخش‌های تازه): خانه و آمار، ظاهر ویترین، قفسه‌ها، آلبوم قیمت، افزودن سریع با عکس،
فرصت ویژه، کد تخفیف و پرسش‌ها. همهٔ صفحه‌ها اول برای موبایل طراحی شده‌اند."""
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits
from catalog.models import Product, Review, Variation
from pricing.models import Album, Size

from . import orders as O
from . import products as P
from . import stats as ST
from .models import MarketSettings, Seller, SellerOrder, SellerShelf, SellerSlide
from .views import _ctx, seller_required

MAX_PHOTOS = 6
MAX_SHELVES = 30
MAX_ALBUMS = 40


def _num(v):
    return P._int(v)


# ------------------------------------------------------------------ خانه
@seller_required
def home(request):
    s = request.seller
    if s.status not in (Seller.Status.ACTIVE, Seller.Status.PAUSED):
        return render(request, "market/status.html", {"meta": {"robots": "noindex, nofollow", "title": "پنل فروشنده"},
                                                       "seller": s, "ms": MarketSettings.load()})
    ms = MarketSettings.load()
    rows, sm = ST.summary(s, 7)
    today = rows[-1]
    now = timezone.now()
    waiting = list(s.orders.filter(status=SellerOrder.Status.NEW).select_related("order").order_by("paid_at")[:5])
    for so in waiting:
        if so.paid_at:
            left = so.paid_at + timedelta(hours=ms.accept_hours) - now
            so.hours_left = max(0, int(left.total_seconds() // 3600))
    prods = Product.objects.filter(seller=s)
    questions = _open_questions(s).count()
    todo = []
    if waiting:
        first = waiting[0]
        left = getattr(first, "hours_left", None)
        hint = ("مهلت پذیرش اولی تمام شده؛ همین حالا بپذیرید یا لغو کنید" if left == 0 else
                f"اولی {left} ساعت دیگر خودکار لغو می‌شود" if left is not None else "")
        todo.append({"n": len(waiting), "text": "سفارش منتظر پذیرش", "hint": hint, "url": "/seller/orders/", "tone": "pink", "icon": "bag"})
    ready = s.orders.filter(status=SellerOrder.Status.ACCEPTED).count()
    if ready:
        todo.append({"n": ready, "text": "سفارش آمادهٔ ارسال", "hint": "کد رهگیری را ثبت کنید", "url": "/seller/orders/?f=accepted",
                     "tone": "teal", "icon": "truck"})
    if questions:
        todo.append({"n": questions, "text": "پرسش بی‌پاسخ", "hint": "پاسخ شما زیر صفحهٔ کالا می‌آید", "url": "/seller/questions/",
                     "tone": "teal", "icon": "chat"})
    rejected = prods.filter(review_status="rejected").count()
    if rejected:
        todo.append({"n": rejected, "text": "کالا نیاز به اصلاح", "hint": "پیام بررسی را ببینید", "url": "/seller/products/?f=rejected",
                     "tone": "saffron", "icon": "alert"})
    out = prods.filter(status="publish", stock_status="outofstock").count()
    if out:
        todo.append({"n": out, "text": "کالای ناموجود در سایت", "hint": "اگر رسیده، موجودش کنید", "url": "/seller/products/?f=out",
                     "tone": "saffron", "icon": "box"})
    from .guides import setup_steps

    setup = setup_steps(s)
    return render(request, "market/home.html", _ctx(
        request, "پنل فروشنده", "home", rows=rows, sm=sm, today=today, chart=ST.chart(rows, "sales"), vchart=ST.chart(rows, "views"),
        todo=todo, setup=setup, bal=O.balances(s), followers=s.followers.count(), followers_new=ST.followers_new(s),
        counts={"live": prods.filter(status="publish").count(), "pending": prods.filter(review_status="pending").count()},
    ))


@seller_required
def stats(request):
    s = request.seller
    n = int(request.GET.get("d") or 30)
    n = n if n in ST.RANGES else 30
    rows, sm = ST.summary(s, n)
    return render(request, "market/stats.html", _ctx(
        request, "آمار فروشگاه", "stats", n=n, ranges=ST.RANGES, rows=rows, sm=sm,
        sales_chart=ST.chart(rows, "sales"), orders_chart=ST.chart(rows, "orders"), views_chart=ST.chart(rows, "views"),
        top_viewed=ST.top_viewed(s, n), top_sold=ST.top_sold(s, n), followers=s.followers.count(),
    ))


@seller_required
def more(request):
    return render(request, "market/more.html", _ctx(request, "بیشتر", "more"))


# ------------------------------------------------------------------ ظاهر ویترین
@seller_required
def look(request):
    s = request.seller
    errors = {}
    if request.method == "POST":
        act = request.POST.get("do") or "identity"
        try:
            if act == "identity":
                accent = (request.POST.get("accent") or "").strip()
                if re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
                    s.accent = accent.upper()
                s.tagline = (request.POST.get("tagline") or "").strip()[:120]
                s.about = (request.POST.get("about") or "").strip()[:3000]
                lay = request.POST.get("layout")
                if lay in dict(Seller._meta.get_field("layout").choices):
                    s.layout = lay
                fid = _num(request.POST.get("featured"))
                s.featured_product = Product.objects.filter(pk=fid, seller=s).first() if fid else None
                for field in ("logo", "cover"):
                    f = request.FILES.get(field)
                    if f:
                        setattr(s, field, P.save_image(f))
                if request.POST.get("remove_cover"):
                    s.cover = None
                s.save()
                msg = "ظاهر فروشگاه ذخیره شد."
                if s.accent_color != s.accent:
                    msg += " رنگ انتخابی برای نوشتهٔ سفید خیلی روشن است؛ تا رنگ تیره‌تری بزنید، رنگ پیش‌فرض نشان داده می‌شود."
                messages.success(request, msg)
            elif act == "photos":
                files = request.FILES.getlist("photos")
                room = MAX_PHOTOS - s.photos.count()
                for f in files[:max(room, 0)]:
                    s.photos.add(P.save_image(f))
                messages.success(request, "عکس‌ها افزوده شد." if files else "عکسی انتخاب نشد.")
            elif act == "photo_del":
                s.photos.remove(_num(request.POST.get("id")) or 0)
            elif act == "slide_add":
                f = request.FILES.get("image")
                if not f:
                    raise ValueError("عکس اسلاید را انتخاب کنید (افقی، دست‌کم ۱۶۰۰ پیکسل پهنا).")
                if s.slides.count() >= SellerSlide.MAX:
                    raise ValueError(f"حداکثر {SellerSlide.MAX} اسلاید.")
                pid = _num(request.POST.get("product"))
                SellerSlide.objects.create(seller=s, image=P.save_image(f), title=(request.POST.get("title") or "").strip()[:80],
                                           subtitle=(request.POST.get("subtitle") or "").strip()[:140],
                                           product=Product.objects.filter(pk=pid, seller=s).first() if pid else None,
                                           order=s.slides.count())
                messages.success(request, "اسلاید افزوده شد.")
            elif act in ("slide_del", "slide_up"):
                sl = get_object_or_404(SellerSlide, pk=_num(request.POST.get("id")) or 0, seller=s)
                if act == "slide_del":
                    sl.delete()
                else:
                    _move(list(s.slides.all()), sl)
            return redirect("/seller/look/" + ("#slides" if act.startswith("slide") else "#photos" if act.startswith("photo") else ""))
        except ValueError as e:
            errors["upload"] = str(e)
            messages.error(request, str(e))
    live = Product.objects.published().filter(seller=s).order_by("-published_at")[:200]
    return render(request, "market/look.html", _ctx(
        request, "ظاهر فروشگاه", "look", errors=errors, accents=Seller.ACCENTS, live=live,
        slides=list(s.slides.select_related("image", "product")), photos=list(s.photos.all()), max_photos=MAX_PHOTOS,
        max_slides=SellerSlide.MAX, layouts=Seller._meta.get_field("layout").choices,
    ))


def _move(items, item):
    """یک خانه بالاتر بردن در فهرست مرتب."""
    i = items.index(item)
    if i > 0:
        items[i - 1], items[i] = items[i], items[i - 1]
    for k, x in enumerate(items):
        if x.order != k:
            type(x).objects.filter(pk=x.pk).update(order=k)


# ------------------------------------------------------------------ قفسه‌ها
@seller_required
def shelves(request):
    s = request.seller
    if request.method == "POST":
        act = request.POST.get("do")
        if act == "add":
            name = (request.POST.get("name") or "").strip()[:60]
            if len(name) < 2:
                messages.error(request, "نام قفسه را بنویسید.")
            elif s.shelves.count() >= MAX_SHELVES:
                messages.error(request, f"حداکثر {MAX_SHELVES} قفسه.")
            elif s.shelves.filter(name=name).exists():
                messages.error(request, "قفسه‌ای با همین نام دارید.")
            else:
                SellerShelf.objects.create(seller=s, name=name, order=s.shelves.count())
                messages.success(request, f"قفسهٔ «{name}» ساخته شد؛ حالا کالاها را از فهرست کالاها در آن بگذارید.")
        else:
            sh = get_object_or_404(SellerShelf, pk=_num(request.POST.get("id")) or 0, seller=s)
            if act == "rename":
                name = (request.POST.get("name") or "").strip()[:60]
                if len(name) >= 2:
                    sh.name = name
                    sh.save(update_fields=["name"])
            elif act == "delete":
                sh.delete()
                messages.success(request, "قفسه حذف شد (کالاهایش سر جایشان هستند).")
            elif act == "up":
                _move(list(s.shelves.all()), sh)
        return redirect("/seller/shelves/")
    rows = s.shelves.annotate(n=Count("products", distinct=True))
    return render(request, "market/shelves.html", _ctx(request, "قفسه‌ها", "shelves", shelves=rows, max_shelves=MAX_SHELVES))


# ------------------------------------------------------------------ آلبوم قیمت
def seller_albums(s):
    return Album.all_objects.filter(seller=s).select_related("base_size").annotate(n=Count("products", distinct=True)).order_by("sort_order", "pk")


def album_rows(album):
    """سایزهای آلبوم با قیمت خودکار و دستی برای فرم."""
    chosen = set(album.sizes.values_list("pk", flat=True)) if album.pk else set()
    out = []
    for z in Size.objects.filter(is_active=True).exclude(type="m2").order_by("sort_order", "pk"):
        manual = (album.size_prices or {}).get(str(z.pk)) if album.pk else None
        auto = None
        if album.pk and album.base_price:
            saved = album.size_prices
            album.size_prices = {}
            auto = album.size_price(z)
            album.size_prices = saved
        out.append({"size": z, "on": z.pk in chosen, "manual": manual, "auto": auto, "base": album.pk and z.pk == album.base_size_id})
    return out


@seller_required
def albums(request):
    s = request.seller
    return render(request, "market/albums.html", _ctx(request, "آلبوم‌های قیمت", "albums", albums=seller_albums(s)))


@seller_required
def album_edit(request, pk=None):
    s = request.seller
    album = get_object_or_404(Album.all_objects, pk=pk, seller=s) if pk else Album(seller=s, profit_percent=0, shipping_fixed=0,
                                                                                    round_to=10_000, in_price_list=False)
    errors = {}
    if request.method == "POST":
        if request.POST.get("do") == "delete" and album.pk:
            n = album.products.count()
            if n:
                messages.error(request, f"این آلبوم {n} کالا دارد؛ اول کالاها را از آلبوم بیرون ببرید.")
                return redirect(f"/seller/albums/{album.pk}/")
            album.delete()
            messages.success(request, "آلبوم حذف شد.")
            return redirect("/seller/albums/")
        name = (request.POST.get("name") or "").strip()[:160]
        base_size = Size.objects.filter(pk=_num(request.POST.get("base_size")) or 0, is_active=True).first()
        base_price = _num(request.POST.get("base_price"))
        size_ids = [int(x) for x in request.POST.getlist("sizes") if str(x).isdigit()]
        sizes = list(Size.objects.filter(pk__in=size_ids, is_active=True))
        if len(name) < 3:
            errors["name"] = "نام آلبوم را بنویسید (مثل «۷۰۰ شانه پلی‌استر»)."
        if not base_size:
            errors["base_size"] = "سایز پایه را انتخاب کنید."
        if not base_price or base_price < 10_000:
            errors["base_price"] = "قیمت سایز پایه را به تومان بنویسید."
        if base_size and base_size not in sizes:
            sizes.append(base_size)
        manual = {}
        for z in sizes:
            v = _num(request.POST.get(f"price_{z.pk}"))
            if v and v >= 10_000 and (not base_size or z.pk != base_size.pk):
                manual[str(z.pk)] = v
        rnd = _num(request.POST.get("round_to"))
        if not errors and not pk and seller_albums(s).count() >= MAX_ALBUMS:
            errors["name"] = f"حداکثر {MAX_ALBUMS} آلبوم."
        if not errors:
            with transaction.atomic():
                album.name, album.base_size, album.base_price = name, base_size, Decimal(base_price)
                album.size_prices, album.round_to = manual, rnd if rnd in (0, 1_000, 10_000, 100_000) else 10_000
                album.profit_percent, album.shipping_fixed, album.waste_value, album.in_price_list = 0, 0, 0, False
                if not album.code:
                    album.code = f"S{s.pk}-{timezone.now().strftime('%y%m%d%H%M%S')}"
                album.save()
                album.sizes.set(sizes)
                from pricing.albums import sync_album_variations

                prods = list(album.products.all())
                if prods:
                    sync_album_variations(prods)
            messages.success(request, f"آلبوم ذخیره شد؛ قیمت {album.products.count()} کالا به‌روز شد." if pk else
                             "آلبوم ساخته شد؛ حالا با «افزودن با عکس» کالاهایش را بسازید یا در صفحهٔ هر کالا آلبوم را انتخاب کنید.")
            return redirect(f"/seller/albums/{album.pk}/")
    return render(request, "market/album_edit.html", _ctx(
        request, album.name if album.pk else "آلبوم تازه", "albums", album=album, errors=errors, rows=album_rows(album),
        sizes=Size.objects.filter(is_active=True).exclude(type="m2").order_by("sort_order", "pk"),
        products=list(album.products.select_related("image").order_by("-pk")[:60]) if album.pk else [],
        post=request.POST if errors else None,
        rounds=[(0, "بدون گرد کردن"), (1_000, "هزار تومان"), (10_000, "ده هزار تومان"), (100_000, "صد هزار تومان")],
    ))


# ------------------------------------------------------------------ افزودن سریع با عکس
@seller_required
def quick(request):
    s = request.seller
    albums_qs = list(seller_albums(s))
    errors, created = {}, []
    if request.method == "POST":
        album = next((a for a in albums_qs if a.pk == _num(request.POST.get("album"))), None)
        cat = P.Category.objects.filter(pk=_num(request.POST.get("category")) or 0).first()
        prefix = (request.POST.get("prefix") or "").strip()[:120]
        files = request.FILES.getlist("photos")
        if not album:
            errors["album"] = "آلبوم قیمت را انتخاب کنید (یا اول یک آلبوم بسازید)."
        if not cat:
            errors["category"] = "دسته را انتخاب کنید."
        if not files:
            errors["photos"] = "عکس فرش‌ها را انتخاب کنید."
        elif len(files) > 60:
            errors["photos"] = "در هر بار حداکثر ۶۰ عکس."
        if not errors:
            from .quick import build

            try:
                created = build(s, album, cat, prefix or album.name, files, request.POST)
            except ValueError as e:
                errors["photos"] = str(e)
            else:
                messages.success(request, f"{len(created)} کالا ساخته شد و برای بررسی رفت. عنوان هر کدام را می‌توانید اصلاح کنید.")
                return redirect("/seller/products/?f=pending")
    return render(request, "market/quick.html", _ctx(request, "افزودن با عکس", "quick", albums=albums_qs, cats=P.categories(),
                                                      attrs=P.spec_attributes(), errors=errors))


# ------------------------------------------------------------------ موجودی با یک لمس
@seller_required
@require_POST
def stock_toggle(request, pk):
    p = get_object_or_404(Product, pk=pk, seller=request.seller)
    on = request.POST.get("on") == "1"
    Variation.objects.filter(product=p).update(is_available=on)
    if on:
        Variation.objects.filter(product=p, stock_qty=0).update(stock_qty=None)
    p.refresh_price_cache()
    p.refresh_from_db(fields=["stock_status"])
    return JsonResponse({"on": p.stock_status != "outofstock"})


@seller_required
@require_POST
def bulk(request):
    """ویرایش گروهی از فهرست کالاها: گذاشتن در قفسه / برداشتن از قفسه / موجود / ناموجود."""
    s = request.seller
    ids = [int(x) for x in request.POST.getlist("ids") if str(x).isdigit()]
    qs = Product.objects.filter(seller=s, pk__in=ids)
    act = request.POST.get("do")
    n = qs.count()
    if not n:
        messages.error(request, "کالایی انتخاب نشده.")
    elif act in ("shelf_add", "shelf_remove"):
        sh = get_object_or_404(SellerShelf, pk=_num(request.POST.get("shelf")) or 0, seller=s)
        (sh.products.add if act == "shelf_add" else sh.products.remove)(*qs)
        messages.success(request, f"{n} کالا {'در' if act == 'shelf_add' else 'از'} قفسهٔ «{sh.name}» {'گذاشته' if act == 'shelf_add' else 'برداشته'} شد.")
    elif act in ("in", "out"):
        Variation.objects.filter(product__in=qs).update(is_available=act == "in")
        for p in qs:
            p.refresh_price_cache()
        messages.success(request, f"{n} کالا {'موجود' if act == 'in' else 'ناموجود'} شد.")
    elif act == "price":
        pct = _num(request.POST.get("percent"))
        sign = -1 if request.POST.get("dir") == "down" else 1
        if not pct or pct > 50:
            messages.error(request, "درصد تغییر قیمت را بین ۱ تا ۵۰ بنویسید.")
        else:
            k = 0
            for v in Variation.objects.filter(product__in=qs, product__album__isnull=True, manual_price__isnull=False):
                v.manual_price = int(round(v.manual_price * (100 + sign * pct) / 100, -4)) or v.manual_price
                if v.sale_price and v.sale_price >= v.manual_price:
                    v.sale_price = None
                v.save()
                k += 1
            for p in qs:
                p.refresh_price_cache()
            messages.success(request, f"قیمت {k} سایز {pct}٪ {'کم' if sign < 0 else 'زیاد'} شد. قیمت کالاهای آلبومی را از خود آلبوم عوض کنید.")
    return redirect(request.POST.get("next") or "/seller/products/")


# ------------------------------------------------------------------ فرصت ویژه
@seller_required
def offers(request):
    from shop.models import SpecialOffer

    s = request.seller
    errors = {}
    if request.method == "POST":
        act = request.POST.get("do")
        if act == "stop":
            o = get_object_or_404(SpecialOffer, pk=_num(request.POST.get("id")) or 0, product__seller=s)
            SpecialOffer.objects.filter(pk=o.pk).update(is_active=False)
            from shop.offers import clear

            clear()
            messages.success(request, "فرصت ویژه تمام شد.")
            return redirect("/seller/offers/")
        p = Product.objects.filter(pk=_num(request.POST.get("product")) or 0, seller=s, status="publish").first()
        size = Size.objects.filter(pk=_num(request.POST.get("size")) or 0).first()
        pct = _num(request.POST.get("percent"))
        fixed = _num(request.POST.get("fixed_price"))
        qty = _num(request.POST.get("quantity")) or 1
        days = _num(request.POST.get("days"))
        if not p:
            errors["product"] = "کالای منتشرشده‌ای انتخاب کنید."
        if p and (not size or not p.variations.filter(size=size).exists()):
            errors["size"] = "این کالا چنین سایزی ندارد؛ فرصت ویژه فقط برای سایزهای استاندارد است."
        if not fixed and not (pct and 1 <= pct <= 70):
            errors["percent"] = "درصد تخفیف (۱ تا ۷۰) یا قیمت ویژه را بنویسید."
        if not errors:
            o = SpecialOffer(product=p, size=size, percent=pct or 10, fixed_price=fixed or None, quantity=min(qty, 99),
                             ends_at=timezone.now() + timedelta(days=days) if days and days <= 90 else None)
            try:
                o.full_clean()
            except Exception as e:  # noqa: BLE001
                errors["percent"] = " ".join(sum(getattr(e, "message_dict", {"": [str(e)]}).values(), []))
            else:
                o.save()
                messages.success(request, "فرصت ویژه ثبت شد و در ویترین و صفحهٔ کالا نشان داده می‌شود.")
                return redirect("/seller/offers/")
    from shop.offers import live_offers

    live_ids = {o.pk for o in live_offers(sellers=True)}
    rows = list(SpecialOffer.objects.filter(product__seller=s).select_related("product__image", "size").order_by("-created_at")[:60])
    for o in rows:
        o.live = o.pk in live_ids
    live = Product.objects.published().filter(seller=s).prefetch_related("variations__size").order_by("-published_at")[:200]
    return render(request, "market/offers.html", _ctx(request, "فرصت ویژه", "offers", rows=rows, live=live, errors=errors,
                                                       post=request.POST if errors else None))


# ------------------------------------------------------------------ کد تخفیف
@seller_required
def coupons(request):
    from shop.models import Coupon

    s = request.seller
    errors = {}
    if request.method == "POST":
        if request.POST.get("do") == "stop":
            Coupon.objects.filter(pk=_num(request.POST.get("id")) or 0, seller=s).update(is_active=False)
            messages.success(request, "کد تخفیف غیرفعال شد.")
            return redirect("/seller/coupons/")
        code = re.sub(r"[^A-Za-z0-9]", "", request.POST.get("code") or "").upper()[:20]
        kind = request.POST.get("kind") if request.POST.get("kind") in ("percent", "fixed") else "percent"
        value = _num(request.POST.get("value"))
        max_d = _num(request.POST.get("max_discount")) or 0
        min_o = _num(request.POST.get("min_order")) or 0
        limit = _num(request.POST.get("usage_limit")) or 0
        days = _num(request.POST.get("days"))
        if len(code) < 4:
            errors["code"] = "کد را با دست‌کم ۴ حرف یا عدد انگلیسی بنویسید (مثل SHAH10)."
        elif Coupon.objects.filter(code=code).exists():
            errors["code"] = "این کد قبلاً گرفته شده؛ کد دیگری بنویسید."
        if kind == "percent" and not (value and 1 <= value <= 50):
            errors["value"] = "درصد تخفیف بین ۱ تا ۵۰."
        if kind == "fixed" and not (value and value >= 10_000):
            errors["value"] = "مبلغ تخفیف را به تومان بنویسید."
        if not errors:
            Coupon.objects.create(code=code, title=f"تخفیف فروشگاه {s.name}"[:120], kind=kind, value=value, max_discount=max_d,
                                  min_order=min_o, usage_limit=limit, per_user_limit=1, seller=s,
                                  ends_at=timezone.now() + timedelta(days=days) if days and days <= 365 else None)
            messages.success(request, f"کد {code} ساخته شد؛ فقط روی کالاهای فروشگاه شما و از سهم شما کم می‌شود.")
            return redirect("/seller/coupons/")
    from shop.coupons import PLACED
    from shop.models import Order

    rows = list(Coupon.objects.filter(seller=s).order_by("-created_at")[:50])
    for c in rows:
        c.used = Order.objects.filter(coupon_code=c.code, status__in=PLACED).count()
    return render(request, "market/coupons.html", _ctx(request, "کد تخفیف", "coupons", rows=rows, errors=errors,
                                                        post=request.POST if errors else None))


# ------------------------------------------------------------------ پرسش‌ها و نظرها
def _open_questions(s):
    answered = Review.objects.filter(parent=OuterRef("pk"))
    return Review.objects.filter(product__seller=s, kind="question", parent__isnull=True).annotate(a=Exists(answered)).filter(a=False)


@seller_required
def questions(request):
    s = request.seller
    if request.method == "POST":
        q = get_object_or_404(Review, pk=_num(request.POST.get("id")) or 0, product__seller=s, parent__isnull=True)
        text = (request.POST.get("answer") or "").strip()
        if len(text) < 2:
            messages.error(request, "پاسخ را بنویسید.")
        elif re.search(r"(?:09\d{9}|0?9\d{2}[\s-]?\d{3}[\s-]?\d{4}|https?://|www\.|@\w{3,})", latin_digits(text)):
            messages.error(request, "شمارهٔ تماس، پیوند یا شناسهٔ شبکه‌های اجتماعی در پاسخ مجاز نیست؛ ارتباط با خریدار از راه ایران کارپت است.")
        else:
            Review.objects.create(product=q.product, parent=q, author_name=f"فروشگاه {s.name}"[:200], content=text[:2000],
                                  is_approved=True, kind=q.kind, user=request.user)
            if q.kind == "question" and not q.is_approved:
                Review.objects.filter(pk=q.pk).update(is_approved=True)
            messages.success(request, "پاسخ ثبت شد و زیر صفحهٔ کالا نشان داده می‌شود.")
        return redirect("/seller/questions/" + ("?t=reviews" if q.kind == "review" else ""))
    tab = "reviews" if request.GET.get("t") == "reviews" else "questions"
    base = Review.objects.filter(product__seller=s, parent__isnull=True).select_related("product__image").prefetch_related("replies")
    if tab == "questions":
        rows = list(base.filter(kind="question").order_by("-created_at")[:80])
    else:
        rows = list(base.filter(kind="review", is_approved=True).order_by("-created_at")[:80])
    return render(request, "market/questions.html", _ctx(request, "پرسش‌ها و نظرها", "questions", rows=rows, t=tab,
                                                          open=_open_questions(s).count()))


def accept_deadline(so, ms=None):
    ms = ms or MarketSettings.load()
    return so.paid_at + timedelta(hours=ms.accept_hours) if so.paid_at else None

