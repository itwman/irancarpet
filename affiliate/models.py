"""همکاری در فروش (بازاریابی): بازاریاب‌ها، کلیک‌ها، پیوند مشتری به بازاریاب، کمیسیون پله‌ای و تسویه."""
import re
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_]{2,19}$")
RESERVED = {"admin", "panel", "api", "www", "irancarpet", "iran", "carpet", "shop", "store", "static", "media", "app",
            "login", "help", "support", "x", "l", "p", "c", "robots", "favicon", "test", "null", "none"}
DEFAULT_TERMS = """- پورسانت فقط برای سفارش‌هایی است که پرداخت و تحویل شده‌اند؛ سفارش لغو یا مرجوع‌شده پورسانت ندارد.
- مشتری از اولین ورود با پیوند شما تا {روز} روز به نام شما ثبت می‌شود؛ اگر با پیوند همکار دیگری بیاید، آخرین پیوند حساب است.
- خرید خودتان (با حساب یا شمارهٔ خودتان) پورسانت ندارد.
- تبلیغ با نام «ایران کارپت» در گوگل ادز، ساختن صفحه یا حساب با نام و نشان ایران کارپت، و پیامک یا ایمیل انبوه ناخواسته ممنوع است.
- قیمت، تخفیف یا شرایطی جز آنچه در سایت آمده به مشتری وعده ندهید.
- تسویه پس از رسیدن مانده به حداقل مبلغ تسویه، به شماره شبای ثبت‌شده به نام خودتان انجام می‌شود."""


class AffiliateSettings(models.Model):
    class Period(models.TextChoices):
        MONTH = "month", "فروش همان ماه (هر ماه شمسی از صفر)"
        ALL = "all", "کل فروش از ابتدای همکاری"

    class Mode(models.TextChoices):
        WHOLE = "whole", "کل فروش دوره با درصد پله‌ای که به آن رسیده"
        BRACKET = "bracket", "پلکانی (هر بخش از فروش با درصد پلهٔ خودش)"

    enabled = models.BooleanField("همکاری در فروش فعال است", default=True)
    auto_approve = models.BooleanField("تأیید خودکار بازاریاب‌های تازه", default=False,
                                       help_text="خاموش: هر ثبت‌نام باید در پنل تأیید شود (پیشنهادی).")
    attribution_days = models.PositiveSmallIntegerField("ماندگاری پیوند (روز)", default=60,
                                                        help_text="خرید مشتری تا این تعداد روز بعد از آخرین ورود با پیوند بازاریاب، به نام او ثبت می‌شود.")
    tier_period = models.CharField("پله بر اساس", max_length=10, choices=Period.choices, default=Period.MONTH)
    tier_mode = models.CharField("روش محاسبهٔ پله", max_length=10, choices=Mode.choices, default=Mode.WHOLE,
                                 help_text="مثال با پلهٔ ۱٫۵٪ تا ۱۵۰ میلیون و ۲٪ بالاتر، برای ۲۰۰ میلیون فروش: "
                                           "روش اول ۲٪ × ۲۰۰ = ۴ میلیون؛ روش پلکانی ۱٫۵٪ × ۱۵۰ + ۲٪ × ۵۰ = ۳٫۲۵ میلیون.")
    new_customers_only = models.BooleanField("فقط مشتری تازه", default=False,
                                             help_text="روشن: برای مشتری‌ای که قبلاً از ایران کارپت خرید کرده پورسانت ثبت نمی‌شود.")
    min_payout = models.PositiveBigIntegerField("حداقل مبلغ تسویه (تومان)", default=1_000_000)
    coupon_enabled = models.BooleanField("کد تخفیف اختصاصی برای هر بازاریاب", default=True,
                                         help_text="برای اینستاگرام و جاهایی که پیوند کلیک‌خور نیست: مشتری کد را در سبد خرید می‌زند، "
                                                   "تخفیف می‌گیرد و خرید به نام بازاریاب ثبت می‌شود.")
    coupon_percent = models.PositiveSmallIntegerField("درصد تخفیف کد بازاریاب", default=2)
    coupon_max = models.PositiveBigIntegerField("سقف تخفیف کد بازاریاب (تومان)", default=2_000_000, help_text="۰ یعنی بی‌سقف")
    short_domain = models.CharField("دامنهٔ پیوند کوتاه", max_length=60, default="crpt.it",
                                    help_text="باید رکورد DNS آن به سرور اشاره کند. خالی: پیوندها با دامنهٔ خود سایت ساخته می‌شوند.")
    terms = models.TextField("قوانین همکاری", default=DEFAULT_TERMS, help_text="هر خط یک بند. {روز} = ماندگاری پیوند")

    class Meta:
        verbose_name = "تنظیمات همکاری در فروش"
        verbose_name_plural = "تنظیمات همکاری در فروش"

    def __str__(self):
        return "تنظیمات همکاری در فروش"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def terms_list(self):
        return [x.lstrip("-• ").strip().replace("{روز}", str(self.attribution_days))
                for x in (self.terms or "").splitlines() if x.strip()]


class CommissionTier(models.Model):
    min_sales = models.PositiveBigIntegerField("از فروش (تومان)", default=0, unique=True,
                                               help_text="پله از این مبلغ شروع می‌شود و تا شروع پلهٔ بعدی ادامه دارد. پلهٔ اول را ۰ بگذارید.")
    percent = models.DecimalField("درصد پورسانت", max_digits=5, decimal_places=2)
    title = models.CharField("نام پله", max_length=40, blank=True, help_text="اختیاری؛ مثل «برنزی»، «نقره‌ای»")

    class Meta:
        verbose_name = "پلهٔ پورسانت"
        verbose_name_plural = "پله‌های پورسانت"
        ordering = ["min_sales"]

    def __str__(self):
        return f"از {self.min_sales:,} — {self.percent}٪"

    def clean(self):
        if self.percent is not None and not (Decimal(0) <= self.percent <= Decimal(50)):
            raise ValidationError({"percent": "درصد باید بین ۰ تا ۵۰ باشد."})


def new_code():
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    while True:
        c = "".join(secrets.choice(alphabet) for _ in range(5))
        if not Affiliate.objects.filter(code=c).exists():
            return c


class Affiliate(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تأیید"
        ACTIVE = "active", "فعال"
        REJECTED = "rejected", "رد شده"
        BLOCKED = "blocked", "متوقف"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="affiliate", verbose_name="حساب کاربری")
    code = models.CharField("کد پیوند", max_length=20, unique=True,
                            help_text="حروف کوچک انگلیسی، عدد و _ (۳ تا ۲۰ حرف)؛ در پیوند کوتاه می‌آید: crpt.it/کد")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    name = models.CharField("نام و نام خانوادگی", max_length=120)
    mobile = models.CharField("موبایل", max_length=11, db_index=True)
    city = models.CharField("شهر", max_length=80, blank=True)
    channels = models.TextField("کجا معرفی می‌کند", blank=True, help_text="صفحهٔ اینستاگرام، کانال، فروشگاه، دکوراسیون داخلی…")
    sheba = models.CharField("شماره شبا", max_length=26, blank=True, help_text="IR و ۲۴ رقم")
    account_holder = models.CharField("به نام", max_length=120, blank=True)
    custom_percent = models.DecimalField("درصد اختصاصی", max_digits=5, decimal_places=2, null=True, blank=True,
                                         help_text="اگر پر باشد، به‌جای پله‌ها همین درصد برای همهٔ فروش‌های این همکار حساب می‌شود.")
    coupon = models.ForeignKey("shop.Coupon", null=True, blank=True, on_delete=models.SET_NULL, related_name="affiliates",
                               verbose_name="کد تخفیف اختصاصی")
    admin_note = models.TextField("یادداشت داخلی", blank=True)
    created_at = models.DateTimeField("تاریخ ثبت‌نام", default=timezone.now)
    approved_at = models.DateTimeField("تاریخ تأیید", null=True, blank=True)

    class Meta:
        verbose_name = "همکار فروش"
        verbose_name_plural = "همکاران فروش"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        self.code = (self.code or "").strip().lower()
        if not CODE_RE.match(self.code) or self.code in RESERVED:
            raise ValidationError({"code": "کد باید ۳ تا ۲۰ حرف کوچک انگلیسی، عدد یا _ باشد و با حرف یا عدد شروع شود."})
        self.sheba = clean_sheba(self.sheba)
        if self.sheba and not valid_sheba(self.sheba):
            raise ValidationError({"sheba": "شماره شبا درست نیست (IR و ۲۴ رقم)."})

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


def clean_sheba(v):
    v = (v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).upper().replace(" ", "").replace("-", "")
    if v and v.isdigit():
        v = "IR" + v
    return v


def valid_sheba(v):
    if not re.match(r"^IR\d{24}$", v or ""):
        return False
    s = v[4:] + "1827" + v[2:4]  # I=18 R=27
    return int(s) % 97 == 1


class Click(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name="clicks")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    path = models.CharField(max_length=300)
    visitor = models.CharField(max_length=16, db_index=True)
    referer = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "ورود با پیوند"
        verbose_name_plural = "ورودها با پیوند"


class CustomerRef(models.Model):
    """مشتری واردشده با پیوند بازاریاب که در سایت وارد حسابش شده؛ خریدش از گوشی یا اپ هم به نام بازاریاب ثبت می‌شود."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="affiliate_ref")
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name="customers")
    clicked_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)


class Link(models.Model):
    """پیوند کوتاه برای هر صفحهٔ دلخواه سایت (لیست قیمت، دسته، مقاله…)."""

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name="links")
    path = models.CharField(max_length=400)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("affiliate", "path")]

    @property
    def slug(self):
        return "x" + base36(self.pk)


def base36(n):
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = chars[r] + out
        if not n:
            return out


class Payout(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name="payouts", verbose_name="همکار")
    amount = models.PositiveBigIntegerField("مبلغ (تومان)")
    reference = models.CharField("کد پیگیری واریز", max_length=60, blank=True)
    note = models.CharField("توضیح", max_length=200, blank=True)
    paid_at = models.DateTimeField("تاریخ واریز", default=timezone.now)

    class Meta:
        verbose_name = "تسویه"
        verbose_name_plural = "تسویه‌ها"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"تسویهٔ {self.amount:,} تومان"


class Commission(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "منتظر پرداخت مشتری"
        PENDING = "pending", "پرداخت شد؛ منتظر تحویل"
        APPROVED = "approved", "قابل تسویه"
        PAID = "paid", "تسویه شد"
        CANCELLED = "cancelled", "لغو شد"

    class Source(models.TextChoices):
        LINK = "link", "پیوند"
        COUPON = "coupon", "کد تخفیف همکار"
        ACCOUNT = "account", "پیوند (حساب مشتری)"
        MANUAL = "manual", "دستی"

    order = models.OneToOneField("shop.Order", on_delete=models.CASCADE, related_name="commission", verbose_name="سفارش")
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name="commissions", verbose_name="همکار")
    source = models.CharField("از راه", max_length=10, choices=Source.choices, default=Source.LINK)
    base = models.PositiveBigIntegerField("مبلغ فروش (تومان)", default=0)
    percent = models.DecimalField("درصد", max_digits=5, decimal_places=2, default=0)
    amount = models.PositiveBigIntegerField("پورسانت (تومان)", default=0)
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.WAITING, db_index=True)
    period = models.CharField("دوره", max_length=7, db_index=True)
    payout = models.ForeignKey(Payout, null=True, blank=True, on_delete=models.SET_NULL, related_name="commissions", verbose_name="تسویه")
    locked = models.BooleanField("مبلغ دستی", default=False, help_text="روشن: پورسانت دیگر خودکار حساب نمی‌شود.")
    created_at = models.DateTimeField("تاریخ", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "پورسانت"
        verbose_name_plural = "پورسانت‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"پورسانت سفارش {self.order.number}"
