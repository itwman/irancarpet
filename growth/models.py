"""ابزارهای افزایش فروش: «خبرم کن»، گزارش جستجو."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProductAlert(models.Model):
    class Kind(models.TextChoices):
        STOCK = "stock", "موجود شد خبرم کن"
        PRICE = "price", "ارزان شد خبرم کن"

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+", verbose_name="فرش")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                             verbose_name="مشتری")
    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices)
    price_at = models.PositiveBigIntegerField("قیمت هنگام ثبت", null=True, blank=True)
    source = models.CharField("از", max_length=10, default="web")
    created_at = models.DateTimeField("ثبت", default=timezone.now, db_index=True)
    sent_at = models.DateTimeField("خبر داده شد", null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "درخواست «خبرم کن»"
        verbose_name_plural = "درخواست‌های «خبرم کن»"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["product", "mobile", "kind"], condition=models.Q(sent_at__isnull=True),
                                               name="alert_once_open")]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.mobile}"


class SearchLog(models.Model):
    """جستجوهای مشتری‌ها؛ جستجوهای بی‌نتیجه یعنی تقاضایی که جوابش را نداریم."""

    query = models.CharField("جستجو", max_length=200)
    source = models.CharField("کجا", max_length=10, choices=[("web", "سایت"), ("app", "اپ"), ("finder", "فرش‌یاب")])
    hits = models.PositiveIntegerField("دفعات", default=1)
    results = models.PositiveIntegerField("تعداد نتیجه (آخرین بار)", default=0)
    first_seen = models.DateTimeField("اولین بار", default=timezone.now)
    last_seen = models.DateTimeField("آخرین بار", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "جستجوی مشتری"
        verbose_name_plural = "جستجوهای مشتری‌ها"
        ordering = ["-hits"]
        unique_together = [("query", "source")]

    def __str__(self):
        return self.query
