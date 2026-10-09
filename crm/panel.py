"""بخش‌های پنل باشگاه مشتریان: کمپین‌ها، پیامک‌های فرستاده‌شده، کاربران مشکوک به اسپم."""
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from core.templatetags.fa import fa_num, jdate, toman
from dashboard.registry import Col, Resource, register

from . import spam
from .models import AutoCampaign, Campaign, PointRedeem, SmsLog

GROUP = "باشگاه مشتریان"


def _mob(o):
    return format_html('<a href="/panel/crm/customer/{}/">{}</a>', o.mobile, fa_num(o.mobile)) if o.mobile else "—"


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

    from .campaigns import extra_vars

    text = message(c.text, {"name": "مدیر"}, Fake() if c.discount else None, CrmSettings.load().marketing_footer, **extra_vars(c))
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
    fieldsets=[("کمپین", ["title", "segment", "inactive_days", "album", "event_date", "offer", "custom_numbers", "text"], "main"),
               ("کد تخفیف شخصی", ["discount", "min_order", "valid_days"], "side")],
    readonly=[("گیرنده‌ها", _camp_people), ("نتیجه", _camp_result), ("آخرین خطا", lambda o: o.last_error or "—")],
    actions={"start": ("شروع یا ادامهٔ ارسال", _camp_start), "stop": ("توقف ارسال", _camp_stop),
             "test": ("پیامک نمونه به مدیران", _camp_test)},
    help="برای هر گیرنده یک کد تخفیف شخصی ساخته می‌شود که فقط با شمارهٔ موبایل خود او و یک‌بار کار می‌کند؛ پخش شدنش در کانال‌ها بی‌اثر است. "
         "اول با «پیامک نمونه به مدیران» متن را ببینید، بعد «شروع ارسال». متغیرها: {name} {code} {discount} {min} {until} {site} "
         "و برای آلبوم: {album} {date}. برای اطلاع افزایش قیمت، «مبلغ تخفیف» را ۰ بگذارید.",
))

register(Resource(
    key="crm-sms", model=SmsLog, title="پیامک‌های فرستاده‌شده", single="پیامک", group=GROUP, icon="chat",
    columns=[Col("created_at", "زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at"),
             Col("kind", "نوع", lambda o: o.get_kind_display()), Col("mobile", "موبایل", _mob),
             Col("order", "سفارش", lambda o: format_html('<a href="/panel/orders/{}/view/">{}</a>', o.order_id, fa_num(o.order.number)) if o.order_id else "—"),
             Col("ok", "نتیجه", lambda o: format_html('<span class="badge-ic b-{}">{}</span>', "ok" if o.ok else "failed",
                                                      "رسید" if o.ok else (o.error[:40] or "ناموفق"))),
             Col("text", "متن", lambda o: (o.text or "")[:70] + ("…" if len(o.text or "") > 70 else ""))],
    search=["mobile", "text", "=order__number"], filters=["kind", "ok"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("order"), can_add=False, fieldsets=[("پیامک", ["mobile", "kind", "text"], "main")],
    help="همهٔ پیامک‌های فرستاده‌شده (سفارش، یادآوری، کمپین، اقساط، پیامک گروهی و…) با متن و نتیجهٔ sms.ir. کد ورود ثبت نمی‌شود. "
         "با کلیک روی موبایل، پروفایل مشتری باز می‌شود.",
))

register(Resource(
    key="crm-points", model=PointRedeem, title="تبدیل امتیاز به کد", single="تبدیل امتیاز", group=GROUP, icon="tag",
    columns=[Col("created_at", "زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at"),
             Col("mobile", "موبایل", _mob), Col("points", "امتیاز", lambda o: fa_num(o.points), "points"),
             Col("coupon", "کد", lambda o: format_html('<code dir="ltr">{}</code> · {} تومان', o.coupon.code, toman(o.coupon.value)) if o.coupon_id else "—")],
    search=["mobile", "coupon__code"], date_filter="created_at", ordering=("-created_at",),
    queryset=lambda qs: qs.select_related("coupon"), can_add=False, fieldsets=[("تبدیل", ["mobile", "points"], "main")],
    help="مشتری‌ها در «حساب کاربری ← باشگاه مشتریان» امتیازشان را به کد تخفیف شخصی تبدیل می‌کنند. تنظیم امتیاز: «تنظیمات ← پیامک سفارش و باشگاه».",
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


# «آلبوم‌های قیمت ← عملیات گروهی»: پیش‌نویس کمپین «قیمت به‌زودی بالا می‌رود» برای علاقه‌مندان هر آلبوم
def _album_notice(request, qs):
    from .interest import album_audience
    from .models import CrmSettings

    when = (request.POST.get("action_value") or "").strip()[:60]
    if not when:
        return "زمان افزایش را بنویسید؛ مثل «شنبه ۲۶ مهر» یا «از هفتهٔ آینده»."
    s, made = CrmSettings.load(), []
    for album in qs:
        n = len(album_audience(album.pk))
        Campaign.objects.create(title=f"افزایش قیمت {album.title}"[:120], segment=Campaign.Segment.ALBUM, album=album,
                                event_date=when, discount=0, text=s.album_text)
        made.append(f"{album.title} ({fa_num(n)} نفر)")
    return (f"{fa_num(len(made))} کمپین پیش‌نویس ساخته شد: {'، '.join(made[:6])}. در «باشگاه مشتریان ← کمپین‌ها» "
            "متن را ببینید، «پیامک نمونه به مدیران» و بعد «شروع ارسال» را بزنید.")


from dashboard.registry import REGISTRY  # noqa: E402

if "albums" in REGISTRY:
    REGISTRY["albums"].actions["notify_interest"] = (
        "پیامک «قیمت به‌زودی بالا می‌رود» به علاقه‌مندان (پیش‌نویس کمپین)", _album_notice, "زمان افزایش؛ مثلاً «شنبه ۲۶ مهر»")


# ------------------------------------------------------------------ تقویم کمپین‌های خودکار
MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def _cal_next(o):
    import jdatetime

    t = jdatetime.date.today()
    try:
        d = jdatetime.date(t.year, o.month, o.day)
    except ValueError:
        return "تاریخ نامعتبر"
    if (o.month, o.day) < (t.month, t.day) or o.last_run_year == t.year:
        try:
            d = jdatetime.date(t.year + 1, o.month, o.day)
        except ValueError:
            return "—"
    left = (d - t).days
    return f"{fa_num(o.day)} {MONTHS[o.month - 1]} {fa_num(d.year)}" + (" (امروز)" if left == 0 else f" ({fa_num(left)} روز دیگر)")


def _cal_people(o):
    from .campaigns import recipients

    return f"{fa_num(len(recipients(Campaign(segment=o.segment, inactive_days=o.inactive_days))))} نفر" if o.pk else "—"


def _cal_preview(o):
    from .campaigns import message
    from .models import CrmSettings

    if not o.text:
        return "—"

    class Fake:
        code, value, min_order = "C9-AB2CD", o.discount, o.min_order
        ends_at = timezone.now() + timezone.timedelta(days=o.valid_days)

    return message(o.text, {"name": "علی"}, Fake() if o.discount else None, CrmSettings.load().marketing_footer)


from django.utils import timezone  # noqa: E402

register(Resource(
    key="crm-calendar", model=AutoCampaign, title="تقویم کمپین‌های خودکار", single="مناسبت", group=GROUP, icon="calendar",
    columns=[Col("date", "تاریخ", lambda o: f"{fa_num(o.day)} {MONTHS[o.month - 1]}", "month"), Col("title", "مناسبت", sort="title"),
             Col("segment", "گیرنده‌ها", lambda o: o.get_segment_display()),
             Col("discount", "کد تخفیف", lambda o: f"{toman(o.discount)} از {toman(o.min_order)}" if o.discount else "بدون کد"),
             Col("next", "نوبت بعدی", _cal_next), Col("enabled", "فعال", lambda o: "بله" if o.enabled else "خاموش", "enabled")],
    search=["title", "text"], filters=["enabled", "segment"], ordering=("month", "day"),
    fieldsets=[("مناسبت", ["title", "month", "day", "hour", "enabled", "segment", "inactive_days", "text", "note"], "main"),
               ("کد تخفیف شخصی", ["discount", "min_order", "valid_days"], "side")],
    readonly=[("گیرنده‌ها (الان)", _cal_people), ("نمونهٔ پیامک", _cal_preview), ("نوبت بعدی", _cal_next),
              ("آخرین ارسال", lambda o: fa_num(o.last_run_year) if o.last_run_year else "هنوز نه")],
    actions={"on": ("روشن کن", lambda r, qs: f"{fa_num(qs.update(enabled=True))} مناسبت روشن شد."),
             "off": ("خاموش کن", lambda r, qs: f"{fa_num(qs.update(enabled=False))} مناسبت خاموش شد.")},
    help="هر سال در روز و ساعت هر مناسبت، کمپین خودش ساخته و برای گیرنده‌ها فرستاده می‌شود (با کد تخفیف شخصی اگر مبلغ گذاشته باشید). "
         "یک روز قبل، متن و تعداد گیرنده‌ها برای مدیران پیامک می‌شود تا اگر خواستید خاموشش کنید. فصل شلوغ دی و بهمن و توقف سفارش از اول اسفند "
         "در متن‌ها لحاظ شده است. مناسبت‌های قمری (مثل روز مادر) هر سال تاریخ شمسی‌شان عوض می‌شود؛ آن‌ها را هر سال با تاریخ همان سال اضافه کنید.",
))


# ------------------------------------------------------------------ پیام‌های «تماس با ما»
from django.utils.html import linebreaks  # noqa: E402

from .models import ContactMessage  # noqa: E402

CM = ContactMessage.Status
CM_BADGE = {"new": "pending", "answered": "completed", "archived": "draft"}


def _cm_status(o):
    return format_html('<span class="badge-ic b-{}">{}</span>', CM_BADGE.get(o.status, "draft"), o.get_status_display())


def _cm_mark(status, label):
    def act(request, qs):
        n = qs.update(status=status)
        return f"{fa_num(n)} پیام «{label}» شد."
    return act


def _cm_reply_info(o):
    if not o.reply_sent:
        return "هنوز پاسخی فرستاده نشده"
    who = o.replied_by.get_full_name() or o.replied_by.username if o.replied_by_id else ""
    return format_html("{}<br><small class=\"muted\">{} {}</small>", linebreaks(o.reply_sent),
                       jdate(o.replied_at, "%Y/%m/%d %H:%M") if o.replied_at else "", who)


def _cm_after_save(request, obj, created, form=None):
    from .contact import send_reply

    send_reply(request, obj)


register(Resource(
    key="contact-messages", model=ContactMessage, title="پیام‌های تماس با ما", single="پیام", group="فروش", icon="chat",
    columns=[Col("created_at", "زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M"), "created_at"),
             Col("name", "فرستنده", lambda o: format_html("{}<br><small>{}</small>", o.name, _mob(o))),
             Col("topic", "موضوع", lambda o: o.get_topic_display()),
             Col("message", "پیام", lambda o: (o.message or "")[:90] + ("…" if len(o.message or "") > 90 else "")),
             Col("status", "وضعیت", _cm_status, "status")],
    search=["name", "mobile", "message"], filters=["status", "topic"], date_filter="created_at", ordering=("-created_at",),
    can_add=False,
    fieldsets=[("پاسخ با پیامک", ["reply"], "main"), ("وضعیت", ["status", "note"], "side")],
    readonly=[("فرستنده", lambda o: format_html("{} — {}", o.name, _mob(o))), ("موضوع", lambda o: o.get_topic_display()),
              ("زمان", lambda o: jdate(o.created_at, "%Y/%m/%d %H:%M")), ("پاسخ فرستاده‌شده", _cm_reply_info)],
    actions={"answered": ("علامت «پاسخ داده شد»", _cm_mark(CM.ANSWERED, "پاسخ داده شد")),
             "archive": ("بایگانی", _cm_mark(CM.ARCHIVED, "بایگانی")), "new": ("برگرداندن به «تازه»", _cm_mark(CM.NEW, "تازه"))},
    after_save=_cm_after_save, badge=lambda: ContactMessage.objects.filter(status=CM.NEW).count(),
    help="پیام‌های فرم «تماس با ما». پاسخ را در کادر «پاسخ با پیامک» بنویسید و «ذخیره» بزنید تا به موبایل فرستنده پیامک شود "
         "(نام او اول و «ایران کارپت» آخر پیامک می‌آید). هر ۷۰ حرف فارسی یک پیامک است. با تلفن جواب دادید؟ "
         "پاسخ را خالی بگذارید و وضعیت را «پاسخ داده شد» کنید. خبر پیام تازه به موبایل مدیران از «تنظیمات ← پیامک سفارش و باشگاه» روشن و خاموش می‌شود.",
))
