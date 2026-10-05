"""فرش‌یاب: پیدا کردن فرش بر اساس نیاز مشتری.

«نیاز» (Need) یک خواستهٔ قابل‌فهم برای مشتری است، مثل «ضخیم و کلفت»، «قرمز» یا «سنتی»؛
و از پنل تعیین می‌شود کدام فرش‌ها در آن قرار می‌گیرند (دسته، ویژگی، کلمه در عنوان).
«درخواست» (FinderRequest) وقتی است که مشتری عکس فرش خودش یا توضیح می‌فرستد و کارشناس جواب می‌دهد.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


def split_words(text):
    """«قرمز، لاکی\nسرخ» → ['قرمز', 'لاکی', 'سرخ']"""
    import re

    return [w.strip() for w in re.split(r"[,،\n؛;]+", text or "") if w.strip()]


class Need(models.Model):
    class Group(models.TextChoices):
        FEEL = "feel", "جنس و ضخامت"
        COLOR = "color", "رنگ"
        STYLE = "style", "سبک و طرح"
        USE = "use", "کاربرد و فضا"

    title = models.CharField("عنوان", max_length=80, help_text="همان چیزی که مشتری می‌بیند؛ مثل «ضخیم و کلفت»")
    subtitle = models.CharField("توضیح کوتاه", max_length=140, blank=True, help_text="مثل «پرز بلند، نرم زیر پا»")
    group = models.CharField("گروه", max_length=10, choices=Group.choices, default=Group.STYLE)
    swatch = models.CharField("رنگ نمونه", max_length=7, blank=True, help_text="برای نیازهای رنگی؛ مثل #B3202A")
    icon = models.CharField("نماد", max_length=30, blank=True, help_text="نام نماد در اپ (اختیاری)")
    is_active = models.BooleanField("فعال", default=True)
    order = models.IntegerField("ترتیب", default=0)

    keywords = models.TextField(
        "کلمه‌هایی که مشتری می‌گوید", blank=True,
        help_text="با ویرگول جدا کنید. وقتی مشتری در جستجو یکی از این‌ها را بنویسد، همین نیاز فهمیده می‌شود. مثل «ضخیم، کلفت، پرزدار، نرم»")

    # قاعده‌ها: فرشی در این نیاز است که دست‌کم یکی از «شامل»ها را داشته باشد و هیچ‌کدام از «به‌جز»ها را نداشته باشد
    categories = models.ManyToManyField("catalog.Category", blank=True, related_name="+", verbose_name="دسته‌ها (با زیردسته‌ها)")
    terms = models.ManyToManyField("catalog.AttributeTerm", blank=True, related_name="+", verbose_name="مقدار ویژگی‌ها",
                                   help_text="مثل شانه ۷۰۰، شانه ۱۰۰۰")
    term_attribute = models.ForeignKey("catalog.Attribute", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                       verbose_name="ویژگی برای کلمه‌های مقدار", help_text="مثلاً «رنگ زمینه»")
    term_keywords = models.CharField(
        "مقدارهایی که این کلمه‌ها را دارند", max_length=400, blank=True,
        help_text="هر مقدار ویژگی بالا که یکی از این کلمه‌ها در نامش باشد؛ مثل «قرمز، لاکی، زرشکی». مقدارهای تازه خودکار حساب می‌شوند.")
    title_keywords = models.CharField("کلمه در عنوان فرش", max_length=400, blank=True,
                                      help_text="فرش‌هایی که یکی از این کلمه‌ها در عنوانشان است؛ مثل «لچک، ترنج، افشان»")
    exclude_categories = models.ManyToManyField("catalog.Category", blank=True, related_name="+", verbose_name="به‌جز این دسته‌ها")
    exclude_keywords = models.CharField("به‌جز فرش‌هایی که این کلمه‌ها در عنوانشان است", max_length=400, blank=True,
                                        help_text="مثل «برجسته»")

    class Meta:
        verbose_name = "نیاز مشتری"
        verbose_name_plural = "نیازهای مشتری (فرش‌یاب)"
        ordering = ["group", "order", "pk"]

    def __str__(self):
        return self.title

    @property
    def keyword_list(self):
        return split_words(self.keywords)


class FinderRequest(models.Model):
    class Kind(models.TextChoices):
        PHOTO = "photo", "عکس فرش"
        TEXT = "text", "توضیح نیاز"

    class Status(models.TextChoices):
        NEW = "new", "تازه"
        ANSWERED = "answered", "پاسخ داده شد"
        CLOSED = "closed", "بسته"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="finder_requests", verbose_name="مشتری")
    mobile = models.CharField("موبایل", max_length=15, blank=True)
    name = models.CharField("نام", max_length=120, blank=True)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.PHOTO)
    text = models.TextField("توضیح مشتری", blank=True)
    wanted = models.JSONField("خواسته‌ها", default=dict, blank=True, help_text="نیازها، سایز و بودجه‌ای که مشتری انتخاب کرده")
    photo = models.CharField("مسیر عکس (خصوصی)", max_length=255, blank=True, editable=False)
    colors = models.JSONField("رنگ‌های غالب عکس", default=list, blank=True, editable=False)
    auto_products = models.JSONField("پیشنهاد خودکار", default=list, blank=True, editable=False)

    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    reply = models.TextField("پاسخ کارشناس", blank=True, help_text="این متن در اپ برای مشتری نمایش داده می‌شود.")
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="+", verbose_name="فرش‌های پیشنهادی کارشناس")
    notify_sms = models.BooleanField("خبر دادن با پیامک", default=True,
                                     help_text="بعد از پاسخ، یک پیامک کوتاه برای مشتری فرستاده می‌شود (اگر خط پیامک تنظیم شده باشد).")

    created_at = models.DateTimeField("زمان ثبت", default=timezone.now, db_index=True)
    answered_at = models.DateTimeField("زمان پاسخ", null=True, blank=True)
    seen_at = models.DateTimeField("دیده‌شده توسط مشتری", null=True, blank=True)

    class Meta:
        verbose_name = "درخواست فرش‌یاب"
        verbose_name_plural = "درخواست‌های فرش‌یاب"
        ordering = ["-created_at"]

    def __str__(self):
        return f"درخواست {self.pk} — {self.name or self.mobile}"
