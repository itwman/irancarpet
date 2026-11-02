"""مارکت‌پلیس: فروشنده‌ها، سفارش هر فروشنده، کمیسیون و تسویه.

- پول مشتری به درگاه ایران کارپت می‌آید؛ سهم فروشنده (مبلغ کالا منهای کمیسیون) بعد از تحویل و گذشتن مهلت مرجوعی واریز می‌شود.
- ارسال با خود فروشنده است؛ کد رهگیری را در پنلش ثبت می‌کند.
- قیمت را فروشنده می‌گذارد؛ کالای تازه یا ویرایش محتوا بعد از تأیید ایران کارپت منتشر می‌شود.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from affiliate.models import clean_sheba, valid_sheba

DEFAULT_TERMS = """- فقط کالای اصل و نو، با عکس واقعی و مشخصات درست ثبت کنید؛ کالای تقلبی یا متفاوت با عکس، با مرجوعی و توقف حساب همراه است.
- قیمت هر کالا را خودتان تعیین می‌کنید و باید با قیمت فروش شما در جاهای دیگر هم‌خوان باشد.
- سفارش تازه را حداکثر ظرف {پذیرش} ساعت تأیید و در زمان آماده‌سازی اعلام‌شده ارسال کنید و کد رهگیری را ثبت کنید.
- اگر کالایی تمام شد، همان لحظه موجودی‌اش را صفر کنید؛ لغو سفارش از طرف فروشنده در امتیاز فروشگاه اثر دارد.
- مبلغ هر سفارش (منهای کمیسیون) {مرجوعی} روز بعد از تحویل به مشتری، به شماره شبای ثبت‌شده به نام خودتان واریز می‌شود.
- ارتباط با مشتری و پاسخ به پیام‌ها از طریق ایران کارپت است؛ گرفتن پول یا سفارش خارج از سایت ممنوع است."""


class MarketSettings(models.Model):
    enabled = models.BooleanField("فروش فروشندگان فعال است", default=True)
    signup_open = models.BooleanField("ثبت‌نام فروشندهٔ تازه باز است", default=True)
    default_commission = models.DecimalField("کمیسیون پیش‌فرض (درصد)", max_digits=5, decimal_places=2, default=Decimal("10"),
                                             help_text="درصدی از مبلغ کالا که سهم ایران کارپت است؛ برای هر دسته یا هر فروشنده جدا هم می‌شود گذاشت.")
    accept_hours = models.PositiveSmallIntegerField("مهلت پذیرش سفارش (ساعت)", default=24)
    auto_deliver_days = models.PositiveSmallIntegerField(
        "تحویل خودکار پس از ارسال (روز)", default=10,
        help_text="اگر مشتری یا مدیر «تحویل شد» را نزد، این‌قدر بعد از ثبت کد رهگیری تحویل‌شده حساب می‌شود.")
    hold_days = models.PositiveSmallIntegerField("مهلت مرجوعی قبل از تسویه (روز)", default=7)
    min_payout = models.PositiveBigIntegerField("حداقل مبلغ تسویه (تومان)", default=1_000_000)
    terms = models.TextField("قوانین فروشندگان", default=DEFAULT_TERMS,
                             help_text="هر خط یک بند. {پذیرش} = مهلت پذیرش، {مرجوعی} = مهلت مرجوعی")

    class Meta:
        verbose_name = "تنظیمات مارکت‌پلیس"
        verbose_name_plural = "تنظیمات مارکت‌پلیس"

    def __str__(self):
        return "تنظیمات مارکت‌پلیس"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def terms_list(self):
        return [x.lstrip("-• ").strip().replace("{پذیرش}", str(self.accept_hours)).replace("{مرجوعی}", str(self.hold_days))
                for x in (self.terms or "").splitlines() if x.strip()]


class CategoryCommission(models.Model):
    category = models.OneToOneField("catalog.Category", on_delete=models.CASCADE, related_name="market_commission", verbose_name="دسته")
    percent = models.DecimalField("کمیسیون (درصد)", max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "کمیسیون دسته"
        verbose_name_plural = "کمیسیون دسته‌ها"

    def __str__(self):
        return f"{self.category} — {self.percent}٪"


class Seller(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تأیید"
        ACTIVE = "active", "فعال"
        PAUSED = "paused", "تعطیل موقت (به خواست فروشنده)"
        SUSPENDED = "suspended", "متوقف"
        REJECTED = "rejected", "رد شده"

    class Kind(models.TextChoices):
        PERSON = "person", "حقیقی"
        COMPANY = "company", "حقوقی (شرکت)"

    class Shipping(models.TextChoices):
        COD = "cod", "پس‌کرایه (هزینه با مشتری)"
        FREE = "free", "ارسال رایگان"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seller", verbose_name="حساب کاربری")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    name = models.CharField("نام فروشگاه", max_length=80, unique=True)
    slug = models.SlugField("نشانی فروشگاه", max_length=60, unique=True, allow_unicode=True)
    logo = models.ForeignKey("core.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="لوگو")
    # ویترین
    cover = models.ForeignKey("core.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="کاور")
    tagline = models.CharField("شعار فروشگاه", max_length=120, blank=True)
    accent = models.CharField("رنگ فروشگاه", max_length=7, default="#8E1F2F")
    layout = models.CharField("چیدمان ویترین", max_length=10, default="showcase",
                              choices=[("showcase", "ویترین"), ("gallery", "گالری"), ("catalog", "کاتالوگ")])
    featured_product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                         verbose_name="پیشنهاد فروشنده")
    photos = models.ManyToManyField("core.Media", blank=True, related_name="+", verbose_name="عکس‌های کارگاه و فروشگاه")
    about = models.TextField("دربارهٔ فروشگاه", blank=True)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.PERSON)
    owner_name = models.CharField("نام صاحب فروشگاه / مدیرعامل", max_length=120)
    national_id = models.CharField("کد ملی / شناسهٔ ملی شرکت", max_length=11, blank=True)
    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    phone = models.CharField("تلفن ثابت", max_length=20, blank=True)
    province = models.CharField("استان", max_length=60, blank=True)
    city = models.CharField("شهر ارسال", max_length=80)
    address = models.TextField("نشانی انبار / فروشگاه", blank=True)
    shipping = models.CharField("هزینهٔ ارسال", max_length=6, choices=Shipping.choices, default=Shipping.COD)
    prep_days = models.PositiveSmallIntegerField("زمان آماده‌سازی (روز کاری)", default=3)
    return_policy = models.CharField("شرایط مرجوعی", max_length=300, blank=True,
                                     default="تا ۷ روز پس از تحویل، در صورت مغایرت با مشخصات یا ایراد تولید")
    sheba = models.CharField("شماره شبا", max_length=26, blank=True)
    account_holder = models.CharField("به نام", max_length=120, blank=True)
    commission_percent = models.DecimalField("کمیسیون اختصاصی (درصد)", max_digits=5, decimal_places=2, null=True, blank=True,
                                             help_text="اگر پر باشد، به‌جای کمیسیون دسته‌ها برای همهٔ کالاهای این فروشنده حساب می‌شود.")
    trusted = models.BooleanField("فروشندهٔ مورد اعتماد", default=False,
                                  help_text="روشن: کالاها و ویرایش‌هایش بدون بررسی منتشر می‌شود.")
    admin_note = models.TextField("یادداشت داخلی", blank=True)
    created_at = models.DateTimeField("تاریخ ثبت‌نام", default=timezone.now)
    approved_at = models.DateTimeField("تاریخ تأیید", null=True, blank=True)

    class Meta:
        verbose_name = "فروشنده"
        verbose_name_plural = "فروشندگان"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/vendor/{self.slug}/"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def clean(self):
        self.sheba = clean_sheba(self.sheba)
        if self.sheba and not valid_sheba(self.sheba):
            raise ValidationError({"sheba": "شماره شبا درست نیست (IR و ۲۴ رقم)."})

    @property
    def shipping_label(self):
        return "ارسال رایگان" if self.shipping == self.Shipping.FREE else "پس‌کرایه"

    ACCENTS = [("#8E1F2F", "لاکی"), ("#1F4E79", "سرمه‌ای"), ("#2F6B3B", "یشمی"), ("#6B3FA0", "بنفش"), ("#9A5B13", "عسلی"),
               ("#0B7C88", "فیروزه‌ای"), ("#22265A", "نیلی"), ("#B3264E", "انار")]

    @property
    def accent_color(self):
        """رنگ فروشگاه، فقط اگر به‌اندازهٔ کافی تیره باشد که متن سفید رویش خوانا بماند (کنتراست ۴٫۵)."""
        import re

        c = (self.accent or "").strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
            return "#8E1F2F"
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
        lin = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in (r, g, b)]
        lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
        return c if 1.05 / (lum + 0.05) >= 4.5 else "#8E1F2F"


class SellerPayout(models.Model):
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="payouts", verbose_name="فروشنده")
    amount = models.PositiveBigIntegerField("مبلغ (تومان)")
    reference = models.CharField("کد پیگیری واریز", max_length=60, blank=True)
    note = models.CharField("توضیح", max_length=200, blank=True)
    paid_at = models.DateTimeField("تاریخ واریز", default=timezone.now)

    class Meta:
        verbose_name = "تسویهٔ فروشنده"
        verbose_name_plural = "تسویهٔ فروشندگان"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"تسویهٔ {self.amount:,} تومان"


class SellerOrder(models.Model):
    """بخشی از سفارش مشتری که یک فروشنده باید ارسال کند."""

    class Status(models.TextChoices):
        WAITING = "waiting", "منتظر پرداخت مشتری"
        NEW = "new", "سفارش تازه"
        ACCEPTED = "accepted", "در حال آماده‌سازی"
        SHIPPED = "shipped", "ارسال شد"
        DELIVERED = "delivered", "تحویل شد"
        CANCELLED = "cancelled", "لغو شد"

    class Settle(models.TextChoices):
        OPEN = "open", "باز"
        PAYABLE = "payable", "قابل تسویه"
        PAID = "paid", "تسویه شد"
        NONE = "none", "بدون تسویه"

    order = models.ForeignKey("shop.Order", on_delete=models.CASCADE, related_name="seller_orders", verbose_name="سفارش")
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="orders", verbose_name="فروشنده")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.WAITING, db_index=True)
    items_total = models.PositiveBigIntegerField("مبلغ کالاها (تومان)", default=0)
    commission = models.PositiveBigIntegerField("کمیسیون ایران کارپت (تومان)", default=0)
    seller_amount = models.PositiveBigIntegerField("سهم فروشنده (تومان)", default=0)
    carrier = models.CharField("شرکت حمل", max_length=60, blank=True)
    tracking_code = models.CharField("کد رهگیری ارسال", max_length=100, blank=True)
    cancel_reason = models.CharField("دلیل لغو", max_length=300, blank=True)
    settle = models.CharField("تسویه", max_length=8, choices=Settle.choices, default=Settle.OPEN, db_index=True)
    payout = models.ForeignKey(SellerPayout, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders", verbose_name="تسویه")
    stock_taken = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField("تاریخ", default=timezone.now, db_index=True)
    paid_at = models.DateTimeField("پرداخت مشتری", null=True, blank=True)
    accepted_at = models.DateTimeField("پذیرش", null=True, blank=True)
    shipped_at = models.DateTimeField("ارسال", null=True, blank=True)
    delivered_at = models.DateTimeField("تحویل", null=True, blank=True)
    payable_at = models.DateTimeField("قابل تسویه از", null=True, blank=True)

    class Meta:
        verbose_name = "سفارش فروشنده"
        verbose_name_plural = "سفارش‌های فروشندگان"
        ordering = ["-created_at"]
        unique_together = [("order", "seller")]

    def __str__(self):
        return f"سفارش {self.order.number} — {self.seller}"

    @property
    def open_for_seller(self):
        return self.status in (self.Status.NEW, self.Status.ACCEPTED)


class SellerSlide(models.Model):
    """اسلاید سربرگ ویترین (تا ۵ تا)."""

    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="slides")
    image = models.ForeignKey("core.Media", on_delete=models.CASCADE, related_name="+", verbose_name="عکس")
    title = models.CharField("عنوان", max_length=80, blank=True)
    subtitle = models.CharField("زیرعنوان", max_length=140, blank=True)
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                verbose_name="پیوند به فرش")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    MAX = 5


class SellerShelf(models.Model):
    """قفسهٔ فروشگاه: دسته‌بندی خود فروشنده (مثل «حراج» یا «اتاق کودک»)؛ هر کالا می‌تواند در چند قفسه باشد."""

    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="shelves")
    name = models.CharField("نام قفسه", max_length=60)
    slug = models.SlugField(max_length=70, allow_unicode=True)
    order = models.PositiveSmallIntegerField(default=0)
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="shelves", verbose_name="کالاها")

    class Meta:
        ordering = ["order", "pk"]
        unique_together = [("seller", "slug")]

    def __str__(self):
        return self.name

    def save(self, *a, **kw):
        if not self.slug:
            from django.utils.text import slugify

            base = slugify(self.name, allow_unicode=True)[:60] or "shelf"
            slug, n = base, 2
            while SellerShelf.objects.filter(seller_id=self.seller_id, slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*a, **kw)


class SellerFollow(models.Model):
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="followers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followed_sellers")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        unique_together = [("seller", "user")]
