from django.conf import settings
from django.db import models
from django.utils import timezone


class ActivityLog(models.Model):
    ACTIONS = [("create", "افزودن"), ("update", "ویرایش"), ("delete", "حذف"), ("action", "عملیات")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=10, choices=ACTIONS)
    section = models.CharField("بخش", max_length=100)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField("مورد", max_length=300, blank=True)
    detail = models.CharField("جزئیات", max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "فعالیت"
        verbose_name_plural = "گزارش فعالیت"


def log(request, action, section, obj=None, detail=""):
    ActivityLog.objects.create(
        user=request.user if request.user.is_authenticated else None, action=action, section=str(section)[:100],
        object_id=str(getattr(obj, "pk", "") or "")[:50], object_repr=str(obj or "")[:300], detail=detail[:500],
    )
