"""ارسال کمپین: برای هر گیرنده یک کد تخفیف شخصی (فقط با موبایل خودش، یک‌بار) و یک پیامک.

قابل ادامه است: اگر ارسال قطع شود یا متوقف کنید، دوباره که شروع کنید فقط به کسانی می‌رود که هنوز پیامک نگرفته‌اند.
"""
import logging
import secrets
import threading
import time

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from core.templatetags.fa import jdate, toman

from .notify import render, send
from .segments import audience

log = logging.getLogger(__name__)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def make_coupon(prefix, mobile, title, discount, min_order, valid_days):
    """یک کد تازهٔ یک‌بارمصرف که فقط با همین موبایل کار می‌کند."""
    from shop.models import Coupon

    for _ in range(10):
        code = f"{prefix}-{''.join(secrets.choice(ALPHABET) for _ in range(5))}"
        if not Coupon.objects.filter(code=code).exists():
            break
    return Coupon.objects.create(
        code=code, title=title[:120], kind=Coupon.Kind.FIXED, value=discount, min_order=min_order,
        ends_at=timezone.now() + timezone.timedelta(days=valid_days), usage_limit=1, per_user_limit=1,
        for_mobile=mobile, is_active=True)


def personal_coupon(prefix, mobile, title, discount, min_order, valid_days):
    """کد تخفیف شخصی؛ اگر برای همین کمپین و همین موبایل ساخته شده و هنوز معتبر است، همان برمی‌گردد."""
    from django.db.models import Q

    from shop.models import Coupon

    c = (Coupon.objects.filter(code__startswith=f"{prefix}-", for_mobile=mobile, is_active=True)
         .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=timezone.now())).first())
    return c or make_coupon(prefix, mobile, title, discount, min_order, valid_days)


def message(campaign_text, c, coupon=None, footer="", **extra):
    text = render(campaign_text, name=c.get("name") or "مشتری", code=coupon.code if coupon else "",
                  discount=toman(coupon.value) if coupon else "", min=toman(coupon.min_order) if coupon else "",
                  until=jdate(coupon.ends_at, "%d %B") if coupon and coupon.ends_at else "",
                  days="", site=settings.SITE_URL.replace("https://", ""), **extra)
    return f"{text}\n{footer}".strip() if footer else text


def recipients(campaign):
    return audience(campaign.segment, campaign.inactive_days, campaign.custom_numbers, album=campaign.album_id)


def extra_vars(campaign):
    return {"album": campaign.album.title if campaign.album_id else "", "date": campaign.event_date}


def start(campaign):
    t = threading.Thread(target=_run, args=(campaign.pk,), daemon=True)
    t.start()
    return t


def run_sync(pk):
    _run(pk, pause=0)


def _run(pk, pause=0.4):
    from .models import Campaign, CrmSettings, SmsLog

    close_old_connections()
    try:
        camp = Campaign.objects.get(pk=pk)
        footer = CrmSettings.load().marketing_footer
        extras = extra_vars(camp)
        people = recipients(camp)
        Campaign.objects.filter(pk=pk).update(total=len(people), status=Campaign.Status.SENDING,
                                              started_at=camp.started_at or timezone.now())
        done = set(SmsLog.objects.filter(campaign=camp, ok=True).values_list("mobile", flat=True))
        sent, failed, fails_in_row = len(done), camp.failed, 0
        for c in people:
            if c["mobile"] in done:
                continue
            if not Campaign.objects.filter(pk=pk, status=Campaign.Status.SENDING).exists():
                return  # متوقف شد
            coupon = None
            if camp.discount:
                coupon = personal_coupon(camp.code_prefix, c["mobile"], camp.title, camp.discount, camp.min_order, camp.valid_days)
            ok = send(c["mobile"], message(camp.text, c, coupon, footer, **extras), SmsLog.Kind.CAMPAIGN, campaign=camp)
            if ok:
                sent += 1
                fails_in_row = 0
            else:
                failed += 1
                fails_in_row += 1
                if fails_in_row >= 5:
                    last = SmsLog.objects.filter(campaign=camp, ok=False).first()
                    Campaign.objects.filter(pk=pk).update(status=Campaign.Status.FAILED, sent=sent, failed=failed,
                                                          last_error=(last.error if last else "")[:300])
                    return
            Campaign.objects.filter(pk=pk).update(sent=sent, failed=failed)
            if pause:
                time.sleep(pause)
        Campaign.objects.filter(pk=pk).update(status=Campaign.Status.DONE, sent=sent, failed=failed, finished_at=timezone.now())
    except Exception:  # noqa: BLE001
        log.exception("crm campaign %s", pk)
        Campaign.objects.filter(pk=pk).update(status=Campaign.Status.FAILED, last_error="خطای داخلی")
    finally:
        close_old_connections()


def results(campaign):
    """(سفارش‌های پرداخت‌شده با کدهای این کمپین، جمع فروش)"""
    from shop.coupons import PLACED
    from shop.models import Order

    qs = Order.objects.filter(coupon_code__startswith=f"{campaign.code_prefix}-", status__in=PLACED)
    from django.db.models import Sum

    return qs.count(), qs.aggregate(s=Sum("items_total"))["s"] or 0
