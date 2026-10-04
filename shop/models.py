import math

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

PAYMENT_MODES = [("full", "پرداخت کامل آنلاین"), ("deposit", "بیعانه آنلاین، بقیه موقع تحویل"), ("installment", "خرید اقساطی")]
INSTALLMENT_STATES = [
    ("review", "در انتظار بررسی مدارک"), ("approved", "تأیید شد"), ("rejected", "رد شد"), ("done", "تکمیل شد (چک‌ها / بتا ثبت شد)"),
]
SHIPPING_MODES = [("free", "ارسال رایگان"), ("cod", "پس‌کرایه (هزینهٔ ارسال با مشتری)")]


class ShopSettings(models.Model):
    """تنظیمات فروش (یک ردیف)."""

    deposit_percent = models.PositiveSmallIntegerField("درصد بیعانه", default=10)
    free_shipping_min = models.PositiveBigIntegerField(
        "حداقل مبلغ ارسال رایگان (تومان)", default=50_000_000,
        help_text="فقط برای سفارش‌هایی که کل مبلغ را آنلاین پرداخت می‌کنند",
    )
    allow_full = models.BooleanField("پرداخت کامل آنلاین فعال باشد", default=True)
    allow_deposit = models.BooleanField("پرداخت بیعانه فعال باشد", default=True)
    sep_enabled = models.BooleanField("درگاه سامان (سپ) فعال باشد", default=True)
    zarinpal_enabled = models.BooleanField("درگاه زرین‌پال فعال باشد", default=True)
    checkout_note = models.TextField("توضیح صفحهٔ تسویه حساب", blank=True)
    admin_mobiles = models.CharField(
        "موبایل مدیران برای اطلاع از سفارش", max_length=200, blank=True, help_text="با ویرگول جدا کنید",
    )
    # درگاه‌ها
    sep_terminal_id = models.CharField("شمارهٔ ترمینال سامان", max_length=30, blank=True)
    zarinpal_merchant_id = models.CharField("مرچنت‌کد زرین‌پال", max_length=64, blank=True)
    zarinpal_sandbox = models.BooleanField("زرین‌پال در حالت آزمایشی (sandbox)", default=False)
    # پیامک sms.ir
    smsir_api_key = models.CharField("کلید API پنل sms.ir", max_length=200, blank=True)
    smsir_otp_template_id = models.CharField("شمارهٔ قالب کد ورود", max_length=20, blank=True, help_text="قالب با متغیر CODE")
    smsir_order_template_id = models.CharField(
        "شمارهٔ قالب پیامک پرداخت به مشتری", max_length=20, blank=True, help_text="متغیرها: ORDER و AMOUNT",
    )
    smsir_admin_template_id = models.CharField(
        "شمارهٔ قالب پیامک سفارش به مدیر", max_length=20, blank=True, help_text="متغیرها: ORDER، NAME و AMOUNT",
    )
    smsir_line_number = models.CharField("شمارهٔ خط ارسال پیامک گروهی", max_length=20, blank=True,
                                         help_text="خط اختصاصی یا خدماتی در پنل sms.ir (برای پیامک گروهی)")

    class Meta:
        verbose_name = "تنظیمات فروش"
        verbose_name_plural = "تنظیمات فروش"

    def __str__(self):
        return "تنظیمات فروش"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def deposit_amount(self, total):
        """بیعانه، گرد شده به بالا تا هزار تومان."""
        return int(math.ceil(total * self.deposit_percent / 100 / 1000) * 1000)

    def shipping_for(self, mode, total):
        return "free" if mode == "full" and total >= self.free_shipping_min else "cod"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار پرداخت"
        ON_HOLD = "on_hold", "در انتظار بررسی اقساط"
        DEPOSIT_PAID = "deposit_paid", "بیعانه پرداخت شد"
        PAID = "paid", "پرداخت کامل"
        PROCESSING = "processing", "در حال آماده‌سازی"
        SHIPPED = "shipped", "ارسال شد"
        COMPLETED = "completed", "تحویل شد"
        CANCELLED = "cancelled", "لغو شده"
        REFUNDED = "refunded", "مسترد شده"

    PAID_STATUSES = {"deposit_paid", "paid", "processing", "shipped", "completed"}

    number = models.PositiveIntegerField("شمارهٔ سفارش", unique=True, editable=False)
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders", verbose_name="مشتری")
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    first_name = models.CharField("نام", max_length=100)
    last_name = models.CharField("نام خانوادگی", max_length=100)
    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    email = models.EmailField("ایمیل", blank=True)
    province = models.CharField("استان", max_length=60)
    city = models.CharField("شهر", max_length=80)
    address = models.TextField("آدرس")
    postal_code = models.CharField("کد پستی", max_length=10, blank=True)
    note = models.TextField("توضیح مشتری", blank=True)

    payment_mode = models.CharField("نوع پرداخت", max_length=20, choices=PAYMENT_MODES, default="full")
    shipping_mode = models.CharField("ارسال", max_length=10, choices=SHIPPING_MODES, default="cod")
    items_total = models.PositiveBigIntegerField("جمع کالاها (تومان)", default=0)
    deposit_percent = models.PositiveSmallIntegerField("درصد بیعانه", default=0)
    online_amount = models.PositiveBigIntegerField("مبلغ پرداخت آنلاین", default=0)
    paid_amount = models.PositiveBigIntegerField("پرداخت‌شده", default=0)

    # خرید اقساطی
    installment_plan = models.ForeignKey("installments.InstallmentPlan", null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name="orders", verbose_name="روش اقساط")
    installment = models.JSONField("جدول اقساط", default=dict, blank=True)
    installment_info = models.JSONField("مشخصات متقاضی اقساط", default=dict, blank=True)
    installment_state = models.CharField("وضعیت اقساط", max_length=10, choices=INSTALLMENT_STATES, blank=True, db_index=True)
    installment_reviewed_at = models.DateTimeField("تاریخ بررسی اقساط", null=True, blank=True)

    admin_note = models.TextField("یادداشت داخلی", blank=True)
    wp_status = models.CharField("وضعیت در وردپرس", max_length=40, blank=True, editable=False)
    wp_payment = models.CharField("روش پرداخت در وردپرس", max_length=200, blank=True, editable=False)
    tracking_code = models.CharField("کد رهگیری ارسال", max_length=100, blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", default=timezone.now, db_index=True)
    paid_at = models.DateTimeField("تاریخ پرداخت", null=True, blank=True)

    NUMBER_START = 200001

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"سفارش {self.number}"

    def save(self, *args, **kwargs):
        if not self.number:
            with transaction.atomic():
                last = Order.objects.select_for_update().filter(number__gte=self.NUMBER_START).order_by("-number").first()
                self.number = (last.number + 1) if last else self.NUMBER_START
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/my-account/orders/{self.number}/"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_installment(self):
        return self.payment_mode == "installment"

    @property
    def grand_total(self):
        """مبلغ کل قابل پرداخت (برای اقساطی: پیش‌پرداخت + جمع اقساط)."""
        if self.is_installment and self.installment:
            return int(self.installment.get("payable_total") or self.items_total)
        return self.items_total

    @property
    def remaining(self):
        return max(self.grand_total - self.paid_amount, 0)

    @property
    def is_paid(self):
        return self.status in self.PAID_STATUSES

    @property
    def is_placed(self):
        """سفارش ثبت قطعی شده (پرداخت شده یا درخواست اقساط بدون پرداخت فرستاده شده)."""
        return self.is_paid or self.status == self.Status.ON_HOLD

    @property
    def can_pay(self):
        return self.status == self.Status.PENDING and self.online_amount > 0

    @property
    def status_label(self):
        if self.is_installment and self.status == self.Status.DEPOSIT_PAID:
            return "پیش‌پرداخت انجام شد"
        return self.get_status_display()

    def mark_paid(self, amount):
        self.paid_amount += amount
        self.paid_at = self.paid_at or timezone.now()
        if self.status == self.Status.PENDING:
            self.status = self.Status.PAID if self.paid_amount >= self.grand_total else self.Status.DEPOSIT_PAID
        self.save(update_fields=["paid_amount", "paid_at", "status"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    variation = models.ForeignKey("catalog.Variation", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    title = models.CharField("کالا", max_length=300)
    size_label = models.CharField("سایز", max_length=150, blank=True)
    unit_price = models.PositiveBigIntegerField("قیمت واحد")
    quantity = models.PositiveIntegerField("تعداد", default=1)

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return self.title

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Payment(models.Model):
    class Status(models.TextChoices):
        INIT = "init", "ارسال به درگاه"
        OK = "ok", "موفق"
        FAILED = "failed", "ناموفق"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField("درگاه", max_length=20)
    amount = models.PositiveBigIntegerField("مبلغ (تومان)")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.INIT, db_index=True)
    token = models.CharField("توکن/Authority", max_length=200, blank=True, db_index=True)
    ref_id = models.CharField("کد پیگیری بانک", max_length=100, blank=True)
    card = models.CharField("کارت", max_length=40, blank=True)
    message = models.CharField("پیام", max_length=300, blank=True)
    raw = models.JSONField("پاسخ خام", default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "تراکنش"
        verbose_name_plural = "تراکنش‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_gateway_display()} {self.amount}"

    def get_gateway_display(self):
        from .gateways import GATEWAY_NAMES

        return GATEWAY_NAMES.get(self.gateway, self.gateway)

    @property
    def res_num(self):
        """شناسهٔ یکتای تراکنش برای بانک"""
        return f"IC{self.pk}"
