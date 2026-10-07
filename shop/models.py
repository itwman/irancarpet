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
    referral_enabled = models.BooleanField("کد معرفی دوستان فعال باشد", default=False,
                                           help_text="هر مشتری یک کد اختصاصی می‌گیرد؛ دوستش با آن تخفیف می‌گیرد و خودش بعد از خرید دوست، کد هدیه.")
    referral_percent = models.PositiveSmallIntegerField("تخفیف دوستِ معرفی‌شده (درصد)", default=3)
    referral_max = models.PositiveBigIntegerField("سقف تخفیف دوست (تومان)", default=2_000_000)
    referral_min_order = models.PositiveBigIntegerField("حداقل خرید برای کد معرفی (تومان)", default=10_000_000)
    referral_reward = models.PositiveBigIntegerField("هدیهٔ معرف (تومان)", default=1_000_000,
                                                     help_text="بعد از خرید دوست، یک کد تخفیف با این مبلغ برای معرف ساخته و پیامک می‌شود")
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
    coupon_code = models.CharField("کد تخفیف", max_length=40, blank=True, db_index=True)
    discount = models.PositiveBigIntegerField("تخفیف (تومان)", default=0, help_text="از جمع کالاها کم شده است")
    reminded_count = models.PositiveSmallIntegerField("تعداد یادآوری پرداخت", default=0, editable=False)
    reminded_at = models.DateTimeField("آخرین یادآوری پرداخت", null=True, blank=True, editable=False)
    review_invited_at = models.DateTimeField("دعوت به ثبت نظر", null=True, blank=True, editable=False)
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
    offer = models.ForeignKey("shop.SpecialOffer", null=True, blank=True, on_delete=models.SET_NULL, related_name="items",
                              verbose_name="فرصت ویژه")

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


class Coupon(models.Model):
    """کد تخفیف: عمومی (مثل «اولین خرید»)، ویژهٔ اپ، یا کد معرفی هر مشتری."""

    class Kind(models.TextChoices):
        PERCENT = "percent", "درصدی"
        FIXED = "fixed", "مبلغ ثابت (تومان)"

    code = models.CharField("کد", max_length=40, unique=True, help_text="حروف انگلیسی و عدد؛ بزرگ و کوچک فرقی ندارد")
    title = models.CharField("عنوان", max_length=120, blank=True, help_text="مثل «تخفیف اولین خرید»")
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.PERCENT)
    value = models.PositiveBigIntegerField("مقدار", help_text="برای درصدی: درصد؛ برای ثابت: تومان")
    max_discount = models.PositiveBigIntegerField("سقف تخفیف (تومان)", default=0, help_text="۰ یعنی بدون سقف")
    min_order = models.PositiveBigIntegerField("حداقل مبلغ سبد (تومان)", default=0)
    starts_at = models.DateTimeField("شروع", null=True, blank=True)
    ends_at = models.DateTimeField("پایان", null=True, blank=True)
    usage_limit = models.PositiveIntegerField("سقف کل استفاده", default=0, help_text="۰ یعنی بی‌سقف")
    per_user_limit = models.PositiveIntegerField("سقف استفادهٔ هر مشتری", default=1, help_text="۰ یعنی بی‌سقف")
    first_order_only = models.BooleanField("فقط اولین خرید", default=False)
    app_only = models.BooleanField("فقط خرید از اپ", default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="referral_codes",
                              verbose_name="صاحب کد معرفی", help_text="اگر پر باشد، کد معرفی همین مشتری است و بعد از خرید دوستش هدیه می‌گیرد")
    for_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+",
                                 verbose_name="فقط برای این مشتری")
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("ساخته شده", default=timezone.now)

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def label(self):
        if self.kind == self.Kind.PERCENT:
            return f"{self.value}٪ تخفیف"
        return f"{self.value:,} تومان تخفیف"


def _in_24h():
    return timezone.now() + timezone.timedelta(hours=24)


class SpecialOffer(models.Model):
    """فرصت ویژهٔ خرید: چند تختهٔ موجود در انبار از یک سایز، با تخفیف و فقط برای خرید تک‌تخته."""

    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="special_offers", verbose_name="فرش")
    size = models.ForeignKey("pricing.Size", on_delete=models.PROTECT, related_name="+", verbose_name="سایز")
    percent = models.PositiveSmallIntegerField("درصد تخفیف", default=10, help_text="روی قیمت روز همان سایز")
    fixed_price = models.PositiveBigIntegerField("یا قیمت ثابت (تومان)", null=True, blank=True,
                                                 help_text="اگر پر شود به‌جای درصد تخفیف همین قیمت گرفته می‌شود.")
    quantity = models.PositiveSmallIntegerField("تعداد موجود در انبار", default=1)
    starts_at = models.DateTimeField("شروع", default=timezone.now)
    ends_at = models.DateTimeField("پایان (اختیاری)", null=True, blank=True,
                                   help_text="خالی = تا وقتی تخته‌ها فروخته شوند یا «تعداد» را صفر کنید. اگر پر شود، "
                                             "شمارندهٔ معکوس تا همین زمان نشان داده می‌شود و بعدش قیمت ویژه تمام می‌شود.")
    is_active = models.BooleanField("فعال", default=True)
    note = models.CharField("یادداشت داخلی", max_length=200, blank=True, help_text="به مشتری نشان داده نمی‌شود؛ مثلاً محل فرش در انبار")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "فرصت ویژهٔ خرید"
        verbose_name_plural = "فرصت‌های ویژهٔ خرید"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product} — {self.size}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.product_id and self.size_id and not self.product.variations.filter(size_id=self.size_id).exists():
            raise ValidationError({"size": "این فرش چنین سایزی ندارد. سایزهای فرش در صفحهٔ خودش (یا آلبومش) تعریف می‌شوند."})
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "پایان باید بعد از شروع باشد."})
        if not self.fixed_price and not (0 < self.percent < 90):
            raise ValidationError({"percent": "درصد تخفیف بین ۱ و ۸۹ باشد (یا قیمت ثابت بنویسید)."})

    def save(self, *a, **kw):
        super().save(*a, **kw)
        from .offers import clear

        clear()

    @property
    def variation(self):
        if not hasattr(self, "_variation"):
            self._variation = self.product.variations.filter(size=self.size).first()
        return self._variation

    @property
    def regular_price(self):
        v = self.variation
        return (v.price or 0) if v else 0

    @property
    def price(self):
        if self.fixed_price:
            return self.fixed_price
        reg = self.regular_price
        if not reg:
            return 0
        return int(math.floor(reg * (100 - min(self.percent, 90)) / 100 / 10_000) * 10_000)

    @property
    def off_percent(self):
        reg = self.regular_price
        return round((1 - self.price / reg) * 100) if reg and self.price else 0

    @property
    def sold(self):
        from shop.offers import taken_q

        return OrderItem.objects.filter(taken_q(), offer=self).count()

    @property
    def remaining(self):
        return max(self.quantity - self.sold, 0)

    @property
    def is_live(self):
        now = timezone.now()
        # فرش یا سایز می‌تواند در سایت «ناموجود» باشد؛ همان تختهٔ انبار با فرصت ویژه فروخته می‌شود
        return bool(self.is_active and self.starts_at <= now and (self.ends_at is None or now < self.ends_at) and self.remaining > 0
                    and self.variation is not None and self.price)
