"""اتصال فروشگاه به رج‌یار (rajyar.ir) برای انتشار محصولات در کانال‌های تلگرام، ایتا، بله، روبیکا و…"""
import datetime

from django.db import models
from django.utils import timezone


DEFAULT_FOOTER = "✅ خرید نقدی و اقساطی، ارسال مستقیم از کاشان\n📞 {تلفن}\n{کانال‌ها}"
WEEKDAYS = [(5, "شنبه"), (6, "یکشنبه"), (0, "دوشنبه"), (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنجشنبه"), (4, "جمعه")]


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
    footer = models.TextField(
        "پایان همهٔ پست‌ها", blank=True, default=DEFAULT_FOOTER,
        help_text="هر خط یک خط پست. {کانال‌ها} = نشانی کانال‌ها و صفحه‌های فروشگاه از «تنظیمات ← سایت و تماس» (تلگرام، ایتا، بله، "
                  "اینستاگرام، آپارات، یوتیوب…)، {تلفن}، {موبایل} و {سایت}. خالی = بدون خط پایانی.")
    # متن پست
    PRICE_MODES = [("none", "قیمت نیاید"), ("sizes", "قیمت سایزهای انتخاب‌شده"), ("from", "فقط «قیمت از …»")]
    price_mode = models.CharField("قیمت در پست", max_length=10, choices=PRICE_MODES, default="sizes")
    price_sizes = models.ManyToManyField("pricing.Size", blank=True, related_name="+", verbose_name="سایزهای قیمت",
                                         help_text="خالی = بزرگ‌ترین دو سایز موجود هر فرش. قیمت همیشه با تاریخ روز انتشار می‌آید.")
    show_specs = models.BooleanField("مشخصات (شانه، تراکم، جنس نخ، رنگ) بیاید", default=True)
    show_summary = models.BooleanField("توضیح کوتاه محصول هم بیاید", default=False)
    button_text = models.CharField("متن دکمه/پیوند", max_length=40, blank=True, default="مشاهده و خرید",
                                   help_text="در پیام‌رسان‌هایی که دکمهٔ شیشه‌ای دارند دکمه می‌شود؛ در بقیه پیوند متنی.")
    # لیست قیمت هفتگی (تصویر)
    weekly_enabled = models.BooleanField("لیست قیمت هفتگی (تصویری) فرستاده شود", default=False)
    weekly_day = models.PositiveSmallIntegerField("روز ارسال", choices=WEEKDAYS, default=5)
    weekly_time = models.TimeField("ساعت ارسال", default=datetime.time(10, 0))
    weekly_sizes = models.ManyToManyField("pricing.Size", blank=True, related_name="+", verbose_name="سایزهای لیست قیمت",
                                          help_text="پیش‌فرض ۱۲، ۹ و ۶ متری. برای هر آلبوم، میانگین قیمت فرش‌های آن در این سایزها می‌آید.")
    weekly_group = models.CharField("ردیف‌های لیست قیمت", max_length=10, default="reeds", choices=[
        ("reeds", "بر اساس شانه و جنس نخ (میانگین همهٔ آلبوم‌ها)"), ("album", "هر آلبوم یک ردیف")])
    weekly_reeds = models.CharField("شانه‌ها", max_length=60, blank=True, default="700, 1000, 1200, 1500",
                                    help_text="با ویرگول؛ خالی = همهٔ شانه‌ها. هر شانه با جنس نخش جدا می‌آید، مثل «۷۰۰ شانه پلی‌استر» و «۷۰۰ شانه آکریلیک».")
    weekly_albums = models.ManyToManyField("pricing.Album", blank=True, related_name="+", verbose_name="فقط از آلبوم‌های",
                                           help_text="خالی = همهٔ آلبوم‌ها (در حالت «هر آلبوم یک ردیف»: آلبوم‌های لیست قیمت سایت).")
    weekly_title = models.CharField("عنوان تصویر", max_length=80, default="قیمت روز فرش ماشینی کاشان")
    # پست روزانهٔ فرش‌ها
    daily_enabled = models.BooleanField("هر روز چند فرش تصادفی فرستاده شود", default=False)
    daily_times = models.CharField("ساعت‌های ارسال روزانه", max_length=60, default="10:00, 17:00, 21:00",
                                   help_text="با ویرگول؛ پیش‌فرض صبح، عصر و شب. هر فرش تا وقتی همهٔ فرش‌ها یک بار نرفته‌اند تکرار نمی‌شود.")
    daily_albums = models.ManyToManyField("pricing.Album", blank=True, related_name="+", verbose_name="فقط از آلبوم‌های",
                                          help_text="خالی = همهٔ فرش‌های موجود و عکس‌دار")
    channels_cache = models.JSONField("کانال‌های مجاز (از آخرین بررسی)", default=list, blank=True, editable=False)
    last_check = models.CharField("نتیجهٔ آخرین بررسی", max_length=300, blank=True, editable=False)

    class Meta:
        verbose_name = "تنظیمات رج‌یار"
        verbose_name_plural = verbose_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def daily_slots(self):
        out = []
        for x in (self.daily_times or "").replace("،", ",").split(","):
            x = x.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
            try:
                h, m = (x.split(":") + ["0"])[:2]
                out.append(datetime.time(int(h), int(m)))
            except ValueError:
                continue
        return sorted(set(out))

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

    class Kind(models.TextChoices):
        PRODUCT = "product", "فرش (دستی یا فرش تازه)"
        DAILY = "daily", "فرش روزانه"
        WEEKLY = "weekly", "لیست قیمت هفتگی"

    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.CASCADE, related_name="rajyar_posts",
                                verbose_name="محصول")
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.PRODUCT, db_index=True)
    slot = models.CharField("نوبت خودکار", max_length=40, null=True, blank=True, unique=True, editable=False)
    image = models.CharField("تصویر", max_length=300, blank=True)
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
        return f"{self.product or self.get_kind_display()} → رج‌یار"
