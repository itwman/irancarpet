"""فرصت‌های ویژهٔ خرید: پیدا کردن فرصت فعال هر سایز و اعمال قیمت ویژه روی سطر سبد.

قیمت ویژه فقط وقتی است که از آن سایز دقیقاً یک تخته در سبد باشد؛ با دو تخته یا بیشتر همه با قیمت معمول حساب می‌شوند.
"""
from django.core.cache import cache
from django.db.models import F, Q, Sum
from django.utils import timezone

CACHE_KEY = "offers:live"


RESERVE_MINUTES = 30  # سفارشی که در حال پرداخت است تا ۳۰ دقیقه همان تخته را نگه می‌دارد


def taken_q(prefix=""):
    """قلم‌هایی که تخته را گرفته‌اند: سفارش پرداخت‌شده، یا در انتظار پرداختِ کمتر از ۳۰ دقیقه."""
    from .coupons import PLACED

    recent = timezone.now() - timezone.timedelta(minutes=RESERVE_MINUTES)
    return (Q(**{f"{prefix}order__status__in": PLACED})
            | Q(**{f"{prefix}order__status": "pending", f"{prefix}order__created_at__gte": recent}))


def live_offers():
    """فرصت‌های فعال (با تعداد باقی‌مانده)؛ ۶۰ ثانیه کش."""
    from .models import SpecialOffer

    ids = cache.get(CACHE_KEY)
    if ids is None:
        now = timezone.now()
        qs = (SpecialOffer.objects.filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now), is_active=True, starts_at__lte=now)
              .annotate(_sold=Sum("items__quantity", filter=taken_q("items__")))
              .filter(Q(_sold__isnull=True) | Q(_sold__lt=F("quantity"))))
        ids = list(qs.values_list("pk", flat=True))
        cache.set(CACHE_KEY, ids, 60)
    out = []
    for o in SpecialOffer.objects.filter(pk__in=ids).select_related("product__image", "product__album", "size").order_by("-created_at"):
        if o.is_live:
            out.append(o)
    return out


def clear():
    cache.delete(CACHE_KEY)


def for_variation(v):
    if not v or not v.size_id:
        return None
    for o in live_offers():
        if o.product_id == v.product_id and o.size_id == v.size_id:
            return o
    return None


def for_product(p):
    return [o for o in live_offers() if o.product_id == p.pk]


def apply_to_line(line):
    """روی سطر سبد (shop.cart.Line یا api._Line): قیمت ویژه فقط برای تعدادهای مجاز (تختهٔ تک در انبار نماند)."""
    line.offer, line.regular_price, line.offer_hint = None, line.unit_price, ""
    o = for_variation(line.variation)
    if not o:
        return
    v = line.variation
    in_stock = line.product.is_purchasable and v.is_available
    if line.qty in o.allowed:
        # حتی اگر فرش یا این سایز در سایت ناموجود باشد، تخته‌های انبار فروخته می‌شوند
        line.offer, line.unit_price, line.regular_price, line.problem = o, o.price, o.regular_price, ""
    elif not in_stock:
        line.problem = f"از این سایز فقط {o.allowed_label} تخته با هم فروخته می‌شود؛ تعداد را درست کنید."
    else:
        line.offer_hint = f"قیمت ویژه برای خرید {o.allowed_label} تخته از این سایز است؛ با این تعداد قیمت معمول حساب شد."


def offer_total(lines):
    return sum(x.total for x in lines if getattr(x, "offer", None) and not x.problem)


def allows_qty(variation, qty):
    """این تعداد از سایز «فقط جفت» به خاطر فرصت ویژه مجاز است؟"""
    o = for_variation(variation)
    return bool(o and qty in o.allowed)
