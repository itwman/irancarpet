from django.db import models
from django.utils import timezone

from . import texts


class CrmSettings(models.Model):
    """تنظیمات پیامک سفارش، پیگیری سفارش ناتمام و باشگاه مشتریان (یک ردیف)."""

    order_sms = models.BooleanField("پیامک ثبت سفارش به مشتری", default=True)
    order_text = models.TextField("متن ثبت سفارش", default=texts.ORDER)
    order_installment_text = models.TextField("متن ثبت سفارش اقساطی", default=texts.ORDER_INSTALLMENT)
    admin_sms = models.BooleanField("پیامک سفارش تازه به مدیران", default=True,
                                    help_text="به شماره‌های «تنظیمات ← فروش و ارسال ← موبایل مدیران»")
    admin_text = models.TextField("متن سفارش تازه (مدیر)", default=texts.ADMIN)
    paid_text = models.TextField("متن پرداخت موفق (مشتری)", default=texts.PAID,
                                 help_text="اگر در «پیامک» شمارهٔ قالب تأیید سفارش sms.ir وارد شده باشد، همان قالب فرستاده می‌شود.")
    admin_paid_text = models.TextField("متن پرداخت موفق (مدیر)", default=texts.ADMIN_PAID)
    status_sms = models.BooleanField("پیامک تغییر وضعیت سفارش", default=True, help_text="ارسال، تحویل و لغو؛ وقتی وضعیت را در پنل عوض می‌کنید")
    shipped_text = models.TextField("متن ارسال شد", default=texts.SHIPPED)
    completed_text = models.TextField("متن تحویل شد", default=texts.COMPLETED)
    cancelled_text = models.TextField("متن لغو شد", default=texts.CANCELLED)

    remind_enabled = models.BooleanField("پیگیری سفارش‌های پرداخت‌نشده", default=True)
    remind_hours = models.CharField("زمان یادآوری‌ها (ساعت بعد از ثبت)", max_length=40, default="1,24,72",
                                    help_text="با ویرگول؛ برای هر عدد یک پیامک. متن اول، دوم و سوم به ترتیب.")
    remind_text_1 = models.TextField("یادآوری اول", default=texts.REMIND_1)
    remind_text_2 = models.TextField("یادآوری دوم (نوسان قیمت)", default=texts.REMIND_2)
    remind_text_3 = models.TextField("یادآوری سوم (آخرین مهلت)", default=texts.REMIND_3)

    winback_auto = models.BooleanField("کد تخفیف خودکار برای مشتریانی که مدتی نخریده‌اند", default=False)
    winback_days = models.PositiveIntegerField("بعد از چند روز بی‌خریدی", default=180)
    winback_amount = models.PositiveBigIntegerField("مبلغ تخفیف (تومان)", default=2_000_000)
    winback_min_order = models.PositiveBigIntegerField("حداقل خرید (تومان)", default=40_000_000)
    winback_valid_days = models.PositiveIntegerField("مهلت استفاده (روز)", default=30)
    winback_text = models.TextField("متن پیامک بازگشت", default=texts.WINBACK)

    points_enabled = models.BooleanField("امتیاز خرید", default=True, help_text="امتیاز از خریدهای پرداخت‌شده؛ مشتری در «حساب کاربری ← باشگاه» آن را به کد تخفیف تبدیل می‌کند")
    points_per = models.PositiveBigIntegerField("هر چند تومان خرید = یک امتیاز", default=1_000_000)
    point_value = models.PositiveIntegerField("ارزش هر امتیاز (تومان)", default=10_000, help_text="۱۰ هزار تومان برای هر میلیون یعنی ۱٪ برگشت")
    points_min_redeem = models.PositiveIntegerField("کمترین امتیاز برای تبدیل", default=100)
    points_min_order = models.PositiveBigIntegerField("حداقل خرید برای کد امتیاز (تومان)", default=0)
    points_valid_days = models.PositiveIntegerField("مهلت کد امتیاز (روز)", default=60)
    points_since = models.DateField("امتیاز خریدهای از این تاریخ به بعد", null=True, blank=True,
                                    help_text="خالی یعنی خریدهای قبلی (دورهٔ وردپرس هم) امتیاز دارند")

    birthday_enabled = models.BooleanField("هدیهٔ تولد", default=True, help_text="مشتری تاریخ تولدش را در صفحهٔ باشگاه ثبت می‌کند")
    birthday_amount = models.PositiveBigIntegerField("مبلغ هدیهٔ تولد (تومان)", default=1_000_000)
    birthday_min_order = models.PositiveBigIntegerField("حداقل خرید برای کد تولد (تومان)", default=20_000_000)
    birthday_valid_days = models.PositiveIntegerField("مهلت کد تولد (روز)", default=14)
    birthday_text = models.TextField("متن پیامک تولد", default=texts.BIRTHDAY)

    cart_enabled = models.BooleanField("یادآوری سبد خرید رهاشده", default=True,
                                       help_text="برای مشتری واردشده‌ای که فرش در سبد گذاشته و سفارش نداده؛ یک‌بار")
    cart_hours = models.PositiveSmallIntegerField("چند ساعت بعد از آخرین تغییر سبد", default=3)
    cart_text = models.TextField("متن یادآوری سبد", default=texts.CART)

    review_reward_enabled = models.BooleanField("جایزهٔ نظر با عکس", default=True,
                                                help_text="بعد از تأیید نظرِ خریدار که عکس دارد، کد هدیه پیامک می‌شود (هر شماره هر ۶۰ روز یک‌بار)")
    review_reward_amount = models.PositiveBigIntegerField("مبلغ جایزهٔ نظر (تومان)", default=500_000)
    review_reward_min_order = models.PositiveBigIntegerField("حداقل خرید برای کد نظر (تومان)", default=10_000_000)
    review_reward_valid_days = models.PositiveIntegerField("مهلت کد نظر (روز)", default=60)
    review_reward_text = models.TextField("متن پیامک جایزهٔ نظر", default=texts.REVIEW_REWARD)

    album_text = models.TextField("متن پیش‌فرض اطلاع افزایش قیمت آلبوم", default=texts.ALBUM,
                                  help_text="متغیرها: {album} نام آلبوم و {date} زمان افزایش. از «آلبوم‌های قیمت ← عملیات گروهی» ساخته می‌شود.")

    vip_total = models.PositiveBigIntegerField("مشتری وفادار از جمع خرید (تومان)", default=150_000_000)
    vip_orders = models.PositiveSmallIntegerField("یا از تعداد سفارش پرداخت‌شده", default=2)
    short_links = models.BooleanField("پیوند کوتاه در پیامک‌ها (crpt.ir)", default=True,
                                      help_text="دامنهٔ کوتاه همان «تنظیمات ← همکاری در فروش» است؛ اگر خالی باشد پیوند با دامنهٔ اصلی ساخته می‌شود")
    marketing_footer = models.CharField("پایان پیامک‌های تبلیغاتی", max_length=40, default="لغو۱۱", blank=True,
                                        help_text="برای پیامک‌های تبلیغاتی (کمپین و بازگشت)؛ پیامک‌های سفارش این را ندارند.")

    class Meta:
        verbose_name = "تنظیمات باشگاه مشتریان"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def hours(self):
        out = []
        for x in (self.remind_hours or "").replace("،", ",").split(","):
            x = x.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
            if x.replace(".", "", 1).isdigit():
                out.append(float(x))
        return sorted(out)[:3]


class Campaign(models.Model):
    class Segment(models.TextChoices):
        BUYERS = "buyers", "همهٔ خریداران"
        INACTIVE = "inactive", "خریدارانی که مدتی نخریده‌اند"
        VIP = "vip", "مشتریان وفادار"
        ACTIVE = "active", "فعال (خرید در ۶ ماه اخیر)"
        NEW = "new", "خریداران تازه (۶۰ روز اخیر)"
        AT_RISK = "at_risk", "در خطر ریزش (۶ تا ۱۲ ماه بی‌خرید)"
        LOST = "lost", "از دست رفته (بیش از یک سال)"
        ALBUM = "album", "علاقه‌مندان یک آلبوم (دیده، در سبد یا سفارش ناتمام)"
        UNPAID = "unpaid", "سفارش داده ولی هرگز پرداخت نکرده"
        REGISTERED = "registered", "ثبت‌نام‌کرده بدون سفارش"
        CUSTOM = "custom", "شماره‌های دلخواه"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        SENDING = "sending", "در حال ارسال"
        DONE = "done", "ارسال شد"
        STOPPED = "stopped", "متوقف شد"
        FAILED = "failed", "ناموفق"

    title = models.CharField("عنوان", max_length=120)
    segment = models.CharField("گیرنده‌ها", max_length=12, choices=Segment.choices, default=Segment.BUYERS)
    inactive_days = models.PositiveIntegerField("بی‌خریدی دست‌کم (روز)", default=180, help_text="فقط برای «مدتی نخریده‌اند»")
    album = models.ForeignKey("pricing.Album", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="آلبوم",
                              help_text="فقط برای «علاقه‌مندان یک آلبوم»")
    event_date = models.CharField("زمان افزایش قیمت", max_length=60, blank=True, help_text="برای متغیر {date}؛ مثل «شنبه ۲۶ مهر»")
    custom_numbers = models.TextField("شماره‌های دلخواه", blank=True, help_text="هر شماره در یک خط")
    discount = models.PositiveBigIntegerField("مبلغ تخفیف (تومان)", default=2_000_000, help_text="۰ یعنی پیامک بدون کد تخفیف")
    min_order = models.PositiveBigIntegerField("حداقل خرید (تومان)", default=40_000_000)
    valid_days = models.PositiveIntegerField("مهلت استفاده (روز)", default=30)
    text = models.TextField("متن پیامک", default=texts.CAMPAIGN,
                            help_text="{name} نام، {code} کد تخفیف شخصی، {discount} مبلغ تخفیف، {min} حداقل خرید، {until} تاریخ پایان، {site} نشانی سایت")
    code_prefix = models.CharField(max_length=8, blank=True, editable=False)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.DRAFT)
    total = models.PositiveIntegerField("گیرنده", default=0)
    sent = models.PositiveIntegerField("ارسال‌شده", default=0)
    failed = models.PositiveIntegerField("ناموفق", default=0)
    last_error = models.CharField("آخرین خطا", max_length=300, blank=True)
    created_at = models.DateTimeField("ساخته شده", default=timezone.now)
    started_at = models.DateTimeField("شروع ارسال", null=True, blank=True)
    finished_at = models.DateTimeField("پایان ارسال", null=True, blank=True)

    class Meta:
        verbose_name = "کمپین"
        verbose_name_plural = "کمپین‌های پیامکی و کد تخفیف"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code_prefix:
            self.code_prefix = f"C{self.pk}"
            Campaign.objects.filter(pk=self.pk).update(code_prefix=self.code_prefix)


class SmsLog(models.Model):
    class Kind(models.TextChoices):
        ORDER = "order", "ثبت سفارش"
        ADMIN = "admin", "خبر به مدیر"
        PAID = "paid", "پرداخت موفق"
        STATUS = "status", "تغییر وضعیت"
        REMIND = "remind", "یادآوری پرداخت"
        CAMPAIGN = "campaign", "کمپین"
        WINBACK = "winback", "بازگشت مشتری"
        BIRTHDAY = "birthday", "تولد"
        CART = "cart", "سبد رهاشده"
        REVIEW = "review", "جایزهٔ نظر"

    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, db_index=True)
    order = models.ForeignKey("shop.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="sms_logs")
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs")
    text = models.TextField("متن")
    ok = models.BooleanField("رسید", default=False)
    error = models.CharField("خطا", max_length=300, blank=True)
    created_at = models.DateTimeField("زمان", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "پیامک فرستاده‌شده"
        verbose_name_plural = "پیامک‌های فرستاده‌شده"
        ordering = ["-created_at"]


class ShortLink(models.Model):
    """پیوند کوتاه پیامک‌ها: crpt.ir/o/<کد> ← مسیری در سایت."""

    code = models.CharField(max_length=12, unique=True)
    target = models.CharField(max_length=500, db_index=True)
    hits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "پیوند کوتاه"
        verbose_name_plural = "پیوندهای کوتاه"

    def __str__(self):
        return self.code


class CartSnapshot(models.Model):
    """آخرین سبد خرید مشتری واردشده (برای یادآوری و بازگرداندن سبد در دستگاه دیگر)."""

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE, related_name="cart_snapshot")
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "سبد ذخیره‌شده"
        verbose_name_plural = "سبدهای ذخیره‌شده"


class ProductView(models.Model):
    """فرشی که مشتری واردشده دیده (برای اطلاع افزایش قیمت آلبوم)."""

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="+")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+")
    seen_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = [("user", "product")]


class PointRedeem(models.Model):
    """تبدیل امتیاز به کد تخفیف. اگر کد بی‌استفاده منقضی شود، امتیازش برمی‌گردد."""

    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    points = models.PositiveIntegerField("امتیاز")
    coupon = models.ForeignKey("shop.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="کد تخفیف")
    created_at = models.DateTimeField("زمان", default=timezone.now)

    class Meta:
        verbose_name = "تبدیل امتیاز"
        verbose_name_plural = "تبدیل‌های امتیاز"
        ordering = ["-created_at"]
