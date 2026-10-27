"""پایان فرصت‌های ویژه (فرش جشنواره‌ای): تصمیم مدیر برای تمدید یا بستن.

فرصتی که زمانش تمام شده ولی تخته دارد «منتظر تصمیم» است (تا ۶۰ روز بعد از پایان). سه روز مانده به پایان «رو به پایان» است.
تمدید خودکار نداریم: شمارندهٔ معکوسی که خودبه‌خود از نو شروع شود فوریت ساختگی است.
"""
import datetime as _dt

from django.db.models import F, Q, Sum
from django.utils import timezone

SOON_DAYS = 3
WAIT_DAYS = 60


def _with_left(qs):
    from .offers import taken_q

    return (qs.annotate(_sold=Sum("items__quantity", filter=taken_q("items__")))
            .filter(Q(_sold__isnull=True) | Q(_sold__lt=F("quantity"))))


def waiting_q(now=None):
    now = now or timezone.now()
    return Q(is_active=True, ends_at__lte=now, ends_at__gte=now - _dt.timedelta(days=WAIT_DAYS))


def ending_q(now=None):
    now = now or timezone.now()
    return Q(is_active=True, starts_at__lte=now, ends_at__gt=now, ends_at__lte=now + _dt.timedelta(days=SOON_DAYS))


def state_filter(qs, value, now=None):
    """فیلتر پنل: waiting | ending"""
    q = {"waiting": waiting_q, "ending": ending_q}.get(value)
    if q is None:
        return qs
    return _with_left(qs.filter(q(now)))


def counts(now=None):
    from .models import SpecialOffer

    qs = SpecialOffer.objects.all()
    return {"waiting": state_filter(qs, "waiting", now).count(), "ending": state_filter(qs, "ending", now).count()}


def month_end(y, m):
    """آخرین دقیقهٔ ماه شمسی y/m (به وقت سایت)."""
    import jdatetime

    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    g = (jdatetime.date(y2, m2, 1) - jdatetime.timedelta(days=1)).togregorian()
    return timezone.make_aware(_dt.datetime(g.year, g.month, g.day, 23, 59))


def next_month_end(ends_at, now=None):
    """فرصتِ تا ۳۰ مهر ← آخر آبان. اگر تا آن موقع کمتر از ۷ روز مانده باشد، یک ماه دیگر."""
    import jdatetime

    now = now or timezone.now()
    base = timezone.localtime(ends_at or now)
    j = jdatetime.date.fromgregorian(date=base.date())
    y, m = (j.year + 1, 1) if j.month == 12 else (j.year, j.month + 1)
    end = month_end(y, m)
    while end - now < _dt.timedelta(days=7):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        end = month_end(y, m)
    return end


def renew(qs, now=None):
    """تمدید تا آخر ماه بعد با همان درصد و تعداد. خروجی: [(فرصت، پایان تازه)]"""
    from .offers import clear

    out = []
    for o in qs:
        o.ends_at = next_month_end(o.ends_at, now)
        o.is_active = True
        o.save(update_fields=["ends_at", "is_active"])
        out.append((o, o.ends_at))
    clear()
    return out


def close(qs):
    """«تمدید نمی‌شود»: غیرفعال و بیرون از اعلان‌ها."""
    from .offers import clear

    n = qs.update(is_active=False)
    clear()
    return n


def daily_admin_sms(now=None):
    """یک پیامک در روز (پس از ساعت ۹) به مدیران، فقط اگر فرصتی منتظر تصمیم یا رو به پایان باشد."""
    from django.conf import settings
    from django.core.cache import cache

    from .models import ShopSettings

    s = ShopSettings.load()
    now = timezone.localtime(now or timezone.now())
    if not s.offer_admin_sms or now.hour < 9:
        return 0
    key = f"offer_sms:{now.date().isoformat()}"
    if cache.get(key):
        return 0
    cache.set(key, 1, 60 * 60 * 30)
    c = counts(now)
    if not c["waiting"] and not c["ending"]:
        return 0
    from core.templatetags.fa import fa_num
    from crm.models import SmsLog
    from crm.notify import admins, send

    parts = [f"{fa_num(c['waiting'])} فرصت تمام‌شده منتظر تمدید" if c["waiting"] else "",
             f"{fa_num(c['ending'])} فرصت تا {fa_num(SOON_DAYS)} روز دیگر تمام می‌شود" if c["ending"] else ""]
    tab = "waiting" if c["waiting"] else "ending"
    text = "فرش جشنواره‌ای: " + "، ".join(p for p in parts if p) + f"\n{settings.SITE_URL}/panel/special-offers/?offer_state={tab}"
    return sum(1 for m in admins() if send(m, text, SmsLog.Kind.ADMIN))
