from django.db import models
from django.db.models import Max, Min
from django.urls import reverse
from django.utils import timezone

from core.models import Media, SeoFields
from pricing.models import Album, PricingSettings, Size

SALE_STATUS_CHOICES = [
    ("available", "موجود"),
    ("unavailable", "ناموجود"),
    ("showroom", "نمایشگاهی"),
    ("coming_soon", "به‌زودی"),
    ("inquiry_only", "استعلام قیمت"),
]
BLOCKED_SALE_STATUSES = {"unavailable", "showroom", "coming_soon", "inquiry_only"}

STOCK_CHOICES = [
    ("instock", "موجود"),
    ("outofstock", "ناموجود"),
    ("onbackorder", "پیش‌سفارش"),
]


# ---------------------------------------------------------------------------
# طبقه‌بندی‌ها
# ---------------------------------------------------------------------------
class Category(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    name = models.CharField("نام", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children", verbose_name="والد"
    )
    description = models.TextField("توضیحات (HTML)", blank=True)
    image = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    order = models.IntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "دستهٔ محصول"
        verbose_name_plural = "دسته‌های محصول"
        ordering = ["order", "name"]
        unique_together = [("parent", "slug")]

    def __str__(self):
        return self.name

    def ancestors(self):
        chain, node = [], self.parent
        while node is not None and len(chain) < 10:
            chain.insert(0, node)
            node = node.parent
        return chain

    @property
    def path(self):
        return "/".join([c.slug for c in self.ancestors()] + [self.slug])

    def get_absolute_url(self):
        return f"/product-category/{self.path}/"

    def descendant_ids(self):
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            ids += frontier
        return ids


class ProductTag(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    name = models.CharField("نام", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True, unique=True)
    description = models.TextField("توضیحات", blank=True)

    class Meta:
        verbose_name = "برچسب محصول"
        verbose_name_plural = "برچسب‌های محصول"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/product-tag/{self.slug}/"


class Brand(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    name = models.CharField("نام", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True, unique=True)
    description = models.TextField("توضیحات", blank=True)
    logo = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "برند"
        verbose_name_plural = "برندها"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/brand/{self.slug}/"


class Attribute(models.Model):
    """ویژگی محصول (شانه، تراکم، اندازه، رنگ زمینه و...)."""

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    slug = models.SlugField("نامک", max_length=100, unique=True, help_text="مثلاً reeds-per-meter")
    label = models.CharField("عنوان", max_length=100)
    is_public = models.BooleanField(
        "صفحهٔ آرشیو دارد", default=False, help_text="آدرس آرشیو: /<نامک ویژگی>/<نامک مقدار>/"
    )
    show_in_filters = models.BooleanField("در فیلترها", default=True)
    order = models.IntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "ویژگی"
        verbose_name_plural = "ویژگی‌ها"
        ordering = ["order", "label"]

    def __str__(self):
        return self.label


class AttributeTerm(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name="terms", verbose_name="ویژگی")
    name = models.CharField("مقدار", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True)
    description = models.TextField("توضیحات", blank=True)
    order = models.IntegerField("ترتیب", default=0)

    class Meta:
        verbose_name = "مقدار ویژگی"
        verbose_name_plural = "مقادیر ویژگی"
        ordering = ["attribute", "order", "name"]
        unique_together = [("attribute", "slug")]

    def __str__(self):
        return f"{self.attribute.label}: {self.name}"

    def get_absolute_url(self):
        return f"/{self.attribute.slug}/{self.slug}/"


# ---------------------------------------------------------------------------
# محصول و تنوع
# ---------------------------------------------------------------------------
class ProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=Product.Status.PUBLISH)


class Product(SeoFields):
    class Status(models.TextChoices):
        PUBLISH = "publish", "منتشرشده"
        DRAFT = "draft", "پیش‌نویس"
        PRIVATE = "private", "خصوصی"

    class Kind(models.TextChoices):
        SIMPLE = "simple", "ساده"
        VARIABLE = "variable", "متغیر (چند سایز)"

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    title = models.CharField("عنوان", max_length=300)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True, unique=True)
    english_name = models.CharField("نام انگلیسی", max_length=300, blank=True)
    content = models.TextField("توضیحات کامل (HTML)", blank=True)
    short_description = models.TextField("توضیح کوتاه", blank=True)
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.PUBLISH, db_index=True)
    kind = models.CharField("نوع", max_length=20, choices=Kind.choices, default=Kind.VARIABLE)
    sku = models.CharField("کد کالا", max_length=100, blank=True)

    image = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="تصویر اصلی")
    gallery = models.ManyToManyField(Media, through="ProductImage", related_name="gallery_products", blank=True)

    categories = models.ManyToManyField(Category, related_name="products", blank=True, verbose_name="دسته‌ها")
    primary_category = models.ForeignKey(
        Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_products", verbose_name="دستهٔ اصلی"
    )
    tags = models.ManyToManyField(ProductTag, related_name="products", blank=True, verbose_name="برچسب‌ها")
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name="products", verbose_name="برند")
    specs = models.ManyToManyField(
        AttributeTerm, related_name="products", blank=True, verbose_name="مشخصات",
        help_text="ویژگی‌های ثابت محصول (شانه، تراکم، جنس نخ و...)",
    )

    # قیمت‌گذاری آلبومی (ICSD Price Manager)
    album = models.ForeignKey(Album, null=True, blank=True, on_delete=models.SET_NULL, related_name="products", verbose_name="آلبوم قیمت")
    custom_base_price = models.DecimalField(
        "قیمت پایهٔ اختصاصی", max_digits=20, decimal_places=2, null=True, blank=True,
        help_text="اگر پر شود به‌جای قیمت پایهٔ آلبوم استفاده می‌شود",
    )
    sale_status = models.CharField("وضعیت فروش", max_length=20, choices=SALE_STATUS_CHOICES, default="available", db_index=True)

    # کش برای فهرست و مرتب‌سازی
    min_price = models.PositiveBigIntegerField("کمترین قیمت", null=True, blank=True, editable=False, db_index=True)
    max_price = models.PositiveBigIntegerField("بیشترین قیمت", null=True, blank=True, editable=False)
    stock_status = models.CharField("موجودی", max_length=20, choices=STOCK_CHOICES, default="instock", db_index=True)

    rating_avg = models.DecimalField("میانگین امتیاز", max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField("تعداد امتیاز", default=0)
    views = models.PositiveIntegerField("بازدید", default=0)
    menu_order = models.IntegerField("ترتیب", default=0)

    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now, db_index=True)
    modified_at = models.DateTimeField("آخرین ویرایش", default=timezone.now)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ["-published_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/product/{self.slug}/"

    @property
    def in_stock(self):
        return self.stock_status != "outofstock" and self.sale_status == "available"

    @property
    def is_purchasable(self):
        return self.sale_status not in BLOCKED_SALE_STATUSES and self.stock_status != "outofstock"

    def refresh_price_cache(self, save=True):
        vs = self.variations.all()
        live = vs.filter(is_available=True)
        agg = (live if live.exists() else vs).aggregate(
            lo=Min("final_price"), lo_sale=Min("sale_price"), hi=Max("final_price")
        )
        lows = [x for x in (agg["lo"], agg["lo_sale"]) if x]
        self.min_price = min(lows) if lows else None
        self.max_price = agg["hi"]
        if self.sale_status != "available":
            self.stock_status = "outofstock" if self.sale_status == "unavailable" else "onbackorder"
        elif vs.exists():
            self.stock_status = "instock" if live.exists() else "outofstock"
        if save:
            Product.objects.filter(pk=self.pk).update(
                min_price=self.min_price, max_price=self.max_price, stock_status=self.stock_status
            )

    def save(self, *args, **kwargs):
        reprice = False
        if self.pk:
            old = Product.objects.filter(pk=self.pk).values("album_id", "custom_base_price", "sale_status").first()
            reprice = old != {"album_id": self.album_id, "custom_base_price": self.custom_base_price, "sale_status": self.sale_status}
        super().save(*args, **kwargs)
        if reprice:
            Variation.reprice_queryset(self.variations.all())


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name="+")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "تصویر گالری"
        verbose_name_plural = "گالری تصاویر"


class Variation(models.Model):
    """تنوع محصول = محصول × سایز. قیمت از آلبوم محصول محاسبه می‌شود؛ قابل override در سطح سایز."""

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variations")
    size = models.ForeignKey(Size, null=True, blank=True, on_delete=models.PROTECT, related_name="variations", verbose_name="سایز")
    attributes = models.ManyToManyField(AttributeTerm, blank=True, related_name="variations", verbose_name="سایر ویژگی‌ها (رنگ و...)")
    sku = models.CharField("کد", max_length=100, blank=True)
    image = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    description = models.TextField("توضیح", blank=True)
    menu_order = models.IntegerField("ترتیب", default=0)

    # override در سطح سایز (معادل size_overrides افزونه)
    override_price = models.DecimalField(
        "قیمت خرید اختصاصی", max_digits=20, decimal_places=2, null=True, blank=True,
        help_text="اگر پر شود، به‌جای فرمول آلبوم استفاده می‌شود (markup و حمل همچنان اعمال می‌شود)",
    )
    manual_price = models.PositiveBigIntegerField(
        "قیمت نهایی دستی", null=True, blank=True, help_text="برای محصولی که آلبوم ندارد"
    )
    sale_price = models.PositiveBigIntegerField("قیمت حراج (نهایی)", null=True, blank=True)
    pair_only = models.BooleanField("فقط زوج", null=True, blank=True, help_text="خالی = پیش‌فرض سایز")
    is_available = models.BooleanField("موجود", default=True)

    final_price = models.PositiveBigIntegerField("قیمت نهایی", null=True, blank=True, editable=False, db_index=True)
    purchase_price = models.PositiveBigIntegerField("قیمت خرید", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "تنوع (سایز)"
        verbose_name_plural = "تنوع‌ها (سایزها)"
        ordering = ["menu_order", "pk"]

    def __str__(self):
        return f"{self.product.title} — {self.size.label if self.size else self.sku}"

    @property
    def is_pair_only(self):
        if self.pair_only is not None:
            return self.pair_only
        return bool(self.size and self.size.default_pair_only)

    @property
    def price(self):
        return self.sale_price or self.final_price

    @property
    def stock_status(self):
        return "instock" if self.is_available else "outofstock"

    def compute_prices(self, settings_obj=None, product=None):
        product = product or self.product
        album = product.album
        purchase = None
        if self.override_price is not None:
            purchase = self.override_price
        elif album and album.is_active and self.size and self.size.is_active:
            purchase = album.purchase_price(self.size, product.custom_base_price)
        if purchase is not None:
            st = settings_obj or PricingSettings.load()
            self.purchase_price = int(purchase)
            self.final_price = st.apply_markup(purchase)
        else:
            self.purchase_price = None
            self.final_price = self.manual_price
        return self.final_price

    def save(self, *args, **kwargs):
        self.compute_prices()
        super().save(*args, **kwargs)

    @classmethod
    def reprice_queryset(cls, qs):
        st = PricingSettings.load()
        items = list(qs.select_related("product__album__base_size", "size"))
        product_ids = set()
        for v in items:
            v.compute_prices(st, v.product)
            product_ids.add(v.product_id)
        cls.objects.bulk_update(items, ["final_price", "purchase_price"], batch_size=1000)
        for p in Product.objects.filter(pk__in=product_ids):
            p.refresh_price_cache()
        return len(items)


class Review(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    author_name = models.CharField("نام", max_length=200)
    author_email = models.EmailField("ایمیل", blank=True)
    rating = models.PositiveSmallIntegerField("امتیاز", null=True, blank=True)
    content = models.TextField("متن")
    is_approved = models.BooleanField("تأییدشده", default=False, db_index=True)
    created_at = models.DateTimeField("تاریخ", default=timezone.now)

    class Meta:
        verbose_name = "نظر محصول"
        verbose_name_plural = "نظرات محصول"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author_name} — {self.product}"
