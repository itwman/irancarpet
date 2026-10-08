"""محاسبهٔ پورسانت پله‌ای و هماهنگی با وضعیت سفارش.

- هر سفارشی که با پیوند یا کد همکار ثبت شود یک ردیف «پورسانت» دارد.
- وضعیت پورسانت از وضعیت سفارش می‌آید: پرداخت‌نشده ← منتظر، پرداخت‌شده ← منتظر تحویل، تحویل‌شده ← قابل تسویه، لغو/مسترد ← لغو.
- درصد بر اساس جمع فروش همکار در دوره (ماه شمسی یا کل) حساب می‌شود و با هر تغییر، پورسانت‌های تسویه‌نشدهٔ آن دوره دوباره حساب می‌شوند.
"""
import logging
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Affiliate, AffiliateSettings, Commission, CommissionTier

log = logging.getLogger(__name__)
COUNTED = {Commission.Status.PENDING, Commission.Status.APPROVED, Commission.Status.PAID}
OPEN = {Commission.Status.WAITING, Commission.Status.PENDING, Commission.Status.APPROVED}


def status_for(order):
    st = order.status
    if st in ("cancelled", "refunded"):
        return Commission.Status.CANCELLED
    if st == "completed":
        return Commission.Status.APPROVED
    if st in order.PAID_STATUSES:
        return Commission.Status.PENDING
    return Commission.Status.WAITING


def period_of(dt, s=None):
    s = s or AffiliateSettings.load()
    if s.tier_period == AffiliateSettings.Period.ALL:
        return "all"
    import jdatetime

    d = jdatetime.date.fromgregorian(date=timezone.localtime(dt).date())
    return f"{d.year:04d}-{d.month:02d}"


def current_period(s=None):
    return period_of(timezone.now(), s)


def tiers():
    rows = cache.get("aff:tiers")
    if rows is None:
        rows = [(t.min_sales, t.percent, t.title) for t in CommissionTier.objects.order_by("min_sales")]
        cache.set("aff:tiers", rows, 600)
    return rows


def rate_for(total, rows=None):
    rows = tiers() if rows is None else rows
    pct = rows[0][1] if rows else Decimal(0)
    for mn, p, _ in rows:
        if total >= mn:
            pct = p
    return Decimal(pct)


def tier_info(total, rows=None):
    """(پلهٔ فعلی، پلهٔ بعدی، مانده تا پلهٔ بعد) برای نمایش به همکار."""
    rows = tiers() if rows is None else rows
    cur = nxt = None
    for i, (mn, p, title) in enumerate(rows):
        if total >= mn or i == 0:
            cur = {"min": mn, "percent": p, "title": title, "index": i + 1}
        elif nxt is None:
            nxt = {"min": mn, "percent": p, "title": title, "index": i + 1}
    return cur, nxt, (nxt["min"] - total if nxt else 0)


def bracket_amount(start, base, rows=None):
    """پورسانت پلکانی بخشی از فروش که از مبلغ start شروع می‌شود و base تومان است."""
    rows = tiers() if rows is None else rows
    if not rows:
        return Decimal(0)
    total = Decimal(0)
    end = start + base
    for i, (mn, p, _) in enumerate(rows):
        lo = 0 if i == 0 else mn
        hi = rows[i + 1][0] if i + 1 < len(rows) else None
        a, b = max(start, lo), (end if hi is None else min(end, hi))
        if b > a:
            total += Decimal(b - a) * Decimal(p) / 100
    return total


def _money(x):
    return int(Decimal(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def order_base(order):
    """مبنای پورسانت: جمع کالاها بعد از تخفیف (بدون هزینهٔ ارسال و سود اقساط)."""
    return int(order.items_total or 0)


def recalc(affiliate, period, s=None):
    s = s or AffiliateSettings.load()
    rows = list(Commission.objects.filter(affiliate=affiliate, period=period).exclude(status=Commission.Status.CANCELLED)
                .order_by("created_at", "pk"))
    counted_total = sum(r.base for r in rows if r.status in COUNTED)
    trs = tiers()
    cum = 0
    for r in rows:
        if r.status == Commission.Status.PAID or r.locked:
            if r.status in COUNTED:
                cum += r.base
            continue
        if affiliate.custom_percent is not None:
            pct = Decimal(affiliate.custom_percent)
            amt = Decimal(r.base) * pct / 100
        elif s.tier_mode == AffiliateSettings.Mode.BRACKET:
            amt = bracket_amount(cum, r.base, trs)
            pct = (amt * 100 / r.base).quantize(Decimal("0.01")) if r.base else Decimal(0)
        else:
            total = counted_total if r.status in COUNTED else counted_total + r.base
            pct = rate_for(total, trs)
            amt = Decimal(r.base) * pct / 100
        if r.status in COUNTED:
            cum += r.base
        amount = _money(amt)
        pct = Decimal(pct).quantize(Decimal("0.01"))
        if (r.percent, r.amount) != (pct, amount):
            Commission.objects.filter(pk=r.pk).update(percent=pct, amount=amount)


def recalc_open(s=None):
    """بعد از تغییر پله‌ها یا تنظیمات: همهٔ دوره‌هایی که پورسانت باز دارند دوباره حساب می‌شوند."""
    s = s or AffiliateSettings.load()
    pairs = Commission.objects.filter(status__in=OPEN).values_list("affiliate_id", "period").distinct()
    affs = {a.pk: a for a in Affiliate.objects.filter(pk__in={a for a, _ in pairs})}
    for aid, period in pairs:
        recalc(affs[aid], period, s)
    return len(pairs)


def sync(order):
    """وضعیت و مبلغ پورسانت را با سفارش هماهنگ می‌کند."""
    c = Commission.objects.filter(order_id=order.pk).select_related("affiliate").first()
    if c is None or c.status == Commission.Status.PAID:
        return c
    st, base = status_for(order), order_base(order)
    if (c.status, c.base) != (st, base):
        Commission.objects.filter(pk=c.pk).update(status=st, base=base, updated_at=timezone.now())
        c.status, c.base = st, base
        recalc(c.affiliate, c.period)
        if st == Commission.Status.APPROVED:
            notify_approved(c)
    return c


def order_saved(sender, instance, created=False, **kw):
    if created or kw.get("raw"):
        return
    try:
        transaction.on_commit(lambda: sync(instance))
    except Exception:  # noqa: BLE001
        log.exception("affiliate sync")


def resync_all():
    """کار دوره‌ای: اگر وضعیت سفارشی بی‌خبر از سیگنال (مثلاً گروهی) عوض شده بود، پورسانتش درست می‌شود."""
    n = 0
    for c in Commission.objects.filter(status__in=OPEN).select_related("order"):
        if (status_for(c.order), order_base(c.order)) != (c.status, c.base):
            sync(c.order)
            n += 1
    return n


def notify_approved(c):
    try:
        from accounts.sms import send_bulk

        send_bulk([c.affiliate.mobile], f"ایران کارپت: سفارش {c.order.number} تحویل شد و پورسانت آن به حساب همکاری شما اضافه شد. "
                                        "irancarpet.net/my-account/affiliate/")
    except Exception:  # noqa: BLE001
        pass


# ------------------------------------------------------------------ آمار
def balances(affiliate):
    from django.db.models import Count, Sum

    out = {k: {"amount": 0, "count": 0} for k in Commission.Status.values}
    for row in affiliate.commissions.values("status").annotate(a=Sum("amount"), n=Count("pk")):
        out[row["status"]] = {"amount": row["a"] or 0, "count": row["n"]}
    return out


def period_sales(affiliate, period=None):
    from django.db.models import Sum

    period = period or current_period()
    return (affiliate.commissions.filter(period=period, status__in=COUNTED).aggregate(s=Sum("base"))["s"] or 0)


def reperiod():
    """بعد از تغییر «پله بر اساس»: دورهٔ پورسانت‌های تسویه‌نشده از نو تعیین و حساب می‌شود."""
    s = AffiliateSettings.load()
    for c in Commission.objects.filter(status__in=OPEN).select_related("order"):
        p = period_of(c.order.created_at, s)
        if p != c.period:
            Commission.objects.filter(pk=c.pk).update(period=p)
    return recalc_open(s)
