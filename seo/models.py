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


class SeoSettings(models.Model):
    """تنظیمات سئو برای موتورهای جستجو و هوش مصنوعی (یک ردیف)."""

    indexnow_enabled = models.BooleanField(
        "ارسال خودکار به IndexNow", default=True,
        help_text="هر بار محصول، قیمت، مقاله یا برگه تغییر کند، نشانی‌اش فوراً به Bing و Yandex خبر داده می‌شود.",
    )
    indexnow_key = models.CharField("کلید IndexNow", max_length=64, blank=True, editable=False)
    indexnow_last_at = models.DateTimeField("آخرین ارسال", null=True, blank=True, editable=False)
    indexnow_last_status = models.CharField("نتیجهٔ آخرین ارسال", max_length=300, blank=True, editable=False)
    indexnow_total = models.PositiveIntegerField("تعداد نشانی‌های ارسال‌شده", default=0, editable=False)
    bing_verification = models.CharField(
        "کد تأیید Bing", max_length=100, blank=True,
        help_text="فقط مقدار content از تگ msvalidate.01 که Bing Webmaster Tools می‌دهد؛ مثل 1A2B3C4D5E...",
    )
    llms_about = models.TextField(
        "معرفی فروشگاه برای هوش مصنوعی", blank=True,
        help_text="چند جملهٔ روشن و دقیق دربارهٔ ایران کارپت (از کی فعالید، کجا هستید، از کدام کارخانه‌ها می‌فروشید، ارسال، ضمانت و...). "
                  "بالای فایل /llms.txt می‌آید.",
    )

    rewrite_enabled = models.BooleanField(
        "انتشار خودکار مقاله‌های بازنویسی‌شده", default=True,
        help_text="هر روز به «تعداد انتشار در روز» مقالهٔ بازنویسی‌شده (به ترتیب اولویت) روی همان نشانی قبلی منتشر می‌شود؛ نسخهٔ قبلی نگه داشته می‌شود.")
    rewrite_hour = models.PositiveSmallIntegerField("ساعت انتشار روزانه", default=9, help_text="به وقت تهران، ۰ تا ۲۳")
    rewrite_per_day = models.PositiveSmallIntegerField("تعداد انتشار در روز", default=2)
    rewrite_review_days = models.PositiveSmallIntegerField(
        "مهلت بررسی (روز)", default=2, help_text="متن تازه این مدت در پنل می‌ماند تا اگر خواستید ویرایش یا رد کنید؛ بعد خودکار منتشر می‌شود.")
    rewrite_repo = models.CharField("مخزن گیت‌هاب متن‌ها", max_length=100, default="itwman/irancarpet", blank=True,
                                    help_text="متن‌های تازه از پوشهٔ content/rewrites/posts این مخزن خوانده می‌شود")
    rewrite_branch = models.CharField("شاخه", max_length=50, default="main", blank=True)
    rewrite_last_sync = models.DateTimeField("آخرین دریافت از گیت‌هاب", null=True, blank=True, editable=False)
    rewrite_last_status = models.CharField("نتیجهٔ آخرین دریافت", max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = "تنظیمات سئو و هوش مصنوعی"
        verbose_name_plural = verbose_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        if not obj.indexnow_key:
            import secrets

            # فقط اگر هنوز کسی کلید نساخته (دو درخواست هم‌زمان کلید یکدیگر را عوض نکنند)
            cls.objects.filter(pk=obj.pk, indexnow_key="").update(indexnow_key=secrets.token_hex(16))
            obj.refresh_from_db()
        return obj
