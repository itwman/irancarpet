"""پیوند کوتاه برای پیامک‌ها (crpt.ir/o/k3h9x2p).

اگر دامنهٔ کوتاه در «تنظیمات ← همکاری در فروش» خالی باشد یا پیوند کوتاه در تنظیمات باشگاه خاموش باشد،
پیوند روی دامنهٔ اصلی ساخته می‌شود (irancarpet.net/s/<کد>/)؛ پس پیامک هیچ‌وقت پیوند خراب ندارد.
"""
import secrets

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.utils import timezone

ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
PREFIXES = {"o", "c", "k", "r", "l"}  # پرداخت سفارش، سبد، باشگاه، نظر، عمومی — همه یک جدول


def _base():
    from .models import CrmSettings

    if not CrmSettings.load().short_links:
        return ""
    try:
        from affiliate.track import short_base

        base = short_base()
    except Exception:  # noqa: BLE001
        return ""
    return "" if base == settings.SITE_URL else base


def local(url):
    url = url or ""
    return url[len(settings.SITE_URL):] if url.startswith(settings.SITE_URL) else url


def shorten(url, prefix="l", days=60):
    """نشانی کامل یا مسیر سایت ← نشانی کوتاه. پیوند تکراری دوباره ساخته نمی‌شود."""
    from .models import ShortLink

    target = local(url)
    if not target.startswith("/"):
        return url
    now = timezone.now()
    link = ShortLink.objects.filter(target=target, expires_at__gt=now + timezone.timedelta(days=3)).first()
    if link is None:
        for _ in range(8):
            code = "".join(secrets.choice(ALPHABET) for _ in range(7))
            if not ShortLink.objects.filter(code=code).exists():
                break
        link = ShortLink.objects.create(code=code, target=target[:500], expires_at=now + timezone.timedelta(days=days))
    base = _base()
    return f"{base}/{prefix}/{link.code}" if base else f"{settings.SITE_URL}/s/{link.code}/"


def personal(url, campaign, mobile, prefix="l", days=30):
    """پیوند کوتاه شخصی یک گیرندهٔ کمپین (اگر قبلاً ساخته شده، همان)؛ کلیک او در گزارش کمپین دیده می‌شود."""
    from .models import ShortLink

    target = local(url) or "/"
    if not target.startswith("/"):
        return url
    now = timezone.now()
    link = ShortLink.objects.filter(campaign=campaign, mobile=mobile, target=target[:500]).first()
    if link is None:
        for _ in range(8):
            code = "".join(secrets.choice(ALPHABET) for _ in range(7))
            if not ShortLink.objects.filter(code=code).exists():
                break
        link = ShortLink.objects.create(code=code, target=target[:500], campaign=campaign, mobile=mobile,
                                        expires_at=now + timezone.timedelta(days=days))
    base = _base()
    return f"{base}/{prefix}/{link.code}" if base else f"{settings.SITE_URL}/s/{link.code}/"


def with_sl(link):
    """مقصد پیوند؛ پیوند کمپین ?sl=کد می‌گیرد تا سایت کلیک را (بدون ربات‌ها) ثبت کند و کوکی منبع بگذارد."""
    if not link.campaign_id:
        return link.target
    sep = "&" if "?" in link.target else "?"
    return f"{link.target}{sep}sl={link.code}"


def resolve(code):
    """مسیر مقصد یا None."""
    from django.db.models import F

    from .models import ShortLink

    code = (code or "").strip().lower()[:12]
    link = ShortLink.objects.filter(code=code).first()
    if link is None or (link.expires_at and link.expires_at < timezone.now()):
        return None
    ShortLink.objects.filter(pk=link.pk).update(hits=F("hits") + 1)
    return with_sl(link)


def view(request, code):
    target = resolve(code)
    if not target:
        raise Http404
    return HttpResponseRedirect(target)
