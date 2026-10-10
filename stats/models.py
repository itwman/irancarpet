"""آمار بازدید سایت، سبک و بدون سرویس بیرونی.

Hit: هر بازدید صفحه (از طریق یک درخواست کوچک جاوااسکریپتی که ربات‌ها معمولاً اجرا نمی‌کنند)، افزودن به سبد و ثبت سفارش.
ریزها فقط RETENTION_DAYS روز می‌مانند؛ هر شب در جدول‌های روزانهٔ کوچک (Daily*) خلاصه می‌شوند و ریزهای کهنه پاک می‌شوند.
نشانی IP و اطلاعات شخصی ذخیره نمی‌شود؛ بازدیدکننده فقط با یک شناسهٔ تصادفی در کوکی شناخته می‌شود.
"""
from django.db import models

RETENTION_DAYS = 45

SRC_LABELS = {
    "search": "جستجو در موتورهای جستجو",
    "social": "شبکه‌های اجتماعی و پیام‌رسان‌ها",
    "compare": "سایت‌های مقایسهٔ قیمت",
    "referral": "سایت‌های دیگر",
    "sms": "پیامک کمپین",
    "utm": "کمپین با UTM",
    "affiliate": "همکاران فروش",
    "app": "اپلیکیشن",
    "direct": "مستقیم یا نامشخص",
}


class Hit(models.Model):
    class Kind(models.TextChoices):
        VIEW = "v", "بازدید صفحه"
        CART = "c", "افزودن به سبد"
        ORDER = "o", "ثبت سفارش"

    at = models.DateTimeField()
    day = models.DateField(db_index=True)
    kind = models.CharField(max_length=1, choices=Kind.choices, default=Kind.VIEW)
    path = models.CharField(max_length=255, blank=True)
    product_id = models.PositiveIntegerField(null=True, blank=True)
    visitor = models.CharField(max_length=16)
    entry = models.BooleanField(default=False)   # اولین صفحهٔ یک نشست (۳۰ دقیقه)
    new = models.BooleanField(default=False)     # اولین بازدید این مرورگر
    src = models.CharField(max_length=10, default="direct")
    src_name = models.CharField(max_length=60, blank=True)
    medium = models.CharField(max_length=40, blank=True)
    utm_campaign = models.CharField(max_length=80, blank=True)
    campaign_id = models.PositiveIntegerField(null=True, blank=True)  # کمپین پیامکی
    link_id = models.PositiveIntegerField(null=True, blank=True)      # پیوند شخصی گیرنده
    device = models.CharField(max_length=1, default="d")              # m موبایل، t تبلت، d رایانه

    class Meta:
        indexes = [models.Index(fields=["day", "kind"]), models.Index(fields=["campaign_id", "day"]),
                   models.Index(fields=["product_id", "day"])]


class DailyTotal(models.Model):
    day = models.DateField(unique=True)
    views = models.PositiveIntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    new_visitors = models.PositiveIntegerField(default=0)
    mobile = models.PositiveIntegerField(default=0)
    carts = models.PositiveIntegerField(default=0)
    orders = models.PositiveIntegerField(default=0)


class DailyStat(models.Model):
    """روزانه به تفکیک منبع ورود."""

    day = models.DateField(db_index=True)
    src = models.CharField(max_length=10)
    src_name = models.CharField(max_length=60, blank=True)
    medium = models.CharField(max_length=40, blank=True)
    utm_campaign = models.CharField(max_length=80, blank=True)
    campaign_id = models.PositiveIntegerField(default=0, db_index=True)
    views = models.PositiveIntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    carts = models.PositiveIntegerField(default=0)
    orders = models.PositiveIntegerField(default=0)


class DailyPage(models.Model):
    day = models.DateField(db_index=True)
    path = models.CharField(max_length=255)
    views = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    entries = models.PositiveIntegerField(default=0)


class DailyProduct(models.Model):
    day = models.DateField(db_index=True)
    product_id = models.PositiveIntegerField(db_index=True)
    views = models.PositiveIntegerField(default=0)
    visitors = models.PositiveIntegerField(default=0)
    carts = models.PositiveIntegerField(default=0)


class RolledDay(models.Model):
    day = models.DateField(unique=True)
    done_at = models.DateTimeField(auto_now_add=True)
