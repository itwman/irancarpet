"""امتیاز خرید باشگاه مشتریان.

امتیاز از سفارش‌های پرداخت‌شدهٔ هر شمارهٔ موبایل حساب می‌شود (لغو یا مرجوع‌شده‌ها نه). تبدیل امتیاز یک کد تخفیف شخصی می‌سازد؛
اگر آن کد بی‌استفاده منقضی شود، امتیازش خودکار برمی‌گردد.
"""
from django.db.models import Q
from django.utils import timezone

EARN_STATUSES = ["deposit_paid", "paid", "processing", "shipped", "completed"]


def for_amount(amount, s=None):
    from .models import CrmSettings

    s = s or CrmSettings.load()
    return int(amount // s.points_per) if s.points_enabled and s.points_per else 0


def _orders(mobile, s):
    from shop.models import Order

    variants = {mobile, mobile[1:], "98" + mobile[1:], "+98" + mobile[1:]}  # سفارش‌های قدیمی وردپرس
    qs = Order.objects.filter(mobile__in=variants, status__in=EARN_STATUSES)
    if s.points_since:
        qs = qs.filter(created_at__date__gte=s.points_since)
    return qs


def earned(mobile, s=None):
    from .models import CrmSettings

    s = s or CrmSettings.load()
    if not mobile or not s.points_enabled:
        return 0
    return sum(for_amount(t or 0, s) for t in _orders(mobile, s).values_list("items_total", flat=True))


def spent(mobile):
    """امتیاز تبدیل‌شده؛ کدی که بی‌استفاده منقضی یا غیرفعال شده حساب نمی‌شود."""
    from shop.coupons import PLACED
    from shop.models import Order

    from .models import PointRedeem

    now, total = timezone.now(), 0
    for r in PointRedeem.objects.filter(mobile=mobile).select_related("coupon"):
        c = r.coupon
        if c is None:
            total += r.points
            continue
        used = Order.objects.filter(coupon_code=c.code, status__in=PLACED).exists()
        alive = c.is_active and (not c.ends_at or c.ends_at > now)
        if used or alive:
            total += r.points
    return total


def balance(mobile, s=None):
    return max(earned(mobile, s) - spent(mobile), 0)


def redeem(mobile, points, s=None):
    """(کد تخفیف، پیام خطا)"""
    from .campaigns import make_coupon
    from .models import CrmSettings, PointRedeem

    s = s or CrmSettings.load()
    if not s.points_enabled:
        return None, "باشگاه امتیاز فعلاً فعال نیست."
    bal = balance(mobile, s)
    if points < s.points_min_redeem:
        return None, f"کمترین امتیاز برای تبدیل {s.points_min_redeem:,} است."
    if points > bal:
        return None, "امتیاز شما کافی نیست."
    coupon = make_coupon("PT", mobile, f"تبدیل {points} امتیاز", points * s.point_value, s.points_min_order, s.points_valid_days)
    PointRedeem.objects.create(mobile=mobile, points=points, coupon=coupon)
    return coupon, ""


def my_coupons(mobile):
    from shop.coupons import PLACED
    from shop.models import Coupon, Order

    now = timezone.now()
    qs = (Coupon.objects.filter(for_mobile=mobile, is_active=True).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
          .order_by("-created_at")[:20])
    used = set(Order.objects.filter(coupon_code__in=[c.code for c in qs], status__in=PLACED).values_list("coupon_code", flat=True))
    return [c for c in qs if c.code not in used]
