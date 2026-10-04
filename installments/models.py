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
    def info_fields(self):
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
            "min_order": self.min_order_amount, "pay_at": self.down_timing,
        }
