from django.db import models
from django.utils import timezone


class Redirect(models.Model):
    class Match(models.TextChoices):
        EXACT = "exact", "دقیق"
        START = "start", "شروع با"
        REGEX = "regex", "عبارت باقاعده"

    source = models.CharField(
        "آدرس مبدأ", max_length=500, db_index=True,
        help_text="بدون دامنه و بدون / ابتدا و انتها؛ فارسی (decode‌شده). مثلاً product/نام-قدیمی",
    )
    match = models.CharField("نوع تطبیق", max_length=10, choices=Match.choices, default=Match.EXACT)
    target = models.CharField("آدرس مقصد", max_length=1000, blank=True, help_text="برای 410 خالی بماند")
    status_code = models.PositiveSmallIntegerField(
        "کد", default=301, choices=[(301, "301 دائمی"), (302, "302 موقت"), (410, "410 حذف‌شده")]
    )
    is_active = models.BooleanField("فعال", default=True, db_index=True)
    hits = models.PositiveIntegerField("تعداد استفاده", default=0)
    last_hit = models.DateTimeField(null=True, blank=True)
    origin = models.CharField("منشأ", max_length=50, blank=True, help_text="rankmath / old_slug / brand_merge / manual")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "ریدایرکت"
        verbose_name_plural = "ریدایرکت‌ها"
        ordering = ["-hits"]

    def __str__(self):
        return f"/{self.source} → {self.target or self.status_code}"

    @staticmethod
    def normalize(path):
        from urllib.parse import unquote

        return unquote(path or "").strip().strip("/")


class NotFoundLog(models.Model):
    path = models.CharField(max_length=255, unique=True)
    hits = models.PositiveIntegerField(default=1)
    referrer = models.CharField(max_length=1000, blank=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "خطای ۴۰۴"
        verbose_name_plural = "گزارش خطاهای ۴۰۴"
        ordering = ["-hits"]

    def __str__(self):
        return self.path
