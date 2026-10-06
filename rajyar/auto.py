"""ارسال خودکار به کانال‌ها: فرش تصادفی روزانه (بدون تکرار) و تصویر هفتگی لیست قیمت.

هر ۱۰ دقیقه از کارهای دوره‌ای (growth.jobs.run_all) صدا زده می‌شود. هر نوبت فقط یک بار فرستاده می‌شود
(ردیف RajyarPost با «نوبت» یکتا)، حتی اگر کارها دوباره یا هم‌زمان اجرا شوند.
"""
import logging

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from .models import RajyarPost, RajyarSettings

log = logging.getLogger(__name__)
WINDOW = timezone.timedelta(hours=2)  # اگر سرور در زمان نوبت خاموش بود، تا ۲ ساعت بعد هنوز فرستاده می‌شود


def ready(s):
    return s.enabled and s.api_key and s.channel_ids


def _claim(slot, kind):
    try:
        with transaction.atomic():
            return RajyarPost.objects.create(slot=slot, kind=kind, status=RajyarPost.Status.SCHEDULED)
    except IntegrityError:
        return None


# ------------------------------------------------------------------ فرش روزانه
def candidates(s):
    from catalog.models import Product

    qs = (Product.objects.published().filter(image__isnull=False, sale_status="available")
          .exclude(stock_status="outofstock").exclude(min_price=None))
    albums = list(s.daily_albums.values_list("pk", flat=True)) if s.pk else []
    if albums:
        qs = qs.filter(album_id__in=albums)
    return qs


def pick_product(s):
    """فرشی که هنوز به کانال‌ها نرفته؛ اگر همه رفته‌اند، آن‌که دیرتر از همه رفته (دور تازه)."""
    qs = candidates(s)
    sent = RajyarPost.objects.exclude(status=RajyarPost.Status.FAILED).exclude(product=None).values("product_id")
    fresh = qs.exclude(pk__in=sent)
    p = fresh.order_by("?").first()
    if p is None:
        last = Max("rajyar_posts__created_at", filter=~Q(rajyar_posts__status=RajyarPost.Status.FAILED))
        p = qs.annotate(last=last).order_by("last", "?").first()
    return p


def send_daily(s, slot=None):
    from .client import send

    post = _claim(slot, RajyarPost.Kind.DAILY) if slot else RajyarPost(kind=RajyarPost.Kind.DAILY)
    if post is None:
        return None
    p = pick_product(s)
    if p is None:
        post.status, post.error = RajyarPost.Status.FAILED, "فرش موجود و عکس‌داری برای ارسال نیست."
        post.save()
        return post
    return send(type(p).objects.select_related("image", "primary_category").get(pk=p.pk), s=s, force_new=True, post=post)


# ------------------------------------------------------------------ لیست قیمت هفتگی
def weekly_body(s, image_url, data, sizes, when=None):
    from django.conf import settings

    from core.templatetags.fa import fa_num
    from pricing.pricelist import PRICE_LIST_PATH

    from . import pricelist_image as P
    from .client import footer_text

    date = P.date_label(when)
    # قیمت‌ها روی تصویر هست؛ متن پست کوتاه می‌ماند (فقط یک خط معرفی، بدون تکرار تاریخ و عددها)
    import re

    labels = [fa_num(P.short_size(z)) for z in sizes]
    nums = [re.match(r"([\d۰-۹.]+)\s*متری", x) for x in labels]
    if all(nums):
        nums = [m.group(1) for m in nums]
        size_txt = ("، ".join(nums[:-1]) + " و " + nums[-1] if len(nums) > 1 else nums[0]) + " متری"
    else:
        size_txt = "، ".join(labels)
    groups = "، ".join(fa_num(n).replace("فرش ", "") for n, _ in data[:6])
    blocks = [f"💰 میانگین قیمت روز فرش ماشینی کاشان در سایزهای {size_txt} 👆"
              + (f"\n({groups})" if groups and len(groups) < 120 else ""),
              "قیمت همهٔ طرح‌ها و سایزها در سایت 👇"]
    foot = footer_text(s)
    if foot:
        blocks.append(foot)
    url = settings.SITE_URL + PRICE_LIST_PATH
    body = {
        "title": f"قیمت روز فرش ماشینی — {date}", "content": "\n\n".join(blocks), "url": url, "image_url": image_url,
        "tags": ["لیست قیمت فرش", "قیمت فرش ماشینی", "فرش کاشان"],
        "external_id": f"pricelist-{timezone.localtime(when or timezone.now()):%Y%m%d%H%M}", "channels": s.channel_ids,
        "language": "fa", "force_new": True,
    }
    if s.button_text:
        body["buttons"] = [{"text": "لیست کامل قیمت", "url": url}]
    return body


def send_weekly(s, slot=None, when=None):
    from . import pricelist_image as P
    from .client import send_body

    post = _claim(slot, RajyarPost.Kind.WEEKLY) if slot else RajyarPost(kind=RajyarPost.Kind.WEEKLY)
    if post is None:
        return None
    png, data, sizes = P.render(s, when)
    if not data:
        post.status, post.error = RajyarPost.Status.FAILED, "برای سایزهای انتخاب‌شده قیمتی پیدا نشد."
        post.save()
        return post
    url = P.save(png, when)
    post.image = url[:300]
    return send_body(weekly_body(s, url, data, sizes, when), post, s)


# ------------------------------------------------------------------ زمان‌بندی
def run(now=None):
    """نوبت‌هایی که وقتشان رسیده را می‌فرستد؛ خروجی: فهرست ارسال‌ها."""
    s = RajyarSettings.load()
    if not ready(s):
        return []
    now = timezone.localtime(now or timezone.now())
    tz = now.tzinfo
    done = []
    if s.daily_enabled:
        for t in s.daily_slots():
            at = timezone.datetime.combine(now.date(), t, tzinfo=tz)
            if at <= now < at + WINDOW:
                try:
                    post = send_daily(s, f"daily:{now:%Y%m%d}:{t:%H%M}")
                except Exception:  # noqa: BLE001
                    log.exception("rajyar daily")
                    post = None
                if post:
                    done.append(post)
    if s.weekly_enabled and now.weekday() == s.weekly_day:
        at = timezone.datetime.combine(now.date(), s.weekly_time, tzinfo=tz)
        if at <= now < at + WINDOW:
            try:
                post = send_weekly(s, f"weekly:{now:%Y%m%d}", now)
            except Exception:  # noqa: BLE001
                log.exception("rajyar weekly")
                post = None
            if post:
                done.append(post)
    return done


def next_runs(s, now=None):
    """برای نمایش در تنظیمات: زمان نوبت‌های بعدی."""
    now = timezone.localtime(now or timezone.now())
    tz, out = now.tzinfo, []
    if s.daily_enabled:
        for t in s.daily_slots():
            at = timezone.datetime.combine(now.date(), t, tzinfo=tz)
            out.append(("فرش روزانه", at if at > now else at + timezone.timedelta(days=1)))
    if s.weekly_enabled:
        days = (s.weekly_day - now.weekday()) % 7
        at = timezone.datetime.combine(now.date() + timezone.timedelta(days=days), s.weekly_time, tzinfo=tz)
        if at <= now:
            at += timezone.timedelta(days=7)
        out.append(("لیست قیمت هفتگی", at))
    return sorted(out, key=lambda x: x[1])
