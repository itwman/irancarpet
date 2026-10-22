"""صفحه‌های سایت: معرفی و ثبت‌نام همکاری در فروش، و پنل همکار در «حساب من»."""
import re
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits, normalize_mobile

from . import commission as C
from . import track
from .models import CODE_RE, RESERVED, Affiliate, AffiliateSettings, Commission, Link, clean_sheba, new_code, valid_sheba

META = {"robots": "noindex, follow"}
LOGIN = "/my-account/login/"


def money_label(v):
    """۱۵۰٬۰۰۰٬۰۰۰ ← «۱۵۰ میلیون»، ۱٬۵۰۰٬۰۰۰٬۰۰۰ ← «۱٫۵ میلیارد»"""
    from core.templatetags.fa import fa_num, toman

    v = int(v or 0)
    for unit, name in ((1_000_000_000, "میلیارد"), (1_000_000, "میلیون"), (1_000, "هزار")):
        if v >= unit:
            x = f"{v / unit:.2f}".rstrip("0").rstrip(".")
            return fa_num(x.replace(".", "٫")) + " " + name
    return toman(v)


def _pct(p):
    from core.templatetags.fa import fa_num

    return fa_num(f"{p:.2f}".rstrip("0").rstrip(".").replace(".", "٫"))


def _tiers_view(s):
    rows = C.tiers()
    out = []
    top = max((float(p) for _, p, _ in rows), default=1) or 1
    for i, (mn, p, title) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else None
        out.append({"min": mn, "max": nxt, "percent": p, "pct": _pct(p), "title": title, "min_label": money_label(mn),
                    "max_label": money_label(nxt) if nxt else "", "height": int(30 + 70 * float(p) / top)})
    return out


def _coupon_for(a, s):
    """کد تخفیف اختصاصی همکار (یک بار ساخته می‌شود؛ با خاموش شدن همکار، کد هم خاموش می‌شود)."""
    from shop.models import Coupon

    if not s.coupon_enabled:
        if a.coupon_id and a.coupon.is_active:
            Coupon.objects.filter(pk=a.coupon_id).update(is_active=False)
        return None
    c = a.coupon
    active = a.is_active
    if c is None:
        code = re.sub(r"[^A-Z0-9]", "", a.code.upper())[:12] or "IC"
        if len(code) < 4 or Coupon.objects.filter(code=code).exists():
            code = code[:8] + secrets.token_hex(2).upper()
        c = Coupon.objects.create(code=code, title=f"کد همکار فروش ({a.name})"[:120], kind=Coupon.Kind.PERCENT,
                                  value=s.coupon_percent, max_discount=s.coupon_max, per_user_limit=0, is_active=active)
        Affiliate.objects.filter(pk=a.pk).update(coupon=c)
        a.coupon = c
    elif (c.value, c.max_discount, c.is_active) != (s.coupon_percent, s.coupon_max, active):
        c.value, c.max_discount, c.is_active = s.coupon_percent, s.coupon_max, active
        c.save(update_fields=["value", "max_discount", "is_active"])
    return c


def activate(a, request=None):
    """تأیید همکار: کد تخفیف ساخته و پیامک خوش‌آمد فرستاده می‌شود."""
    first = a.approved_at is None
    a.status = Affiliate.Status.ACTIVE
    a.approved_at = a.approved_at or timezone.now()
    a.save(update_fields=["status", "approved_at"])
    _coupon_for(a, AffiliateSettings.load())
    if first:
        try:
            from accounts.sms import send_bulk

            send_bulk([a.mobile], f"{a.name} عزیز، حساب همکاری در فروش ایران کارپت فعال شد. پیوندهای شما: "
                                  "irancarpet.net/my-account/affiliate/")
        except Exception:  # noqa: BLE001
            pass


def landing(request):
    s = AffiliateSettings.load()
    if not s.enabled:
        raise Http404
    a = getattr(request.user, "affiliate", None) if request.user.is_authenticated else None
    if a is not None and request.method == "POST":
        return redirect("/my-account/affiliate/")
    errors, data = {}, {}
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{LOGIN}?next=/affiliate/%23join")
        data = {k: (request.POST.get(k) or "").strip() for k in ("name", "city", "channels", "code", "sheba", "account_holder")}
        if len(data["name"]) < 3:
            errors["name"] = "نام و نام خانوادگی را بنویسید."
        code = latin_digits(data["code"]).lower()
        if code:
            if not CODE_RE.match(code) or code in RESERVED:
                errors["code"] = "فقط حروف کوچک انگلیسی، عدد و _ (۳ تا ۲۰ حرف)."
            elif Affiliate.objects.filter(code=code).exists():
                errors["code"] = "این کد قبلاً گرفته شده؛ کد دیگری بنویسید."
        sheba = clean_sheba(data["sheba"])
        if sheba and not valid_sheba(sheba):
            errors["sheba"] = "شماره شبا درست نیست (IR و ۲۴ رقم)."
        if not request.POST.get("terms"):
            errors["terms"] = "برای ثبت‌نام، قوانین همکاری را بپذیرید."
        if not errors:
            from accounts.views import profile_of

            mobile = normalize_mobile(getattr(profile_of(request.user), "mobile", "") or request.user.username)
            a = Affiliate.objects.create(
                user=request.user, code=code or new_code(), name=data["name"][:120], mobile=mobile, city=data["city"][:80],
                channels=data["channels"][:2000], sheba=sheba, account_holder=data["account_holder"][:120] or data["name"][:120])
            if s.auto_approve:
                activate(a)
            else:
                try:
                    from shop.notify import admin_text

                    admin_text(f"ثبت‌نام تازهٔ همکاری در فروش: {a.name} ({a.city or '—'}). برای تأیید به پنل ← همکاران فروش بروید.")
                except Exception:  # noqa: BLE001
                    pass
            return redirect("/my-account/affiliate/")
    return render(request, "affiliate/landing.html", {
        "meta": {"title": "همکاری در فروش ایران کارپت", "description":
                 "با معرفی فرش‌های ایران کارپت به دوستان و مخاطبانتان، از هر خرید پورسانت پله‌ای بگیرید."},
        "s": s, "tiers": _tiers_view(s), "terms": s.terms_list(), "errors": errors, "data": data,
        "calc": {"tiers": [[int(mn), float(p)] for mn, p, _ in C.tiers()], "mode": s.tier_mode},
        "a": a, "top": top_percent(), "faq": faq(s), "facts": _facts(),
        "jsonld": _faq_jsonld(faq(s)),
    })


def top_percent():
    rows = C.tiers()
    return _pct(max((p for _, p, _ in rows), default=0)) if rows else ""


def _facts():
    """دلیل‌هایی که بازاریاب با آن‌ها فرش ایران کارپت را راحت‌تر می‌فروشد (از تنظیمات خود سایت)."""
    out = [("مستقیم از کاشان", "فرش ماشینی ۷۰۰ تا ۱۵۰۰ شانه، بی‌واسطه و با قیمت روشن برای هر سایز.")]
    try:
        from installments.models import InstallmentPlan

        if InstallmentPlan.objects.filter(is_active=True).exists():
            out.append(("خرید اقساطی", "مشتری‌ای که نقد نمی‌تواند بخرد، اقساطی می‌خرد؛ پورسانت شما روی قیمت فرش است."))
    except Exception:  # noqa: BLE001
        pass
    try:
        from content.models import ContentSettings

        w = ContentSettings.load().warranty
        if w:
            out.append((w, "ضمانت کتبی؛ خیال مشتری‌ای که به شما اعتماد کرده راحت است."))
    except Exception:  # noqa: BLE001
        pass
    out.append(("ارسال به سراسر ایران", "سفارش از هر شهری ثبت می‌شود؛ مخاطبان شما لازم نیست کاشانی باشند."))
    return out


def faq(s):
    from core.templatetags.fa import fa_num, toman

    days = fa_num(s.attribution_days)
    items = [
        ("برای همکاری باید فروشنده یا مغازه‌دار باشم؟",
         "نه. هر کسی که مخاطب دارد می‌تواند همکار شود: صفحهٔ اینستاگرام، کانال تلگرام، طراح داخلی، فروشگاه جهیزیه یا حتی معرفی به دوستان و فامیل. هزینه‌ای هم ندارد."),
        ("اگر مشتری همان روز خرید نکند چه؟",
         f"تا {days} روز بعد از باز کردن پیوند شما، هر خریدی که از سایت کند به نام شما ثبت می‌شود؛ حتی اگر چند روز بعد و از گوشی دیگری خرید کند، به شرط اینکه یک بار با همان شماره وارد سایت شده باشد."),
        ("پورسانت کی واریز می‌شود؟",
         f"بعد از تحویل فرش به مشتری، پورسانت «قابل تسویه» می‌شود. وقتی جمعش به {toman(s.min_payout)} تومان رسید، به شماره شبای خودتان واریز و پیامکش برایتان فرستاده می‌شود."),
        ("درصد پورسانت چطور بالا می‌رود؟",
         ("هرچه جمع فروش " + ("همان ماه" if s.tier_period == "month" else "شما از ابتدای همکاری") +
          " بیشتر شود، به پلهٔ بالاتر می‌رسید و درصد همهٔ پورسانت‌های تسویه‌نشدهٔ آن دوره هم خودکار بالا می‌رود.")),
        ("در اینستاگرام که پیوند پست کلیک نمی‌شود، چه کنم؟",
         (f"پیوند کوتاه عمومی را در بیو بگذارید و در پست و استوری کد تخفیف اختصاصی‌تان را بنویسید؛ مشتری با کد شما {fa_num(s.coupon_percent)}٪ تخفیف می‌گیرد و خریدش به نام شما ثبت می‌شود."
          if s.coupon_enabled else "پیوند کوتاه عمومی را در بیو بگذارید و در استوری از برچسب «لینک» استفاده کنید.")),
        ("قیمت را خودم تعیین می‌کنم؟",
         "نه؛ مشتری با همان قیمت سایت می‌خرد و پرداخت، ارسال، ضمانت و پشتیبانی با ایران کارپت است. شما فقط معرفی می‌کنید."),
        ("از کجا بفهمم چه کسی با پیوند من خرید کرده؟",
         "در پنل همکاری، تعداد بازدید، سفارش‌ها، مبلغ هر خرید و پورسانتش را می‌بینید. نام و نشانی مشتری‌ها برای حفظ حریم خصوصی نمایش داده نمی‌شود."),
    ]
    return items


def _faq_jsonld(items):
    import json

    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}, ensure_ascii=False)


def _affiliate_or_redirect(request):
    a = getattr(request.user, "affiliate", None)
    return a


@login_required(login_url=LOGIN)
def dashboard(request):
    a = _affiliate_or_redirect(request)
    if a is None:
        return redirect("/affiliate/")
    s = AffiliateSettings.load()
    if request.method == "POST" and request.POST.get("action") == "bank":
        sheba = clean_sheba(request.POST.get("sheba"))
        if sheba and not valid_sheba(sheba):
            messages.error(request, "شماره شبا درست نیست (IR و ۲۴ رقم).")
        else:
            a.sheba, a.account_holder = sheba, (request.POST.get("account_holder") or "").strip()[:120]
            a.save(update_fields=["sheba", "account_holder"])
            messages.success(request, "اطلاعات حساب بانکی ذخیره شد.")
        return redirect("/my-account/affiliate/#bank")
    ctx = {"meta": {**META, "title": "پنل همکاری در فروش"}, "a": a, "s": s}
    if a.is_active:
        period = C.current_period(s)
        sales = C.period_sales(a, period)
        cur, nxt, left = C.tier_info(sales)
        bal = C.balances(a)
        since = timezone.now() - timezone.timedelta(days=30)
        clicks30 = a.clicks.filter(created_at__gte=since)
        top = (clicks30.exclude(product=None).values("product__title").annotate(n=Count("pk")).order_by("-n")[:5])
        ctx.update({
            "general": track.general_link(a), "coupon": _coupon_for(a, s), "period": period, "period_label": _period_label(period),
            "sales": sales, "tier": cur, "next_tier": nxt, "left": left,
            "rate": a.custom_percent if a.custom_percent is not None else (cur["percent"] if cur else 0),
            "progress": min(100, int(sales * 100 / nxt["min"])) if nxt and nxt["min"] else 100,
            "bal": bal, "payable": bal["approved"]["amount"], "upcoming": bal["pending"]["amount"] + bal["waiting"]["amount"],
            "paid_total": bal["paid"]["amount"],
            "clicks30": clicks30.count(), "visitors30": clicks30.values("visitor").distinct().count(),
            "orders30": a.commissions.filter(created_at__gte=since).exclude(status=Commission.Status.CANCELLED).count(),
            "top_products": top,
            "commissions": a.commissions.select_related("order").order_by("-created_at")[:30],
            "payouts": a.payouts.all()[:20], "tiers": _tiers_view(s),
            "links": [(lk, track.page_link(a, lk)) for lk in a.links.order_by("-created_at")[:10]],
        })
    return render(request, "affiliate/dashboard.html", ctx)


def _period_label(p):
    if p == "all":
        return "از ابتدای همکاری"
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    y, m = p.split("-")
    from core.templatetags.fa import fa_num

    return fa_num(f"{months[int(m) - 1]} {int(y)}")


def _share_text(p, link, offer=None):
    from core.templatetags.fa import fa_num, toman

    if offer:
        size = f" ({offer.size.label})" if offer.size_id else ""
        price = f"\n🔥 فرصت ویژه{size}: {toman(offer.price)} تومان به‌جای {toman(offer.regular_price)}، فقط {offer.remaining} تخته"
    else:
        price = f"\nقیمت از {toman(p.min_price)} تومان" if p.min_price else ""
    return fa_num(f"{p.title}{price}\nخرید نقدی و اقساطی با ارسال به سراسر ایران 👇\n") + link


TABS = {"best": "پرفروش", "offers": "فرصت‌های ویژه", "new": "تازه‌ها", "random": "تصادفی"}
PER_PAGE = 12


def _rate(a, s):
    if a.custom_percent is not None:
        return float(a.custom_percent)
    cur, _, _ = C.tier_info(C.period_sales(a, C.current_period(s)))
    return float(cur["percent"]) if cur else 0.0


def _sellable():
    """فرش‌هایی که همکار می‌تواند بفروشد: منتشرشده، موجود، عکس‌دار، با قیمت."""
    from catalog.models import BLOCKED_SALE_STATUSES, Product

    return (Product.objects.published().filter(image__isnull=False, min_price__gt=0)
            .exclude(stock_status="outofstock").exclude(sale_status__in=BLOCKED_SALE_STATUSES))


def _best_ids():
    """پرفروش‌های ۹۰ روز اخیر (تعداد تخته)، بعد پربازدیدها؛ ۱۰ دقیقه کش."""
    from django.core.cache import cache

    ids = cache.get("aff:best")
    if ids is None:
        from shop.models import Order, OrderItem

        since = timezone.now() - timezone.timedelta(days=90)
        sold = (OrderItem.objects.filter(order__status__in=Order.PAID_STATUSES, order__created_at__gte=since, product__isnull=False)
                .values("product").annotate(n=Sum("quantity")).order_by("-n").values_list("product", flat=True)[:300])
        live = set(_sellable().values_list("pk", flat=True))
        ids = [i for i in sold if i in live]
        seen = set(ids)
        ids += [i for i in _sellable().order_by("-views").values_list("pk", flat=True)[:600] if i not in seen]
        cache.set("aff:best", ids, 600)
    return ids


def _card(a, p, rate, offer=None):
    from core.templatetags.fa import fa_num, reeds_of, thumb, toman

    link = track.product_link(a, p)
    price = offer.price if offer else (p.min_price or 0)
    sizes = sum(1 for v in p.variations.all() if v.is_available and v.price)
    d = {"id": p.pk, "title": fa_num(p.title), "image": thumb(p.image, 480) if p.image_id else "",
         "download": p.image.file.url if p.image_id and p.image.file else "", "url": p.get_absolute_url(),
         "price": toman(price) if price else "", "from": not offer and sizes > 1,
         "reeds": fa_num(reeds_of(p.title)), "sizes": fa_num(sizes) if sizes else "",
         "commission": toman(int(price * rate / 100 / 1000) * 1000) if price and rate else "",
         "link": link, "text": _share_text(p, link, offer)}
    if offer:
        from core.templatetags.fa import jdate

        d["offer"] = {"percent": fa_num(offer.off_percent), "regular": toman(offer.regular_price),
                      "size": offer.size.label if offer.size_id else "", "left": fa_num(offer.remaining),
                      "ends": jdate(offer.ends_at, "%d %B") if offer.ends_at else ""}
    return d


@login_required(login_url=LOGIN)
def products(request):
    """فرش‌ها برای ساختن پیوند (JSON): زبانه‌های پرفروش، فرصت ویژه، تازه، تصادفی؛ یا جستجو. فقط فرش‌های موجود."""
    a = _affiliate_or_redirect(request)
    if a is None or not a.is_active:
        return JsonResponse({"items": []}, status=403)
    import random

    from django.db.models import Prefetch

    from catalog.models import Product, Variation
    from catalog.search import search

    s = AffiliateSettings.load()
    rate = _rate(a, s)
    q = (request.GET.get("q") or "").strip()[:80]
    tab = request.GET.get("tab") if request.GET.get("tab") in TABS else "best"
    reeds = (request.GET.get("reeds") or "").strip()
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    lo, hi = (page - 1) * PER_PAGE, page * PER_PAGE
    prefetch = Prefetch("variations", queryset=Variation.objects.only("product_id", "is_available", "sale_price", "final_price"))
    base = _sellable().select_related("image").prefetch_related(prefetch)
    if reeds.isdigit():
        base = base.filter(specs__attribute__slug="reeds-per-meter", specs__slug=reeds)
    items, more = [], False

    if q:
        m = re.search(r"/product/([^/?#]+)", q)
        if m:
            from urllib.parse import unquote

            qs = Product.objects.published().filter(slug=unquote(m.group(1))).select_related("image").prefetch_related(prefetch)
        else:
            qs, _ = search(base, q)
            qs = qs.order_by("-_rank", "-views")
        rows = list(qs[lo:hi + 1])
        more, rows = len(rows) > PER_PAGE, rows[:PER_PAGE]
        items = [_card(a, p, rate) for p in rows]
    elif tab == "offers":
        from shop.offers import live_offers

        offers = [o for o in live_offers() if o.product.status == "publish" and o.price
                  and (not reeds.isdigit() or o.product.specs.filter(attribute__slug="reeds-per-meter", slug=reeds).exists())]
        more = len(offers) > hi
        items = [_card(a, o.product, rate, o) for o in offers[lo:hi]]
    else:
        if tab == "new":
            ids = list(base.order_by("-published_at").values_list("pk", flat=True)[lo:hi + 1])
        elif tab == "random":
            pool = list(base.values_list("pk", flat=True)) if reeds.isdigit() else list(_sellable().values_list("pk", flat=True))
            seed = request.GET.get("seed") or "0"
            random.Random(seed).shuffle(pool)  # همان دانه = همان ترتیب، تا «بیشتر» تکراری نیاورد
            ids = pool[lo:hi + 1]
        else:
            allowed = set(base.values_list("pk", flat=True)) if reeds.isdigit() else None
            ids = [i for i in _best_ids() if allowed is None or i in allowed][lo:hi + 1]
        more, ids = len(ids) > PER_PAGE, ids[:PER_PAGE]
        by = {p.pk: p for p in base.filter(pk__in=ids)}
        items = [_card(a, by[i], rate) for i in ids if i in by]
    return JsonResponse({"items": items, "more": more, "page": page})


@login_required(login_url=LOGIN)
@require_POST
def make_link(request):
    """پیوند کوتاه برای هر صفحهٔ سایت (لیست قیمت، دسته، مقاله…)."""
    a = _affiliate_or_redirect(request)
    if a is None or not a.is_active:
        return JsonResponse({"error": "حساب همکاری فعال نیست."}, status=403)
    path = track.local_path(request.POST.get("url"))
    if not path:
        return JsonResponse({"error": "نشانی یکی از صفحه‌های irancarpet.net را بچسبانید."}, status=400)
    from catalog.models import Product

    m = re.match(r"^/product/([^/?#]+)/$", path)
    if m:
        from urllib.parse import unquote

        p = Product.objects.filter(slug=unquote(m.group(1))).first()
        if p:
            return JsonResponse({"link": track.product_link(a, p), "path": path})
    if path == "/":
        return JsonResponse({"link": track.general_link(a), "path": path})
    if a.links.count() >= 500:
        return JsonResponse({"error": "تعداد پیوندها به سقف رسیده است."}, status=400)
    link, _ = Link.objects.get_or_create(affiliate=a, path=path)
    return JsonResponse({"link": track.page_link(a, link), "path": path})
