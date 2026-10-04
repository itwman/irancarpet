from django.conf import settings
from django.db import models


class SeoFields(models.Model):
    """فیلدهای سئو مشترک (معادل متای Rank Math).

    در عنوان و توضیحات می‌توان از متغیرهای Rank Math مثل %title% و %sep% استفاده کرد.
    """

    seo_title = models.CharField("عنوان سئو", max_length=300, blank=True)
    seo_description = models.TextField("توضیحات متا", blank=True)
    focus_keyword = models.CharField("کلمهٔ کلیدی", max_length=300, blank=True)
    robots = models.CharField(
        "robots", max_length=100, blank=True, help_text="مثلاً noindex,nofollow — خالی یعنی index,follow"
    )
    canonical_url = models.CharField("canonical", max_length=500, blank=True)

    class Meta:
        abstract = True

    @property
    def is_noindex(self):
        return "noindex" in (self.robots or "")


class Media(models.Model):
    """فایل رسانه (معادل attachment وردپرس). مسیر فایل نسبت به پوشهٔ uploads است."""

    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    file = models.FileField("فایل", upload_to="%Y/%m/", max_length=500)
    title = models.CharField("عنوان", max_length=500, blank=True)
    alt = models.CharField("متن جایگزین (alt)", max_length=500, blank=True)
    caption = models.TextField("زیرنویس", blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "رسانه"
        verbose_name_plural = "رسانه‌ها"

    def __str__(self):
        return self.title or self.file.name

    @property
    def url(self):
        return self.file.url if self.file else ""

    @property
    def absolute_url(self):
        return settings.SITE_URL + self.url if self.file else ""


class SiteSettings(models.Model):
    """تنظیمات کلی سایت (یک ردیف)."""

    site_name = models.CharField("نام سایت", max_length=200, default="ایران کارپت")
    tagline = models.CharField("شعار", max_length=300, blank=True)
    title_separator = models.CharField("جداکنندهٔ عنوان", max_length=10, default="-")
    home_title = models.CharField("عنوان صفحهٔ اصلی", max_length=300, blank=True)
    home_description = models.TextField("توضیحات صفحهٔ اصلی", blank=True)
    title_templates = models.JSONField(
        "قالب عنوان/توضیحات پیش‌فرض", default=dict, blank=True,
        help_text="کلیدها مثل pt_product_title یا tax_product_cat_description (از Rank Math)",
    )
    phone = models.CharField("تلفن", max_length=100, blank=True)
    whatsapp = models.CharField("شمارهٔ واتساپ", max_length=20, blank=True, help_text="با کد کشور، بدون صفر و +؛ مثل 989121234567")
    email = models.EmailField("ایمیل", blank=True)
    address = models.TextField("آدرس", blank=True)
    trust_points = models.JSONField(
        "امتیازهای فروشگاه", default=list, blank=True,
        help_text='فهرست [عنوان، توضیح]؛ مثل [["ارسال رایگان", "برای سفارش‌های بالای ۲۵ میلیون تومان"]]',
    )
    footer_html = models.TextField("HTML فوتر", blank=True)

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return self.site_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
