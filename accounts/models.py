from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    mobile = models.CharField("موبایل", max_length=11, unique=True, null=True, blank=True)
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    province = models.CharField("استان", max_length=60, blank=True)
    city = models.CharField("شهر", max_length=80, blank=True)
    address = models.TextField("آدرس", blank=True)
    postal_code = models.CharField("کد پستی", max_length=10, blank=True)

    class Meta:
        verbose_name = "پروفایل مشتری"
        verbose_name_plural = "پروفایل مشتریان"

    def __str__(self):
        return self.mobile or self.user.get_username()


class OtpCode(models.Model):
    mobile = models.CharField(max_length=11, db_index=True)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    LIFETIME = 120  # ثانیه
    MAX_ATTEMPTS = 5

    class Meta:
        verbose_name = "کد یک‌بارمصرف"
        verbose_name_plural = "کدهای یک‌بارمصرف"

    @classmethod
    def create(cls, mobile, code):
        return cls.objects.create(mobile=mobile, code_hash=make_password(code))

    @property
    def expired(self):
        return (timezone.now() - self.created_at).total_seconds() > self.LIFETIME

    def verify(self, code):
        if self.used or self.expired or self.attempts >= self.MAX_ATTEMPTS:
            return False
        self.attempts += 1
        ok = check_password(code, self.code_hash)
        if ok:
            self.used = True
        self.save(update_fields=["attempts", "used"])
        return ok
