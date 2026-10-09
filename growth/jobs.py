"""کارهای دوره‌ای (هر ۱۰ دقیقه): یادآوری پرداخت، «خبرم کن»، دعوت به ثبت نظر، به‌روز کردن صفحه‌های فرود.

همهٔ پیامک‌ها با خط پیامک گروهی فرستاده می‌شوند؛ اگر خط تنظیم نشده باشد، کاری انجام نمی‌شود و چیزی هم علامت نمی‌خورد.
"""
import logging

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)
td = timezone.timedelta

QUICKPAY_SALT, REVIEW_SALT = "quickpay", "review-invite"


def sms_ready():
    from accounts.sms import _cfg

    return bool(_cfg("SMSIR_API_KEY") and _cfg("SMSIR_LINE_NUMBER"))


def send(mobile, text, kind="other", order=None):
    from accounts.sms import send_bulk

    ok, msg = send_bulk([mobile], text, kind=kind, order=order)
    if not ok:
        log.warning("sms to %s failed: %s", mobile, msg)
    return ok


def quickpay_url(order):
    return f"{settings.SITE_URL}/o/{signing.dumps(order.number, salt=QUICKPAY_SALT, compress=True)}/"


def review_url(order):
    return f"{settings.SITE_URL}/review/{signing.dumps(order.number, salt=REVIEW_SALT, compress=True)}/"


# ------------------------------------------------------------------ یادآوری پرداخت
def remind_unpaid(now=None):
    """پیگیری سفارش‌های پرداخت‌نشده؛ زمان‌ها و متن‌ها در «باشگاه مشتریان» (crm.jobs) تنظیم می‌شوند."""
    from crm.jobs import remind_unpaid as run

    return run(now)


# ------------------------------------------------------------------ «خبرم کن»
def run_alerts(now=None):
    from .models import ProductAlert

    now = now or timezone.now()
    ProductAlert.objects.filter(sent_at__isnull=True, created_at__lt=now - td(days=120)).delete()
    sent = 0
    for a in ProductAlert.objects.filter(sent_at__isnull=True).select_related("product")[:500]:
        p = a.product
        if p.status != "publish":
            continue
        url = settings.SITE_URL + p.get_absolute_url()
        if a.kind == "stock" and p.is_purchasable:
            text = f"«{p.title}» دوباره در ایران کارپت موجود شد: {url}"
        elif a.kind == "price" and a.price_at and p.min_price and p.min_price <= a.price_at * 0.98:
            text = f"قیمت «{p.title}» در ایران کارپت کم شد: از {p.min_price:,} تومان. {url}"
        else:
            continue
        if send(a.mobile, text, "alert"):
            ProductAlert.objects.filter(pk=a.pk).update(sent_at=now)
            sent += 1
    return sent


# ------------------------------------------------------------------ دعوت به ثبت نظر
def invite_reviews(now=None):
    """۷ روز بعد از ارسال یا تحویل، فقط برای سفارش‌های همین سایت (نه سفارش‌های قدیمی وردپرس)."""
    from shop.models import Order

    from crm.links import shorten
    from crm.models import CrmSettings
    from core.templatetags.fa import toman

    cs = CrmSettings.load()
    gift = (f" با فرستادن عکس، کد هدیهٔ {toman(cs.review_reward_amount)} تومانی می‌گیرید."
            if cs.review_reward_enabled and cs.review_reward_amount else "")
    now = now or timezone.now()
    qs = Order.objects.filter(status__in=["shipped", "completed"], review_invited_at__isnull=True, wp_id__isnull=True,
                              created_at__gte=now - td(days=90), created_at__lte=now - td(days=7))
    sent = 0
    for o in qs[:100]:
        text = (f"{o.first_name} عزیز، امیدواریم از فرش‌تان راضی باشید. نظر و عکس فرش در خانه‌تان به خریداران دیگر کمک می‌کند.{gift}"
                f" ثبت نظر: {shorten(review_url(o), 'r')}")
        if send(o.mobile, text, "invite", o):
            Order.objects.filter(pk=o.pk).update(review_invited_at=now)
            sent += 1
    return sent


# ------------------------------------------------------------------ همه
def run_all(out=print):
    done = {}
    if sms_ready():
        for name, fn in (("خبرم کن", run_alerts), ("دعوت به نظر", invite_reviews)):
            try:
                done[name] = fn()
            except Exception:  # noqa: BLE001
                log.exception(name)
        try:
            from crm.jobs import run as crm_run

            done.update(crm_run())
        except Exception:  # noqa: BLE001
            log.exception("crm jobs")
    else:
        out("خط پیامک تنظیم نشده؛ پیامک‌ها فرستاده نمی‌شوند.")
    try:
        from rajyar.client import refresh

        n = refresh()
        if n:
            done["وضعیت رج‌یار"] = n
        from rajyar.auto import run as rajyar_auto

        sent = rajyar_auto()
        if sent:
            done["پست خودکار کانال‌ها"] = len(sent)
    except Exception:  # noqa: BLE001
        log.exception("rajyar refresh")
    try:
        from market.orders import run_jobs as market_jobs

        n = market_jobs()
        if n:
            done["سفارش فروشندگان"] = n
    except Exception:  # noqa: BLE001
        log.exception("market jobs")
    try:
        from affiliate.commission import resync_all

        n = resync_all()
        if n:
            done["پورسانت همکاران"] = n
    except Exception:  # noqa: BLE001
        log.exception("affiliate resync")
    if cache.add("jobs:landing", 1, 6 * 3600):
        try:
            from landing.build import sync

            done["صفحه‌های فرود"] = sync(log=out)
        except Exception:  # noqa: BLE001
            cache.delete("jobs:landing")
            log.exception("landing sync")
    out(" | ".join(f"{k}: {v}" for k, v in done.items()) or "کاری نبود.")
    return done
