"""قیمت‌گذاری آلبومی — نسخهٔ جنگوی افزونهٔ ICSD Price Manager v2.

فرمول‌ها (عیناً مطابق افزونه):
    نرخ هر متر مربع  = قیمت پایه آلبوم ÷ مساحت سایز پایه
    قیمت خرید سایز   = نرخ × مساحت سایز  (+ پرتی، فقط برای سایزهای needs_waste)
    قیمت نهایی       = گرد( قیمت خرید × (۱ + markup٪) + حمل ثابت )

گرد قطر D → مساحت = D² (نه π r²).
"""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.utils import timezone


class PricingSettings(models.Model):
    """تنظیمات سراسری قیمت‌گذاری (یک ردیف)."""

    class RoundMethod(models.TextChoices):
        UP = "up", "رو به بالا"
        NEAREST = "nearest", "نزدیک‌ترین"

    markup_percent = models.DecimalField("درصد سود فروش", max_digits=6, decimal_places=2, default=Decimal("15"))
    shipping_fixed = models.PositiveBigIntegerField("هزینهٔ حمل ثابت (تومان)", default=500_000)
    round_to = models.PositiveIntegerField("گرد کردن به (تومان)", default=100_000)
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
        from catalog.models import Variation  # جلوگیری از import چرخشی

        Variation.reprice_queryset(Variation.objects.all())

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


class Album(models.Model):
    class WasteType(models.TextChoices):
        FIXED = "fixed", "مبلغ ثابت"
        PERCENT = "percent", "درصدی"

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False, help_text="شناسهٔ گروه mnswmc")
    name = models.CharField("نام آلبوم", max_length=160)
    code = models.CharField("کد", max_length=40, unique=True)
    company = models.CharField("کارخانه / برند", max_length=120, blank=True)
    description = models.TextField("توضیحات", blank=True)
    base_size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="+", verbose_name="سایز پایه")
    base_price = models.DecimalField("قیمت پایه (خرید، تومان)", max_digits=20, decimal_places=2, default=0)
    waste_type = models.CharField("نوع پرتی", max_length=20, choices=WasteType.choices, default=WasteType.FIXED)
    waste_value = models.DecimalField("مقدار پرتی", max_digits=20, decimal_places=2, default=0)
    is_active = models.BooleanField("فعال", default=True)
    sort_order = models.IntegerField("ترتیب", default=0)
    last_updated = models.DateTimeField("آخرین تغییر قیمت", default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "آلبوم قیمت"
        verbose_name_plural = "آلبوم‌های قیمت"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def purchase_price(self, size, custom_base_price=None):
        """هستهٔ فرمول: قیمت خرید یک سایز در این آلبوم."""
        base_area = Decimal(self.base_size.area or 0)
        base_price = Decimal(custom_base_price if custom_base_price is not None else self.base_price)
        if base_area <= 0 or base_price <= 0 or not size:
            return None
        price = base_price / base_area * Decimal(size.area)
        if size.needs_waste and self.waste_value > 0:
            if self.waste_type == self.WasteType.PERCENT:
                price = price * (1 + self.waste_value / 100)
            else:
                price = price + self.waste_value
        return price

    def set_base_price(self, new_price, user=None, reason="album_base_update"):
        old = self.base_price
        self.base_price = Decimal(new_price)
        self.last_updated = timezone.now()
        self.save()
        PriceLog.objects.create(album=self, old_price=old, new_price=self.base_price, user=user,
                                reason=reason + ("+scaled" if getattr(self, "_scaled", False) else ""))

    def save(self, *args, **kwargs):
        changed, ratio = False, None
        self._scaled = False
        if self.pk:
            old = Album.objects.filter(pk=self.pk).values("base_price", "base_size_id", "waste_type", "waste_value", "is_active").first()
            changed = old != {
                "base_price": self.base_price, "base_size_id": self.base_size_id,
                "waste_type": self.waste_type, "waste_value": self.waste_value, "is_active": self.is_active,
            }
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
