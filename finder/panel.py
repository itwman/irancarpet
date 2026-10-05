"""بخش‌های «فرش‌یاب» در پنل: نیازها و درخواست‌های مشتری."""
from django.db.models import Count
from django.utils.html import format_html, format_html_join

from core.templatetags.fa import fa_num, jdate
from dashboard.registry import Col, Resource, badge, register, yesno

from . import engine, services
from .models import FinderRequest, Need


def _swatch(o):
    if not o.swatch:
        return "—"
    return format_html('<span style="display:inline-block;width:22px;height:22px;border-radius:7px;background:{};'
                       'border:1px solid #0002;vertical-align:middle"></span>', o.swatch)


def _sample(o):
    if not o.pk:
        return "بعد از ذخیره، فرش‌های این نیاز اینجا دیده می‌شوند."
    if not engine.has_rules(o):
        return format_html('<span class="text-danger">هنوز قاعده‌ای ندارد؛ دست‌کم یک دسته، مقدار ویژگی یا کلمهٔ عنوان بدهید.</span>')
    qs = engine._base().filter(engine.need_q(o))
    n = qs.count()
    items = format_html_join("", '<li><a href="/product/{}/" target="_blank" rel="noopener">{}</a></li>',
                             ((p.slug, fa_num(p.title)) for p in qs.order_by("-views")[:8]))
    return format_html("<strong>{} فرش موجود</strong><ul class='mt-2 mb-0'>{}</ul>", fa_num(n), items)


register(Resource(
    key="finder-needs", model=Need, title="نیازهای مشتری", single="نیاز", group="فرش‌یاب", icon="sliders",
    columns=[Col("title", "عنوان", sort="title"), Col("group", "گروه", lambda o: o.get_group_display(), "group"),
             Col("swatch", "رنگ", _swatch),
             Col("count", "فرش موجود", lambda o: fa_num(engine.need_count(o)) if engine.has_rules(o) else "بدون قاعده"),
             Col("is_active", "فعال", yesno("is_active"), "is_active")],
    search=["title", "keywords"], filters=["group", "is_active"], ordering=("group", "order", "pk"),
    fieldsets=[("نیاز", ["title", "subtitle", "group", "keywords"], "main"),
               ("کدام فرش‌ها در این نیاز هستند؟ (دست‌کم یکی از این‌ها)", ["categories", "terms", "term_attribute", "term_keywords",
                                                                        "title_keywords"], "main"),
               ("به‌جز", ["exclude_categories", "exclude_keywords"], "main"),
               ("نمایش", ["swatch", "icon", "is_active", "order"], "side")],
    readonly=[("فرش‌های این نیاز", _sample)],
    help="هر «نیاز» چیزی است که مشتری در اپ فرش‌یاب انتخاب می‌کند یا می‌نویسد. نیازهای یک گروه با «یا» و گروه‌های مختلف با «و» "
         "ترکیب می‌شوند؛ مثلاً «قرمز» یا «سرمه‌ای»، و «سنتی».",
))


def _photo(o, size=72):
    if not o.photo:
        return format_html('<span class="thumb thumb--empty"></span>')
    return format_html('<img class="thumb" src="/panel/finder-photo/{}/" alt="" loading="lazy" style="width:{}px;height:{}px;object-fit:cover">',
                       o.pk, size, size)


def _big_photo(o):
    if not o.photo:
        return "عکسی نفرستاده؛ فقط توضیح."
    return format_html('<a href="/panel/finder-photo/{0}/" target="_blank"><img src="/panel/finder-photo/{0}/" alt="" '
                       'style="max-width:100%;max-height:420px;border-radius:14px"></a>', o.pk)


def _colors(o):
    hexes = [c["hex"] for c in o.colors if "hex" in c]
    names = [c["title"] for c in o.colors if "title" in c]
    if not hexes:
        return "—"
    sw = format_html_join("", '<span title="{0}" style="display:inline-block;width:28px;height:28px;border-radius:8px;background:{0};'
                              'margin-left:4px;border:1px solid #0002"></span>', ((h,) for h in hexes))
    return format_html("{}<div class='mt-1'>{}</div>", sw, "، ".join(names) or "")


def _wanted(o):
    w = o.wanted or {}
    parts = services.need_titles(w.get("needs"))
    if w.get("q"):
        parts.insert(0, f"«{w['q']}»")
    if w.get("size"):
        from pricing.models import Size

        s = Size.objects.filter(pk=w["size"]).first()
        if s:
            parts.append(s.label)
    if w.get("max"):
        parts.append(f"تا {int(w['max']):,} تومان".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
    return "، ".join(parts) or "—"


def _auto(o):
    if not o.auto_products:
        return "—"
    from catalog.models import Product

    by = {p.pk: p for p in Product.objects.filter(pk__in=o.auto_products)}
    return format_html("<ol class='mb-0'>{}</ol>", format_html_join(
        "", '<li><a href="/product/{}/" target="_blank" rel="noopener">{}</a> <small class="muted">(شناسه {})</small></li>',
        ((by[i].slug, fa_num(by[i].title), fa_num(i)) for i in o.auto_products if i in by)))


def _customer(o):
    return format_html("{}<br><small class='muted'>{}</small>", o.name or "—", fa_num(o.mobile))


def _after(request, obj, created, form):
    services.after_reply(obj, request)


register(Resource(
    key="finder-requests", model=FinderRequest, title="درخواست‌های مشتری", single="درخواست", group="فرش‌یاب", icon="search",
    columns=[Col("photo", "عکس", _photo), Col("customer", "مشتری", _customer),
             Col("text", "خواسته", lambda o: (o.text[:70] + ("…" if len(o.text) > 70 else "")) or _wanted(o)),
             Col("status", "وضعیت", badge("status"), "status"),
             Col("created_at", "زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at")],
    search=["name", "mobile", "text"], filters=["status", "kind"], date_filter="created_at",
    ordering=("-created_at",), can_add=False,
    fieldsets=[("پاسخ به مشتری", ["reply", "products"], "main"), ("وضعیت", ["status", "notify_sms"], "side")],
    readonly=[("عکس فرش مشتری", _big_photo), ("مشتری", _customer), ("توضیح مشتری", lambda o: o.text or "—"),
              ("خواسته‌های انتخاب‌شده", _wanted), ("رنگ‌های غالب عکس", _colors),
              ("پیشنهاد خودکار (مشتری همین حالا دیده)", _auto)],
    after_save=_after,
    help="مشتری عکس فرش خودش یا توضیح خواسته‌اش را فرستاده. فرش‌های مشابه را در «فرش‌های پیشنهادی کارشناس» انتخاب کنید و "
         "اگر لازم است چند خط توضیح بنویسید؛ با ذخیره، پاسخ در اپ مشتری نمایش داده می‌شود.",
))
