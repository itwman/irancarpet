"""تاریخ رسانه‌هایی که از پنل آپلود شده بودند و تاریخ نداشتند: زمان فایل روی دیسک (وگرنه شناسه به ترتیب)."""
import os
from datetime import datetime, timezone as dt_tz

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    Media = apps.get_model("core", "Media")
    now = timezone.now()
    root = settings.MEDIA_ROOT
    rows = list(Media.objects.filter(created_at__isnull=True).order_by("pk").values_list("pk", "file"))
    for i, (pk, f) in enumerate(rows):
        when = None
        try:
            when = datetime.fromtimestamp(os.path.getmtime(os.path.join(root, f)), tz=dt_tz.utc) if f else None
        except OSError:
            pass
        if when is None or when > now:
            when = now - timezone.timedelta(seconds=len(rows) - i)  # ترتیب آپلود حفظ شود
        Media.objects.filter(pk=pk).update(created_at=when)


class Migration(migrations.Migration):
    dependencies = [("core", "0016_trashed_file")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
