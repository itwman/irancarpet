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


def send(mobile, text):
    from accounts.sms import send_bulk

    ok, msg = send_bulk([mobile], text)
    if not ok:
        log.warning("sms to %s failed: %s", mobile, msg)
    return ok


def quickpay_url(order):
    return f"{settings.SITE_URL}/o/{signing.dumps(order.number, salt=QUICKPAY_SALT, compress=True)}/"


def review_url(order):
    return f"{settings.SITE_URL}/review/{signing.dumps(order.number, salt=REVIEW_SALT, compress=True)}/"


# ------------------------------------------------------------------ یادآوری پرداخت
def remind_unpaid(now=None):
    """سفارش ثبت‌شده‌ای که پرداخت نشده: یک ساعت بعد و یک روز بعد پیامک با پیوند پرداخت."""
    from shop.coupons import PLACED
    from shop.models import Order

    now = now or timezone.now()
    qs = Order.objects.filter(status="pending", online_amount__gt=0, wp_id__isnull=True,
                              created_at__gte=now - td(days=3), reminded_count__lt=2)
    sent = 0
    for o in qs:
        due = o.created_at + (td(hours=1) if o.reminded_count == 0 else td(hours=24))
        if now < due:
            continue
        # بعد از این سفارش، سفارش دیگری را پرداخت کرده؟ پس یادآوری لازم نیست
        if o.user_id and Order.objects.filter(user_id=o.user_id, status__in=PLACED, created_at__gt=o.created_at).exists():
            Order.objects.filter(pk=o.pk).update(reminded_count=2)
            continue
        first = o.reminded_count == 0
        text = (f"{o.first_name} عزیز، سفارش {o.number} شما در ایران کارپت منتظر پرداخت است. "
                + ("فرش‌های انتخابی‌تان را برایتان نگه داشته‌ایم. " if first else "تا فردا فرصت دارید. ")
                + f"پرداخت: {quickpay_url(o)}")
        if send(o.mobile, text):
            Order.objects.filter(pk=o.pk).update(reminded_count=o.reminded_count + 1, reminded_at=now)
            sent += 1
    return sent


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
        if send(a.mobile, text):
            ProductAlert.objects.filter(pk=a.pk).update(sent_at=now)
            sent += 1
    return sent


# ------------------------------------------------------------------ دعوت به ثبت نظر
def invite_reviews(now=None):
    """۷ روز بعد از ارسال یا تحویل، فقط برای سفارش‌های همین سایت (نه سفارش‌های قدیمی وردپرس)."""
    from shop.models import Order

    now = now or timezone.now()
    qs = Order.objects.filter(status__in=["shipped", "completed"], review_invited_at__isnull=True, wp_id__isnull=True,
                              created_at__gte=now - td(days=90), created_at__lte=now - td(days=7))
    sent = 0
    for o in qs[:100]:
        text = (f"{o.first_name} عزیز، امیدواریم از فرش‌تان راضی باشید. نظر و عکس فرش در خانه‌تان به خریداران دیگر کمک می‌کند: "
                f"{review_url(o)}")
        if send(o.mobile, text):
            Order.objects.filter(pk=o.pk).update(review_invited_at=now)
            sent += 1
    return sent


# ------------------------------------------------------------------ همه
def run_all(out=print):
    done = {}
    if sms_ready():
        for name, fn in (("یادآوری پرداخت", remind_unpaid), ("خبرم کن", run_alerts), ("دعوت به نظر", invite_reviews)):
            try:
                done[name] = fn()
            except Exception:  # noqa: BLE001
                log.exception(name)
    else:
        out("خط پیامک تنظیم نشده؛ پیامک‌ها فرستاده نمی‌شوند.")
    if cache.add("jobs:landing", 1, 6 * 3600):
        try:
            from landing.build import sync

            done["صفحه‌های فرود"] = sync(log=out)
        except Exception:  # noqa: BLE001
            cache.delete("jobs:landing")
            log.exception("landing sync")
    out(" | ".join(f"{k}: {v}" for k, v in done.items()) or "کاری نبود.")
    return done
