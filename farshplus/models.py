from django.db import models
from django.utils import timezone

STATUS_LABELS = {
    "PUBLISHED": "منتشر شده", "PROCESSING": "در حال پردازش", "PENDING_REVIEW": "در انتظار بررسی", "HIDDEN": "پنهان (ناموجود)",
    "ARCHIVED": "بایگانی", "REMOVED": "حذف شده", "QUEUED": "در صف ارسال", "ERROR": "خطا", "": "ارسال نشده",
}


class FarshPlusSettings(models.Model):
    """تنظیمات اتصال به فرش پلاس (یک ردیف) — همان تنظیمات افزونهٔ ووکامرس."""

    enabled = models.BooleanField("اتصال فعال باشد", default=True)
    url = models.URLField("آدرس فرش پلاس", default="https://farshplus.com")
    api_key = models.CharField("کلید API", max_length=200, blank=True)
    auto_sync = models.BooleanField("ارسال خودکار محصولات تازه و تغییرات", default=True)
    default_in_feed = models.BooleanField("نمایش در فید (برای ارسال‌های تکی)", default=True,
                                          help_text="ارسال گروهی همیشه بی‌صدا و بدون نمایش در فید است")
    hashtags = models.BooleanField("دسته‌ها و برچسب‌ها به‌عنوان هشتگ", default=True)
    hide_out_of_stock = models.BooleanField("محصول ناموجود در فرش پلاس پنهان شود", default=True)
    max_images = models.PositiveSmallIntegerField("حداکثر تصویر هر محصول", default=5)
    categories = models.ManyToManyField("catalog.Category", blank=True, verbose_name="فقط این دسته‌ها",
                                        help_text="خالی = همهٔ دسته‌ها")
    # هدیهٔ «اپ فرش پلاس را نصب کن و پیج ما را دنبال کن» (کد شخصی، فقط با موبایل خود مشتری، یک بار)
    gift_enabled = models.BooleanField("هدیهٔ دنبال‌کردن در فرش پلاس فعال باشد", default=True)
    gift_amount = models.PositiveBigIntegerField("مبلغ هدیه (تومان)", default=1_000_000)
    gift_min_order = models.PositiveBigIntegerField("حداقل خرید برای استفاده (تومان)", default=10_000_000)
    gift_valid_days = models.PositiveSmallIntegerField("اعتبار کد (روز)", default=30)
    gift_require_app = models.BooleanField("فقط اگر با اپ (نه وب) وارد فرش پلاس شده باشد", default=True)
    gift_app_url = models.CharField("لینک اپ فرش پلاس", max_length=300, default="https://cafebazaar.ir/app/ir.farshplus.farshplus")
    gift_page_url = models.CharField("پیج ایران کارپت در فرش پلاس", max_length=300, default="https://farshplus.com/@irancarpet/")
    gift_text = models.TextField("پیامک کد هدیه", default="ایران کارپت | ممنون که در فرش پلاس همراه ما شدید.\n"
                                 "کد هدیه {discount} تومانی شما: {code}\nبرای خرید بالای {min} تومان، تا {until}\n{site}",
                                 help_text="{code} {discount} {min} {until} {site}")
    rate_limited_until = models.DateTimeField("توقف تا", null=True, blank=True)
    connection = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    last_scan_at = models.DateTimeField(null=True, blank=True)
    last_refresh_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "تنظیمات فرش پلاس"
        verbose_name_plural = "تنظیمات فرش پلاس"

    def __str__(self):
        return "تنظیمات فرش پلاس"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def limits(self):
        lim = {"daily_products": 200, "max_images": 5, "max_image_mb": 8.0}
        for k, v in (self.connection or {}).get("limits", {}).items():
            if v:
                lim[k] = v
        return lim

    @property
    def paused(self):
        return bool(self.rate_limited_until and self.rate_limited_until > timezone.now())


class FarshPlusItem(models.Model):
    """وضعیت یک محصول در فرش پلاس (معادل متاهای _fpc_* افزونه)."""

    product = models.OneToOneField("catalog.Product", on_delete=models.CASCADE, related_name="farshplus")
    external_id = models.CharField("شناسه نزد فرش پلاس", max_length=64, unique=True)
    enabled = models.BooleanField("ارسال", null=True, blank=True, help_text="خالی = طبق تنظیم ارسال خودکار")
    in_feed = models.BooleanField("نمایش در فید", null=True, blank=True)
    post_id = models.PositiveBigIntegerField("شناسهٔ پست", null=True, blank=True)
    post_url = models.URLField("آدرس پست", max_length=500, blank=True)
    status = models.CharField("وضعیت", max_length=32, blank=True, db_index=True,
                              choices=[(k, v) for k, v in STATUS_LABELS.items()])
    synced_at = models.DateTimeField("آخرین ارسال", null=True, blank=True)
    error = models.CharField("خطا", max_length=500, blank=True)
    images_hash = models.CharField(max_length=64, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True)
    # صف
    queued = models.BooleanField("در صف", default=False, db_index=True)
    mode = models.CharField(max_length=10, default="auto")  # auto | bulk | manual
    attempts = models.PositiveSmallIntegerField(default=0)
    next_try_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "محصول در فرش پلاس"
        verbose_name_plural = "محصولات در فرش پلاس"

    def __str__(self):
        return str(self.product)

    @property
    def has_remote(self):
        return bool(self.post_id) and self.status not in ("REMOVED", "HIDDEN")

    def get_status_display(self):
        return STATUS_LABELS.get(self.status, self.status)

    @staticmethod
    def external_id_for(product):
        return str(product.wp_id) if product.wp_id else f"dj-{product.pk}"
