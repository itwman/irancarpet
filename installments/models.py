from decimal import Decimal

from django.db import models


class InstallmentPlan(models.Model):
    """یک روش خرید اقساطی (مثل «چک صیادی» یا «بازنشستگان — سامانهٔ بتا»). همه‌چیز از پنل قابل تغییر است."""

    class Kind(models.TextChoices):
        CHEQUE = "cheque", "چک صیادی"
        BETA = "beta", "سامانهٔ بتا (بانک رفاه)"
        OTHER = "other", "سایر"

    class DownTiming(models.TextChoices):
        CHECKOUT = "checkout", "همان موقع ثبت سفارش (آنلاین)"
        APPROVAL = "approval", "بعد از تأیید مدارک (آنلاین)"

    title = models.CharField("عنوان", max_length=120)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.CHEQUE)
    summary = models.CharField("خلاصه (یک خط)", max_length=200, blank=True,
                               help_text="مثلاً «۵۰٪ پیش‌پرداخت، بقیه تا ۱۲ ماه با چک صیادی»")
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.IntegerField("ترتیب", default=0)

    # محاسبه
    monthly_rate = models.DecimalField("سود ماهانه (درصد)", max_digits=5, decimal_places=2, default=Decimal("6"),
                                       help_text="سود با راس‌گیری: درصد ماهانه × (میانگین روزهای سررسید ÷ ۳۰)")
    min_down_percent = models.PositiveSmallIntegerField("حداقل پیش‌پرداخت (٪)", default=50)
    max_down_percent = models.PositiveSmallIntegerField("حداکثر پیش‌پرداخت (٪)", default=90)
    down_step = models.PositiveSmallIntegerField("گام انتخاب پیش‌پرداخت (٪)", default=5)
    min_months = models.PositiveSmallIntegerField("کمترین مدت (ماه)", default=1)
    max_months = models.PositiveSmallIntegerField("بیشترین مدت (ماه)", default=12)
    allow_monthly = models.BooleanField("قسط ماهانه", default=True)
    allow_bimonthly = models.BooleanField("قسط دوماه‌یک‌بار", default=True)
    first_due_days = models.PositiveSmallIntegerField(
        "شروع اقساط چند روز بعد از ثبت سفارش", default=14,
        help_text="زمان آماده‌شدن فرش؛ تاریخ اولین قسط = این روز + یک دوره")
    round_to = models.PositiveIntegerField("گرد کردن مبلغ هر قسط به (تومان)", default=100_000, help_text="رو به بالا")
    min_order_amount = models.PositiveBigIntegerField("حداقل مبلغ سبد (تومان)", default=0)
    down_timing = models.CharField("زمان پرداخت پیش‌پرداخت", max_length=10, choices=DownTiming.choices,
                                   default=DownTiming.CHECKOUT)

    # اطلاعاتی که از مشتری گرفته می‌شود
    ask_holder_name = models.BooleanField("نام و نام خانوادگی (صاحب چک / بازنشسته)", default=True)
    ask_national_code = models.BooleanField("کد ملی", default=True)
    ask_cheque_image = models.BooleanField("تصویر یک برگ چک", default=False)
    ask_sayad_id = models.BooleanField("شناسهٔ صیادی چک (۱۶ رقم)", default=False)
    ask_bank_name = models.BooleanField("نام بانک", default=False)
    ask_pensioner_type = models.BooleanField("بازنشسته یا مستمری‌بگیر", default=False)
    ask_retiree_id = models.BooleanField("شمارهٔ بازنشستگی / مستمری", default=False)
    ask_sms_mobile = models.BooleanField("موبایلی که پیامک بانک به آن می‌رود", default=False)

    # متن‌ها
    description = models.TextField("شرایط و توضیحات", blank=True, help_text="در صفحهٔ خرید اقساطی و تسویه حساب")
    submit_note = models.TextField("راهنمای کنار فرم مدارک", blank=True,
                                   help_text="مثلاً «تصویر واضح یک برگ چک، بدون نوشتن مبلغ و تاریخ»")
    review_note = models.TextField("پیام بعد از ثبت درخواست", blank=True,
                                   help_text="در صفحهٔ سفارش، تا وقتی درخواست بررسی نشده")
    approved_note = models.TextField("پیام بعد از تأیید", blank=True,
                                     help_text="در صفحهٔ سفارش بعد از تأیید؛ مثلاً نحوهٔ نوشتن چک‌ها و نشانی پست")
    approved_sms = models.TextField(
        "پیامک تأیید به مشتری", blank=True,
        help_text="متغیرها: {name} {order} {link} — برای ارسال، «شمارهٔ خط پیامک گروهی» در تنظیمات پیامک لازم است")
    rejected_sms = models.TextField("پیامک رد درخواست", blank=True, help_text="متغیرها: {name} {order}")

    INFO_FIELDS = [
        # کلید، فیلد مدل، برچسب، نوع
        ("holder_name", "ask_holder_name", "نام و نام خانوادگی", "text"),
        ("national_code", "ask_national_code", "کد ملی", "national_code"),
        ("pensioner_type", "ask_pensioner_type", "بازنشسته یا مستمری‌بگیر", "pensioner"),
        ("retiree_id", "ask_retiree_id", "شمارهٔ بازنشستگی / مستمری", "digits"),
        ("sms_mobile", "ask_sms_mobile", "موبایلی که پیامک بانک به آن می‌رود", "mobile"),
        ("bank_name", "ask_bank_name", "نام بانک", "text"),
        ("sayad_id", "ask_sayad_id", "شناسهٔ صیادی چک (۱۶ رقم)", "sayad"),
        ("cheque_image", "ask_cheque_image", "تصویر یک برگ چک", "image"),
    ]
    PENSIONER_CHOICES = ["بازنشسته", "مستمری‌بگیر"]

    class Meta:
        verbose_name = "روش اقساط"
        verbose_name_plural = "روش‌های اقساط"
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.title

    @property
    def beta_auto(self):
        """بتا با اتصال خودکار: فقط کد ملی لازم است و پیش‌پرداخت بعد از تأیید بتا گرفته می‌شود."""
        if self.kind != self.Kind.BETA:
            return False
        if not hasattr(self, "_beta_auto"):
            self._beta_auto = BetaSettings.load().ready
        return self._beta_auto

    @property
    def down_at_checkout(self):
        return self.down_timing == self.DownTiming.CHECKOUT and not self.beta_auto

    @property
    def info_fields(self):
        if self.beta_auto:
            return [(k, label, typ) for k, attr, label, typ in self.INFO_FIELDS
                    if k == "national_code" or (k == "holder_name" and self.ask_holder_name)]
        return [(k, label, typ) for k, attr, label, typ in self.INFO_FIELDS if getattr(self, attr)]

    def steps(self):
        out = []
        if self.allow_monthly:
            out.append(1)
        if self.allow_bimonthly:
            out.append(2)
        return out or [1]

    def months_for(self, step):
        return [m for m in range(max(self.min_months, step), self.max_months + 1) if m % step == 0]

    def down_options(self):
        lo, hi = min(self.min_down_percent, 100), min(max(self.max_down_percent, self.min_down_percent), 100)
        step = max(self.down_step, 1)
        vals = list(range(lo, hi + 1, step))
        if vals[-1] != hi:
            vals.append(hi)
        return vals

    def config(self):
        """تنظیمات برای ماشین‌حساب صفحه (JSON)."""
        return {
            "id": self.pk, "title": self.title, "kind": self.kind, "summary": self.summary,
            "rate": float(self.monthly_rate), "down": self.down_options(), "min_down": self.min_down_percent,
            "steps": self.steps(), "months": {str(s): self.months_for(s) for s in self.steps()},
            "min_order": self.min_order_amount, "pay_at": "checkout" if self.down_at_checkout else "approval",
        }


class BetaSettings(models.Model):
    """اتصال خودکار به سامانهٔ بتا (بستر تأمین اعتبار بانک رفاه — بانکداری باز api.rb24.ir)."""

    class Unit(models.TextChoices):
        RIAL = "rial", "ریال"
        TOMAN = "toman", "تومان"

    enabled = models.BooleanField(
        "اتصال خودکار به بتا فعال", default=False,
        help_text="روشن: مشتری بازنشسته بعد از ثبت سفارش، در صفحهٔ سفارش اعتبارش را می‌بیند و با رمز پیامکی بانک خرید را تأیید می‌کند؛ "
                  "فروش خودکار در بتا ثبت می‌شود. خاموش: همان روش دستی (ثبت در پنل بتا توسط شما).")
    client_id = models.CharField("شناسهٔ کاربری (client_id)", max_length=200, blank=True,
                                 help_text="از سامانهٔ بانکداری باز بانک رفاه")
    client_secret = models.CharField("رمز (client_secret)", max_length=300, blank=True)
    api_key = models.CharField("کلید API بتا (API-KEY)", max_length=300, blank=True,
                               help_text="کلیدی که سامانهٔ بتا به فروشگاه داده است")
    grant_type = models.CharField("نوع احراز (grant_type)", max_length=50, default="client_credentials",
                                  help_text="معمولاً client_credentials؛ فقط اگر بانک مقدار دیگری گفت عوض کنید")
    base_url = models.URLField("نشانی سرویس", default="https://api.rb24.ir")
    amount_unit = models.CharField("واحد مبلغ در بتا", max_length=5, choices=Unit.choices, default=Unit.RIAL,
                                   help_text="مبلغ‌ها در سایت تومان است؛ اگر بانک گفت مبلغ‌ها تومانی است، «تومان» را بزنید")
    sale_title = models.CharField("عنوان فروش در بتا", max_length=100, default="فرش - سفارش {order}",
                                  help_text="متغیر: {order} شمارهٔ سفارش. همین عنوان در پیامک بانک به مشتری دیده می‌شود.")
    daily_limit = models.PositiveSmallIntegerField(
        "سقف استعلام اعتبار برای هر مشتری در روز", default=5,
        help_text="برای جلوگیری از استعلام اعتبار دیگران با کد ملی آن‌ها")
    last_test = models.JSONField(default=dict, blank=True, editable=False)

    class Meta:
        verbose_name = verbose_name_plural = "اتصال سامانهٔ بتا"

    def __str__(self):
        return "سامانهٔ بتا"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def ready(self):
        return bool(self.enabled and self.client_id and self.client_secret and self.api_key)

    def to_bank(self, toman):
        return int(toman) * (10 if self.amount_unit == self.Unit.RIAL else 1)

    def to_toman(self, amount):
        return int(amount or 0) // (10 if self.amount_unit == self.Unit.RIAL else 1)


class BetaSale(models.Model):
    """یک خرید اقساطی در سامانهٔ بتا برای یک سفارش: استعلام، رمز یک‌بارمصرف، شمارهٔ فروش و وضعیت وصول اقساط."""

    order = models.OneToOneField("shop.Order", on_delete=models.CASCADE, related_name="beta", verbose_name="سفارش")
    national_code = models.CharField("کد ملی", max_length=10)
    cellphone = models.CharField("موبایل ثبت‌شده در بتا (نیمه)", max_length=20, blank=True)
    credit = models.BigIntegerField("توان بازپرداخت ماهانه (تومان)", null=True, blank=True)
    checked_at = models.DateTimeField("زمان استعلام", null=True, blank=True)
    inquiries = models.JSONField(default=list, blank=True)  # زمان استعلام‌ها برای سقف روزانه
    start_ym = models.CharField("ماه شروع کسر", max_length=7, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)  # همان بدنه‌ای که رمز برایش فرستاده شد (رمز به آن حساس است)
    otp_sent_at = models.DateTimeField(null=True, blank=True)
    sale_id = models.BigIntegerField("شمارهٔ فروش در بتا", null=True, blank=True, db_index=True)
    registered_at = models.DateTimeField("زمان ثبت فروش", null=True, blank=True)
    installments = models.JSONField(default=list, blank=True)
    paid_count = models.PositiveSmallIntegerField("قسط وصول‌شده", default=0)
    failed_count = models.PositiveSmallIntegerField("قسط وصول‌نشده", default=0)
    synced_at = models.DateTimeField("آخرین به‌روزرسانی اقساط", null=True, blank=True)
    last_error = models.CharField("آخرین خطا", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "خرید بتا"
        verbose_name_plural = "خریدهای بتا"
        ordering = ["-pk"]

    def __str__(self):
        return f"بتا {self.sale_id or '—'} / سفارش {self.order_id}"

    @property
    def count(self):
        return len([i for i in self.installments if not i.get("deleted")])
