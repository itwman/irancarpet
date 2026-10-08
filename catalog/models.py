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
    video_url = models.URLField("ویدیوی فرش", blank=True, max_length=400,
                                help_text="پیوند ویدیو در آپارات (aparat.com/v/...) یا فایل mp4. در صفحهٔ فرش و نتایج گوگل نمایش داده می‌شود.")
    content = models.TextField("توضیحات کامل (HTML)", blank=True)
    short_description = models.TextField("توضیح کوتاه", blank=True)
    # متن خودکار از «قالب متن محصول» (برنامهٔ content)
    use_template = models.BooleanField(
        "متن از قالب", default=False,
        help_text="روشن: توضیحات و خلاصه از «قالب متن محصول» ساخته می‌شود و با قیمت و تنظیمات به‌روز می‌ماند؛ "
                  "متن دستی بالا نگه داشته می‌شود ولی نمایش داده نمی‌شود.")
    design_name = models.CharField("نام نقشه", max_length=120, blank=True, db_index=True,
                                   help_text="مثل «آرشان». فرش‌های هم‌آلبوم با نقشهٔ یکسان، «رنگ‌های دیگر» همدیگر نشان داده می‌شوند.")
    color_count = models.PositiveSmallIntegerField("تعداد رنگ", null=True, blank=True)
    custom_note = models.TextField("یادداشت اختصاصی", blank=True,
                                   help_text="یک یا دو جملهٔ مخصوص همین فرش (مثلاً حس طرح یا پیشنهاد اتاق)؛ جای {یادداشت} در قالب می‌نشیند.")
    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.PUBLISH, db_index=True)
    kind = models.CharField("نوع", max_length=20, choices=Kind.choices, default=Kind.VARIABLE)
    sku = models.CharField("کد کالا", max_length=100, blank=True, help_text="خالی بگذارید تا خودکار ساخته شود")

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
    only_sizes = models.ManyToManyField(
        Size, blank=True, related_name="+", verbose_name="فقط این سایزهای آلبوم",
        help_text="خالی = همهٔ سایزهای آلبوم. مثلاً برای محصول جدای «فرش گرد قطر ۱٫۵» فقط همان سایز را انتخاب کنید؛ "
                  "قیمتش از همان آلبوم می‌آید و فرش اصلی هم همهٔ سایزهایش را نگه می‌دارد.")
    single_sizes = models.ManyToManyField(
        Size, blank=True, related_name="+", verbose_name="این سایزها تکی هم فروخته شوند",
        help_text="سایزهایی که در آلبوم «فقط جفت» هستند ولی در این محصول یک‌تخته هم سفارش گرفته می‌شوند.")
    # مارکت‌پلیس: کالای فروشندهٔ دیگر (خالی = کالای خود ایران کارپت)
    seller = models.ForeignKey("market.Seller", null=True, blank=True, on_delete=models.SET_NULL, related_name="products",
                               verbose_name="فروشنده", help_text="خالی یعنی کالای خود ایران کارپت")
    review_status = models.CharField("بررسی", max_length=10, blank=True, db_index=True, choices=[
        ("pending", "در انتظار بررسی"), ("approved", "تأیید شد"), ("rejected", "رد شد")])
    review_note = models.CharField("پیام بررسی به فروشنده", max_length=300, blank=True)
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
    # نمایهٔ جستجو (catalog/search.py): متن نرمال‌شده بدون فاصله
    search_title = models.CharField(max_length=600, blank=True, editable=False)
    search_text = models.TextField(blank=True, editable=False)

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
        pool = live if live.exists() else vs
        agg = pool.aggregate(hi=Max("final_price"))
        self.min_price = min((v.price for v in pool.only("sale_price", "final_price") if v.price), default=None)
        if self.album_id:
            # مثل سایت قبلی: قیمت محصول آلبومی = قیمت سایز پایه (۱۲ متری)
            base = pool.filter(size_id=self.album.base_size_id).only("sale_price", "final_price").first()
            if base and base.price:
                self.min_price = base.price
        self.max_price = agg["hi"]
        if self.sale_status != "available":
            self.stock_status = "outofstock" if self.sale_status == "unavailable" else "onbackorder"
        elif vs.exists():
            self.stock_status = "instock" if live.exists() else "outofstock"
        if save:
            Product.objects.filter(pk=self.pk).update(
                min_price=self.min_price, max_price=self.max_price, stock_status=self.stock_status
            )

    @staticmethod
    def next_sku():
        """کد کالای بعدی: یکی بیشتر از بزرگ‌ترین کد عددی موجود (مثل افزونهٔ کدساز وردپرس)."""
        nums = [int(x) for x in Product.objects.exclude(sku="").values_list("sku", flat=True) if x.isdigit() and len(x) < 12]
        return str(max(nums, default=100000) + 1)

    def save(self, *args, **kwargs):
        if not (self.sku or "").strip():
            self.sku = self.next_sku()
        reprice = False
        if self.pk:
            old = Product.objects.filter(pk=self.pk).values("album_id", "custom_base_price", "sale_status").first()
            reprice = old != {"album_id": self.album_id, "custom_base_price": self.custom_base_price, "sale_status": self.sale_status}
        from .search import index_values

        self.search_title, self.search_text = index_values(self)
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
    stock_qty = models.PositiveIntegerField("تعداد موجودی", null=True, blank=True,
                                            help_text="خالی = بی‌شمار. با هر سفارش پرداخت‌شده کم می‌شود و در صفر ناموجود می‌شود.")

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
    def on_sale(self):
        """حراج فقط وقتی معتبر است که از قیمت نهایی کمتر باشد."""
        return bool(self.sale_price and self.final_price and self.sale_price < self.final_price)

    @property
    def price(self):
        return self.sale_price if self.on_sale else (self.final_price or self.sale_price)

    @property
    def price_source(self):
        """قیمت این سایز از کجا می‌آید (برای نمایش در پنل)."""
        product = self.product
        album = product.album
        if self.override_price is not None:
            return "override", "قیمت خرید اختصاصی همین سایز"
        if album and album.is_active and self.size and self.size.is_active:
            if product.custom_base_price is not None:
                return "custom", "قیمت پایهٔ اختصاصی محصول"
            return "album", "قیمت آلبوم"
        if album and not album.is_active:
            return "manual", "قیمت دستی (آلبوم غیرفعال است)"
        return "manual", "قیمت دستی"

    @property
    def stock_status(self):
        return "instock" if self.is_available else "outofstock"

    def compute_prices(self, settings_obj=None, product=None):
        """قیمت نهایی: از آلبوم (اگر محصول آلبوم دارد و این سایز در آلبوم هست)، وگرنه قیمت دستی."""
        product = product or self.product
        album = product.album
        size = self.size if self.size_id else None
        if album and album.is_active and size and size.is_active and album.offers(size):
            if self.override_price is not None:
                final = album.price_from_purchase(self.override_price, size)
                purchase = self.override_price
            else:
                final = album.size_price(size, product.custom_base_price)
                purchase = album.purchase_price(size, product.custom_base_price)
            if final is not None:
                self.final_price = final
                self.purchase_price = int(purchase) if purchase is not None else None
                return self.final_price
        self.purchase_price = None
        self.final_price = self.manual_price
        return self.final_price

    def save(self, *args, **kwargs):
        self.compute_prices()
        super().save(*args, **kwargs)

    @classmethod
    def reprice_queryset(cls, qs, scale_sale=True):
        """محاسبهٔ دوبارهٔ قیمت‌ها. اگر قیمت نهایی عوض شود، قیمت حراج هم هم‌نسبت تغییر می‌کند تا درصد تخفیف بماند."""
        st = PricingSettings.load()
        items = list(qs.select_related("product__album__base_size", "size"))
        product_ids, album_sizes = set(), {}
        for v in items:
            a = v.product.album
            if a is not None:
                if a.pk not in album_sizes:
                    album_sizes[a.pk] = set(a.sizes.values_list("pk", flat=True))
                a._size_ids = album_sizes[a.pk]
            old = v.final_price
            v.compute_prices(st, v.product)
            if scale_sale and v.sale_price and old and v.final_price and old != v.final_price:
                v.sale_price = int(round(v.sale_price * v.final_price / old, -4)) or None
            product_ids.add(v.product_id)
        cls.objects.bulk_update(items, ["final_price", "purchase_price", "sale_price"], batch_size=1000)
        for p in Product.objects.filter(pk__in=product_ids).select_related("album"):
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
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="کاربر")
    mobile = models.CharField("موبایل", max_length=11, blank=True)
    verified = models.BooleanField("خریدار این فرش", default=False, help_text="نظر از طرف کسی که همین فرش را خریده")

    class Meta:
        verbose_name = "نظر محصول"
        verbose_name_plural = "نظرات محصول"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author_name} — {self.product}"


class ReviewPhoto(models.Model):
    """عکس مشتری از فرش در خانه‌اش (همراه نظر)."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField("عکس", upload_to="reviews/%Y/%m/")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "عکس نظر"
        verbose_name_plural = "عکس‌های نظر"

    def save(self, *a, **kw):
        if self.image and not self.pk and not getattr(self.image, "_committed", True):
            from core.images import optimize_upload

            self.image, _w, _h = optimize_upload(self.image.file) if hasattr(self.image, "file") else (self.image, 0, 0)
        super().save(*a, **kw)

    @property
    def url(self):
        return self.image.url if self.image else ""
