"""پنل: قالب‌های متن، بخش‌های مشترک، عملیات گروهی متن روی محصولات."""
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.templatetags.fa import fa_num, jdate
from dashboard.registry import REGISTRY, Col, Resource, register, yesno

from .models import ContentTemplate, InfoBlock

VARS = [
    ("{عنوان}", "عنوان فرش"), ("{نقشه}", "نام نقشه (از فیلد «نام نقشه» یا عنوان)"), ("{رنگ}", "رنگ زمینه"),
    ("{شانه} {تراکم}", "از مشخصات"), ("{گره}", "شانه × تراکم (گره در متر مربع)"), ("{جنس_نخ}", "جنس نخ خاب"),
    ("{دستگاه} {درجه}", "از مشخصات"), ("{برند}", "برند فرش، یا ویژگی «برند»، یا کارخانهٔ آلبوم"),
    ("{تعداد_رنگ}", "فیلد «تعداد رنگ» فرش"), ("{برجسته}", "«برجسته» اگر در عنوان باشد"),
    ("{یادداشت}", "یادداشت اختصاصی هر فرش"), ("{ماه}", "ماه و سال امروز، مثل «مهر ۱۴۰۵»"),
    ("{قیمت_سایزها}", "فهرست قیمت روز سایزها (در یک خط تنها)"), ("{قیمت_پایه} {سایز_پایه}", "قیمت سایز پایهٔ آلبوم"),
    ("{ارسال_رایگان}", "جملهٔ ارسال رایگان با سقف از «تنظیمات ← فروش و ارسال»"), ("{حد_ارسال_رایگان}", "مثل «۵۰ میلیون تومان»"),
    ("{بیعانه}", "درصد بیعانه از تنظیمات"), ("{اقساط}", "روش‌های فعال اقساط (در یک خط تنها)"),
    ("{هزینه_ارسال} {زمان_آماده_سازی} {جریمه_لغو} {ضمانت} {جفتی}", "از «تنظیمات ← متن محصولات»"),
    ("{لینک:دسته}", "پیوند به دستهٔ اصلی"), ("{لینک:لیست_قیمت}", "پیوند به لیست قیمت آلبوم"),
    ("{لینک:۱۲متری}", "پیوند به صفحهٔ «فرش … شانه ۱۲ متری»"), ("{لینک:اقساطی}", "پیوند به برگهٔ خرید اقساطی"),
    ("{لینک:برند} {لینک:رنگ}", "پیوند به برند یا رنگ"), ("{لینک:دسته|متن دلخواه}", "پیوند با متن دلخواه"),
    ("[[ … ]]", "بخش اختیاری: فقط اگر همهٔ متغیرهای داخلش مقدار داشته باشند"),
    ("## تیتر / - مورد / **پررنگ**", "قالب‌بندی؛ خط خالی = پاراگراف تازه"),
]


def vars_help(o=None):
    rows = format_html_join("", '<li><code dir="rtl">{}</code> {}</li>', VARS)
    return format_html('<ul class="vars-help">{}</ul><p class="hint">هر نشانی در کل صفحه فقط یک بار پیوند می‌شود. '
                       'اگر متغیر لازمی خالی باشد، آن خط نمایش داده نمی‌شود.</p>', rows)


def _preview_link(o):
    if not o.pk:
        return "پس از ذخیره"
    return format_html('<a href="/panel/content-templates/{}/preview/" target="_blank" rel="noopener">پیش‌نمایش روی یک فرش</a>', o.pk)


def _usage(o):
    from catalog.models import Product

    from .render import template_for

    if not o.pk:
        return "—"
    n = 0
    qs = Product.objects.filter(use_template=True).select_related("album", "primary_category")
    for p in qs.iterator(chunk_size=500):
        t = template_for(p)
        if t and t.pk == o.pk:
            n += 1
    return f"{fa_num(n)} فرش"


register(Resource(
    key="content-templates", model=ContentTemplate, title="قالب‌های متن محصول", single="قالب متن", group="فروشگاه", icon="pen",
    columns=[Col("name", "نام", sort="name"),
             Col("for", "برای", lambda o: "، ".join([a.name for a in o.albums.all()] + [c.name for c in o.categories.all()])
                 or ("پیش‌فرض همهٔ فرش‌ها" if o.is_default else "—")),
             Col("is_default", "پیش‌فرض", yesno("is_default")), Col("is_active", "فعال", yesno("is_active"), "is_active"),
             Col("updated_at", "آخرین تغییر", lambda o: jdate(o.updated_at, "%Y/%m/%d %H:%M"), "updated_at")],
    search=["name", "body"], filters=["is_active", "is_default", "albums"], ordering=("-is_default", "name"),
    queryset=lambda qs: qs.prefetch_related("albums", "categories"),
    fieldsets=[("قالب", ["name", "bullets", "body", "title_pattern"], "main"),
               ("کجا به‌کار رود", ["albums", "categories", "is_default", "is_active"], "side")],
    readonly=[("پیش‌نمایش", _preview_link), ("استفاده", _usage), ("راهنمای متغیرها", vars_help)],
    help="متن هر فرش موقع نمایش از روی قالب ساخته می‌شود؛ با تغییر قالب، قیمت‌ها یا تنظیمات، متن همهٔ فرش‌ها یک‌جا به‌روز می‌شود. "
         "ترتیب انتخاب قالب: قالب آلبوم فرش ← قالب دستهٔ فرش ← قالب پیش‌فرض. فقط فرش‌هایی که «متن از قالب» دارند از قالب استفاده می‌کنند.",
))

register(Resource(
    key="info-blocks", model=InfoBlock, title="بخش‌های مشترک صفحهٔ فرش", single="بخش مشترک", group="فروشگاه", icon="layers",
    columns=[Col("title", "عنوان", sort="title"), Col("order", "ترتیب", lambda o: fa_num(o.order), "order"),
             Col("albums", "فقط برای", lambda o: "، ".join(a.name for a in o.albums.all()) or "همهٔ فرش‌ها"),
             Col("is_open", "باز", yesno("is_open")), Col("is_active", "فعال", yesno("is_active"), "is_active")],
    search=["title", "body"], filters=["is_active"], ordering=("order", "pk"),
    queryset=lambda qs: qs.prefetch_related("albums"),
    fieldsets=[("بخش", ["title", "body"], "main"), ("نمایش", ["order", "is_open", "is_active", "albums"], "side")],
    readonly=[("راهنمای متغیرها", vars_help)],
    help="این بخش‌ها (ارسال و تحویل، پرداخت و بیعانه، اقساط، ضمانت، شانه و تراکم) زیر توضیحات همهٔ فرش‌ها به‌صورت بازشونده می‌آیند — "
         "چه متن فرش از قالب باشد چه دستی. عددها (سقف ارسال رایگان، درصد بیعانه، روش‌های اقساط) از تنظیمات خوانده می‌شوند.",
))


# ------------------------------------------------------------------ عملیات گروهی روی محصولات
def _to_template(request, qs):
    from .render import design_from_title

    n = 0
    for p in qs.only("pk", "title", "design_name"):
        fields = {"use_template": True, "modified_at": timezone.now()}
        if not p.design_name:
            fields["design_name"] = design_from_title(p.title)[:120]
        type(p).objects.filter(pk=p.pk).update(**fields)
        n += 1
    _clear()
    return (f"متن {fa_num(n)} فرش از این به بعد از قالب ساخته می‌شود. متن قبلی پاک نشده و با «برگرداندن متن دستی» برمی‌گردد.")


def _to_manual(request, qs):
    n = qs.update(use_template=False, modified_at=timezone.now())
    _clear()
    return f"{fa_num(n)} فرش دوباره متن دستی خودش را نشان می‌دهد."


def _clear():
    try:
        from dashboard.auth import clear_site_cache

        clear_site_cache()
    except Exception:  # noqa: BLE001
        pass


REGISTRY["products"].actions["use_template"] = ("متن از قالب (جایگزین متن قدیمی)", _to_template)
REGISTRY["products"].actions["use_manual"] = ("برگرداندن متن دستی", _to_manual)
REGISTRY["products"].filters.append("use_template")
