"""همگام‌سازی کاتالوگ میان دو استقرار همین کد: «منبع» (ایران کارپت) و «مقصد» (فرشستان).

منبع: خوراک امن محصولات (feed.py) و دریافت سفارش‌های مقصد.
مقصد: گرفتن محصولات با عنوان، نامک، متن و عکس اختصاصی خودش (sync.py)، جفت کردن کالاهای قدیمی (match.py)،
فرستادن سفارش‌ها به منبع (orders.py) و بازبینی قیمت و موجودی لحظهٔ پرداخت (live.py).
همهٔ کلیدها و تنظیمات از پنل ← تنظیمات ← «همگام‌سازی کاتالوگ».
"""
from django.db import models
from django.utils import timezone

DEFAULT_TITLE = "فرش ماشینی {نقشه} زمینه {رنگ} {شانه} شانه {بافت}"


class MirrorSettings(models.Model):
    # ---------------------------------------------------------------- منبع (ایران کارپت)
    feed_enabled = models.BooleanField("این سایت منبع کاتالوگ است (خوراک برای فرشستان)", default=False,
                                       help_text="فقط روی ایران کارپت روشن شود.")
    # ---------------------------------------------------------------- مقصد (فرشستان)
    enabled = models.BooleanField("محصولات از سایت منبع گرفته شوند", default=False,
                                  help_text="فقط روی فرشستان روشن شود. هر ۱۰ دقیقه قیمت و موجودی، و محصولات تازه یا ویرایش‌شده گرفته می‌شوند.")
    live = models.BooleanField("اعمال تغییرات (خاموش = فقط گزارش)", default=False,
                               help_text="اول خاموش بگذارید و گزارش را ببینید؛ بعد روشن کنید.")
    source_url = models.URLField("نشانی سایت منبع", default="https://irancarpet.net")
    api_key = models.CharField("کلید اتصال", max_length=200, blank=True,
                               help_text="یک رشتهٔ تصادفی بلند؛ در هر دو سایت باید یکی باشد.")
    price_percent = models.DecimalField("تغییر قیمت نسبت به منبع (درصد)", max_digits=5, decimal_places=2, default=0,
                                        help_text="۰ = همان قیمت. مثلاً ۲ یعنی ۲٪ گران‌تر و ‎-۲ یعنی ۲٪ ارزان‌تر.")
    round_to = models.PositiveIntegerField("گرد کردن قیمت به (تومان)", default=10_000,
                                           help_text="فقط وقتی درصد صفر نیست به کار می‌رود.")
    title_pattern = models.CharField("الگوی عنوان فرش", max_length=200, default=DEFAULT_TITLE,
                                     help_text="جای‌خالی‌ها: {نقشه} {رنگ} {شانه} {بافت} {عنوان}. عنوان باید با ایران کارپت فرق کند.")
    skip_categories = models.TextField("این دسته‌های منبع نیایند", blank=True, help_text="هر خط نام یا نامک یک دسته")
    batch = models.PositiveSmallIntegerField("حداکثر محصول تازه در هر نوبت", default=60,
                                             help_text="برای بار اول (دانلود عکس‌ها) کم نگه دارید تا سرور فشار نخورد.")
    push_orders = models.BooleanField("سفارش‌ها در پنل منبع هم ثبت شوند", default=True)
    orders_since = models.DateTimeField("ارسال سفارش‌های ثبت‌شده از", null=True, blank=True,
                                        help_text="خالی = از لحظهٔ روشن شدن همگام‌سازی")
    last_sync_at = models.DateTimeField("آخرین همگام‌سازی", null=True, blank=True, editable=False)
    last_result = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        verbose_name = "تنظیمات همگام‌سازی کاتالوگ"
        verbose_name_plural = verbose_name

    def __str__(self):
        return "همگام‌سازی کاتالوگ"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_target(self):
        return bool(self.enabled and self.api_key and self.source_url)


class MirrorLink(models.Model):
    """مقصد: پیوند محصول این سایت به محصول منبع."""

    source_pk = models.PositiveIntegerField("شناسه در منبع", unique=True)
    product = models.OneToOneField("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="mirror",
                                   verbose_name="محصول")
    source_title = models.CharField("عنوان در منبع", max_length=300, blank=True)
    source_modified = models.CharField(max_length=40, blank=True, editable=False)
    stock_hash = models.CharField(max_length=40, blank=True, editable=False)
    vmap = models.JSONField(default=dict, blank=True, editable=False)   # شناسهٔ تنوع منبع ← تنوع این‌جا
    omap = models.JSONField(default=dict, blank=True, editable=False)   # شناسهٔ فرصت ویژهٔ منبع ← فرصت این‌جا
    legacy = models.BooleanField("کالای قدیمی جفت‌شده", default=False)
    excluded = models.BooleanField("نیاید (پنهان)", default=False)
    removed = models.BooleanField("در منبع حذف شده", default=False)
    synced_at = models.DateTimeField("آخرین همگام‌سازی", null=True, blank=True)
    error = models.CharField("خطا", max_length=300, blank=True)

    class Meta:
        verbose_name = "محصول همگام"
        verbose_name_plural = "محصولات همگام"
        ordering = ["-synced_at"]

    def __str__(self):
        return self.source_title or str(self.source_pk)


class MirrorMedia(models.Model):
    """مقصد: عکس منبع ← نسخهٔ بازسازی‌شدهٔ همین سایت (یک بار دانلود)."""

    source_pk = models.PositiveIntegerField(unique=True)
    media = models.ForeignKey("core.Media", on_delete=models.CASCADE, related_name="+")


class MirrorOrder(models.Model):
    """سفارش ردوبدل‌شده. مقصد: role=out (سفارش این‌جا که به منبع رفت). منبع: role=in (سفارشی که از مقصد آمد)."""

    role = models.CharField(max_length=3, choices=[("out", "فرستاده‌شده"), ("in", "دریافت‌شده")])
    order = models.OneToOneField("shop.Order", on_delete=models.CASCADE, related_name="mirror", verbose_name="سفارش")
    remote_ref = models.CharField("شمارهٔ سفارش در سایت دیگر", max_length=40, blank=True)
    last_status = models.CharField(max_length=20, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "سفارش همگام"
        verbose_name_plural = "سفارش‌های همگام"
        constraints = [models.UniqueConstraint(fields=["role", "remote_ref"], condition=models.Q(role="in"),
                                               name="mirror_in_ref_unique")]
