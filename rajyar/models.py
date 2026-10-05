"""اتصال فروشگاه به رج‌یار (rajyar.ir) برای انتشار محصولات در کانال‌های تلگرام، ایتا، بله، روبیکا و…"""
from django.db import models
from django.utils import timezone


class RajyarSettings(models.Model):
    enabled = models.BooleanField("اتصال فعال باشد", default=False)
    url = models.URLField("نشانی API رج‌یار", default="https://rajyar.ir/api/v1/")
    api_key = models.CharField("کلید API", max_length=200, blank=True,
                               help_text="در رج‌یار ← کلیدهای API ساخته می‌شود؛ مثل rjy_…")
    channels = models.CharField(
        "کانال‌ها", max_length=200, blank=True,
        help_text="شناسهٔ کانال‌های رج‌یار با ویرگول، مثل 2 یا 2,5. فهرست کانال‌ها بعد از «بررسی اتصال» کنار صفحه دیده می‌شود. "
                  "تا خالی است چیزی فرستاده نمی‌شود (تا محصولات به کانال‌های دیگرِ این کلید نروند).")
    auto_new = models.BooleanField("فرش‌های تازه خودکار فرستاده شوند", default=False,
                                   help_text="هر محصولی که برای اولین بار منتشر شود و عکس داشته باشد، به کانال‌ها می‌رود.")
    interval_minutes = models.PositiveSmallIntegerField("فاصلهٔ بین پست‌ها در ارسال گروهی (دقیقه)", default=30)
    tags = models.CharField("برچسب‌های ثابت", max_length=200, blank=True, default="فرش ماشینی، فرش کاشان، ایران کارپت",
                            help_text="با ویرگول؛ در کانال‌هایی که هشتگ روشن است، هشتگ می‌شوند.")
    footer = models.CharField("خط پایانی پست", max_length=200, blank=True,
                              default="خرید نقدی و اقساطی، ارسال مستقیم از کاشان")
    channels_cache = models.JSONField("کانال‌های مجاز (از آخرین بررسی)", default=list, blank=True, editable=False)
    last_check = models.CharField("نتیجهٔ آخرین بررسی", max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = "تنظیمات رج‌یار"
        verbose_name_plural = verbose_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def channel_ids(self):
        out = []
        for x in (self.channels or "").replace("،", ",").split(","):
            x = x.strip()
            if x.isdigit():
                out.append(int(x))
        return out


class RajyarPost(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "فرستاده شد"
        SCHEDULED = "scheduled", "در صف انتشار"
        PUBLISHED = "published", "منتشر شد"
        PARTIAL = "partial", "بخشی منتشر شد"
        FAILED = "failed", "خطا"
        CANCELLED = "cancelled", "لغو شد"

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="rajyar_posts", verbose_name="محصول")
    remote_id = models.PositiveIntegerField("شناسه در رج‌یار", null=True, blank=True)
    status = models.CharField("وضعیت", max_length=12, choices=Status.choices, default=Status.SENT, db_index=True)
    publish_at = models.DateTimeField("زمان انتشار", null=True, blank=True)
    links = models.JSONField("پیوند پیام‌ها", default=list, blank=True)
    error = models.CharField("خطا", max_length=300, blank=True)
    created_at = models.DateTimeField("زمان ارسال", default=timezone.now, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "ارسال به کانال"
        verbose_name_plural = "ارسال‌ها به کانال‌ها (رج‌یار)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product} → رج‌یار"
