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


class AppSettings(models.Model):
    latest_version = models.CharField("آخرین نسخه", max_length=20, default="1.0.0")
    min_version = models.CharField("کمترین نسخهٔ قابل استفاده", max_length=20, default="1.0.0",
                                   help_text="نسخه‌های پایین‌تر مجبور به به‌روزرسانی می‌شوند")
    update_url = models.CharField("لینک دریافت اپ", max_length=300, blank=True, help_text="صفحهٔ اپ در کافه‌بازار")
    update_note = models.TextField("توضیح نسخهٔ تازه", blank=True)
    home_notice = models.CharField("پیام بالای صفحهٔ اول اپ", max_length=200, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "تنظیمات اپلیکیشن"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
