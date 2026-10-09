"""پیامک‌های سفارش از خط اختصاصی (sms.ir، ارسال متنی) با ثبت در «پیامک‌های فرستاده‌شده».

ارسال در پس‌زمینه و بعد از ثبت قطعی در پایگاه داده انجام می‌شود تا ثبت سفارش یا ذخیرهٔ پنل معطل sms.ir نماند.
"""
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, transaction

from core.templatetags.fa import toman

log = logging.getLogger(__name__)


class _Safe(dict):
    def __missing__(self, key):
        return ""


def render(template, **ctx):
    try:
        return (template or "").format_map(_Safe(ctx)).strip()
    except (ValueError, IndexError):  # آکولاد نادرست در متن دستی
        return template or ""


def send(mobile, text, kind, order=None, campaign=None):
    """ارسال یک پیامک و ثبت نتیجه. خروجی: True اگر sms.ir پذیرفت."""
    from accounts.sms import send_bulk
    from accounts.utils import normalize_mobile

    from .models import SmsLog

    mobile = normalize_mobile(mobile)
    if not mobile or not text:
        return False
    ok, msg = send_bulk([mobile], text)
    SmsLog.objects.create(mobile=mobile, kind=kind, order=order, campaign=campaign, text=text[:2000], ok=ok, error=(msg or "")[:300])
    if not ok:
        log.warning("sms %s to %s failed: %s", kind, mobile, msg)
    return ok


def later(fn, *args):
    """بعد از commit، در یک رشتهٔ جدا."""
    def run():
        close_old_connections()
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            log.exception("crm notify %s", getattr(fn, "__name__", fn))
        finally:
            close_old_connections()

    transaction.on_commit(lambda: threading.Thread(target=run, daemon=True).start())


def admins():
    from accounts.utils import normalize_mobile
    from shop.models import ShopSettings

    raw = (ShopSettings.load().admin_mobiles or "").replace("،", ",").split(",")
    return [m for m in (normalize_mobile(x) for x in raw) if m]


def context(order, **extra):
    from core.models import SiteSettings
    from growth.jobs import quickpay_url

    site = SiteSettings.load()
    track = f"{settings.SITE_URL}{order.get_absolute_url()}"
    return {
        "name": order.first_name or "مشتری", "number": order.number, "total": toman(order.grand_total),
        "amount": toman(order.online_amount or order.items_total), "paid": toman(order.paid_amount),
        "link": track, "pay_link": quickpay_url(order), "mobile": order.mobile, "city": order.city,
        "mode": order.get_payment_mode_display(), "panel": f"{settings.SITE_URL}/panel/orders/{order.pk}/view/",
        "tracking": f" کد رهگیری: {order.tracking_code}." if order.tracking_code else "",
        "phone": site.mobile or site.phone or "", **extra,
    }


def sample_context():
    """نمونهٔ متغیرها برای پیامک آزمایشی."""
    from core.models import SiteSettings

    site = SiteSettings.load()
    url = settings.SITE_URL
    return {"name": "علی", "number": "10234", "total": toman(48_500_000), "amount": toman(48_500_000), "paid": toman(48_500_000),
            "link": f"{url}/order/10234/", "pay_link": f"{url}/pay/10234/", "mobile": "09120000000", "city": "تهران",
            "mode": "پرداخت کامل", "panel": f"{url}/panel/orders/", "tracking": " کد رهگیری: 123456789.",
            "phone": site.mobile or site.phone or "", "code": "C1-AB2CD", "discount": toman(2_000_000), "min": toman(40_000_000),
            "until": "۱۵ آبان", "site": url.replace("https://", "")}


# ------------------------------------------------------------------ ثبت سفارش
def order_placed_now(order):
    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    ctx = context(order)
    if s.order_sms and not SmsLog.objects.filter(order=order, kind=SmsLog.Kind.ORDER).exists():
        tpl = s.order_installment_text if order.payment_mode == "installment" else s.order_text
        send(order.mobile, render(tpl, **ctx), SmsLog.Kind.ORDER, order)
    if s.admin_sms:
        text = render(s.admin_text, **ctx)
        for m in admins():
            send(m, text, SmsLog.Kind.ADMIN, order)


def order_placed(order):
    later(order_placed_now, order)


# ------------------------------------------------------------------ پرداخت
def order_paid_now(order, amount, customer=True, admin=True):
    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    ctx = context(order, paid=toman(amount))
    if customer:
        send(order.mobile, render(s.paid_text, **ctx), SmsLog.Kind.PAID, order)
    if admin:
        text = render(s.admin_paid_text, **ctx)
        for m in admins():
            send(m, text, SmsLog.Kind.ADMIN, order)


def order_paid(order, amount, customer=True, admin=True):
    later(order_paid_now, order, amount, customer, admin)


# ------------------------------------------------------------------ تغییر وضعیت در پنل
STATUS_FIELDS = {"shipped": "shipped_text", "completed": "completed_text", "cancelled": "cancelled_text"}


def status_changed_now(order, old):
    from .models import CrmSettings, SmsLog

    s = CrmSettings.load()
    field = STATUS_FIELDS.get(order.status)
    if not s.status_sms or not field or old == order.status:
        return False
    return send(order.mobile, render(getattr(s, field), **context(order)), SmsLog.Kind.STATUS, order)


def status_changed(order, old):
    if old != order.status and order.status in STATUS_FIELDS:
        later(status_changed_now, order, old)
