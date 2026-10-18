"""هدیهٔ «اپ فرش پلاس را نصب کن و پیج ایران کارپت را دنبال کن».

مشتری فقط موبایلش را می‌دهد؛ سایت از فرش پلاس می‌پرسد «صاحب این شماره پیج ما را دنبال می‌کند و با اپ آمده؟»
و اگر بله، یک کد شخصی (فقط با همین موبایل، یک‌بارمصرف، با حداقل خرید و مهلت) به همان شماره پیامک می‌شود.
کد روی صفحه نشان داده نمی‌شود: کسی که شمارهٔ دیگری را وارد کند، چیزی به دست نمی‌آورد.
هر شماره فقط یک بار هدیه می‌گیرد؛ اگر کد قبلی هنوز معتبر و استفاده‌نشده است، همان دوباره فرستاده می‌شود.
"""
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .client import ApiError
from .models import FarshPlusSettings

PREFIX = "FP"
RESEND_SECONDS = 600


def live(s=None):
    s = s or FarshPlusSettings.load()
    return s if (s.enabled and s.gift_enabled and s.api_key) else None


def _existing(mobile):
    from shop.coupons import PLACED
    from shop.models import Coupon, Order

    c = Coupon.objects.filter(code__startswith=f"{PREFIX}-", for_mobile=mobile).order_by("-created_at").first()
    if c is None:
        return None, False
    used = Order.objects.filter(coupon_code=c.code, status__in=PLACED).exists()
    usable = c.is_active and not used and (c.ends_at is None or c.ends_at > timezone.now())
    return c, usable


def claim(mobile, client=None):
    """خروجی: (ok, پیام برای مشتری)."""
    from crm.campaigns import make_coupon, message
    from crm.notify import send

    from .sync import client as make_client

    s = live()
    if s is None:
        return False, "این هدیه فعلاً فعال نیست."
    c, usable = _existing(mobile)
    if c is not None and not usable:
        return False, "این شماره قبلاً هدیهٔ فرش پلاس را گرفته است."
    if c is None:
        try:
            st = (client or make_client(s)).follower(mobile)
        except ApiError:
            return False, "الان به فرش پلاس دسترسی نداریم؛ چند دقیقهٔ دیگر دوباره امتحان کنید."
        if not st.get("follows"):
            return False, ("با این شماره در فرش پلاس، پیج ایران کارپت دنبال نشده است. "
                           "اگر تازه دنبال کرده‌اید، مطمئن شوید با همین شماره وارد فرش پلاس شده‌اید.")
        if s.gift_require_app and not st.get("app"):
            return False, "پیج را دنبال کرده‌اید؛ حالا یک بار اپ فرش پلاس را در گوشی باز کنید و دوباره امتحان کنید."
        c = make_coupon(PREFIX, mobile, "هدیهٔ دنبال‌کردن در فرش پلاس", s.gift_amount, s.gift_min_order, s.gift_valid_days)
    if not cache.add(f"fpgift:sms:{mobile}", 1, RESEND_SECONDS):
        return True, "کد هدیه همین چند دقیقه پیش به این شماره پیامک شد."
    text = message(s.gift_text, {"name": ""}, c)
    if not send(mobile, text, "fpgift"):
        cache.delete(f"fpgift:sms:{mobile}")
        return False, "پیامک فرستاده نشد؛ کمی بعد دوباره امتحان کنید."
    return True, f"کد هدیهٔ {c.value:,} تومانی به شمارهٔ {mobile} پیامک شد.".replace(",", "٬")


def ip_allowed(request, limit=12):
    """هر نشانی در ساعت حداکثر چند بار (تا کسی فهرست شماره‌ها را امتحان نکند)."""
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
    key = f"fpgift:ip:{ip}"
    cache.add(key, 0, 3600)
    try:
        return cache.incr(key) <= limit
    except ValueError:
        return True


def info():
    s = live()
    if s is None:
        return None
    from core.qr import svg

    return {"amount": s.gift_amount, "min_order": s.gift_min_order, "days": s.gift_valid_days, "app_url": s.gift_app_url,
            "page_url": s.gift_page_url, "app_qr": svg(s.gift_app_url), "require_app": s.gift_require_app,
            "url": "/farshplus-gift/", "site": settings.SITE_URL}
