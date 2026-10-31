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
    shop_api_token = models.CharField(
        "توکن Shop API ترب", max_length=300, blank=True,
        help_text="از پنل ترب ← اطلاعات فروشگاه ← دسترسی API ← ساخت توکن. فقط یک بار نشان داده می‌شود؛ همین‌جا بچسبانید. "
                  "با آن وضعیت فروشگاه و محصولات در ترب و قیمتی که ترب نشان می‌دهد در «پنل ← وضعیت در ترب» دیده می‌شود.")
    shop_state = models.JSONField(default=dict, blank=True, editable=False)   # آخرین پاسخ /shop/ و نتیجهٔ همگام‌سازی
    products_synced_at = models.DateTimeField(null=True, blank=True, editable=False)

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


class TorobProduct(models.Model):
    """کپی وضعیت هر محصول فروشگاه در ترب (Shop API) و مقایسه‌اش با سایت."""

    torob_id = models.CharField(max_length=60, unique=True)
    page_url = models.URLField(max_length=1000, blank=True)
    statuses = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=40, blank=True, db_index=True)   # وضعیت اصلی (اولین) یا «ok»
    price = models.PositiveBigIntegerField(default=0)                     # قیمتی که ترب نشان می‌دهد (تومان)
    availability = models.BooleanField(default=False)
    error_title = models.CharField(max_length=200, blank=True)
    torob_updated_at = models.DateTimeField(null=True, blank=True)
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    site_price = models.PositiveBigIntegerField(default=0)                # قیمتی که باید باشد (همان قاعدهٔ فید ترب)
    site_available = models.BooleanField(default=False)
    problem = models.CharField(max_length=20, blank=True, db_index=True)  # price، stock، missing، 404، ""
    site_status = models.PositiveSmallIntegerField(default=0)             # پاسخ سایت برای page_url (فقط خارج از دسترس‌ها)
    site_location = models.CharField(max_length=1000, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "محصولات در ترب"
