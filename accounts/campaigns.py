"""ارسال پیامک گروهی در پس‌زمینه (دسته‌های ۱۰۰تایی، قابل ادامه بعد از قطع شدن)."""
import logging
import re
import threading
import time

from django.db import close_old_connections
from django.utils import timezone

from . import sms
from .utils import normalize_mobile

log = logging.getLogger(__name__)
BATCH = 100


def recipients(c):
    from shop.models import Order

    from .models import Profile, SmsCampaign

    if c.audience == SmsCampaign.Audience.CUSTOM:
        raw = [x.replace(" ", "") for x in re.split(r"[\n\r,،;]+", c.custom_numbers or "")]
    elif c.audience == SmsCampaign.Audience.BUYERS:
        raw = list(Order.objects.values_list("mobile", flat=True))
    else:
        raw = list(Profile.objects.exclude(mobile=None).filter(user__is_active=True, user__is_staff=False).values_list("mobile", flat=True))
        raw += list(Order.objects.values_list("mobile", flat=True))
    out, seen = [], set()
    for m in raw:
        m = normalize_mobile(m)
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def start(c):
    """ارسال را در یک رشتهٔ پس‌زمینه شروع یا ادامه می‌دهد."""
    t = threading.Thread(target=_run, args=(c.pk,), daemon=True)
    t.start()
    return t


def _run(pk):
    from .models import SmsCampaign

    close_old_connections()
    try:
        c = SmsCampaign.objects.get(pk=pk)
        nums = recipients(c)
        SmsCampaign.objects.filter(pk=pk).update(total=len(nums), status=SmsCampaign.Status.SENDING)
        pos = c.sent + c.failed
        fails = 0
        while pos < len(nums):
            if SmsCampaign.objects.filter(pk=pk, status=SmsCampaign.Status.SENDING).count() == 0:
                return   # متوقف شد
            batch = nums[pos:pos + BATCH]
            ok, msg = sms.send_bulk(batch, c.text)
            if ok:
                SmsCampaign.objects.filter(pk=pk).update(sent=c.sent + len(batch))
                c.sent += len(batch)
                fails = 0
            else:
                fails += 1
                SmsCampaign.objects.filter(pk=pk).update(last_error=msg[:300])
                if fails >= 3:
                    SmsCampaign.objects.filter(pk=pk).update(status=SmsCampaign.Status.FAILED)
                    return
                time.sleep(5)
                continue
            pos += len(batch)
            time.sleep(1)
        SmsCampaign.objects.filter(pk=pk).update(status=SmsCampaign.Status.DONE, finished_at=timezone.now())
    except Exception:  # noqa: BLE001
        log.exception("sms campaign %s", pk)
        SmsCampaign.objects.filter(pk=pk).update(status=SmsCampaign.Status.FAILED, last_error="خطای داخلی")
    finally:
        close_old_connections()
