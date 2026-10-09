"""کارهای دوره‌ای باشگاه مشتریان (از growth.jobs.run_all هر ۱۰ دقیقه): پیگیری سفارش ناتمام و کد بازگشت خودکار."""
import logging

from django.core.cache import cache
from django.utils import timezone

from .notify import context, render, send

log = logging.getLogger(__name__)
td = timezone.timedelta


def remind_unpaid(now=None):
    """سفارش ثبت‌شده‌ای که پرداخت آنلاینش انجام نشده: پیامک در زمان‌های تنظیمات (پیش‌فرض ۱، ۲۴ و ۷۲ ساعت)."""
    from shop.coupons import PLACED
    from shop.models import Order

    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    steps = s.hours()
    if not s.remind_enabled or not steps:
        return 0
    texts = [s.remind_text_1, s.remind_text_2, s.remind_text_3]
    now = now or timezone.now()
    window = td(hours=steps[-1]) + td(days=2)
    from django.db.models import Q

    qs = Order.objects.filter(Q(created_at__gte=now - window) | Q(reminded_at__gte=now - window),
                              status="pending", online_amount__gt=0, wp_id__isnull=True, reminded_count__lt=len(steps))
    sent = 0
    for o in qs:
        step = o.reminded_count
        due = o.created_at + td(hours=steps[step])
        if step and o.reminded_at:  # فاصلهٔ دو یادآوری هیچ‌وقت کمتر از فاصلهٔ برنامه نشود (سفارش قدیمی پشت سر هم پیامک نگیرد)
            due = max(due, o.reminded_at + td(hours=steps[step] - steps[step - 1]))
        if now < due:
            continue
        # بعد از این سفارش، سفارش دیگری را پرداخت کرده؟ پس یادآوری لازم نیست
        if Order.objects.filter(mobile=o.mobile, status__in=PLACED, created_at__gt=o.created_at).exists() or (
                o.user_id and Order.objects.filter(user_id=o.user_id, status__in=PLACED, created_at__gt=o.created_at).exists()):
            Order.objects.filter(pk=o.pk).update(reminded_count=len(steps))
            continue
        tpl = texts[min(step, len(texts) - 1)] or texts[0]
        if send(o.mobile, render(tpl, **context(o)), SmsLog.Kind.REMIND, o):
            Order.objects.filter(pk=o.pk).update(reminded_count=step + 1, reminded_at=now)
            sent += 1
    return sent


def winback(now=None, limit=40):
    """مشتریانی که «winback_days» روز است نخریده‌اند (و در یک سال گذشته کد بازگشت نگرفته‌اند): کد شخصی + پیامک. روزی یک‌بار."""
    from .campaigns import message, personal_coupon
    from .models import CrmSettings, SmsLog
    from .segments import customers

    s = CrmSettings.load()
    if not s.winback_auto or not cache.add("crm:winback:day", 1, 20 * 3600):
        return 0
    now = now or timezone.now()
    got = set(SmsLog.objects.filter(kind=SmsLog.Kind.WINBACK, created_at__gte=now - td(days=365)).values_list("mobile", flat=True))
    sent = 0
    for c in customers().values():
        if sent >= limit:
            break
        if not c["paid_orders"] or not c["last"] or c["mobile"] in got:
            continue
        days = (now - c["last"]).days
        if not (s.winback_days <= days <= s.winback_days + 60):
            continue
        coupon = personal_coupon("WB", c["mobile"], "کد بازگشت مشتری", s.winback_amount, s.winback_min_order, s.winback_valid_days) \
            if s.winback_amount else None
        if send(c["mobile"], message(s.winback_text, c, coupon, s.marketing_footer), SmsLog.Kind.WINBACK):
            sent += 1
    return sent


def birthday(now=None, limit=200):
    """روزی یک‌بار: کد هدیهٔ تولد برای کسانی که تولدشان (شمسی) امروز است؛ هر شماره سالی یک‌بار."""
    import jdatetime

    from accounts.models import Profile
    from accounts.utils import normalize_mobile

    from .campaigns import make_coupon, message
    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    if not s.birthday_enabled or not cache.add("crm:birthday:day", 1, 20 * 3600):
        return 0
    now = now or timezone.now()
    j = jdatetime.date.fromgregorian(date=timezone.localtime(now).date())
    got = set(SmsLog.objects.filter(kind=SmsLog.Kind.BIRTHDAY, ok=True, created_at__gte=now - td(days=300)).values_list("mobile", flat=True))
    sent = 0
    for p in Profile.objects.filter(birth_month=j.month, birth_day=j.day, user__is_active=True).select_related("user")[:limit]:
        m = normalize_mobile(p.mobile or "") or normalize_mobile(p.user.username or "")
        if not m or m in got:
            continue
        coupon = make_coupon("BD", m, "هدیهٔ تولد", s.birthday_amount, s.birthday_min_order, s.birthday_valid_days) if s.birthday_amount else None
        if send(m, message(s.birthday_text, {"name": p.user.first_name}, coupon), SmsLog.Kind.BIRTHDAY):
            sent += 1
    return sent


def abandoned_carts(now=None, limit=100):
    """سبدی که چند ساعت دست نخورده و سفارشی پس از آن ثبت نشده: یک پیامک با پیوند بازگرداندن سبد."""
    from shop.models import Order

    from .carts import restore_url
    from .club import mobile_of
    from .models import CartSnapshot, CrmSettings, SmsLog

    s = CrmSettings.load()
    if not s.cart_enabled:
        return 0
    now = now or timezone.now()
    qs = (CartSnapshot.objects.filter(reminded_at__isnull=True, updated_at__lte=now - td(hours=s.cart_hours),
                                      updated_at__gte=now - td(days=7), user__is_active=True)
          .select_related("user", "user__profile")[:limit])
    sent = 0
    for snap in qs:
        CartSnapshot.objects.filter(pk=snap.pk).update(reminded_at=now)
        user, m = snap.user, mobile_of(snap.user)
        if not m or not snap.data:
            continue
        if Order.objects.filter(user=user, created_at__gte=snap.updated_at - td(hours=1)).exists():
            continue  # بعد از آخرین تغییر سبد سفارش داده
        if SmsLog.objects.filter(mobile=m, kind=SmsLog.Kind.CART, created_at__gte=now - td(days=3)).exists():
            continue
        text = render(s.cart_text, name=user.first_name or "مشتری", cart_link=restore_url(user))
        if send(m, text, SmsLog.Kind.CART):
            sent += 1
    return sent


def review_rewards(now=None, limit=50):
    """نظرِ تأییدشدهٔ خریدار که عکس دارد ← کد هدیه (هر شماره هر ۶۰ روز یک‌بار)."""
    from django.db.models import Count

    from accounts.utils import normalize_mobile
    from catalog.models import Review

    from .campaigns import make_coupon, message
    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    if not s.review_reward_enabled or not s.review_reward_amount:
        return 0
    now = now or timezone.now()
    qs = (Review.objects.filter(is_approved=True, verified=True, parent__isnull=True, created_at__gte=now - td(days=45))
          .exclude(mobile="").annotate(_ph=Count("photos")).filter(_ph__gt=0).order_by("created_at")[:limit])
    sent = 0
    for r in qs:
        m = normalize_mobile(r.mobile)
        if not m or SmsLog.objects.filter(mobile=m, kind=SmsLog.Kind.REVIEW, created_at__gte=now - td(days=60)).exists():
            continue
        coupon = make_coupon("RV", m, "جایزهٔ نظر با عکس", s.review_reward_amount, s.review_reward_min_order, s.review_reward_valid_days)
        name = (r.author_name or "").split(" ")[0]
        if send(m, message(s.review_reward_text, {"name": name}, coupon), SmsLog.Kind.REVIEW):
            sent += 1
        else:
            coupon.is_active = False
            coupon.save(update_fields=["is_active"])
    return sent


def _jtoday(now):
    import jdatetime

    return jdatetime.date.fromgregorian(date=timezone.localtime(now).date())


def auto_campaigns(now=None):
    """تقویم کمپین‌ها: روز مناسبت سر ساعت، کمپین ساخته و ارسالش شروع می‌شود؛ یک روز پیش از آن، پیش‌نمایش برای مدیران."""
    from .campaigns import message, recipients
    from .models import AutoCampaign, Campaign, CrmSettings, SmsLog
    from .notify import admins

    now = now or timezone.now()
    s = CrmSettings.load()
    today = _jtoday(now)
    tomorrow = today + __import__("jdatetime").timedelta(days=1)
    hour = timezone.localtime(now).hour
    started = 0
    for a in AutoCampaign.objects.filter(enabled=True):
        if (a.month, a.day) == (tomorrow.month, tomorrow.day) and a.preview_year != tomorrow.year and s.calendar_preview and hour >= 12:
            probe = Campaign(title=a.title, segment=a.segment, inactive_days=a.inactive_days, discount=a.discount)
            n = len(recipients(probe))
            sample = message(a.text, {"name": "مشتری"}, None, s.marketing_footer)
            text = f"پیش‌نمایش کمپین فردا ساعت {a.hour}: «{a.title}» برای {n} نفر" + (f"، با کد {a.discount:,} تومانی" if a.discount else "") + \
                f".\n{sample[:300]}\nبرای لغو: پنل ← باشگاه مشتریان ← تقویم کمپین‌ها"
            for m in admins():
                send(m, text, SmsLog.Kind.ADMIN)
            AutoCampaign.objects.filter(pk=a.pk).update(preview_year=tomorrow.year)
        if (a.month, a.day) == (today.month, today.day) and a.last_run_year != today.year and hour >= a.hour:
            Campaign.objects.create(title=f"{a.title} {today.year}"[:120], segment=a.segment, inactive_days=a.inactive_days,
                                    discount=a.discount, min_order=a.min_order, valid_days=a.valid_days, text=a.text,
                                    status=Campaign.Status.SENDING, started_at=now)
            AutoCampaign.objects.filter(pk=a.pk).update(last_run_year=today.year)
            started += 1
    return started


def weekly_offer(now=None):
    """هر هفته یک فرصت ویژه (بیشترین تخفیف، در ۶۰ روز گذشته فرستاده‌نشده) برای مشتریان."""
    from shop.offers import live_offers

    from .models import Campaign, CrmSettings

    s = CrmSettings.load()
    now = now or timezone.now()
    local = timezone.localtime(now)
    if not s.offer_sms_enabled or local.weekday() != s.offer_sms_weekday or local.hour < s.offer_sms_hour:
        return 0
    if Campaign.objects.filter(offer__isnull=False, created_at__gte=now - td(days=6)).exists():
        return 0
    recent = set(Campaign.objects.filter(offer__isnull=False, created_at__gte=now - td(days=60)).values_list("offer_id", flat=True))
    pool = [o for o in live_offers() if o.pk not in recent and o.off_percent >= s.offer_sms_min_percent]
    if not pool:
        return 0
    o = sorted(pool, key=lambda x: (-x.off_percent, x.price))[0]
    Campaign.objects.create(title=f"فرصت ویژهٔ هفته: {o.product.title}"[:120], segment=s.offer_sms_segment, discount=0,
                            text=s.offer_sms_text, offer=o, status=Campaign.Status.SENDING, started_at=now)
    return 1


def run():
    from .campaigns import resume_sending

    done = {}
    for name, fn in (("یادآوری پرداخت", remind_unpaid), ("کد بازگشت مشتری", winback), ("هدیهٔ تولد", birthday),
                     ("سبد رهاشده", abandoned_carts), ("جایزهٔ نظر", review_rewards), ("تقویم کمپین‌ها", auto_campaigns),
                     ("فرصت ویژهٔ هفته", weekly_offer), ("ادامهٔ ارسال کمپین‌ها", resume_sending)):
        try:
            n = fn()
            if n:
                done[name] = n
        except Exception:  # noqa: BLE001
            log.exception(name)
    return done
