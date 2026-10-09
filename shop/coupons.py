"""بررسی و اعمال کد تخفیف + کد معرفی دوستان."""
import secrets

from django.db.models import Q
from django.utils import timezone

from .models import Coupon, Order, ShopSettings

PLACED = Order.PAID_STATUSES | {"on_hold"}


def find(code):
    code = (code or "").strip().upper()
    return Coupon.objects.filter(code=code).first() if code else None


def _mobile_of(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    from accounts.utils import normalize_mobile

    return normalize_mobile(getattr(getattr(user, "profile", None), "mobile", "") or "") or normalize_mobile(user.username or "") or ""


def check(code, user, total, source="web"):
    """(coupon, تخفیف، پیام خطا) — تخفیف به تومان و هرگز بیشتر از جمع سبد نیست."""
    c = find(code)
    if c is None or not c.is_active:
        return None, 0, "این کد تخفیف معتبر نیست."
    now = timezone.now()
    if c.starts_at and now < c.starts_at:
        return None, 0, "زمان استفاده از این کد هنوز نرسیده است."
    if c.ends_at and now > c.ends_at:
        return None, 0, "مهلت این کد تخفیف تمام شده است."
    if c.for_user_id and (not user or user.pk != c.for_user_id):
        return None, 0, "این کد مخصوص مشتری دیگری است."
    if c.for_mobile and _mobile_of(user) != c.for_mobile:
        return None, 0, "این کد مخصوص شمارهٔ موبایل دیگری است؛ با همان شماره‌ای که پیامک گرفته‌اید وارد شوید."
    if c.app_only and not source.startswith("app"):
        return None, 0, "این کد فقط برای خرید از اپ است."
    if c.min_order and total < c.min_order:
        return None, 0, f"این کد برای خریدهای بالای {c.min_order:,} تومان است."
    if c.owner_id:
        s = ShopSettings.load()
        if not s.referral_enabled:
            return None, 0, "کد معرفی فعلاً فعال نیست."
        if user and c.owner_id == user.pk:
            return None, 0, "نمی‌توانید از کد معرفی خودتان استفاده کنید."
    if user and user.is_authenticated and c.affiliates.filter(user=user).exists():
        return None, 0, "نمی‌توانید از کد همکاری خودتان استفاده کنید."
    used = Order.objects.filter(coupon_code=c.code, status__in=PLACED)
    if c.usage_limit and used.count() >= c.usage_limit:
        return None, 0, "ظرفیت استفاده از این کد تمام شده است."
    if user:
        mine = used.filter(user=user).count()
        if c.per_user_limit and mine >= c.per_user_limit:
            return None, 0, "شما قبلاً از این کد استفاده کرده‌اید."
        if (c.first_order_only or c.owner_id) and Order.objects.filter(user=user, status__in=PLACED).exists():
            return None, 0, "این کد فقط برای اولین خرید است."
    if c.kind == Coupon.Kind.PERCENT:
        d = total * min(c.value, 100) // 100
    else:
        d = c.value
    if c.max_discount:
        d = min(d, c.max_discount)
    d = int(min(d, total) // 1000 * 1000)  # گرد به هزار تومان
    if d <= 0:
        return None, 0, "این کد برای این سبد تخفیفی ندارد."
    return c, d, ""


def apply(summary, code, user, source="web"):
    """summary را با تخفیف برمی‌گرداند: total کم می‌شود و subtotal/discount/coupon اضافه می‌شود."""
    out = {**summary, "subtotal": summary["total"], "discount": 0, "coupon": None, "coupon_error": ""}
    if not code:
        return out
    base = summary["total"] - summary.get("offer_total", 0)  # کد تخفیف روی فرصت ویژه (که خودش تخفیف دارد) اعمال نمی‌شود
    c, d, err = check(code, user, base, source)
    if err:
        out["coupon_error"] = err
        return out
    out.update(discount=d, coupon=c, total=summary["total"] - d)
    return out


def referral_code(user):
    """کد معرفی اختصاصی هر مشتری (یک بار ساخته می‌شود)."""
    s = ShopSettings.load()
    c = Coupon.objects.filter(owner=user).first()
    if c is None:
        while True:
            code = "IC" + secrets.token_hex(3).upper()
            if not Coupon.objects.filter(code=code).exists():
                break
        c = Coupon.objects.create(code=code, title="کد معرفی", kind=Coupon.Kind.PERCENT, value=s.referral_percent,
                                  max_discount=s.referral_max, min_order=s.referral_min_order, per_user_limit=1, owner=user)
    elif (c.value, c.max_discount, c.min_order) != (s.referral_percent, s.referral_max, s.referral_min_order):
        c.value, c.max_discount, c.min_order = s.referral_percent, s.referral_max, s.referral_min_order
        c.save(update_fields=["value", "max_discount", "min_order"])
    return c


def reward_referrer(order):
    """بعد از پرداخت سفارشی که با کد معرفی بوده، معرف یک کد هدیه می‌گیرد (یک بار برای هر سفارش)."""
    c = find(order.coupon_code)
    if not c or not c.owner_id:
        return None
    s = ShopSettings.load()
    if not s.referral_enabled or not s.referral_reward:
        return None
    gift_code = f"GIFT{order.number}"
    if Coupon.objects.filter(code=gift_code).exists():
        return None
    gift = Coupon.objects.create(code=gift_code, title=f"هدیهٔ معرفی (سفارش {order.number})", kind=Coupon.Kind.FIXED,
                                 value=s.referral_reward, per_user_limit=1, usage_limit=1, for_user=c.owner,
                                 ends_at=timezone.now() + timezone.timedelta(days=180))
    owner = c.owner
    mobile = getattr(getattr(owner, "profile", None), "mobile", "") or owner.username
    try:
        from accounts.sms import send_bulk

        send_bulk([mobile], f"دوست شما با کد معرفی‌تان از ایران کارپت خرید کرد. کد هدیهٔ شما: {gift_code} "
                            f"({s.referral_reward:,} تومان تخفیف، تا ۶ ماه).")
    except Exception:  # noqa: BLE001
        pass
    return gift
