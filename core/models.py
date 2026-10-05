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
    mobile = models.CharField("موبایل پاسخگو", max_length=20, blank=True, help_text="برای تماس و پیامک؛ مثل 09121234567")
    telegram = models.URLField("تلگرام", blank=True, help_text="نشانی کامل؛ مثل https://t.me/username")
    eitaa = models.URLField("ایتا", blank=True, help_text="نشانی کامل؛ مثل https://eitaa.com/username")
    telegram_channel = models.URLField("کانال تلگرام", blank=True)
    eitaa_channel = models.URLField("کانال ایتا", blank=True)
    instagram = models.URLField("اینستاگرام", blank=True)
    farshplus = models.URLField("صفحه در فرش پلاس", blank=True)
    email = models.EmailField("ایمیل", blank=True)
    address = models.TextField("آدرس", blank=True)
    # فروشگاه حضوری (برای گوگل‌مپ، نشان، بلد و Schema کسب‌وکار محلی)
    store_name = models.CharField("نام فروشگاه حضوری", max_length=150, blank=True, help_text="مثل «فروشگاه فرش ایران کارپت کاشان»")
    store_city = models.CharField("شهر", max_length=80, blank=True, default="کاشان")
    store_province = models.CharField("استان", max_length=80, blank=True, default="اصفهان")
    store_postal_code = models.CharField("کد پستی فروشگاه", max_length=10, blank=True)
    store_days = models.CharField("روزهای کاری", max_length=10, blank=True, default="sat-thu", choices=[
        ("sat-thu", "شنبه تا پنجشنبه"), ("sat-wed", "شنبه تا چهارشنبه"), ("all", "همهٔ روزها"), ("sat-fri", "شنبه تا جمعه")])
    store_open = models.TimeField("ساعت باز شدن", null=True, blank=True)
    store_close = models.TimeField("ساعت بسته شدن", null=True, blank=True)
    store_open2 = models.TimeField("نوبت عصر: باز شدن", null=True, blank=True, help_text="اگر ظهر تعطیل است")
    store_close2 = models.TimeField("نوبت عصر: بسته شدن", null=True, blank=True)
    store_hours_note = models.CharField("توضیح ساعت کاری", max_length=150, blank=True, help_text="مثل «جمعه‌ها با هماهنگی تلفنی»")
    latitude = models.DecimalField("عرض جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("طول جغرافیایی", max_digits=9, decimal_places=6, null=True, blank=True)
    map_google = models.URLField("پیوند گوگل‌مپ", blank=True, max_length=1500)
    map_neshan = models.URLField("پیوند نشان", blank=True, max_length=1500)
    map_balad = models.URLField("پیوند بلد", blank=True, max_length=1500)
    trust_points = models.JSONField(
        "امتیازهای فروشگاه", default=list, blank=True,
        help_text='فهرست [عنوان، توضیح]؛ مثل [["ارسال رایگان", "برای سفارش‌های بالای ۲۵ میلیون تومان"]]',
    )
    footer_html = models.TextField("HTML فوتر", blank=True)
    trust_badge = models.ForeignKey(
        "core.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="تصویر نماد (فوتر)",
        help_text="تصویر سبک از نماد اعتماد که در پایین همهٔ صفحه‌ها می‌آید و به برگهٔ مجوزها لینک می‌شود.",
    )
    trust_html = models.TextField(
        "کد نماد اعتماد (اینماد و...)", blank=True,
        help_text="کدی که اینماد داده را کامل اینجا بچسبانید. فقط در برگهٔ مجوزها (/license/) بار می‌شود تا سرعت سایت کم نشود.",
    )

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return self.site_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    DAY_CODES = {"sat-thu": ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
                 "sat-wed": ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"],
                 "all": ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                 "sat-fri": ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}

    @property
    def has_store(self):
        return bool(self.address and (self.store_open or self.map_google or self.map_neshan or self.map_balad or self.latitude))

    @property
    def store_hours(self):
        """«شنبه تا پنجشنبه ۹ تا ۱۳ و ۱۶ تا ۲۱»"""
        if not self.store_open or not self.store_close:
            return self.store_hours_note
        from .templatetags.fa import fa_num

        t = lambda x: fa_num(x.strftime("%H:%M").lstrip("0").replace(":00", ""))  # noqa: E731
        txt = f"{self.get_store_days_display()} {t(self.store_open)} تا {t(self.store_close)}"
        if self.store_open2 and self.store_close2:
            txt += f" و {t(self.store_open2)} تا {t(self.store_close2)}"
        return txt + (f"؛ {self.store_hours_note}" if self.store_hours_note else "")

    def local_business(self):
        """Schema کسب‌وکار محلی برای گوگل."""
        import re

        from django.conf import settings

        if not self.has_store:
            return None
        phones = ["+98" + p[1:] if p.startswith("0") else p for p in (re.sub(r"\D", "", x or "") for x in (self.phone, self.mobile)) if p]
        data = {
            "@context": "https://schema.org", "@type": "HomeGoodsStore", "@id": settings.SITE_URL + "/#store",
            "name": self.store_name or self.site_name, "url": settings.SITE_URL + "/",
            "image": settings.SITE_URL + "/static/img/logo.png", "priceRange": "$$",
            "address": {"@type": "PostalAddress", "streetAddress": self.address, "addressLocality": self.store_city,
                        "addressRegion": self.store_province, "postalCode": self.store_postal_code or None, "addressCountry": "IR"},
            "telephone": phones[0] if phones else None,
            "sameAs": [u for u in (self.map_google, self.map_neshan, self.map_balad) if u] + [url for _, _, url in self.follows],
        }
        if self.latitude and self.longitude:
            data["geo"] = {"@type": "GeoCoordinates", "latitude": float(self.latitude), "longitude": float(self.longitude)}
        if self.store_open and self.store_close:
            days = self.DAY_CODES.get(self.store_days or "sat-thu", self.DAY_CODES["sat-thu"])
            spans = [(self.store_open, self.store_close)]
            if self.store_open2 and self.store_close2:
                spans.append((self.store_open2, self.store_close2))
            data["openingHoursSpecification"] = [{"@type": "OpeningHoursSpecification", "dayOfWeek": days,
                                                  "opens": a.strftime("%H:%M"), "closes": b.strftime("%H:%M")} for a, b in spans]
        data["address"] = {k: v for k, v in data["address"].items() if v}
        return {k: v for k, v in data.items() if v}

    @property
    def messengers(self):
        """پیام‌رسان‌ها برای گفتگو: [(کلید، نام، نشانی)]"""
        from .templatetags.fa import wa_link

        out = []
        if self.whatsapp:
            out.append(("whatsapp", "واتساپ", wa_link(self.whatsapp)))
        if self.telegram:
            out.append(("telegram", "تلگرام", self.telegram))
        if self.eitaa:
            out.append(("eitaa", "ایتا", self.eitaa))
        return out

    @property
    def follows(self):
        """صفحه‌ها و کانال‌های فروشگاه: [(کلید، نام، نشانی)]"""
        out = []
        for key, name in (("telegram_channel", "کانال تلگرام"), ("eitaa_channel", "کانال ایتا"),
                          ("instagram", "اینستاگرام"), ("farshplus", "فرش پلاس")):
            url = getattr(self, key)
            if url:
                out.append((key, name, url))
        return out

    @property
    def socials(self):
        """پیام‌رسان‌های گفتگو + صفحه‌ها و کانال‌ها"""
        return list(self.messengers) + self.follows
