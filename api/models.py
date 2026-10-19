import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


class ApiToken(models.Model):
    """توکن ورود اپلیکیشن؛ خود توکن ذخیره نمی‌شود، فقط هش آن."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_tokens")
    key_hash = models.CharField(max_length=64, unique=True)
    device = models.CharField("دستگاه", max_length=150, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "توکن اپ"
        verbose_name_plural = "توکن‌های اپ"

    @classmethod
    def issue(cls, user, device=""):
        key = secrets.token_urlsafe(32)
        cls.objects.create(user=user, key_hash=_hash(key), device=device[:150])
        return key

    @classmethod
    def lookup(cls, key):
        if not key:
            return None
        return cls.objects.select_related("user").filter(key_hash=_hash(key), user__is_active=True).first()


class Device(models.Model):
    """گوشی‌هایی که اپ را نصب کرده‌اند (برای آمار و اعلان)."""

    install_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    platform = models.CharField(max_length=20, default="android")
    app_version = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    first_seen = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "دستگاه"
        verbose_name_plural = "دستگاه‌های نصب‌شده"


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "product")]
        verbose_name = "علاقه‌مندی"
        verbose_name_plural = "علاقه‌مندی‌ها"


class AppNotification(models.Model):
    """اعلان‌هایی که اپ در پس‌زمینه می‌گیرد و روی گوشی نشان می‌دهد."""

    class Kind(models.TextChoices):
        DEAL = "deal", "تخفیف"
        NEW = "new", "فرش تازه"
        NEWS = "news", "خبر"

    title = models.CharField("عنوان", max_length=120)
    body = models.CharField("متن", max_length=300)
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.NEWS)
    image = models.ForeignKey("core.Media", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="تصویر")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="محصول")
    category = models.ForeignKey("catalog.Category", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="دسته")
    url = models.CharField("پیوند", max_length=300, blank=True, help_text="اگر محصول یا دسته انتخاب نشده")
    is_active = models.BooleanField("فعال", default=True)
    created_at = models.DateTimeField("زمان ارسال", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "اعلان اپ"
        verbose_name_plural = "اعلان‌های اپ"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


APP_URL = "https://cafebazaar.ir/app/net.irancarpet.app"
FINDER_URL = "https://cafebazaar.ir/app/net.irancarpet.finder"
# اپ فروشگاهی هر سایت (قالب SITE_THEME): تا صفحهٔ کافه‌بازارش آماده شود، فایل نصبی روی خود سایت
# (پس از انتشار، «لینک دریافت اپ» را در پنل بگذارید)
STORE_APP_URLS = {"farshestan": "/wp-content/uploads/app/farshestan.apk"}


class AppSettings(models.Model):
    latest_version = models.CharField("آخرین نسخه", max_length=20, default="1.0.0")
    min_version = models.CharField("کمترین نسخهٔ قابل استفاده", max_length=20, default="1.0.0",
                                   help_text="نسخه‌های پایین‌تر مجبور به به‌روزرسانی می‌شوند")
    update_url = models.CharField("لینک دریافت اپ", max_length=300, blank=True, help_text="صفحهٔ اپ در کافه‌بازار")
    update_note = models.TextField("توضیح نسخهٔ تازه", blank=True)
    home_notice = models.CharField("پیام بالای صفحهٔ اول اپ", max_length=200, blank=True)
    finder_url = models.CharField("لینک اپ فرش‌یاب", max_length=300, blank=True, default=FINDER_URL,
                                  help_text="صفحهٔ فرش‌یاب در کافه‌بازار؛ خالی = در سایت معرفی نشود")
    promote_home = models.BooleanField("معرفی اپ‌ها در صفحهٔ اول سایت", default=True)
    promote_bar = models.BooleanField("نوار نصب اپ برای موبایل‌های اندرویدی", default=True,
                                      help_text="پایین صفحه؛ با یک ضربه بسته می‌شود و تا ۳۰ روز دوباره نمی‌آید")

    class Meta:
        verbose_name = verbose_name_plural = "تنظیمات اپلیکیشن"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete("apps_promo")

    @property
    def app_url(self):
        if self.update_url:
            return self.update_url
        from django.conf import settings

        url = STORE_APP_URLS.get(settings.SITE_THEME, APP_URL)
        return settings.SITE_URL + url if url.startswith("/") else url

    def promo(self):
        """اپ‌هایی که در سایت معرفی می‌شوند (برای قالب‌ها؛ در کش)."""
        from core.qr import svg

        from core import brand, features

        apps = [{"key": "app", "name": f"اپ {brand.name()}", "text": "خرید فرش، پرداخت قسطی و پیگیری سفارش در گوشی؛ با اعلان فرصت‌های ویژه.",
                 "url": self.app_url, "qr": svg(self.app_url)}]
        if self.finder_url and features.is_on("finder"):
            apps.append({"key": "finder", "name": "فرش‌یاب", "text": "بگو چه فرشی می‌خواهی یا عکس فرشت را بفرست؛ مشابهش را پیدا می‌کنیم.",
                         "url": self.finder_url, "qr": svg(self.finder_url)})
        return {"home": self.promote_home, "bar": self.promote_bar, "apps": apps}
