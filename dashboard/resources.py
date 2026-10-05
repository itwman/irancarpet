"""همهٔ بخش‌های پنل در اینجا تعریف می‌شوند."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.html import format_html, format_html_join

from blog.models import BlogCategory, BlogTag, Comment, Faq, Page, Post
from catalog.models import Attribute, AttributeTerm, Brand, Category, Product, ProductTag, Review
from core.models import Media
from core.templatetags.fa import fa_num, jdate, toman
from pricing.models import Album, PriceLog, Size
from seo.models import NotFoundLog, Redirect
from shop.models import Order, Payment

from .models import ActivityLog
from .registry import Col, Inline, Resource, badge, register, thumb, yesno

SEO = ("سئو (عنوان و توضیح در گوگل)", ["seo_title", "seo_description", "focus_keyword", "robots", "canonical_url"], "side")


def jd(attr, fmt="%Y/%m/%d"):
    return lambda o: jdate(getattr(o, attr), fmt)


def money(attr):
    return lambda o: format_html('<span class="num">{}</span>', toman(getattr(o, attr)) if getattr(o, attr) not in (None, "") else "—")


def link(url_fn, text_fn):
    return lambda o: format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url_fn(o), text_fn(o))


# ================================================================== فروش
register(Resource(
    key="orders", model=Order, title="سفارش‌ها", single="سفارش", group="فروش", icon="receipt",
    columns=[Col("number", "شماره", lambda o: fa_num(o.number), "number"),
             Col("customer", "مشتری", lambda o: format_html("{}<br><small class='muted'>{}</small>", o.full_name, fa_num(o.mobile))),
             Col("items_total", "مبلغ", money("items_total"), "items_total"),
             Col("paid_amount", "پرداخت‌شده", money("paid_amount"), "paid_amount"),
             Col("payment_mode", "پرداخت", lambda o: o.get_payment_mode_display() + (
                 format_html(' <span class="badge-ic b-inst-{}">{}</span>', o.installment_state, o.get_installment_state_display())
                 if o.installment_state else "")),
             Col("status", "وضعیت", badge("status"), "status"),
             Col("created_at", "تاریخ", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    search=["=number", "mobile", "first_name", "last_name", "email", "city"],
    filters=["status", "payment_mode", "installment_state", "installment_plan", "shipping_mode", "province"], date_filter="created_at",
    ordering=("-created_at",), can_add=False, edit_url=lambda o: f"/panel/orders/{o.pk}/view/",
))

register(Resource(
    key="payments", model=Payment, title="تراکنش‌ها", single="تراکنش", group="فروش", icon="card",
    columns=[Col("order", "سفارش", lambda o: format_html('<a href="/panel/orders/{}/view/">{}</a>', o.order_id, fa_num(o.order.number))),
             Col("gateway", "درگاه", lambda o: o.get_gateway_display()),
             Col("amount", "مبلغ", money("amount"), "amount"),
             Col("status", "وضعیت", badge("status"), "status"),
             Col("ref_id", "کد پیگیری", lambda o: fa_num(o.ref_id)),
             Col("message", "پیام", lambda o: o.message),
             Col("created_at", "تاریخ", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    search=["ref_id", "token", "=order__number"], filters=["gateway", "status"], date_filter="created_at",
    queryset=lambda qs: qs.select_related("order"), can_add=False, can_delete=False,
    edit_url=lambda o: f"/panel/orders/{o.order_id}/view/",
))

User = get_user_model()
register(Resource(
    key="customers", model=User, title="مشتریان و کارمندان", single="کاربر", group="فروش", icon="users",
    columns=[Col("name", "نام", lambda o: o.get_full_name() or "—"),
             Col("mobile", "موبایل", lambda o: fa_num(getattr(getattr(o, "profile", None), "mobile", "") or o.username)),
             Col("email", "ایمیل", lambda o: o.email),
             Col("orders", "سفارش", lambda o: fa_num(o._orders), "_orders"),
             Col("is_staff", "دسترسی پنل", yesno("is_staff"), "is_staff"),
             Col("date_joined", "عضویت", jd("date_joined"), "date_joined")],
    search=["username", "first_name", "last_name", "email", "profile__mobile"], filters=["is_staff", "is_active"],
    date_filter="date_joined", ordering=("-date_joined",), can_add=True,
    queryset=lambda qs: qs.select_related("profile").annotate(_orders=Count("orders")),
    edit_url=lambda o: f"/panel/customers/{o.pk}/edit/",
))

from installments.models import InstallmentPlan  # noqa: E402

register(Resource(
    key="installment-plans", model=InstallmentPlan, title="روش‌های اقساط", single="روش اقساط", group="فروش", icon="calendar",
    columns=[Col("title", "عنوان", sort="title"), Col("kind", "نوع", lambda o: o.get_kind_display()),
             Col("monthly_rate", "سود ماهانه", lambda o: fa_num(o.monthly_rate.normalize()) + "٪", "monthly_rate"),
             Col("down", "پیش‌پرداخت", lambda o: f"{fa_num(o.min_down_percent)} تا {fa_num(o.max_down_percent)}٪"),
             Col("months", "مدت", lambda o: f"{fa_num(o.min_months)} تا {fa_num(o.max_months)} ماه"),
             Col("orders", "سفارش", lambda o: fa_num(o._n), "_n"), Col("is_active", "فعال", yesno("is_active"))],
    search=["title"], filters=["is_active", "kind"], ordering=("sort_order", "pk"),
    queryset=lambda qs: qs.annotate(_n=Count("orders")),
    fieldsets=[("روش", ["title", "kind", "summary", "description"], "main"),
               ("اطلاعاتی که از مشتری گرفته می‌شود", ["ask_holder_name", "ask_national_code", "ask_cheque_image", "ask_sayad_id",
                                                       "ask_bank_name", "ask_pensioner_type", "ask_retiree_id", "ask_sms_mobile",
                                                       "submit_note"], "main"),
               ("پیام‌ها", ["review_note", "approved_note", "approved_sms", "rejected_sms"], "main"),
               ("محاسبه", ["monthly_rate", "min_down_percent", "max_down_percent", "down_step", "min_months", "max_months",
                           "allow_monthly", "allow_bimonthly", "first_due_days", "round_to", "min_order_amount", "down_timing"], "side"),
               ("وضعیت", ["is_active", "sort_order"], "side")],
    readonly=[("نمونهٔ محاسبه برای ۱۰۰ میلیون تومان", lambda o: _plan_example(o))],
    help="سود با راس‌گیری: درصد ماهانه × (میانگین روزهای سررسید ÷ ۳۰). مثلاً ۲ قسط ماهانه = راس ۴۵ روز = ۱٫۵ × سود ماهانه. "
         "تاریخ قسط‌ها از «تاریخ سفارش + روزهای آماده‌سازی» شمرده می‌شود.",
))


def _plan_example(p):
    from installments.calc import QuoteError, quote

    if not p.pk:
        return "—"
    rows = []
    for step in p.steps():
        for m in sorted({p.months_for(step)[0], p.months_for(step)[-1]} if p.months_for(step) else []):
            try:
                q = quote(p, 100_000_000, p.min_down_percent, m, step)
            except QuoteError as e:
                rows.append((str(e), "", "", ""))
                continue
            rows.append((f"{fa_num(m)} ماه {'دوماهه' if step == 2 else 'ماهانه'}", f"{fa_num(q['interest_percent'])}٪",
                         f"{fa_num(q['count'])} × {toman(q['installment'])}", toman(q["payable_total"])))
    return format_html('<table class="tbl tbl-sm"><thead><tr><th>مدت</th><th>سود</th><th>اقساط</th><th>جمع کل</th></tr></thead><tbody>{}</tbody></table>',
                       format_html_join("", "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>", rows))


# ================================================================ فروشگاه
register(Resource(
    key="products", model=Product, title="محصولات", single="محصول", group="فروشگاه", icon="carpet",
    columns=[Col("image", "", thumb(), cls="w-thumb"),
             Col("title", "عنوان", lambda o: fa_num(o.title), "title"),
             Col("album", "آلبوم قیمت", lambda o: o.album.name if o.album else "—"),
             Col("min_price", "قیمت", money("min_price"), "min_price"),
             Col("stock_status", "موجودی", badge("stock_status"), "stock_status"),
             Col("status", "وضعیت", badge("status"), "status"),
             Col("published_at", "انتشار", jd("published_at"), "published_at")],
    search=["title", "sku", "slug", "=id"], filters=["status", "stock_status", "sale_status", "album", "brand", "categories", "tags", "specs"],
    date_filter="published_at", ordering=("-published_at",),
    queryset=lambda qs: qs.select_related("image", "album", "brand", "primary_category").prefetch_related("tags", "categories", "specs__attribute"),
    extra_columns=lambda: _product_extra_columns(),
    view_url=lambda o: o.get_absolute_url(), edit_url=lambda o: f"/panel/products/{o.pk}/edit/",
    actions={
        "publish": ("انتشار", lambda r, qs: f"{qs.update(status='publish')} محصول منتشر شد."),
        "draft": ("پیش‌نویس کردن", lambda r, qs: f"{qs.update(status='draft')} محصول پیش‌نویس شد."),
        "available": ("وضعیت فروش: موجود", lambda r, qs: _set_sale(qs, "available")),
        "unavailable": ("وضعیت فروش: ناموجود", lambda r, qs: _set_sale(qs, "unavailable")),
        "set_album": ("تغییر آلبوم قیمت", lambda r, qs: _set_album(r, qs), "آلبوم", lambda: _album_choices()),
        "follow_album": ("پیروی کامل از قیمت آلبوم (حذف قیمت‌های اختصاصی و حراج)", lambda r, qs: _follow_album(qs)),
        "clear_sale": ("حذف قیمت حراج", lambda r, qs: _clear_sale(qs)),
    },
    custom_filters={"own_price": ("قیمت جدا از آلبوم", [
        ("any", "هر نوع"), ("custom", "قیمت پایهٔ اختصاصی"), ("override", "قیمت خرید اختصاصی سایز"), ("sale", "قیمت حراج"),
    ], lambda qs, v: qs.filter(_override_q(v)).distinct())},
))


def _album_choices():
    return [("0", "— بدون آلبوم (قیمت دستی) —")] + [
        (str(a.pk), f"{a.name} — ۱۲ متری {toman(a.size_price(a.base_size)) or '—'}")
        for a in Album.objects.filter(is_active=True).select_related("base_size").order_by("sort_order", "name")]


def _set_album(request, qs):
    """اختصاص گروهی محصولات به یک آلبوم (یا خارج کردن از آلبوم با ثابت ماندن قیمت فعلی)."""
    from django.db import transaction
    from django.utils import timezone

    from catalog.models import Variation
    from pricing.albums import sync_album_variations

    val = (request.POST.get("action_value") or "").strip()
    album = Album.objects.filter(pk=val, is_active=True).first() if val.isdigit() and val != "0" else None
    if val != "0" and album is None:
        return "آلبوم انتخاب نشد؛ چیزی تغییر نکرد."
    ids = list(qs.values_list("pk", flat=True))
    with transaction.atomic():
        if album is None:
            # قیمت فعلی هر سایز به‌عنوان قیمت دستی ثابت می‌ماند
            vs = list(Variation.objects.filter(product_id__in=ids))
            for v in vs:
                v.manual_price = v.final_price or v.manual_price
                v.override_price = None
            Variation.objects.bulk_update(vs, ["manual_price", "override_price"], batch_size=1000)
            Product.objects.filter(pk__in=ids).update(album=None, custom_base_price=None, modified_at=timezone.now())
            Variation.reprice_queryset(Variation.objects.filter(product_id__in=ids), scale_sale=False)
            return f"{fa_num(len(ids))} محصول از آلبوم خارج شد؛ قیمت فعلی‌شان به‌صورت قیمت دستی ماند."
        Product.objects.filter(pk__in=ids).update(album=album, custom_base_price=None, modified_at=timezone.now())
        Variation.objects.filter(product_id__in=ids).update(override_price=None)
        st = sync_album_variations(list(Product.objects.filter(pk__in=ids).select_related("album")))
    return (f"{fa_num(len(ids))} محصول به آلبوم «{album.name}» رفت و قیمت‌ها به‌روز شد"
            f" ({fa_num(st['created'])} سایز تازه، {fa_num(st['deleted'])} سایز خارج از آلبوم حذف شد).")


def _chips(items):
    items = [str(x) for x in items]
    if not items:
        return "—"
    return format_html('<span class="chips-p">{}</span>', format_html_join("", "<span>{}</span>", ((fa_num(x),) for x in items)))


def _product_extra_columns():
    from catalog.models import Attribute

    cols = [
        Col("sku", "کد کالا", lambda o: fa_num(o.sku or "—"), "sku"),
        Col("tags", "برچسب‌ها", lambda o: _chips(t.name for t in o.tags.all())),
        Col("categories", "دسته‌ها", lambda o: _chips(c.name for c in o.categories.all())),
        Col("brand", "برند", lambda o: o.brand.name if o.brand else "—"),
        Col("sale_status", "وضعیت فروش", badge("sale_status"), "sale_status"),
        Col("views", "بازدید", lambda o: fa_num(o.views), "views"),
    ]
    for a in Attribute.objects.order_by("order", "label"):
        cols.append(Col(f"attr_{a.pk}", a.label, (lambda aid: lambda o: _chips(t.name for t in o.specs.all() if t.attribute_id == aid))(a.pk)))
    return cols


def _override_q(kind):
    from pricing.overrides import override_filter

    return override_filter(kind)


def _follow_album(qs):
    from pricing.overrides import follow_album

    n = follow_album(list(qs))
    return f"{fa_num(n)} محصول حالا دقیقاً از قیمت آلبومش پیروی می‌کند (محصولات بدون آلبوم دست نخوردند)."


def _clear_sale(qs):
    from pricing.overrides import clear_sales

    return f"قیمت حراج {fa_num(clear_sales(list(qs)))} سایز حذف شد."


def _set_sale(qs, status):
    n = 0
    for p in qs:
        p.sale_status = status
        p.save()
        p.refresh_price_cache()
        n += 1
    return f"وضعیت فروش {n} محصول تغییر کرد."


TAX_FIELDS = ("اطلاعات", ["name", "slug", "description"], "main")
register(Resource(
    key="categories", model=Category, title="دسته‌های محصول", single="دسته", group="فروشگاه", icon="folder",
    columns=[Col("image", "", thumb(), cls="w-thumb"), Col("name", "نام", sort="name"),
             Col("parent", "والد", lambda o: o.parent.name if o.parent else "—"),
             Col("n", "محصول", lambda o: fa_num(o._n), "_n"), Col("order", "ترتیب", lambda o: fa_num(o.order), "order")],
    search=["name", "slug"], ordering=("order", "name"), slug_from="name",
    queryset=lambda qs: qs.select_related("parent", "image").annotate(_n=Count("products")),
    fieldsets=[TAX_FIELDS, ("جایگاه", ["parent", "order", "image"], "side"), SEO],
    view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="brands", model=Brand, title="برندها", single="برند", group="فروشگاه", icon="tag",
    columns=[Col("logo", "", thumb("logo"), cls="w-thumb"), Col("name", "نام", sort="name"), Col("n", "محصول", lambda o: fa_num(o._n), "_n")],
    search=["name", "slug"], ordering=("name",), slug_from="name",
    queryset=lambda qs: qs.select_related("logo").annotate(_n=Count("products")),
    fieldsets=[TAX_FIELDS, ("لوگو", ["logo"], "side"), SEO], view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="tags", model=ProductTag, title="برچسب‌های محصول", single="برچسب", group="فروشگاه", icon="hash",
    columns=[Col("name", "نام", sort="name"), Col("slug", "نامک"), Col("n", "محصول", lambda o: fa_num(o._n), "_n")],
    search=["name", "slug"], ordering=("name",), slug_from="name",
    queryset=lambda qs: qs.annotate(_n=Count("products")), fieldsets=[TAX_FIELDS, SEO], view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="attributes", model=Attribute, title="ویژگی‌ها (شانه، رنگ و…)", single="ویژگی", group="فروشگاه", icon="sliders",
    columns=[Col("label", "نام", sort="label"), Col("slug", "نامک"), Col("is_public", "صفحهٔ عمومی", yesno("is_public")),
             Col("show_in_filters", "در فیلترها", yesno("show_in_filters")), Col("n", "مقدار", lambda o: fa_num(o._n), "_n")],
    search=["label", "slug"], ordering=("order",), slug_from="label",
    queryset=lambda qs: qs.annotate(_n=Count("terms")),
    fieldsets=[("اطلاعات", ["label", "slug", "order"], "main"), ("نمایش", ["is_public", "show_in_filters"], "side")],
    inlines=[Inline(AttributeTerm, "attribute", ["name", "slug", "order"], "مقدارها", extra=2)],
))
register(Resource(
    key="terms", model=AttributeTerm, title="مقدار ویژگی‌ها", single="مقدار", group="فروشگاه", icon="list", nav=False,
    columns=[Col("attribute", "ویژگی", lambda o: o.attribute.label), Col("name", "مقدار", lambda o: fa_num(o.name), "name"),
             Col("n", "محصول", lambda o: fa_num(o._n), "_n")],
    search=["name", "slug"], filters=["attribute"], ordering=("attribute__order", "order"), slug_from="name",
    queryset=lambda qs: qs.select_related("attribute").annotate(_n=Count("products")),
    fieldsets=[("اطلاعات", ["attribute", "name", "slug", "order", "description"], "main"), SEO],
    view_url=lambda o: o.get_absolute_url() if o.attribute.is_public else "",
))


def _review_after_save(request, obj, created, form=None):
    from catalog.reviews import recompute

    reply = (request.POST.get("reply") or "").strip()
    if reply:
        Review.objects.create(product=obj.product, parent=obj, author_name="ایران کارپت", content=reply, is_approved=True, rating=0)
    recompute(obj.product)


def _review_set(qs, approved):
    from catalog.reviews import recompute

    n = qs.update(is_approved=approved)
    for p in {r.product for r in qs.select_related("product")}:
        recompute(p)
    return n


def _review_photos(o):
    photos = list(o.photos.all())
    if not photos:
        return "—"
    return format_html_join("", '<a href="{0}" target="_blank"><img src="{0}" alt="" style="width:110px;height:110px;object-fit:cover;'
                                'border-radius:10px;margin:0 0 6px 6px"></a>', ((p.url,) for p in photos))


register(Resource(
    key="reviews", model=Review, title="نظرات محصولات", single="نظر", group="فروشگاه", icon="chat",
    columns=[Col("author_name", "نویسنده", sort="author_name"),
             Col("content", "متن", lambda o: (o.content or "")[:90]),
             Col("product", "محصول", lambda o: fa_num(o.product.title)[:50]),
             Col("rating", "امتیاز", lambda o: "★" * (o.rating or 0), "rating"),
             Col("photos", "عکس", lambda o: fa_num(o._ph) if o._ph else ""),
             Col("is_approved", "تأیید", yesno("is_approved"), "is_approved"),
             Col("created_at", "تاریخ", jd("created_at"), "created_at")],
    search=["author_name", "content", "product__title"], filters=["is_approved", "rating"], date_filter="created_at",
    ordering=("-created_at",), queryset=lambda qs: qs.select_related("product").annotate(_ph=Count("photos")),
    fieldsets=[("نظر", ["author_name", "author_email", "rating", "content"], "main"),
               ("وضعیت", ["product", "is_approved", "verified", "created_at"], "side")],
    after_save=_review_after_save, can_add=False,
    view_url=lambda o: o.product.get_absolute_url() + "#reviews",
    actions={"approve": ("تأیید", lambda r, qs: f"{_review_set(qs, True)} نظر تأیید شد."),
             "unapprove": ("رد تأیید", lambda r, qs: f"{_review_set(qs, False)} نظر از نمایش خارج شد.")},
    readonly=[("عکس‌های مشتری", _review_photos), ("خریدار این فرش", lambda o: "بله" if o.verified else "خیر"),
              ("موبایل", lambda o: fa_num(o.mobile) or "—")],
))
register(Resource(
    key="faqs", model=Faq, title="پرسش‌های متداول", single="پرسش", group="فروشگاه", icon="help",
    columns=[Col("question", "پرسش", sort="question"), Col("product", "محصول", lambda o: o.product.title[:40] if o.product else "عمومی"),
             Col("is_active", "فعال", yesno("is_active")), Col("order", "ترتیب", lambda o: fa_num(o.order), "order")],
    search=["question", "answer"], filters=["is_active"], ordering=("order",), queryset=lambda qs: qs.select_related("product"),
    fieldsets=[("پرسش", ["question", "answer"], "main"), ("تنظیمات", ["product", "group", "order", "is_active"], "side")],
))

# ============================================================== قیمت‌گذاری
register(Resource(
    key="albums", model=Album, title="آلبوم‌های قیمت", single="آلبوم", group="قیمت‌گذاری", icon="layers",
    columns=[Col("name", "نام", sort="name"), Col("code", "کد"), Col("company", "شرکت"),
             Col("base_size", "سایز پایه", lambda o: o.base_size.label if o.base_size else "—"),
             Col("base_price", "خرید ۱۲ متری", money("base_price"), "base_price"),
             Col("sale12", "فروش ۱۲ متری", lambda o: format_html('<span class="num">{}</span>', toman(o.size_price(o.base_size)) or "—")),
             Col("profit_percent", "سود", lambda o: fa_num(o.profit_percent.normalize()) + "٪", "profit_percent"),
             Col("waste", "پرتی", lambda o: (toman(int(o.waste_value or 0)) or "۰") + ("٪" if o.waste_type == "percent" else "")),
             Col("n", "محصول", lambda o: fa_num(o._n), "_n"), Col("is_active", "فعال", yesno("is_active")),
             Col("last_updated", "به‌روزرسانی", jd("last_updated"), "last_updated")],
    search=["name", "code", "company"], filters=["is_active", "in_price_list", "base_size", "waste_type"], ordering=("sort_order", "name"),
    view_url=lambda o: o.get_absolute_url() if o.slug else None,
    queryset=lambda qs: qs.select_related("base_size").annotate(_n=Count("products")),
    fieldsets=[("آلبوم", ["name", "code", "company", "description"], "main"),
               ("سایزها", ["sizes", "even_sizes"], "main"),
               ("صفحهٔ لیست قیمت سایت", ["in_price_list", "public_name", "slug", "list_intro", "seo_title", "seo_description"], "main"),
               ("قیمت", ["base_size", "base_price", "profit_percent", "shipping_fixed", "waste_type", "waste_value", "round_to"], "side"),
               ("وضعیت", ["is_active", "sort_order"], "side")],
    readonly=[("قیمت فروش سایزها", lambda o: _album_preview(o)),
              ("محصولات با قیمت جدا از آلبوم", lambda o: _album_own_prices(o))],
    after_save=lambda r, o, c, f: _album_saved(r, o, c, f),
    initial=lambda: _album_initial(),
    actions={"percent": ("تغییر درصدی قیمت پایه", lambda r, qs: _album_percent(r, qs), "درصد (مثلاً ۵ یا -۳)"),
             "follow": ("پیروی کامل همهٔ محصولات این آلبوم‌ها از قیمت آلبوم", lambda r, qs: _album_follow(qs))},
    help="قیمت فروش ۱۲ متری = قیمت خرید × (۱ + درصد سود) + هزینهٔ ارسال؛ بقیهٔ سایزها به نسبت متراژ، رو به بالا گرد می‌شوند. "
         "مشتری برای محصولات آلبوم همهٔ «سایزهای آلبوم» را می‌بیند و با هر تغییر، قیمت‌ها خودکار به‌روز می‌شوند.",
))
def _album_saved(request, obj, created, form):
    from catalog.models import Product
    from pricing.albums import sync_album_variations

    _album_log(request, obj, created, form)
    if created or {"sizes", "even_sizes"} & set(form.changed_data):
        sync_album_variations(list(Product.objects.filter(album=obj).select_related("album")))


def _album_initial():
    """آلبوم تازه: سایز پایه ۱۲ متری، و سایزها/سود/ارسال/پرتی مثل آخرین آلبوم."""
    from pricing.models import PricingSettings

    st = PricingSettings.load()
    init = {"base_size": Size.objects.filter(slug="12-meter").values_list("pk", flat=True).first(),
            "profit_percent": st.markup_percent, "shipping_fixed": st.shipping_fixed, "round_to": st.round_to}
    last = Album.objects.filter(is_active=True).exclude(sizes=None).order_by("-pk").first()
    if last:
        init.update(sizes=list(last.sizes.values_list("pk", flat=True)), even_sizes=list(last.even_sizes.values_list("pk", flat=True)),
                    waste_type=last.waste_type, waste_value=last.waste_value, round_to=last.round_to)
    else:
        init["sizes"] = list(Size.objects.filter(slug__in=["12-meter", "9-meter", "6-meter"]).values_list("pk", flat=True))
    return init


def _album_preview(album):
    from django.utils.html import format_html, format_html_join

    if not album.pk:
        return "پس از ذخیره"
    rows = [(fa_num(s.label), toman(album.size_price(s)) or "—") for s in album.sizes.order_by("sort_order")]
    if not rows:
        return "سایزی انتخاب نشده"
    return format_html('<span class="album-prev">{}</span>', format_html_join("", "<span>{}<b>{}</b></span>", rows))


def _album_log(request, obj, created, form):
    if not created and "base_price" in form.changed_data:
        PriceLog.objects.create(album=obj, old_price=form.initial.get("base_price") or 0, new_price=obj.base_price,
                                reason="panel_edit" + ("+scaled" if getattr(obj, "_scaled", False) else ""), user=request.user)


def _album_own_prices(album):
    from django.utils.html import format_html

    from catalog.models import Product
    from pricing.overrides import override_filter

    if not album.pk:
        return "—"
    n = Product.objects.filter(album=album).filter(override_filter("any")).distinct().count()
    if not n:
        return "ندارد؛ همه دقیقاً از قیمت آلبوم پیروی می‌کنند"
    return format_html('<a href="/panel/products/?album={}&own_price=any">{} محصول</a>', album.pk, fa_num(n))


def _album_follow(qs):
    from catalog.models import Product
    from pricing.overrides import follow_album

    n = follow_album(list(Product.objects.filter(album__in=qs)))
    return f"{fa_num(n)} محصول حالا دقیقاً از قیمت آلبومشان پیروی می‌کنند."


def _album_percent(request, qs):
    from .forms import to_en

    try:
        p = Decimal(to_en(request.POST.get("action_value", "")).replace("٪", "").replace("%", "").strip())
    except Exception:  # noqa: BLE001
        return "درصد نامعتبر بود؛ چیزی تغییر نکرد."
    n = 0
    for album in qs:
        album.set_base_price((album.base_price * (1 + p / 100)).quantize(Decimal("1")), request.user, "bulk_percent")
        n += 1
    return f"قیمت پایهٔ {fa_num(n)} آلبوم {fa_num(p)}٪ تغییر کرد و قیمت محصولاتشان دوباره محاسبه شد."


register(Resource(
    key="sizes", model=Size, title="سایزها", single="سایز", group="قیمت‌گذاری", icon="ruler",
    columns=[Col("label", "عنوان", lambda o: fa_num(o.label), "label"), Col("slug", "نامک"), Col("type", "نوع", badge("type"), "type"),
             Col("area", "متراژ", lambda o: fa_num(o.area.normalize()), "area"), Col("default_pair_only", "فقط جفت", yesno("default_pair_only")),
             Col("needs_waste", "پرتی", yesno("needs_waste")), Col("is_active", "فعال", yesno("is_active")),
             Col("n", "تنوع", lambda o: fa_num(o._n), "_n")],
    search=["label", "slug"], filters=["type", "is_active", "needs_waste"], ordering=("sort_order",),
    queryset=lambda qs: qs.annotate(_n=Count("variations")),
    fieldsets=[("سایز", ["label", "slug", "type", "width", "length", "diameter", "area"], "main"),
               ("قواعد", ["default_pair_only", "needs_waste", "is_active", "sort_order"], "side")],
))
register(Resource(
    key="pricelog", model=PriceLog, title="تاریخچهٔ قیمت", single="تغییر قیمت", group="قیمت‌گذاری", icon="clock",
    columns=[Col("album", "آلبوم", lambda o: o.album.name if o.album else (o.product.title if o.product else "—")),
             Col("old_price", "قیمت قبلی", money("old_price")), Col("new_price", "قیمت جدید", money("new_price")),
             Col("reason", "دلیل"), Col("user", "کاربر", lambda o: o.user.get_full_name() or o.user.username if o.user else "—"),
             Col("created_at", "تاریخ", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    filters=["album"], date_filter="created_at", ordering=("-created_at",), can_add=False,
    queryset=lambda qs: qs.select_related("album", "product", "user"), edit_url=lambda o: "/panel/pricelog/",
))

# ================================================================== مجله
register(Resource(
    key="posts", model=Post, title="نوشته‌های مجله", single="نوشته", group="مجله و برگه‌ها", icon="pen",
    columns=[Col("image", "", thumb(), cls="w-thumb"), Col("title", "عنوان", lambda o: fa_num(o.title), "title"),
             Col("status", "وضعیت", badge("status"), "status"), Col("views", "بازدید", lambda o: fa_num(o.views), "views"),
             Col("published_at", "انتشار", jd("published_at"), "published_at")],
    search=["title", "slug"], filters=["status", "categories"], date_filter="published_at", ordering=("-published_at",),
    queryset=lambda qs: qs.select_related("image"), slug_from="title",
    fieldsets=[("نوشته", ["title", "slug", "content", "excerpt"], "main"),
               ("انتشار", ["status", "published_at", "author_name"], "side"),
               ("دسته و برچسب", ["primary_category", "categories", "tags"], "side"),
               ("تصویر شاخص", ["image"], "side"), SEO],
    view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="pages", model=Page, title="برگه‌ها", single="برگه", group="مجله و برگه‌ها", icon="file",
    columns=[Col("title", "عنوان", sort="title"), Col("path", "آدرس", lambda o: format_html('<span class="ltr-num">/{}/</span>', o.path)),
             Col("template", "قالب ویژه"), Col("status", "وضعیت", badge("status"), "status"),
             Col("modified_at", "ویرایش", jd("modified_at"), "modified_at")],
    search=["title", "slug"], filters=["status"], ordering=("title",), slug_from="title",
    queryset=lambda qs: qs.select_related("parent__parent"),
    fieldsets=[("برگه", ["title", "slug", "content"], "main"),
               ("انتشار", ["status", "parent", "template", "menu_order", "published_at"], "side"),
               ("تصویر", ["image"], "side"), SEO],
    view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="blog-categories", model=BlogCategory, title="دسته‌های مجله", single="دسته", group="مجله و برگه‌ها", icon="folder",
    columns=[Col("name", "نام", sort="name"), Col("parent", "والد", lambda o: o.parent.name if o.parent else "—"),
             Col("n", "نوشته", lambda o: fa_num(o._n), "_n")],
    search=["name", "slug"], ordering=("name",), slug_from="name",
    queryset=lambda qs: qs.select_related("parent").annotate(_n=Count("posts")),
    fieldsets=[TAX_FIELDS, ("جایگاه", ["parent"], "side"), SEO], view_url=lambda o: o.get_absolute_url(),
))
register(Resource(
    key="blog-tags", model=BlogTag, title="برچسب‌های مجله", single="برچسب", group="مجله و برگه‌ها", icon="hash",
    columns=[Col("name", "نام", sort="name"), Col("n", "نوشته", lambda o: fa_num(o._n), "_n")],
    search=["name", "slug"], ordering=("name",), slug_from="name",
    queryset=lambda qs: qs.annotate(_n=Count("posts")), fieldsets=[TAX_FIELDS, SEO], view_url=lambda o: o.get_absolute_url(),
))


def _comment_after_save(request, obj, created, form=None):
    reply = (request.POST.get("reply") or "").strip()
    if reply:
        Comment.objects.create(post=obj.post, parent=obj, author_name="ایران کارپت", content=reply, is_approved=True)


register(Resource(
    key="comments", model=Comment, title="دیدگاه‌های مجله", single="دیدگاه", group="مجله و برگه‌ها", icon="chat",
    columns=[Col("author_name", "نویسنده"), Col("content", "متن", lambda o: (o.content or "")[:90]),
             Col("post", "نوشته", lambda o: o.post.title[:50]), Col("is_approved", "تأیید", yesno("is_approved"), "is_approved"),
             Col("created_at", "تاریخ", jd("created_at"), "created_at")],
    search=["author_name", "content"], filters=["is_approved"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("post"), can_add=False, after_save=_comment_after_save,
    fieldsets=[("دیدگاه", ["author_name", "author_email", "content"], "main"), ("وضعیت", ["post", "is_approved", "created_at"], "side")],
    actions={"approve": ("تأیید", lambda r, qs: f"{qs.update(is_approved=True)} دیدگاه تأیید شد."),
             "unapprove": ("رد تأیید", lambda r, qs: f"{qs.update(is_approved=False)} دیدگاه پنهان شد.")},
    view_url=lambda o: o.post.get_absolute_url(),
))

# ================================================================== رسانه
register(Resource(
    key="media", model=Media, title="کتابخانهٔ رسانه", single="فایل", group="رسانه", icon="image",
    columns=[Col("file", "", lambda o: format_html('<img class="thumb" src="{}" alt="" loading="lazy">', o.url), cls="w-thumb"),
             Col("title", "عنوان", sort="title"), Col("alt", "متن جایگزین"), Col("size", "ابعاد", lambda o: fa_num(f"{o.width}×{o.height}") if o.width else ""),
             Col("created_at", "تاریخ", jd("created_at"), "created_at")],
    search=["title", "alt", "file"], date_filter="created_at", ordering=("-created_at",),
    fieldsets=[("فایل", ["file", "title", "alt", "caption"], "main")], list_template="dashboard/media_list.html",
))

# ==================================================================== سئو
register(Resource(
    key="redirects", model=Redirect, title="ریدایرکت‌ها", single="ریدایرکت", group="سئو", icon="arrow",
    columns=[Col("source", "از", lambda o: format_html('<span class="ltr-num">{}</span>', o.source), "source"),
             Col("target", "به", lambda o: format_html('<span class="ltr-num">{}</span>', o.target or "—")),
             Col("status_code", "کد", lambda o: fa_num(o.status_code), "status_code"), Col("match", "تطبیق", badge("match")),
             Col("hits", "بازدید", lambda o: fa_num(o.hits), "hits"), Col("is_active", "فعال", yesno("is_active"))],
    search=["source", "target"], filters=["status_code", "match", "is_active", "origin"], ordering=("-created_at",),
    fieldsets=[("ریدایرکت", ["source", "target", "match", "status_code"], "main"), ("وضعیت", ["is_active"], "side")],
    help="مسیرها را بدون دامنه بنویسید؛ مثل /product/old-name/",
))
register(Resource(
    key="notfound", model=NotFoundLog, title="خطاهای ۴۰۴", single="خطا", group="سئو", icon="alert",
    columns=[Col("path", "آدرس", lambda o: format_html('<span class="ltr-num">{}</span>', o.path), "path"),
             Col("hits", "تعداد", lambda o: fa_num(o.hits), "hits"),
             Col("referrer", "از صفحهٔ", lambda o: format_html('<span class="ltr-num small">{}</span>', (o.referrer or "")[:60])),
             Col("last_seen", "آخرین بار", jd("last_seen", "%Y/%m/%d %H:%M"), "last_seen"),
             Col("fix", "", lambda o: format_html('<a class="btn btn-sm btn-ic-soft" href="/panel/redirects/add/?source={}">ساخت ریدایرکت</a>', o.path))],
    search=["path", "referrer"], ordering=("-hits",), can_add=False, edit_url=lambda o: f"/panel/redirects/add/?source={o.path}",
))

# ============================================================ گزارش فعالیت
register(Resource(
    key="activity", model=ActivityLog, title="گزارش فعالیت", single="فعالیت", group="تنظیمات", icon="clock",
    columns=[Col("user", "کاربر", lambda o: (o.user.get_full_name() or o.user.username) if o.user else "—"),
             Col("action", "عمل", badge("action")), Col("section", "بخش"), Col("object_repr", "مورد"), Col("detail", "جزئیات"),
             Col("created_at", "زمان", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    search=["object_repr", "section", "detail"], filters=["action", "user"], date_filter="created_at",
    ordering=("-created_at",), can_add=False, can_delete=False, queryset=lambda qs: qs.select_related("user"),
    edit_url=lambda o: "/panel/activity/",
))

# ================================================================ فرش پلاس
from farshplus.models import STATUS_LABELS, FarshPlusItem  # noqa: E402


def _fp_queue(request, qs, mode="manual", enabled=None):
    from farshplus.sync import queue

    n = 0
    for item in qs:
        if enabled is not None:
            item.enabled = enabled
        queue(item, mode)
        n += 1
    return n


def _fp_status(o):
    return format_html('<span class="badge-ic b-fp-{}">{}</span>', (o.status or "none").lower(), o.get_status_display())


register(Resource(
    key="farshplus", model=FarshPlusItem, title="محصولات در فرش پلاس", single="مورد", group="فروشگاه", icon="arrow",
    columns=[Col("thumb", "", lambda o: thumb()(o.product), cls="w-thumb"),
             Col("product", "محصول", lambda o: fa_num(o.product.title)),
             Col("status", "وضعیت", _fp_status, "status"),
             Col("post", "پست", lambda o: format_html('<a href="{}" target="_blank" rel="noopener">دیدن</a>', o.post_url) if o.post_url else "—"),
             Col("queued", "در صف", lambda o: "بله" if o.queued else ""),
             Col("synced_at", "آخرین ارسال", jd("synced_at", "%Y/%m/%d %H:%M"), "synced_at"),
             Col("error", "خطا", lambda o: format_html('<span class="text-danger small">{}</span>', o.error[:80]) if o.error else "")],
    search=["product__title", "external_id"], filters=["status", "queued"], ordering=("-synced_at",),
    queryset=lambda qs: qs.select_related("product__image"), can_add=False, can_delete=False,
    edit_url=lambda o: f"/panel/products/{o.product_id}/edit/#farshplus",
    actions={
        "send": ("ارسال / به‌روزرسانی", lambda r, qs: f"{_fp_queue(r, qs)} مورد در صف ارسال قرار گرفت."),
        "remove": ("برداشتن از فرش پلاس", lambda r, qs: f"{_fp_queue(r, qs, enabled=False)} مورد برای حذف از فرش پلاس در صف قرار گرفت."),
    },
    help="ارسال‌ها هر ۵ دقیقه به‌صورت خودکار انجام می‌شود. تنظیمات و ارسال گروهی در «تنظیمات ← فرش پلاس» است.",
))


# ================================================================ اپلیکیشن
from api.models import AppNotification, Device  # noqa: E402

register(Resource(
    key="app-notifications", model=AppNotification, title="اعلان‌های اپ", single="اعلان", group="اپلیکیشن", icon="bell",
    columns=[Col("title", "عنوان", sort="title"), Col("kind", "نوع", badge("kind"), "kind"),
             Col("target", "مقصد", lambda o: o.product.title if o.product else (o.category.name if o.category else (o.url or "—"))),
             Col("is_active", "فعال", yesno("is_active")), Col("created_at", "زمان ارسال", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    search=["title", "body"], filters=["kind", "is_active"], ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("product", "category"),
    fieldsets=[("اعلان", ["title", "body", "kind", "image"], "main"), ("مقصد با زدن روی اعلان", ["product", "category", "url"], "side"),
               ("ارسال", ["is_active", "created_at"], "side")],
    help="اپ هر چند ساعت یک‌بار اعلان‌های تازه را می‌گیرد و روی گوشی نشان می‌دهد. برای ارسال در آینده، «زمان ارسال» را جلوتر بگذارید.",
))
register(Resource(
    key="app-devices", model=Device, title="نصب‌های اپ", single="دستگاه", group="اپلیکیشن", icon="phone",
    columns=[Col("model", "گوشی"), Col("app_version", "نسخه", sort="app_version"),
             Col("user", "مشتری", lambda o: (o.user.get_full_name() or o.user.username) if o.user else "—"),
             Col("first_seen", "نصب", jd("first_seen"), "first_seen"), Col("last_seen", "آخرین استفاده", jd("last_seen", "%Y/%m/%d %H:%M"), "last_seen")],
    search=["model", "app_version"], filters=["app_version"], date_filter="last_seen", ordering=("-last_seen",),
    can_add=False, queryset=lambda qs: qs.select_related("user"), edit_url=lambda o: "/panel/app-devices/",
))


# ================================================================ پیامک گروهی
from accounts.models import SmsCampaign  # noqa: E402


def _sms_count(c):
    from accounts.campaigns import recipients

    n = len(recipients(c)) if c.pk else 0
    t = c.text or ""
    per = 70 if len(t) <= 70 else 67
    parts = max(1, -(-len(t) // per)) if t else 0
    return f"{fa_num(n)} گیرنده · {fa_num(len(t))} حرف ({fa_num(parts)} پیامک برای هر نفر)"


def _sms_start(request, qs):
    from accounts import sms
    from accounts.campaigns import start

    n = 0
    for c in qs.exclude(status=SmsCampaign.Status.DONE):
        if not (sms._cfg("SMSIR_API_KEY") and sms._cfg("SMSIR_LINE_NUMBER")):
            return "اول در «تنظیمات ← پیامک» کلید API و شمارهٔ خط ارسال را وارد کنید."
        SmsCampaign.objects.filter(pk=c.pk).update(status=SmsCampaign.Status.SENDING, last_error="")
        start(c)
        n += 1
    return f"ارسال {fa_num(n)} پیامک گروهی شروع شد؛ پیشرفت را در همین فهرست ببینید (صفحه را تازه کنید)."


def _sms_test(request, qs):
    from accounts import sms
    from accounts.utils import normalize_mobile
    from shop.models import ShopSettings

    admins = [m for m in (normalize_mobile(x) for x in (ShopSettings.load().admin_mobiles or "").replace("،", ",").split(",")) if m]
    if not admins:
        return "در «تنظیمات ← فروش» شمارهٔ موبایل مدیر را وارد کنید."
    c = qs.first()
    ok, msg = sms.send_bulk(admins[:3], c.text)
    return f"پیامک آزمایشی به {fa_num(len(admins[:3]))} شمارهٔ مدیر فرستاده شد." if ok else f"sms.ir نپذیرفت: {msg}"


def _sms_initial():
    from api.models import AppSettings

    url = AppSettings.load().update_url or "https://cafebazaar.ir/app/net.irancarpet.app"
    return {"title": "معرفی اپلیکیشن تازه", "audience": "all",
            "text": f"ایران کارپت | اپلیکیشن تازهٔ ما آمد: فرش را با دوربین گوشی در اتاقتان ببینید و راحت‌تر بخرید.\nدریافت از بازار: {url}\nلغو۱۱"}


register(Resource(
    key="sms", model=SmsCampaign, title="پیامک گروهی", single="پیامک گروهی", group="فروش", icon="send",
    columns=[Col("title", "عنوان", sort="title"), Col("audience", "گیرنده‌ها", badge("audience")),
             Col("status", "وضعیت", badge("status", {"sending": "teal", "done": "green", "failed": "pink"}), "status"),
             Col("progress", "پیشرفت", lambda o: f"{fa_num(o.sent)} از {fa_num(o.total)}" + (f" · ناموفق {fa_num(o.failed)}" if o.failed else "")),
             Col("created_at", "تاریخ", jd("created_at", "%Y/%m/%d %H:%M"), "created_at")],
    search=["title", "text"], filters=["status", "audience"], ordering=("-created_at",),
    fieldsets=[("پیامک", ["title", "text"], "main"), ("گیرنده‌ها", ["audience", "custom_numbers"], "side")],
    readonly=[("برآورد", _sms_count), ("وضعیت", lambda o: o.get_status_display()), ("آخرین خطا", lambda o: o.last_error or "—")],
    initial=_sms_initial,
    actions={"send": ("شروع یا ادامهٔ ارسال", _sms_start),
             "stop": ("توقف ارسال", lambda r, qs: f"{fa_num(qs.filter(status='sending').update(status='failed', last_error='متوقف شد'))} ارسال متوقف شد."),
             "test": ("ارسال آزمایشی به موبایل مدیر", _sms_test)},
    help="پیامک را بسازید و ذخیره کنید؛ اول «ارسال آزمایشی» و بعد «شروع ارسال» را از عملیات گروهی بزنید. "
         "برای پیامک تبلیغاتی، عبارت «لغو۱۱» در انتهای متن لازم است.",
))
import finder.panel  # noqa: E402,F401  فرش‌یاب
import growth.panel  # noqa: E402,F401  رشد فروش
