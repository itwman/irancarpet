"""بخش‌های پنل مدیریت: فروشندگان، بررسی کالاها، سفارش‌ها، تسویه و کمیسیون دسته‌ها."""
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.html import format_html

from catalog.models import Product
from core.templatetags.fa import fa_num, jdate, toman
from dashboard.registry import REGISTRY, Col, Resource, register, thumb

from . import orders as O
from . import products as P
from .models import CategoryCommission, MarketSettings, Seller, SellerOrder, SellerPayout

G = "مارکت‌پلیس"
BADGE = {"pending": "pending", "active": "publish", "paused": "draft", "suspended": "cancelled", "rejected": "cancelled",
         "waiting": "pending", "new": "pending", "accepted": "processing", "shipped": "shipped", "delivered": "completed",
         "cancelled": "cancelled", "approved": "publish"}


def _badge(o):
    return format_html('<span class="badge-ic b-{}">{}</span>', BADGE.get(o.status, "draft"), o.get_status_display())


def _sms(mobile, text):
    try:
        from accounts.sms import send_bulk

        send_bulk([mobile], text, kind="market")
    except Exception:  # noqa: BLE001
        pass


def _activate(s):
    first = s.approved_at is None
    s.status = Seller.Status.ACTIVE
    s.approved_at = s.approved_at or timezone.now()
    s.save(update_fields=["status", "approved_at"])
    P.set_visibility(s)
    if first:
        _sms(s.mobile, f"فروشگاه «{s.name}» در ایران کارپت فعال شد. کالاهایتان را از پنل فروشنده اضافه کنید: irancarpet.net/seller/")


def _approve_sellers(request, qs):
    n = 0
    for s in qs.exclude(status=Seller.Status.ACTIVE):
        _activate(s)
        n += 1
    return f"{fa_num(n)} فروشنده فعال شد."


def _set(status, label):
    def fn(request, qs):
        n = 0
        for s in qs:
            s.status = status
            s.save(update_fields=["status"])
            P.set_visibility(s)
            n += 1
        return f"{fa_num(n)} فروشنده {label}."
    return fn


def _pay(request, qs):
    ref = (request.POST.get("action_value") or "").strip()
    done, skipped = [], 0
    for s in qs:
        p = O.pay(s, ref)
        if p:
            done.append(f"{s.name}: {toman(p.amount)}")
        else:
            skipped += 1
    msg = ("تسویه ثبت شد — " + "، ".join(done)) if done else "تسویه‌ای ثبت نشد."
    if skipped:
        msg += f" ({fa_num(skipped)} فروشنده ماندهٔ قابل تسویه کمتر از حداقل داشت.)"
    return msg


def _payable(o):
    v = o.orders.filter(settle=SellerOrder.Settle.PAYABLE).aggregate(s=Sum("seller_amount"))["s"] or 0
    return format_html("<strong>{}</strong>", toman(v)) if v else "۰"


def _seller_saved(request, obj, created, form=None):
    if obj.status == Seller.Status.ACTIVE and not obj.approved_at:
        _activate(obj)
    else:
        P.set_visibility(obj)


register(Resource(
    key="sellers", model=Seller, title="فروشندگان", single="فروشنده", group=G, icon="users",
    columns=[Col("name", "فروشگاه", lambda o: o.name, "name"), Col("city", "شهر", lambda o: o.city),
             Col("status", "وضعیت", _badge, "status"), Col("mobile", "موبایل", lambda o: fa_num(o.mobile)),
             Col("products", "کالا", lambda o: fa_num(o.products.filter(status="publish").count())),
             Col("pending", "منتظر بررسی", lambda o: fa_num(o.products.filter(review_status="pending").count()) or "—"),
             Col("payable", "قابل تسویه", _payable),
             Col("created_at", "ثبت‌نام", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["name", "slug", "mobile", "city", "owner_name", "national_id"], filters=["status", "kind", "trusted"],
    date_filter="created_at", ordering=("-created_at",),
    fieldsets=[("فروشگاه", ["name", "slug", "about", "city", "province", "address", "phone"], "main"),
               ("هویت", ["kind", "owner_name", "national_id", "mobile"], "main"),
               ("ارسال", ["shipping", "prep_days", "return_policy"], "main"),
               ("حساب بانکی", ["sheba", "account_holder"], "main"),
               ("وضعیت", ["status", "trusted", "commission_percent"], "side"), ("یادداشت داخلی", ["admin_note"], "side")],
    readonly=[("صفحهٔ فروشگاه", lambda o: format_html('<a href="{0}" target="_blank">{0}</a>', o.get_absolute_url()) if o.pk else "—"),
              ("قابل تسویه", lambda o: _payable(o) if o.pk else "—"),
              ("فروش تحویل‌شده", lambda o: f"{toman(o.orders.filter(status='delivered').aggregate(s=Sum('items_total'))['s'] or 0)} تومان" if o.pk else "—")],
    view_url=lambda o: o.get_absolute_url(), can_add=False, after_save=_seller_saved,
    actions={"approve": ("تأیید و فعال کردن", _approve_sellers),
             "suspend": ("توقف فروشنده (کالاها پنهان می‌شوند)", _set(Seller.Status.SUSPENDED, "متوقف شد")),
             "reject": ("رد درخواست", _set(Seller.Status.REJECTED, "رد شد")),
             "pay": ("ثبت تسویه (واریز همهٔ مبالغ قابل تسویه)", _pay, "کد پیگیری واریز")},
    help="درخواست‌های تازه «در انتظار تأیید» هستند؛ قبل از تأیید با فروشنده تماس بگیرید و هویت و شبا را بررسی کنید. "
         "«مورد اعتماد» یعنی کالاهای این فروشنده بدون بررسی منتشر شوند. تسویه: فروشنده‌ها را انتخاب کنید ← «ثبت تسویه» بعد از واریز.",
))


# ------------------------------------------------------------------ بررسی کالاها
def _approve_products(request, qs):
    n = 0
    for p in qs.select_related("seller"):
        P.approve(p)
        n += 1
    return f"{fa_num(n)} کالا تأیید و منتشر شد."


def _reject_products(request, qs):
    note = (request.POST.get("action_value") or "").strip()
    n = 0
    for p in qs.select_related("seller"):
        P.reject(p, note)
        n += 1
    return f"{fa_num(n)} کالا برای اصلاح به فروشنده برگشت."


def _review_badge(o):
    if o.review_status == "pending":
        return format_html('<span class="badge-ic b-pending">در انتظار بررسی</span>')
    if o.review_status == "rejected":
        return format_html('<span class="badge-ic b-cancelled">رد شد</span> <small class="muted">{}</small>', o.review_note[:60])
    return format_html('<span class="badge-ic b-{}">{}</span>', "publish" if o.status == "publish" else "draft",
                       "در سایت" if o.status == "publish" else "پنهان")


def _price_range(o):
    if not o.min_price:
        return "—"
    return toman(o.min_price) if o.min_price == o.max_price or not o.max_price else f"{toman(o.min_price)} تا {toman(o.max_price)}"


register(Resource(
    key="seller-products", model=Product, title="کالاهای فروشندگان", single="کالای فروشنده", group=G, icon="carpet",
    columns=[Col("image", "", thumb(), cls="w-thumb"), Col("title", "عنوان", lambda o: fa_num(o.title), "title"),
             Col("seller", "فروشنده", lambda o: o.seller.name if o.seller_id else "—"),
             Col("price", "قیمت", _price_range, "min_price"), Col("review", "بررسی", _review_badge, "review_status"),
             Col("modified_at", "آخرین ویرایش", lambda o: jdate(o.modified_at, "%Y/%m/%d %H:%M"), "modified_at")],
    search=["title", "sku", "=id"], filters=["seller", "review_status", "status"], ordering=("-pk",),
    queryset=lambda qs: qs.filter(seller__isnull=False).select_related("image", "seller"),
    view_url=lambda o: o.get_absolute_url(), edit_url=lambda o: f"/panel/products/{o.pk}/edit/", can_add=False, can_delete=True,
    fieldsets=[("کالا", ["title"], "main")],
    actions={"approve": ("تأیید و انتشار", _approve_products),
             "reject": ("برگرداندن برای اصلاح", _reject_products, "دلیل (برای فروشنده پیامک می‌شود)")},
    custom_filters={"queue": ("صف بررسی", [("1", "فقط در انتظار بررسی")], lambda qs, v: qs.filter(review_status="pending") if v == "1" else qs)},
    help="کالای تازه و ویرایش عنوان، متن، عکس یا مشخصات کالاهای فروشندگان اینجا منتظر بررسی می‌ماند. روی عنوان بزنید تا در ویرایشگر محصول ببینید "
         "و اگر لازم است اصلاح کنید؛ بعد «تأیید و انتشار» یا «برگرداندن برای اصلاح». تغییر قیمت و موجودی نیاز به بررسی ندارد.",
))


# ------------------------------------------------------------------ سفارش فروشندگان
def _so_deliver(request, qs):
    return f"{fa_num(sum(1 for so in qs if O.deliver(so)))} سفارش تحویل‌شده ثبت شد."


def _so_cancel(request, qs):
    reason = (request.POST.get("action_value") or "").strip()
    return f"{fa_num(sum(1 for so in qs if O.cancel(so, reason, by_seller=False)))} سفارش لغو شد."


def _so_payable(request, qs):
    n = qs.filter(status=SellerOrder.Status.DELIVERED, settle=SellerOrder.Settle.OPEN).update(
        settle=SellerOrder.Settle.PAYABLE, payable_at=timezone.now())
    return f"{fa_num(n)} سفارش قابل تسویه شد."


def _so_badge(o):
    b = _badge(o)
    if o.status == SellerOrder.Status.NEW and o.paid_at:
        late = (timezone.now() - o.paid_at).total_seconds() / 3600 > MarketSettings.load().accept_hours
        if late:
            return format_html('{} <span class="badge-ic b-cancelled">دیر</span>', b)
    return b


register(Resource(
    key="seller-orders", model=SellerOrder, title="سفارش‌های فروشندگان", single="سفارش فروشنده", group=G, icon="receipt",
    columns=[Col("order", "سفارش", lambda o: format_html('<a href="/panel/orders/{}/view/">{}</a>', o.order_id, fa_num(o.order.number))),
             Col("seller", "فروشنده", lambda o: o.seller.name), Col("items_total", "مبلغ", lambda o: toman(o.items_total), "items_total"),
             Col("commission", "کمیسیون", lambda o: toman(o.commission), "commission"),
             Col("status", "وضعیت", _so_badge, "status"),
             Col("settle", "تسویه", lambda o: o.get_settle_display(), "settle"),
             Col("tracking", "رهگیری", lambda o: o.tracking_code or "—"),
             Col("created_at", "تاریخ", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["=order__number", "seller__name", "tracking_code"], filters=["status", "settle", "seller"], date_filter="created_at",
    ordering=("-created_at",), queryset=lambda qs: qs.select_related("order", "seller"), can_add=False, can_delete=False,
    fieldsets=[("ارسال", ["carrier", "tracking_code", "cancel_reason"], "main"), ("مبلغ", ["commission", "seller_amount"], "side")],
    readonly=[("وضعیت", lambda o: _badge(o) if o.pk else "—"), ("فروشنده", lambda o: o.seller.name if o.pk else "—"),
              ("قابل تسویه از", lambda o: jdate(o.payable_at, "%Y/%m/%d") if o.pk and o.payable_at else "—")],
    actions={"deliver": ("ثبت تحویل به مشتری", _so_deliver),
             "cancel": ("لغو (برگشت پول مشتری با شما)", _so_cancel, "دلیل لغو"),
             "payable": ("قابل تسویه همین حالا (بدون صبر برای مهلت مرجوعی)", _so_payable)},
    help="هر سفارش مشتری که کالای فروشنده دارد، برای هر فروشنده یک ردیف اینجا دارد. «دیر» یعنی فروشنده در مهلت، سفارش را نپذیرفته. "
         "بعد از تحویل و گذشت مهلت مرجوعی، مبلغ خودکار «قابل تسویه» می‌شود.",
))

register(Resource(
    key="seller-payouts", model=SellerPayout, title="تسویهٔ فروشندگان", single="تسویه", group=G, icon="card",
    columns=[Col("seller", "فروشنده", lambda o: o.seller.name), Col("amount", "مبلغ", lambda o: toman(o.amount), "amount"),
             Col("reference", "کد پیگیری", lambda o: o.reference or "—"), Col("paid_at", "تاریخ", lambda o: jdate(o.paid_at, "%Y/%m/%d"), "paid_at")],
    search=["seller__name", "reference"], filters=["seller"], date_filter="paid_at", ordering=("-paid_at",),
    queryset=lambda qs: qs.select_related("seller"), can_add=False, fieldsets=[("تسویه", ["reference", "note", "paid_at"], "main")],
    help="تسویه از «فروشندگان ← انتخاب ← ثبت تسویه» ساخته می‌شود.",
))

register(Resource(
    key="category-commissions", model=CategoryCommission, title="کمیسیون دسته‌ها", single="کمیسیون دسته", group=G, icon="tag",
    columns=[Col("category", "دسته", lambda o: str(o.category)), Col("percent", "کمیسیون", lambda o: f"{fa_num(o.percent.normalize())}٪", "percent")],
    ordering=("category__name",), fieldsets=[("کمیسیون", ["category", "percent"], "main")],
    help="برای دسته‌ای که اینجا نیست، کمیسیون پیش‌فرض (تنظیمات ← مارکت‌پلیس) حساب می‌شود؛ زیر‌دسته‌ها کمیسیون دستهٔ بالاتر را می‌گیرند. "
         "کمیسیون اختصاصی هر فروشنده (در صفحهٔ فروشنده) بر این‌ها مقدم است.",
))

# فهرست محصولات اصلی: فیلتر فروشنده
_products = REGISTRY.get("products")
if _products and "seller" not in _products.filters:
    _products.filters.append("seller")

# جستجوی آژاکسی فروشنده در فیلترها و فرم‌ها
from dashboard.ac import AC, Spec  # noqa: E402

if not AC.get("seller"):
    AC.register("seller", Spec(Seller, ["name", "slug", "mobile", "city"], order="name"))
