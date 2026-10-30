"""متن محصولات: قالب متن (برای هر آلبوم یا دسته)، بلوک‌های مشترک پایین صفحه و تنظیمات عددی آن‌ها.

متن هر فرش موقع نمایش از روی قالب ساخته می‌شود؛ پس با تغییر قیمت، سقف ارسال رایگان، روش‌های اقساط
یا خود قالب، متن همهٔ فرش‌ها یک‌جا به‌روز می‌شود.
"""
from django.db import models
from django.utils import timezone

HELP_VARS = "متغیرها را در آکولاد بنویسید، مثل {نقشه}. راهنمای کامل متغیرها پایین همین صفحه است."


class ContentTemplate(models.Model):
    name = models.CharField("نام قالب", max_length=120)
    albums = models.ManyToManyField("pricing.Album", blank=True, related_name="content_templates", verbose_name="برای آلبوم‌های",
                                    help_text="فرش‌های این آلبوم‌ها از این قالب استفاده می‌کنند.")
    categories = models.ManyToManyField("catalog.Category", blank=True, related_name="content_templates", verbose_name="یا برای دسته‌های",
                                        help_text="اگر آلبوم فرش قالب جدا نداشت، قالب دستهٔ آن به‌کار می‌رود.")
    is_default = models.BooleanField("قالب پیش‌فرض", default=False, help_text="برای فرش‌هایی که آلبوم و دسته‌شان قالب جدا ندارد.")
    title_pattern = models.CharField(
        "الگوی عنوان (ساخت گروهی)", max_length=255, default="فرش {شانه} شانه[[ {برجسته}]] نقشه {نقشه} زمینه {رنگ}",
        help_text="فقط برای ساخت گروهی فرش‌ها. بخش داخل [[ ]] فقط وقتی می‌آید که متغیرهایش مقدار داشته باشند.")
    bullets = models.TextField("خلاصهٔ کنار قیمت", blank=True,
                               help_text="هر خط یک مورد. " + HELP_VARS)
    body = models.TextField("متن توضیحات", blank=True,
                            help_text="خطی که با ## شروع شود تیتر است و خطی که با - شروع شود فهرست. " + HELP_VARS)
    is_active = models.BooleanField("فعال", default=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    class Meta:
        verbose_name = "قالب متن محصول"
        verbose_name_plural = "قالب‌های متن محصول"
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name


class InfoBlock(models.Model):
    """بخش‌های مشترک زیر توضیحات همهٔ فرش‌ها (ارسال، پرداخت، اقساط، ضمانت…)؛ یک بار نوشته می‌شوند."""

    title = models.CharField("عنوان", max_length=120)
    body = models.TextField("متن", help_text="خطی که با - شروع شود فهرست است. " + HELP_VARS)
    albums = models.ManyToManyField("pricing.Album", blank=True, related_name="+", verbose_name="فقط برای آلبوم‌های",
                                    help_text="خالی = همهٔ فرش‌ها")
    order = models.IntegerField("ترتیب", default=0)
    is_open = models.BooleanField("باز نمایش داده شود", default=False)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "بخش مشترک صفحهٔ فرش"
        verbose_name_plural = "بخش‌های مشترک صفحهٔ فرش"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.title


SYNONYMS = "لاکی، قرمز\nنقره ای، سیلور، نقره\nطوسی، خاکستری، توسی\nسرمه ای، سورمه ای\nمشکی، سیاه\nطلایی، گلد\nکرم، کرمی\nبژ، بژی"


class ContentSettings(models.Model):
    """عددها و جمله‌هایی که در قالب‌ها و بخش‌های مشترک به‌کار می‌روند."""

    prep_time = models.CharField("زمان آماده‌سازی", max_length=80, default="۱۰ تا ۱۴ روز کاری", help_text="متغیر {زمان_آماده_سازی}")
    shipping_cost = models.CharField("هزینهٔ ارسال (پس‌کرایه)", max_length=120, default="حدود ۲۰۰ تا ۵۰۰ هزار تومان",
                                     help_text="متغیر {هزینه_ارسال}؛ کلی، نه برای هر سایز")
    cancel_penalty = models.PositiveSmallIntegerField("درصد جریمهٔ لغو", default=5, help_text="متغیر {جریمه_لغو}")
    pair_colors = models.CharField("رنگ‌هایی که معمولاً جفتی بافته می‌شوند", max_length=255, default="آبی، زرد، لاکی، کرم",
                                   help_text="با ویرگول جدا کنید. برای فرش‌های این رنگ‌ها متغیر {جفتی} جملهٔ زیر را می‌گذارد.")
    pair_note = models.CharField(
        "جملهٔ جفتی", max_length=300,
        default="فرش‌های زمینهٔ {رنگ} معمولاً جفتی بافته می‌شوند؛ اگر فقط یک تخته می‌خواهید، پیش از سفارش با کارشناس هماهنگ کنید.")
    color_synonyms = models.TextField(
        "رنگ‌های هم‌معنی", blank=True, default=SYNONYMS,
        help_text="هر خط یک گروه، با ویرگول جدا. در افزودن سریع، فرشی با رنگ هم‌معنی در همان آلبوم «تکراری» شناخته می‌شود "
                  "(مثلاً «آوین سیلور» همان «آوین نقره ای» است). اولین کلمهٔ هر خط شکل اصلی است.")
    warranty = models.CharField("ضمانت (جنس نامعلوم)", max_length=200, default="۲ تا ۷ سال ضمانت",
                                help_text="متغیر {ضمانت} برای فرشی که جنس نخ خابش ثبت نشده")
    warranty_polyester = models.CharField("ضمانت فرش پلی‌استر", max_length=200, default="۲ سال ضمانت")
    warranty_acrylic = models.CharField("ضمانت فرش آکریلیک", max_length=200, default="۷ سال ضمانت")

    @staticmethod
    def years(text):
        """«۷ سال ضمانت» ← ۷ (برای Schema)."""
        import re

        m = re.search(r"([0-9۰-۹]+)\s*سال", text or "")
        return int(m.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))) if m else None

    def warranty_for(self, material):
        return {"polyester": self.warranty_polyester, "acrylic": self.warranty_acrylic}.get(material) or self.warranty

    class Meta:
        verbose_name = "تنظیمات متن محصولات"
        verbose_name_plural = "تنظیمات متن محصولات"

    def __str__(self):
        return "تنظیمات متن محصولات"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def pair_list(self):
        return [x.strip() for x in (self.pair_colors or "").replace("،", ",").split(",") if x.strip()]


class ContentEdit(models.Model):
    """سابقهٔ جایگزینی گروهی متن (برای برگرداندن)."""

    created_at = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    summary = models.CharField(max_length=300)
    backup = models.JSONField(default=list)  # [{id, field, old}]
    undone = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class NameHint(models.Model):
    """نوشتهٔ فینگلیش نام فایل ← نقشه یا رنگی که کاربر در افزودن سریع تأیید کرده (یادگیری از اصلاح‌ها)."""
    kind = models.CharField(max_length=10, choices=[("design", "نقشه"), ("color", "رنگ زمینه")])
    latin = models.CharField("نوشتهٔ نام فایل", max_length=80)
    persian = models.CharField("فارسی", max_length=120)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("kind", "latin")]
        verbose_name = "نام فینگلیش آموخته"
        verbose_name_plural = "نام‌های فینگلیش آموخته"

    def __str__(self):
        return f"{self.latin} ← {self.persian}"
