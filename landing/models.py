"""صفحه‌های فرود ترکیبی برای جستجوهای دقیق مثل «فرش ۱۲۰۰ شانه کرم ۹ متری».

صفحه‌ها خودکار از روی فرش‌های موجود ساخته می‌شوند (sync) و متن، عنوان و توضیح هرکدام از پنل قابل تغییر است.
"""
from django.db import models
from django.utils import timezone


class LandingPage(models.Model):
    slug = models.SlugField("نامک", max_length=200, unique=True, allow_unicode=True)
    title = models.CharField("عنوان صفحه (H1)", max_length=200)
    reeds = models.ForeignKey("catalog.AttributeTerm", null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                              verbose_name="شانه")
    size = models.ForeignKey("pricing.Size", null=True, blank=True, on_delete=models.CASCADE, related_name="+", verbose_name="سایز")
    color = models.ForeignKey("finder.Need", null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                              verbose_name="رنگ", limit_choices_to={"group": "color"})
    style = models.ForeignKey("finder.Need", null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                              verbose_name="سبک یا جنس (اختیاری)", help_text="مثل «برجسته» یا «سنتی»؛ برای صفحه‌های دستی")
    auto = models.BooleanField("ساخت خودکار", default=True, editable=False)

    intro = models.TextField("متن بالای صفحه", blank=True, help_text="خالی بماند تا متن از روی فرش‌ها و قیمت‌ها خودکار ساخته شود.")
    content = models.TextField("متن پایین صفحه", blank=True)
    seo_title = models.CharField("عنوان در گوگل", max_length=255, blank=True)
    seo_description = models.TextField("توضیح در گوگل", blank=True)
    is_active = models.BooleanField("فعال", default=True)

    count = models.PositiveIntegerField("تعداد فرش", default=0, editable=False)
    min_price = models.PositiveBigIntegerField("کمترین قیمت", null=True, blank=True, editable=False)
    max_price = models.PositiveBigIntegerField("بیشترین قیمت", null=True, blank=True, editable=False)
    synced_at = models.DateTimeField("آخرین به‌روزرسانی", default=timezone.now, editable=False)

    class Meta:
        verbose_name = "صفحهٔ فرود"
        verbose_name_plural = "صفحه‌های فرود (سایز، شانه، رنگ)"
        ordering = ["-count"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/carpets/{self.slug}/"

    @property
    def last_updated(self):
        return self.synced_at
