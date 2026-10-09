"""بخش‌های پنل باشگاه مشتریان: کمپین‌ها، پیامک‌های فرستاده‌شده، کاربران مشکوک به اسپم."""
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from core.templatetags.fa import fa_num, jdate, toman
from dashboard.registry import Col, Resource, register

from . import spam
from .models import Campaign, SmsLog

GROUP = "باشگاه مشتریان"


def _ready():
    from accounts import sms

    return bool(sms._cfg("SMSIR_API_KEY") and sms._cfg("SMSIR_LINE_NUMBER"))


def _camp_start(request, qs):
    from .campaigns import start

    if not _ready():
        return "اول در «تنظیمات ← پیامک» کلید API و شمارهٔ خط اختصاصی را وارد کنید."
    n = 0
    for c in qs.exclude(status=Campaign.Status.DONE):
        Campaign.objects.filter(pk=c.pk).update(status=Campaign.Status.SENDING, last_error="")
        start(c)
        n += 1
    return f"ارسال {fa_num(n)} کمپین شروع شد؛ پیشرفت را در همین فهرست ببینید (صفحه را تازه کنید)."


def _camp_stop(request, qs):
    n = qs.filter(status=Campaign.Status.SENDING).update(status=Campaign.Status.STOPPED)
    return f"{fa_num(n)} کمپین متوقف شد؛ با «شروع ارسال» از همان‌جا ادامه می‌دهد."


def _camp_test(request, qs):
    from .campaigns import message
    from .models import CrmSettings
    from .notify import admins, send

    to = admins()[:3]
    if not to:
        return "در «تنظیمات ← فروش و ارسال» موبایل مدیران را وارد کنید."
    c = qs.first()

    class Fake:
        code, value, min_order = f"{c.code_prefix}-TEST1", c.discount, c.min_order
        from django.utils import timezone as _tz
        ends_at = _tz.now() + _tz.timedelta(days=c.valid_days)

    text = message(c.text, {"name": "مدیر"}, Fake() if c.discount else None, CrmSettings.load().marketing_footer)
    ok = all(send(m, text, SmsLog.Kind.CAMPAIGN) for m in to)
    return f"پیامک نمونه به {fa_num(len(to))} مدیر فرستاده شد." if ok else "sms.ir نپذیرفت؛ «پیامک‌های فرستاده‌شده» را ببینید."


def _camp_people(o):
    from .campaigns import recipients

    if not o.pk:
        return "—"
    n = len(recipients(o))
    t = o.text or ""
    parts = max(1, -(-len(t) // (70 if len(t) <= 70 else 67)))
    return f"{fa_num(n)} گیرنده · حدود {fa_num(parts)} پیامک برای هر نفر"


def _camp_result(o):
    from .campaigns import results

    if not o.discount:
        return "—"
    n, s = results(o)
    return format_html("{} خرید · {} تومان", fa_num(n), toman(s)) if n else "هنوز خریدی نشده"


register(Resource(
    key="crm-campaigns", model=Campaign, title="کمپین‌های پیامکی و کد تخفیف", single="کمپین", group=GROUP, icon="send",
    columns=[Col("title", "عنوان", sort="title"), Col("segment", "گیرنده‌ها", lambda o: o.get_segment_display()),
             Col("discount", "تخفیف", lambda o: f"{toman(o.discount)} از {toman(o.min_order)}" if o.discount else "بدون کد"),
             Col("status", "وضعیت", lambda o: format_html('<span class="badge-ic b-{}">{}</span>',
                                                          {"sending": "processing", "done": "completed", "stopped": "on_hold"}.get(o.status, o.status),
                                                          o.get_status_display())),
             Col("progress", "ارسال", lambda o: f"{fa_num(o.sent)} از {fa_num(o.total)}" + (f" · {fa_num(o.failed)} ناموفق" if o.failed else "")),
             Col("result", "نتیجه", _camp_result),
             Col("created_at", "ساخته شده", lambda o: jdate(o.created_at, "%Y/%m/%d"), "created_at")],
    search=["title"], filters=["status", "segment"], ordering=("-created_at",),
    fieldsets=[("کمپین", ["title", "segment", "inactive_days", "custom_numbers", "text"], "main"),
               ("کد تخفیف شخصی", ["discount", "min_order", "valid_days"], "side")],
    readonly=[("گیرنده‌ها", _camp_people), ("نتیجه", _camp_result), ("آخرین خطا", lambda o: o.last_error or "—")],
    actions={"start": ("شروع یا ادامهٔ ارسال", _camp_start), "stop": ("توقف ارسال", _camp_stop),
             "test": ("پیامک نمونه به مدیران", _camp_test)},
    help="برای هر گیرنده یک کد تخفیف شخصی ساخته می‌شود که فقط با شمارهٔ موبایل خود او و یک‌بار کار می‌کند؛ پخش شدنش در کانال‌ها بی‌اثر است. "
         "اول با «پیامک نمونه به مدیران» متن را ببینید، بعد «شروع ارسال». متغیرها: {name} {code} {discount} {min} {until} {site}.",
))

register(Resource(
    key="crm-sms", model=SmsLog, title="پیامک‌های فرستاده‌شده", single="پیامک", group=GROUP, icon="chat",
    columns=[Col("created_at", "زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at"),
             Col("kind", "نوع", lambda o: o.get_kind_display()), Col("mobile", "موبایل", lambda o: fa_num(o.mobile)),
             Col("order", "سفارش", lambda o: format_html('<a href="/panel/orders/{}/view/">{}</a>', o.order_id, fa_num(o.order.number)) if o.order_id else "—"),
             Col("ok", "نتیجه", lambda o: format_html('<span class="badge-ic b-{}">{}</span>', "ok" if o.ok else "failed",
                                                      "رسید" if o.ok else (o.error[:40] or "ناموفق"))),
             Col("text", "متن", lambda o: (o.text or "")[:70] + ("…" if len(o.text or "") > 70 else ""))],
    search=["mobile", "text", "=order__number"], filters=["kind", "ok"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("order"), can_add=False, fieldsets=[("پیامک", ["mobile", "kind", "text"], "main")],
    help="همهٔ پیامک‌های سفارش، یادآوری و کمپین که از خط اختصاصی فرستاده شده، با نتیجهٔ sms.ir.",
))

User = get_user_model()


def _spam_delete(request, qs):
    n = spam.delete_safe(qs)
    return f"{fa_num(n)} کاربر حذف شد."


def _spam_disable(request, qs):
    ids = list(spam.candidates(qs).values_list("pk", flat=True))
    n = User.objects.filter(pk__in=ids).update(is_active=False)
    return f"{fa_num(n)} کاربر غیرفعال شد (دیگر نمی‌توانند وارد شوند)."


def _spam_reasons(o):
    rs = spam.reasons(o)
    s = sum(p for p, _ in rs)
    lvl = "failed" if s >= 9 else "pending" if s >= 7 else "draft"
    return format_html('<span class="badge-ic b-{}">{}</span> <small class="muted">{}</small>', lvl, fa_num(s), "، ".join(r for _, r in rs))


def _spam_level(qs, v):
    ids = [u.pk for u in qs if spam.level(u) == v]
    return qs.filter(pk__in=ids)


register(Resource(
    key="spam-users", model=User, title="کاربران مشکوک به اسپم", single="کاربر", group=GROUP, icon="alert",
    columns=[Col("username", "نام کاربری", lambda o: o.username[:40]), Col("email", "ایمیل", lambda o: o.email),
             Col("score", "امتیاز و دلیل", _spam_reasons),
             Col("date_joined", "عضویت", lambda o: jdate(o.date_joined, "%Y/%m/%d"), "date_joined")],
    search=["username", "email"], filters=["is_active"], date_filter="date_joined", ordering=("-date_joined",),
    queryset=lambda qs: spam.candidates(qs).select_related("profile"), can_add=False, per_page=100,
    custom_filters={"level": ("احتمال", [("high", "زیاد (۹+)"), ("medium", "متوسط (۷ و ۸)"), ("low", "کم")], _spam_level)},
    edit_url=lambda o: f"/panel/customers/{o.pk}/edit/",
    actions={"delete_spam": ("حذف کاربرهای انتخاب‌شده", _spam_delete), "disable_spam": ("غیرفعال کردن", _spam_disable)},
    help="فقط کاربرانی اینجا هستند که هیچ سفارشی ندارند، موبایل معتبر ایران ندارند، کارمند، همکار فروش یا فروشنده نیستند "
         "(بیشترشان ثبت‌نام‌های ایمیلی دورهٔ وردپرس‌اند). حذف هم دوباره همین شرط‌ها را بررسی می‌کند. "
         "ثبت‌نام فعلی سایت فقط با موبایل و کد پیامکی است، پس اسپم تازه ساخته نمی‌شود.",
))

# منوی باشگاه مشتریان درست بعد از «فروش»
from dashboard.registry import GROUPS  # noqa: E402

if GROUP in GROUPS and "فروش" in GROUPS:
    GROUPS.remove(GROUP)
    GROUPS.insert(GROUPS.index("فروش") + 1, GROUP)
