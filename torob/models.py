from decimal import Decimal

from django.db import models


class TorobSettings(models.Model):
    """تنظیمات فید ترب (معادل افزونهٔ irancarpet-torob-pricing وردپرس)."""

    enabled = models.BooleanField("فید ترب فعال", default=True)
    emalls_enabled = models.BooleanField("فید ایمالز فعال", default=True,
                                         help_text="نشانی برای پنل ایمالز: https://irancarpet.net (همان روش افزونهٔ رسمی ووکامرس ایمالز)")
    only_album = models.BooleanField("فقط محصولات دارای آلبوم قیمت", default=True,
                                     help_text="مثل سایت قبلی؛ محصولات بدون آلبوم در ترب نمی‌آیند")
    per_page = models.PositiveIntegerField("تعداد در هر صفحه", default=100, help_text="ترب حداقل ۱۰۰ می‌خواهد")
    price_divisor = models.PositiveIntegerField("تقسیم‌کنندهٔ قیمت", default=1, help_text="برای تبدیل ریال به تومان ۱۰")
    tax_percent = models.DecimalField("درصد مالیات افزوده", max_digits=6, decimal_places=2, default=Decimal("0"))
    decrease_rate = models.DecimalField("درصد کاهش قیمت در ترب", max_digits=6, decimal_places=2, default=Decimal("0"))
    round_to = models.PositiveIntegerField("گرد کردن قیمت ترب به", default=0, help_text="۰ = بدون گرد کردن")
    title_suffix = models.CharField("پسوند عنوان", max_length=100, blank=True)
    registry_text = models.CharField("متن رجیستر", max_length=100, blank=True)
    guarantee_attr = models.CharField("نامک ویژگی گارانتی", max_length=100, blank=True)
    excluded = models.ManyToManyField("catalog.Product", blank=True, related_name="+", verbose_name="محصولات مستثنی از ترب")

    class Meta:
        verbose_name = verbose_name_plural = "تنظیمات فید ترب"

    def __str__(self):
        return "فید ترب"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete("torob_rows")
