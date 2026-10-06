"""رج‌یار در پنل: عملیات گروهی «ارسال به کانال‌ها» روی محصولات و فهرست ارسال‌ها."""
import jdatetime
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.templatetags.fa import fa_num, jdate
from dashboard.registry import REGISTRY, Col, Resource, badge, register

from .models import RajyarPost, RajyarSettings

MAX_BULK = 50


def _start_choices():
    now = timezone.localtime()
    out = [("now", "همین حالا")]
    for h, m in ((10, 0), (13, 0), (18, 0), (20, 30)):
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        for day, label in ((0, "امروز"), (1, "فردا")):
            tt = t + timezone.timedelta(days=day)
            if tt > now + timezone.timedelta(minutes=10):
                out.append((tt.isoformat(), f"{label} ساعت {fa_num(f'{h}:{m:02d}')}"))
    return out


def send_bulk(request, qs):
    from .client import RajyarError, send

    s = RajyarSettings.load()
    if not (s.enabled and s.api_key):
        return "اتصال رج‌یار در «تنظیمات ← رج‌یار» فعال نیست."
    if not s.channel_ids:
        return "اول در «تنظیمات ← رج‌یار» کانال‌ها را انتخاب کنید."
    val = request.POST.get("action_value") or "now"
    start = None if val == "now" else timezone.datetime.fromisoformat(val)
    items = list(qs.filter(status="publish").select_related("image", "primary_category").prefetch_related("specs__attribute")[:MAX_BULK])
    gap = timezone.timedelta(minutes=max(s.interval_minutes, 1))
    ok = bad = 0
    err = ""
    for i, p in enumerate(items):
        at = (start or timezone.now()) + gap * i if (start or i) else None
        try:
            post = send(p, publish_at=at, force_new=True, s=s)
        except RajyarError as e:
            return f"ارسال انجام نشد: {e}"
        if post.status == RajyarPost.Status.FAILED:
            bad, err = bad + 1, post.error
        else:
            ok += 1
    msg = f"{fa_num(ok)} فرش به رج‌یار رفت"
    if len(items) > 1:
        msg += f" (هر {fa_num(s.interval_minutes)} دقیقه یکی)"
    if bad:
        msg += f"؛ {fa_num(bad)} مورد خطا داشت: {err}"
    if qs.count() > MAX_BULK:
        msg += f"؛ هر بار حداکثر {fa_num(MAX_BULK)} فرش."
    return msg + "."


# عملیات گروهی روی فهرست محصولات
REGISTRY["products"].actions["rajyar"] = ("ارسال به کانال‌ها (رج‌یار)", send_bulk, "زمان انتشار اولین پست", _start_choices)


def _links(o):
    if not o.links:
        return "—"
    return format_html_join(" ", '<a href="{}" target="_blank" rel="noopener">پیام {}</a>',
                            ((u, fa_num(i + 1)) for i, u in enumerate(o.links)))


register(Resource(
    key="rajyar-posts", model=RajyarPost, title="ارسال به کانال‌ها", single="ارسال", group="فروشگاه", icon="send",
    columns=[Col("product", "پست", lambda o: format_html('<a href="/panel/products/{}/edit/">{}</a>', o.product_id, fa_num(o.product.title))
                 if o.product_id else (format_html('<a href="{}" target="_blank" rel="noopener">تصویر لیست قیمت</a>', o.image) if o.image
                                       else o.get_kind_display())),
             Col("kind", "نوع", lambda o: o.get_kind_display(), "kind"),
             Col("status", "وضعیت", badge("status"), "status"),
             Col("publish_at", "زمان انتشار", lambda o: jdate(o.publish_at, "%Y/%m/%d %H:%M") if o.publish_at else "فوری", "publish_at"),
             Col("links", "پیام‌ها", _links),
             Col("error", "خطا", lambda o: o.error or ""),
             Col("created_at", "ارسال", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at")],
    search=["product__title"], filters=["status", "kind"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("product"), can_add=False,
    fieldsets=[("ارسال", ["status"], "side")],
    help="برای فرستادن فرش‌ها به کانال‌ها: «محصولات» ← انتخاب فرش‌ها ← عملیات گروهی «ارسال به کانال‌ها (رج‌یار)». "
         "چینش پست (ایموجی، امضا، هشتگ) از تنظیمات هر کانال در رج‌یار می‌آید.",
))
