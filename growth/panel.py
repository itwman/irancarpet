"""بخش‌های پنل: صفحه‌های فرود، کدهای تخفیف، خبرم کن، جستجوها."""
from django.utils.html import format_html

from core.templatetags.fa import fa_num, jdate, toman
from dashboard.registry import Col, Resource, register, yesno

from landing.models import LandingPage
from shop.models import Coupon

from .models import ProductAlert, SearchLog


def _sync(request, qs):
    from landing.build import sync

    msgs = []
    n = sync(log=msgs.append)
    return msgs[-1] if msgs else f"{n} صفحهٔ تازه ساخته شد."


register(Resource(
    key="landing-pages", model=LandingPage, title="صفحه‌های فرود", single="صفحهٔ فرود", group="سئو", icon="layers",
    columns=[Col("title", "عنوان", sort="title"), Col("count", "فرش", lambda o: fa_num(o.count), "count"),
             Col("price", "بازهٔ قیمت", lambda o: f"{toman(o.min_price)} تا {toman(o.max_price)}" if o.min_price else "—"),
             Col("is_active", "فعال", yesno("is_active"), "is_active"),
             Col("custom", "متن دستی", lambda o: "بله" if o.intro or o.seo_title else "خودکار")],
    search=["title", "slug"], filters=["is_active", "auto", "reeds", "size", "color"], ordering=("-count",),
    fieldsets=[("صفحه", ["title", "slug", "intro", "content"], "main"),
               ("سئو", ["seo_title", "seo_description"], "main"),
               ("فرش‌های صفحه", ["reeds", "size", "color", "style"], "side"), ("وضعیت", ["is_active"], "side")],
    readonly=[("تعداد فرش", lambda o: fa_num(o.count)), ("آخرین به‌روزرسانی", lambda o: jdate(o.synced_at, "%Y/%m/%d %H:%M"))],
    view_url=lambda o: o.get_absolute_url(),
    actions={"sync": ("ساخت صفحه‌های تازه و به‌روزرسانی همه", _sync)},
    after_save=lambda request, obj, created, form=None: __import__("landing.build", fromlist=["refresh"]).refresh(obj),
    help="این صفحه‌ها خودکار از روی فرش‌های موجود ساخته می‌شوند (سایز، رنگ، شانه×سایز، شانه×رنگ، رنگ×سایز) و هر ۶ ساعت به‌روز می‌شوند. "
         "صفحه‌ای که کمتر از ۴ فرش دارد در گوگل ایندکس نمی‌شود. متن و عنوان هر صفحه را می‌توانید دستی بنویسید.",
))


def _coupon_value(o):
    return f"{fa_num(o.value)}٪" + (f" (تا {toman(o.max_discount)})" if o.max_discount else "") if o.kind == "percent" else f"{toman(o.value)} تومان"


def _coupon_used(o):
    from shop.coupons import PLACED
    from shop.models import Order

    return fa_num(Order.objects.filter(coupon_code=o.code, status__in=PLACED).count())


register(Resource(
    key="coupons", model=Coupon, title="کدهای تخفیف", single="کد تخفیف", group="فروش", icon="tag",
    columns=[Col("code", "کد", lambda o: format_html('<code dir="ltr">{}</code>', o.code), "code"), Col("title", "عنوان"),
             Col("value", "تخفیف", _coupon_value), Col("used", "استفاده", _coupon_used),
             Col("owner", "نوع", lambda o: "کد معرفی" if o.owner_id else ("هدیه" if o.for_user_id else "عمومی")),
             Col("is_active", "فعال", yesno("is_active"), "is_active"),
             Col("ends_at", "پایان", lambda o: jdate(o.ends_at) if o.ends_at else "—", "ends_at")],
    search=["code", "title"], filters=["is_active", "kind", "first_order_only", "app_only"], ordering=("-created_at",),
    fieldsets=[("کد", ["code", "title", "kind", "value", "max_discount", "min_order"], "main"),
               ("محدودیت‌ها", ["starts_at", "ends_at", "usage_limit", "per_user_limit", "first_order_only", "app_only", "for_user"], "main"),
               ("وضعیت", ["is_active", "owner"], "side")],
    help="مثال «اولین خرید»: کد WELCOME، درصدی ۵، سقف ۳٬۰۰۰٬۰۰۰، فقط اولین خرید. کد معرفی دوستان را در «تنظیمات ← فروش و ارسال» روشن کنید.",
))

register(Resource(
    key="product-alerts", model=ProductAlert, title="خبرم کن", single="درخواست", group="فروش", icon="bell",
    columns=[Col("product", "فرش", lambda o: fa_num(o.product.title)[:60]), Col("kind", "نوع", lambda o: o.get_kind_display()),
             Col("mobile", "موبایل", lambda o: fa_num(o.mobile)),
             Col("sent_at", "خبر داده شد", lambda o: jdate(o.sent_at, "%Y/%m/%d %H:%M") if o.sent_at else "منتظر"),
             Col("created_at", "ثبت", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["mobile", "product__title"], filters=["kind", "source"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("product"), can_add=False, fieldsets=[("درخواست", ["kind", "mobile"], "main")],
    help="مشتری‌هایی که خواسته‌اند وقتی فرشی موجود یا ارزان شد خبرشان کنیم. پیامک خودکار هر ۱۰ دقیقه بررسی و فرستاده می‌شود.",
))

register(Resource(
    key="search-log", model=SearchLog, title="جستجوهای مشتری‌ها", single="جستجو", group="سئو", icon="search",
    columns=[Col("query", "جستجو", lambda o: o.query, "query"), Col("source", "کجا", lambda o: o.get_source_display(), "source"),
             Col("hits", "دفعات", lambda o: fa_num(o.hits), "hits"),
             Col("results", "نتیجه", lambda o: format_html('<span class="badge-ic b-{}">{}</span>', "failed" if not o.results else "ok",
                                                          "بی‌نتیجه" if not o.results else fa_num(o.results)), "results"),
             Col("last_seen", "آخرین بار", lambda o: jdate(o.last_seen, "%Y/%m/%d"), "last_seen")],
    search=["query"], filters=["source"], date_filter="last_seen", ordering=("-hits",), can_add=False,
    custom_filters={"empty": ("نتیجه", [("1", "فقط بی‌نتیجه‌ها")], lambda qs, v: qs.filter(results=0) if v == "1" else qs)},
    fieldsets=[("جستجو", ["query"], "main")],
    help="جستجوهای بی‌نتیجه یعنی مشتری چیزی خواسته که نداریم یا پیدایش نکرده: برای خرید از کارخانه، نوشتن مقاله یا اضافه کردن کلمه به «نیازهای مشتری» فرش‌یاب.",
))


# ------------------------------------------------------------------ فرصت ویژهٔ خرید
from django.utils import timezone as _tz  # noqa: E402

from shop.models import SpecialOffer  # noqa: E402


def _offer_state(o):
    now = _tz.now()
    if not o.is_active:
        return format_html('<span class="badge-ic b-draft">خاموش</span>')
    if o.ends_at and o.ends_at <= now:
        return format_html('<span class="badge-ic b-cancelled">تمام شد</span>')
    if o.starts_at > now:
        return format_html('<span class="badge-ic b-pending">هنوز شروع نشده</span>')
    if o.remaining <= 0:
        return format_html('<span class="badge-ic b-completed">فروخته شد</span>')
    if not o.ends_at:
        return format_html('<span class="badge-ic b-publish">فعال</span> <small class="muted">تا فروش</small>')
    left = o.ends_at - now
    h, m = divmod(int(left.total_seconds()) // 60, 60)
    return format_html('<span class="badge-ic b-publish">فعال</span> <small class="muted">{} ساعت و {} دقیقه مانده</small>', fa_num(h), fa_num(m))


def _renew(request, qs):
    n = 0
    for o in qs:
        o.ends_at = max(o.ends_at or _tz.now(), _tz.now()) + _tz.timedelta(hours=24)
        o.is_active = True
        o.save()
        n += 1
    return f"{fa_num(n)} فرصت ۲۴ ساعت تمدید شد."


def _end(request, qs):
    n = qs.update(ends_at=_tz.now())
    from shop.offers import clear

    clear()
    return f"{fa_num(n)} فرصت تمام شد."


register(Resource(
    key="special-offers", model=SpecialOffer, title="فرصت‌های ویژهٔ خرید", single="فرصت ویژه", group="فروشگاه", icon="tag",
    columns=[Col("product", "فرش", lambda o: format_html('<a href="/panel/products/{}/edit/">{}</a>', o.product_id, fa_num(o.product.title))),
             Col("size", "سایز", lambda o: fa_num(o.size.label)),
             Col("price", "قیمت ویژه", lambda o: format_html('<del class="muted">{}</del><br><strong>{}</strong>', toman(o.regular_price), toman(o.price))),
             Col("off", "تخفیف", lambda o: f"{fa_num(o.off_percent)}٪"),
             Col("left", "مانده", lambda o: f"{fa_num(o.remaining)} از {fa_num(o.quantity)}"),
             Col("state", "وضعیت", _offer_state),
             Col("ends_at", "پایان", lambda o: jdate(o.ends_at, "%Y/%m/%d %H:%M") if o.ends_at else "تا فروش", "ends_at")],
    search=["product__title", "note"], filters=["is_active"], ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("product", "size"),
    fieldsets=[("فرصت", ["product", "size", "percent", "fixed_price", "quantity"], "main"),
               ("زمان", ["starts_at", "ends_at", "is_active"], "side"), ("انبار", ["note"], "side")],
    readonly=[("قیمت روز این سایز", lambda o: f"{toman(o.regular_price)} تومان" if o.pk and o.regular_price else "—"),
              ("قیمت ویژه", lambda o: f"{toman(o.price)} تومان" if o.pk and o.price else "—"),
              ("فروخته‌شده", lambda o: fa_num(o.sold) if o.pk else "—")],
    view_url=lambda o: o.product.get_absolute_url(),
    actions={"end": ("پایان همین حالا", _end), "renew": ("تمدید ۲۴ ساعت (برای فرصت‌های زمان‌دار)", _renew)},
    help="تک‌تخته‌های انبار با تخفیف: فرش و سایز را انتخاب کنید (حتی اگر فرش یا آن سایز در سایت «ناموجود» باشد). "
         "قیمت ویژه فقط برای تعدادهایی است که بعد از خرید، تختهٔ تک در انبار نماند (باقی‌مانده صفر یا زوج): "
         "۲ تخته ← فقط جفت؛ ۳ ← ۱ یا ۳؛ ۴ ← ۲ یا ۴؛ ۵ ← ۱، ۳ یا ۵. تعداد دیگر با قیمت معمول حساب می‌شود و کد تخفیف روی فرصت اعمال نمی‌شود. "
         "بدون «پایان»، فرصت تا فروش تخته‌ها (یا صفر کردن «تعداد») می‌ماند. اگر «پایان» بگذارید، شمارندهٔ معکوس تا همان زمان نشان داده می‌شود و فرصت واقعاً تمام می‌شود. "
         "قیمت روز از آلبوم می‌آید؛ اگر قیمت آلبوم را به‌روز کنید، قیمت ویژه هم به همان نسبت به‌روز می‌شود.",
))
