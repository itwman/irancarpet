"""قیمت‌گذاری آلبومی — نسخهٔ جنگوی افزونهٔ «قیمت‌گذاری آلبومی ایران‌کارپت» (irancarpet-album-pricing)

فرمول‌ها (عیناً مطابق افزونه؛ همهٔ تنظیمات برای هر آلبوم جداست):
    قیمت فروش سایز پایه (۱۲ متری) = قیمت خرید × (۱ + درصد سود) + هزینهٔ ارسال
    قیمت فروش هر سایز              = قیمت فروش پایه × (متراژ ÷ متراژ پایه)
    سایز با پرتی (۹ متری ۲٫۵×۳٫۵)  = همان + پرتی (مبلغ ثابت یا درصدی)
    همه رو به بالا به مضرب «گرد کردن» (پیش‌فرض ۱۰٬۰۰۰ تومان) گرد می‌شوند.

مشتری برای محصولِ دارای آلبوم، همهٔ سایزهای فعال آن آلبوم را می‌بیند.
"""
import math
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class PricingSettings(models.Model):
    """تنظیمات پیش‌فرض قیمت‌گذاری (یک ردیف) — برای آلبوم‌های تازه."""

    class RoundMethod(models.TextChoices):
        UP = "up", "رو به بالا"
        NEAREST = "nearest", "نزدیک‌ترین"

    markup_percent = models.DecimalField("درصد سود پیش‌فرض آلبوم تازه", max_digits=6, decimal_places=2, default=Decimal("15"))
    shipping_fixed = models.PositiveBigIntegerField("هزینهٔ ارسال پیش‌فرض آلبوم تازه (تومان)", default=0)
    round_to = models.PositiveIntegerField("گرد کردن پیش‌فرض آلبوم تازه (تومان)", default=10_000)
    round_method = models.CharField("روش گرد کردن", max_length=10, choices=RoundMethod.choices, default=RoundMethod.UP)
    show_size_table = models.BooleanField("نمایش جدول قیمت سایزها در صفحهٔ محصول", default=True)

    class Meta:
        verbose_name = "تنظیمات قیمت‌گذاری"
        verbose_name_plural = "تنظیمات قیمت‌گذاری"

    def __str__(self):
        return "تنظیمات قیمت‌گذاری"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def apply_markup(self, purchase_price):
        """قیمت خرید → قیمت نهایی مشتری (markup + حمل + گرد)."""
        price = Decimal(purchase_price) * (1 + self.markup_percent / 100) + self.shipping_fixed
        if self.round_to > 1:
            step = Decimal(self.round_to)
            mode = ROUND_CEILING if self.round_method == self.RoundMethod.UP else ROUND_HALF_UP
            price = (price / step).quantize(Decimal(1), rounding=mode) * step
        return int(price.quantize(Decimal(1), rounding=ROUND_HALF_UP))


class Size(models.Model):
    class Type(models.TextChoices):
        RECT = "rect", "مستطیل"
        RUNNER = "runner", "کناره"
        RUG = "rug", "قالیچه"
        DOORMAT = "doormat", "پادری / رویه‌پشتی"
        ROUND = "round", "گرد"
        CUSTOM = "custom", "سفارشی / برشی"

    slug = models.SlugField("نامک", max_length=64, unique=True)
    label = models.CharField("عنوان", max_length=160)
    type = models.CharField("نوع", max_length=20, choices=Type.choices, default=Type.RECT)
    width = models.DecimalField("عرض (متر)", max_digits=8, decimal_places=2, default=0)
    length = models.DecimalField("طول (متر)", max_digits=8, decimal_places=2, default=0)
    diameter = models.DecimalField("قطر (متر)", max_digits=8, decimal_places=2, default=0)
    area = models.DecimalField("مساحت (m²)", max_digits=10, decimal_places=4, default=0, help_text="برای گرد: قطر²")
    default_pair_only = models.BooleanField("پیش‌فرض فقط زوج", default=False)
    needs_waste = models.BooleanField("هزینهٔ پرتی دارد", default=False, help_text="فقط ۹ متری مستطیل")
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.IntegerField("ترتیب", default=0)
    legacy_slugs = models.JSONField(
        "نامک‌های قدیمی وردپرس", default=list, blank=True,
        help_text="نامک‌های pa_carpet-size که به این سایز نگاشت می‌شوند (برای ایمپورت)",
    )

    class Meta:
        verbose_name = "سایز"
        verbose_name_plural = "سایزها"
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        if self.type == self.Type.ROUND and self.diameter:
            self.area = self.diameter * self.diameter
        elif self.width and self.length and not self.area:
            self.area = self.width * self.length
        super().save(*args, **kwargs)

    @property
    def dimensions(self):
        if self.type == self.Type.ROUND:
            return f"قطر {_num(self.diameter)} متر"
        if self.length and self.width:
            return f"{_num(self.length)} × {_num(self.width)}"
        return ""


def _num(d):
    s = f"{Decimal(d):.2f}".rstrip("0").rstrip(".")
    return s


def public_title(name, public_name=""):
    """نام آلبوم در لیست قیمت سایت: «700 شانه ورجین» ← «فرش 700 شانه ورجین» (مگر نام دلخواه داده شده باشد)."""
    if (public_name or "").strip():
        return public_name.strip()
    t = (name or "").strip()
    if t.startswith("آلبوم"):
        t = t[len("آلبوم"):].strip(" -–:")
    return t if t.startswith("فرش") else f"فرش {t}"


class Album(models.Model):
    class WasteType(models.TextChoices):
        FIXED = "fixed", "مبلغ ثابت"
        PERCENT = "percent", "درصدی"

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False, help_text="شناسهٔ آلبوم در وردپرس")
    name = models.CharField("نام آلبوم", max_length=160)
    code = models.CharField("کد", max_length=40, unique=True, blank=True, help_text="خالی بگذارید تا خودکار ساخته شود")
    company = models.CharField("کارخانه / برند", max_length=120, blank=True)
    description = models.TextField("توضیحات", blank=True)
    base_size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="+", verbose_name="سایز پایه")
    base_price = models.DecimalField("قیمت خرید ۱۲ متری (تومان)", max_digits=20, decimal_places=2, default=0)
    profit_percent = models.DecimalField("درصد سود", max_digits=6, decimal_places=2, default=Decimal("15"))
    shipping_fixed = models.PositiveBigIntegerField("هزینهٔ ارسال (تومان)", default=0,
                                                    help_text="به قیمت ۱۲ متری اضافه می‌شود و برای بقیهٔ سایزها به نسبت متراژ")
    waste_type = models.CharField("نوع پرتی", max_length=20, choices=WasteType.choices, default=WasteType.FIXED)
    waste_value = models.DecimalField("مقدار پرتی", max_digits=20, decimal_places=2, default=0,
                                      help_text="فقط برای سایزهای «با پرتی» (۹ متری ۲٫۵×۳٫۵)، روی قیمت فروش")
    round_to = models.PositiveIntegerField("گرد کردن به (تومان)", default=10_000, help_text="رو به بالا")
    sizes = models.ManyToManyField(Size, blank=True, related_name="albums", verbose_name="سایزهای آلبوم",
                                   help_text="مشتری همین سایزها را برای محصولات این آلبوم می‌بیند")
    even_sizes = models.ManyToManyField(Size, blank=True, related_name="+", verbose_name="سایزهای فقط زوج")
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.IntegerField("ترتیب", default=0)
    last_updated = models.DateTimeField("آخرین تغییر قیمت", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    # صفحهٔ عمومی «لیست قیمت»
    in_price_list = models.BooleanField("نمایش در لیست قیمت سایت", default=True)
    public_name = models.CharField("نام در لیست قیمت", max_length=160, blank=True,
                                   help_text="خالی = «فرش» + نام آلبوم؛ مثلاً «فرش 700 شانه ورجین مهرآوران»")
    slug = models.SlugField("نامک صفحهٔ لیست", max_length=160, allow_unicode=True, blank=True,
                            help_text="آدرس: /carpets-price-list/نامک/ — خالی بگذارید تا از نام ساخته شود")
    list_intro = models.TextField("متن معرفی در صفحهٔ لیست", blank=True, help_text="HTML ساده؛ زیر فهرست فرش‌ها نمایش داده می‌شود")
    seo_title = models.CharField("عنوان سئو", max_length=300, blank=True,
                                 help_text="خالی = خودکار. متغیرها: %title% %currentmonth% %currentyear% %sitename%")
    seo_description = models.TextField("توضیحات متا", blank=True, help_text="خالی = خودکار از قیمت‌ها")

    PRICE_FIELDS = ("base_price", "base_size_id", "profit_percent", "shipping_fixed", "waste_type", "waste_value", "round_to", "is_active")

    class Meta:
        verbose_name = "آلبوم قیمت"
        verbose_name_plural = "آلبوم‌های قیمت"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def title(self):
        return public_title(self.name, self.public_name)

    def get_absolute_url(self):
        from .pricelist import PRICE_LIST_PATH

        return f"{PRICE_LIST_PATH}{self.slug}/"

    def make_slug(self):
        from django.utils.text import slugify

        base = slugify(self.title, allow_unicode=True)[:150] or (self.code or "album").lower()
        slug, n = base, 2
        while Album.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    # ------------------------------------------------------------ فرمول
    def _base_area(self):
        a = Decimal(self.base_size.area or 0)
        return a if a > 0 else Decimal(12)

    def sale_base(self, buy=None):
        """قیمت فروش سایز پایه (قبل از گرد کردن)."""
        buy = Decimal(buy if buy is not None else self.base_price)
        return buy * (1 + Decimal(self.profit_percent) / 100) + Decimal(self.shipping_fixed)

    def _waste(self, price, size):
        if size.needs_waste and self.waste_value:
            if self.waste_type == self.WasteType.PERCENT:
                return price * (1 + Decimal(self.waste_value) / 100)
            return price + Decimal(self.waste_value)
        return price

    def raw_price(self, size, buy=None):
        base = self.sale_base(buy)
        if size.pk == self.base_size_id:
            return base
        return self._waste(base * Decimal(size.area) / self._base_area(), size)

    def round_up(self, price):
        price = Decimal(price)
        if not self.round_to:
            return int(price.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        steps = float(price / Decimal(self.round_to))
        return int(math.ceil(steps - 1e-6)) * int(self.round_to)

    def size_price(self, size, buy=None):
        """قیمت فروش نهایی یک سایز (همان عددی که مشتری می‌بیند)."""
        buy = Decimal(buy if buy is not None else self.base_price)
        if buy <= 0 or not size or not size.area:
            return None
        return self.round_up(self.raw_price(size, buy))

    def price_from_purchase(self, purchase, size):
        """قیمت خرید اختصاصی یک سایز → قیمت فروش (سود + سهم ارسال به نسبت متراژ)."""
        ship = Decimal(self.shipping_fixed) * Decimal(size.area or 0) / self._base_area()
        return self.round_up(Decimal(purchase) * (1 + Decimal(self.profit_percent) / 100) + ship)

    def purchase_price(self, size, buy=None):
        """قیمت خرید معادل یک سایز (فقط برای نمایش)."""
        buy = Decimal(buy if buy is not None else self.base_price)
        if buy <= 0 or not size:
            return None
        return buy * Decimal(size.area) / self._base_area()

    def size_ids(self):
        if not hasattr(self, "_size_ids"):
            self._size_ids = set(self.sizes.values_list("pk", flat=True)) if self.pk else set()
        return self._size_ids

    def offers(self, size):
        ids = self.size_ids()
        return bool(size) and (not ids or size.pk in ids)

    def set_base_price(self, new_price, user=None, reason="album_base_update"):
        old = self.base_price
        self.base_price = Decimal(new_price)
        self.last_updated = timezone.now()
        self.save()
        PriceLog.objects.create(album=self, old_price=old, new_price=self.base_price, user=user,
                                reason=reason + ("+scaled" if getattr(self, "_scaled", False) else ""))

    @staticmethod
    def next_code():
        nums = [int(c[4:]) for c in Album.objects.filter(code__startswith="ALB-").values_list("code", flat=True) if c[4:].isdigit()]
        return f"ALB-{max(nums, default=0) + 1:03d}"

    def save(self, *args, **kwargs):
        if not (self.code or "").strip():
            self.code = self.next_code()
        if not (self.slug or "").strip():
            self.slug = self.make_slug()
        changed, ratio = False, None
        self._scaled = False
        if self.pk:
            old = Album.objects.filter(pk=self.pk).values(*self.PRICE_FIELDS).first()
            changed = old != {f: getattr(self, f) for f in self.PRICE_FIELDS}
            if old and old["base_price"] != self.base_price:
                self.last_updated = timezone.now()
                if old["base_price"] and self.base_price and old["base_size_id"] == self.base_size_id:
                    ratio = Decimal(self.base_price) / Decimal(old["base_price"])
        super().save(*args, **kwargs)
        if changed:
            self.reprice(ratio)

    def reprice(self, ratio=None):
        """قیمت همهٔ سایزهای محصولات آلبوم را دوباره حساب می‌کند.
        ratio: نسبت قیمت پایهٔ تازه به قبلی؛ قیمت‌های اختصاصی محصولات هم به همین نسبت تغییر می‌کنند
        تا اختلاف نسبی آن‌ها با آلبوم (مثلاً ارزان‌تر بودن پلی‌استر) حفظ شود."""
        from catalog.models import Variation

        if ratio and ratio != 1:
            from .overrides import scale_album_overrides

            scale_album_overrides(self, ratio)
            self._scaled = True
        Variation.reprice_queryset(Variation.objects.filter(product__album=self))


class PriceLog(models.Model):
    album = models.ForeignKey(Album, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    old_price = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    new_price = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    reason = models.CharField(max_length=120, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "لاگ قیمت"
        verbose_name_plural = "لاگ تغییرات قیمت"
        ordering = ["-created_at"]


STANDARD_SIZES = [
    # slug, label, type, width, length, diameter, area, pair_only, needs_waste, order, legacy WP slugs
    ("12-meter", "۱۲ متری (۴ × ۳)", "rect", 3, 4, 0, 12, False, False, 10, ["12"]),
    ("9-meter", "۹ متری مستطیل (۳.۵ × ۲.۵)", "rect", 2.5, 3.5, 0, 9, False, True, 20, ["9"]),
    ("6-meter", "۶ متری (۳ × ۲)", "rect", 2, 3, 0, 6, False, False, 30, ["6"]),
    ("9-meter-square", "۹ متری مربع (۳ × ۳)", "rect", 3, 3, 0, 9, True, False, 40, ["فرش-3-در-3"]),
    ("15-meter", "۱۵ متری (۵ × ۳)", "rect", 3, 5, 0, 15, True, False, 50, ["15"]),
    ("24-meter", "۲۴ متری (۶ × ۴)", "rect", 4, 6, 0, 24, True, False, 60, ["24-متری"]),
    ("runner-4x1", "کناره ۴ × ۱", "runner", 1, 4, 0, 4, True, False, 70, ["کناره-41", "کناره-4x1"]),
    ("runner-3x1", "کناره ۳ × ۱", "runner", 1, 3, 0, 3, True, False, 80, ["کناره-31", "کناره-3x1"]),
    ("runner-2x1", "کناره ۲ × ۱", "runner", 1, 2, 0, 2, True, False, 90, ["کناره-21", "کناره-2x1"]),
    ("rug-225x150", "قالیچه ۲.۲۵ × ۱.۵", "rug", 1.5, 2.25, 0, 3.375, True, False, 100, ["ghalicheh", "قالیچه-1-5x2-25"]),
    ("rug-150x100", "قالیچه ۱.۵ × ۱", "rug", 1, 1.5, 0, 1.5, True, False, 110, ["ذرع-و-نیم-1-51-متری", "درخ-و-نیم", "قالیچه-1x1-50"]),
    ("doormat-85x50", "پادری ۰.۸۵ × ۰.۵", "doormat", 0.5, 0.85, 0, 0.425, True, False, 120, ["پادری", "5983-سانتی-متر", "5080-سانتی-متر"]),
    ("pillow-100x50", "رویه‌پشتی ۱ × ۰.۵", "doormat", 0.5, 1, 0, 0.5, True, False, 130, ["رویه-پشتی", "50100-سانتی-متر"]),
    ("round-d3", "گرد قطر ۳", "round", 0, 0, 3, 9, True, False, 140, []),
    ("round-d2", "گرد قطر ۲", "round", 0, 0, 2, 4, True, False, 150, []),
    ("round-d150", "گرد قطر ۱.۵", "round", 0, 0, 1.5, 2.25, True, False, 160, ["150-150-سانتی-متر"]),
    ("round-d1", "گرد قطر ۱", "round", 0, 0, 1, 1, True, False, 170, ["100100-سانتی-متر"]),
]


def seed_sizes():
    for slug, label, typ, w, l, d, area, pair, waste, order, legacy in STANDARD_SIZES:
        Size.objects.get_or_create(
            slug=slug,
            defaults=dict(
                label=label, type=typ, width=w, length=l, diameter=d, area=area,
                default_pair_only=pair, needs_waste=waste, sort_order=order, legacy_slugs=legacy,
            ),
        )
