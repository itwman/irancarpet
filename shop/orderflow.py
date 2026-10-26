"""گردش سفارش در پنل: تغییر وضعیت (تکی و گروهی)، موعدها، عقب‌افتاده‌ها، لغو خودکار و خبر روزانه به مدیر.

موعد هر سفارش:
  پرداخت‌نشده      ← ثبت + «لغو خودکار بعد از» روز (اگر خاموش باشد، ۷ روز فقط برای نمایش)
  بررسی اقساط      ← ثبت + «مهلت بررسی اقساط»
  پرداخت‌شده/آماده‌سازی ← پرداخت + «مهلت آماده‌سازی»
  ارسال‌شده        ← ارسال + «مهلت رسیدن بار»
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

PREP = ("deposit_paid", "paid", "processing")
OPEN = ("pending", "on_hold", *PREP, "shipped")
SOON_DAYS = 2


def _s():
    from .models import ShopSettings

    return ShopSettings.load()


def _pending_days(s):
    return s.pending_cancel_days or 7


def due(order, s=None):
    """موعد اقدام برای این سفارش، یا None برای سفارش بسته‌شده."""
    s = s or _s()
    st = order.status
    if st == "pending":
        return order.created_at + timedelta(days=_pending_days(s))
    if st == "on_hold":
        return order.created_at + timedelta(days=s.review_days)
    if st in PREP:
        return (order.paid_at or order.status_at or order.created_at) + timedelta(days=s.prep_days)
    if st == "shipped":
        return (order.status_at or order.updated_at) + timedelta(days=s.transit_days)
    return None


def state(order, s=None, now=None):
    """late | soon | ok | None"""
    d = due(order, s)
    if d is None:
        return None
    now = now or timezone.now()
    if d < now:
        return "late"
    return "soon" if d - now < timedelta(days=SOON_DAYS) else "ok"


def late_q(kind="late", s=None, now=None):
    """سفارش‌های عقب‌افتاده (یا نزدیک موعد) به‌صورت Q برای فیلتر فهرست."""
    s = s or _s()
    now = now or timezone.now()
    edge = now if kind == "late" else now + timedelta(days=SOON_DAYS)

    def before(days):
        return edge - timedelta(days=days)

    q = (Q(status="pending", created_at__lt=before(_pending_days(s)))
         | Q(status="on_hold", created_at__lt=before(s.review_days))
         | Q(status__in=PREP, paid_at__lt=before(s.prep_days))
         | Q(status__in=PREP, paid_at__isnull=True, status_at__lt=before(s.prep_days))
         | Q(status="shipped", status_at__lt=before(s.transit_days)))
    if kind == "soon":  # فقط آن‌هایی که هنوز عقب نیفتاده‌اند
        q &= ~late_q("late", s, now)
    return q


# ------------------------------------------------------------------ تغییر وضعیت
def change(order, new, tracking=None, request=None, notify=True):
    """تغییر وضعیت با همهٔ پیامدها (پیامک مشتری، ترب‌پی/دیجی‌پی، پورسانت با سیگنال، گزارش پنل). خروجی: پیام‌ها."""
    old = order.status
    fields = []
    if tracking is not None and tracking.strip() and tracking.strip() != order.tracking_code:
        order.tracking_code = tracking.strip()[:100]
        fields.append("tracking_code")
    if old == new and not fields:
        return []
    order.status = new
    order.save()
    msgs = []
    if notify:
        from crm.notify import status_changed

        status_changed(order, old)
    from .bnpl import on_status

    msgs += list(on_status(order, old))
    if request is not None:
        from dashboard.models import log

        log(request, "update", "سفارش‌ها", order, "وضعیت: " + order.get_status_display())
    return msgs


def bulk(qs, new, allowed, request=None, notify=True, tracking=None):
    """(انجام‌شده، ردشده، پیام‌ها) — فقط سفارش‌هایی که وضعیتشان در allowed است."""
    done, skipped, msgs = [], [], []
    for o in qs.order_by("number"):
        if o.status not in allowed:
            skipped.append(o)
            continue
        msgs += change(o, new, (tracking or {}).get(o.pk), request, notify)
        done.append(o)
    return done, skipped, msgs


def cancellable(o):
    """فقط سفارش بی‌پرداخت (پول مشتری پیش ما نیست)."""
    return o.status in ("pending", "on_hold") and not o.paid_amount


# ------------------------------------------------------------------ کارهای دوره‌ای
def auto_cancel(now=None):
    """سفارش‌های بی‌پرداخت قدیمی‌تر از «لغو خودکار بعد از» روز لغو می‌شوند (اقساطی‌ها نه؛ پیامکی به مشتری نمی‌رود)."""
    from .models import Order

    s = _s()
    if not s.pending_cancel_days:
        return 0
    now = now or timezone.now()
    qs = Order.objects.filter(status="pending", paid_amount=0, created_at__lt=now - timedelta(days=s.pending_cancel_days)) \
        .exclude(payment_mode="installment")
    n = 0
    for o in qs[:500]:
        o.admin_note = ((o.admin_note + "\n") if o.admin_note else "") + \
            f"لغو خودکار: {s.pending_cancel_days} روز بدون پرداخت."
        change(o, "cancelled", notify=False)
        n += 1
    return n


def late_summary(s=None):
    from .models import Order

    s = s or _s()
    late = Order.objects.filter(late_q("late", s)).exclude(status="pending")
    return {"total": late.count(), "prep": late.filter(status__in=PREP).count(), "shipped": late.filter(status="shipped").count(),
            "review": late.filter(status="on_hold").count()}


def daily_admin_sms(now=None):
    """یک پیامک در روز (پس از ساعت ۹) به مدیران، فقط اگر سفارش عقب‌افتاده باشد."""
    from django.core.cache import cache

    s = _s()
    now = timezone.localtime(now or timezone.now())
    if not s.late_admin_sms or now.hour < 9:
        return 0
    key = f"late_sms:{now.date().isoformat()}"
    if cache.get(key):
        return 0
    cache.set(key, 1, 60 * 60 * 30)
    r = late_summary(s)
    if not r["total"]:
        return 0
    from core.templatetags.fa import fa_num
    from crm.models import SmsLog
    from crm.notify import admins, send

    parts = [f"{fa_num(r['prep'])} منتظر ارسال" if r["prep"] else "", f"{fa_num(r['shipped'])} ارسال‌شدهٔ تحویل‌نشده" if r["shipped"] else "",
             f"{fa_num(r['review'])} اقساطی بررسی‌نشده" if r["review"] else ""]
    from django.conf import settings

    text = (f"{fa_num(r['total'])} سفارش عقب‌افتاده: " + "، ".join(p for p in parts if p) +
            f"\n{settings.SITE_URL}/panel/orders/?late=late")
    return sum(1 for m in admins() if send(m, text, SmsLog.Kind.ADMIN))
