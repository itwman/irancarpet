"""روند خودکار بتا برای یک سفارش اقساطی: بررسی اعتبار ← رمز یک‌بارمصرف ← ثبت فروش ← پیگیری وصول."""
import datetime as dt
import logging
import uuid

import jdatetime
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from . import beta
from .beta import BetaError
from .calc import QuoteError, quote
from .models import BetaSale, BetaSettings
from .orders import valid_national_code

log = logging.getLogger(__name__)
MONTHS_KEY = "beta_months"
OTP_SECONDS = 120


class FlowError(Exception):
    """پیام برای مشتری."""


def is_auto(order):
    plan = order.installment_plan
    return bool(order.is_installment and plan and plan.kind == "beta" and BetaSettings.load().ready)


def open_for(order):
    """جعبهٔ بتا در صفحهٔ سفارش نشان داده شود؟"""
    return (is_auto(order) and order.installment_state == "review"
            and order.status not in (order.Status.CANCELLED, order.Status.REFUNDED))


def sale_for(order, create=True):
    try:
        return order.beta
    except BetaSale.DoesNotExist:
        if not create:
            return None
    nc = str((order.installment_info or {}).get("national_code") or "")
    return BetaSale.objects.create(order=order, national_code=nc if valid_national_code(nc) else "")


def months(force=False):
    """ماه‌های مجاز شروع (کش ۳ ساعت)."""
    got = None if force else cache.get(MONTHS_KEY)
    if got is None:
        got = beta.months()
        cache.set(MONTHS_KEY, got, 3 * 3600)
    return got


def month_label(ym):
    try:
        y, m = (int(x) for x in str(ym).split("/")[:2])
        return f"{jdatetime.date(y, m, 1).j_months_fa[m - 1]} {y}"
    except (ValueError, IndexError, AttributeError):
        return str(ym)


def _today_count(user):
    since = timezone.now() - dt.timedelta(hours=24)
    n = 0
    for rows in BetaSale.objects.filter(order__user=user).values_list("inquiries", flat=True):
        n += sum(1 for t in rows or [] if t >= since.isoformat())
    return n


def fits(order, sale=None):
    sale = sale or sale_for(order, create=False)
    if not sale or sale.credit is None:
        return None
    return int(order.installment.get("installment") or 0) <= sale.credit


def suggest(order, sale):
    """کمترین تعداد قسطی که با پیش‌پرداخت فعلی در اعتبار جا می‌شود؛ None اگر هیچ‌کدام."""
    plan, q = order.installment_plan, order.installment
    if sale.credit is None:
        return None
    for m in plan.months_for(1):
        if m < q.get("months", 0):
            continue
        try:
            if quote(plan, q["total"], q["down_percent"], m, 1)["installment"] <= sale.credit:
                return m
        except QuoteError:
            continue
    return None


# ---------------------------------------------------------------- گام‌ها
def check(order, nc=None):
    """استعلام توان بازپرداخت. خروجی پیام برای مشتری."""
    s = BetaSettings.load()
    sale = sale_for(order)
    if sale.sale_id:
        raise FlowError("این خرید در بتا ثبت شده است.")
    nc = (nc or sale.national_code or "").strip()
    if not valid_national_code(nc):
        raise FlowError("کد ملی درست نیست.")
    if order.user_id and _today_count(order.user) >= max(int(s.daily_limit or 0), 1):
        raise FlowError("امروز بیش از حد مجاز اعتبار استعلام شده است؛ فردا دوباره امتحان کنید یا با ما تماس بگیرید.")
    sale.inquiries = [t for t in sale.inquiries if t >= (timezone.now() - dt.timedelta(days=2)).isoformat()] + [timezone.now().isoformat()]
    if nc != sale.national_code:
        sale.national_code = nc
        sale.credit = None
        info = dict(order.installment_info or {})
        info["national_code"] = nc
        order.installment_info = info
        order.save(update_fields=["installment_info"])
    try:
        r = beta.inquiry(nc, s)
    except BetaError as e:
        sale.last_error = e.admin_text[:300]
        sale.credit = None
        sale.save()
        raise FlowError(e.customer_text) from e
    sale.credit = r["credit"]
    sale.cellphone = beta.mask_mobile(r["cellphone"])
    sale.checked_at = timezone.now()
    sale.last_error = ""
    sale.save()
    if fits(order, sale):
        return "اعتبار شما در بتا برای این خرید کافی است. ماه شروع اقساط را انتخاب کنید و «ارسال رمز» را بزنید."
    m = suggest(order, sale)
    if m:
        return f"اعتبار ماهانهٔ شما برای این تعداد قسط کافی نیست؛ با {m} قسط یا بیشتر جا می‌شود. تعداد قسط را عوض کنید."
    return "اعتبار ماهانهٔ شما در بتا برای این خرید کافی نیست. پیش‌پرداخت را بیشتر کنید یا با ما تماس بگیرید."


def requote(order, months_n, down_percent):
    """تغییر تعداد قسط یا پیش‌پرداخت پیش از ثبت در بتا."""
    sale = sale_for(order)
    if sale.sale_id:
        raise FlowError("این خرید در بتا ثبت شده و دیگر تغییر نمی‌کند.")
    if order.paid_amount:
        raise FlowError("پیش‌پرداخت پرداخت شده است؛ برای تغییر با ما تماس بگیرید.")
    q = order.installment
    try:
        nq = quote(order.installment_plan, q["total"], down_percent, months_n, 1)
    except (QuoteError, ValueError) as e:
        raise FlowError(str(e) if isinstance(e, QuoteError) else "مقادیر درست نیست.") from e
    order.installment = nq
    order.deposit_percent = nq["down_percent"]
    order.online_amount = nq["down"]
    order.save(update_fields=["installment", "deposit_percent", "online_amount"])
    sale.payload, sale.otp_sent_at = {}, None
    sale.save(update_fields=["payload", "otp_sent_at"])
    if sale.credit is not None and not fits(order, sale):
        return "اقساط تازه هنوز از اعتبار ماهانهٔ شما بیشتر است."
    return "اقساط به‌روز شد."


def payload_for(order, ym, s):
    q = order.installment
    return {
        "title": (s.sale_title or "سفارش {order}").replace("{order}", str(order.number))[:100],
        "amount": s.to_bank(int(q["installment"]) * int(q["count"])),
        "numberOfInstallments": int(q["count"]),
        "startDateYearMonth": ym,
    }


def send_otp(order, ym):
    s = BetaSettings.load()
    sale = sale_for(order)
    if sale.sale_id:
        raise FlowError("این خرید در بتا ثبت شده است.")
    if not sale.national_code or sale.credit is None:
        raise FlowError("اول «بررسی اعتبار» را بزنید.")
    if not fits(order, sale):
        raise FlowError("اقساط از اعتبار ماهانهٔ شما بیشتر است؛ تعداد قسط یا پیش‌پرداخت را عوض کنید.")
    try:
        allowed = [k for k, _ in months()]
    except BetaError as e:
        raise FlowError(e.customer_text) from e
    if ym not in allowed:
        raise FlowError("ماه شروع اقساط را از فهرست انتخاب کنید.")
    payload = payload_for(order, ym, s)
    if (sale.otp_sent_at and payload == sale.payload
            and (timezone.now() - sale.otp_sent_at).total_seconds() < OTP_SECONDS):
        return "رمز همین حالا فرستاده شده؛ پیامک بانک را ببینید."
    try:
        beta.request_otp(sale.national_code, payload, s)
    except BetaError as e:
        sale.last_error = e.admin_text[:300]
        sale.save(update_fields=["last_error"])
        if e.code != 4444:
            raise FlowError(e.customer_text) from e
    sale.payload, sale.start_ym, sale.request_id = payload, ym, uuid.uuid4()
    sale.otp_sent_at = timezone.now()
    sale.save(update_fields=["payload", "start_ym", "request_id", "otp_sent_at"])
    return f"رمز یک‌بارمصرف بانک رفاه به {chr(0x2066) + sale.cellphone + chr(0x2069) if sale.cellphone else 'موبایل شما'} پیامک شد؛ تا ۲ دقیقه آن را وارد کنید."


def confirm(order, otp, site_url=""):
    s = BetaSettings.load()
    otp = "".join(ch for ch in str(otp or "") if ch.isdigit())
    with transaction.atomic():
        sale = BetaSale.objects.select_for_update().get(pk=sale_for(order).pk)
        if sale.sale_id:
            return "خرید شما در بتا ثبت شده است."
        if not sale.payload or not sale.request_id:
            raise FlowError("اول «ارسال رمز» را بزنید.")
        if not otp:
            raise FlowError("رمز پیامک‌شده را وارد کنید.")
        if sale.payload != payload_for(order, sale.start_ym, s):
            raise FlowError("اقساط بعد از ارسال رمز عوض شده؛ دوباره «ارسال رمز» را بزنید.")
        sale_id = None
        try:
            sale_id = beta.consume(sale.national_code, sale.payload, otp, sale.request_id, s)
        except BetaError as e:
            if e.code in (0, 4406, 500):  # شاید ثبت شده و پاسخ نرسیده
                try:
                    got = beta.by_request(sale.request_id, s)
                except BetaError:
                    got = None
                sale_id = got and int(got["id"])
            if not sale_id:
                sale.last_error = e.admin_text[:300]
                sale.save(update_fields=["last_error"])
                raise FlowError(e.customer_text) from e
        if not sale_id:
            got = beta.by_request(sale.request_id, s)
            sale_id = got and int(got["id"])
        if not sale_id:
            sale.last_error = "ثبت فروش پاسخ بی‌شماره داد"
            sale.save(update_fields=["last_error"])
            raise FlowError(beta.SHOP_PROBLEM)
        sale.sale_id, sale.registered_at, sale.last_error = sale_id, timezone.now(), ""
        sale.save(update_fields=["sale_id", "registered_at", "last_error"])
    finalize(order, sale, site_url)
    return "خرید اقساطی شما در سامانهٔ بتا ثبت شد. جدول اقساط را بانک هم پیامک می‌کند."


def schedule_from(ym, count, each):
    y, m = (int(x) for x in ym.split("/")[:2])
    out = []
    for k in range(count):
        idx = m - 1 + k
        jy, jm = y + idx // 12, idx % 12 + 1
        jd = jdatetime.date(jy, jm, 1)
        out.append({"n": k + 1, "date": jd.togregorian().isoformat(), "jdate": f"{jy}/{jm:02d}", "amount": each,
                    "label": month_label(f"{jy}/{jm}")})
    return out


def finalize(order, sale, site_url=""):
    from .orders import set_state

    q = dict(order.installment)
    q["schedule"] = schedule_from(sale.start_ym, int(q["count"]), int(q["installment"]))
    q["start"] = q["schedule"][0]["date"] if q["schedule"] else q.get("start")
    q["beta_sale_id"] = sale.sale_id
    order.installment = q
    order.save(update_fields=["installment"])
    set_state(order, "approved", site_url)
    order.refresh_from_db()
    if not (order.online_amount and order.paid_amount < order.online_amount):
        order.installment_state = "done"
        order.save(update_fields=["installment_state"])
    try:
        sync(sale)
    except BetaError:
        pass


# ---------------------------------------------------------------- پیگیری وصول
def sync(sale):
    rows = beta.installments(sale.sale_id)
    live = [r for r in rows if not r["deleted"]]
    sale.installments = rows
    sale.paid_count = sum(1 for r in live if r["ok"] or r["status"] == 2)
    sale.failed_count = sum(1 for r in live if r["status"] == 3)
    sale.synced_at = timezone.now()
    sale.last_error = ""
    sale.save(update_fields=["installments", "paid_count", "failed_count", "synced_at", "last_error"])
    return sale


def sync_due(limit=200, force=False):
    """روزانه: اقساط خریدهای ثبت‌شده‌ای که هنوز همه وصول نشده‌اند."""
    if not BetaSettings.load().ready:
        return 0
    old = timezone.now() - dt.timedelta(minutes=5 if force else 20 * 60)
    from django.db.models import Q

    n = 0
    for sale in BetaSale.objects.filter(sale_id__isnull=False).filter(Q(synced_at__isnull=True) | Q(synced_at__lt=old))[:limit]:
        if sale.installments and sale.paid_count >= sale.count:
            continue
        try:
            sync(sale)
            n += 1
        except BetaError as e:
            sale.last_error = e.admin_text[:300]
            sale.save(update_fields=["last_error"])
    return n
