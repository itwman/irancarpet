"""ایران کارپت (آبان ۱۴۰۵): صف بازنویسی روزی یک مقاله، تا گوگل ارزیابی بخش مقاله‌ها را تمام کند.
فقط اگر هنوز همان پیش‌فرض ۲ است؛ بعداً از پنل ← تنظیمات سئو قابل تغییر است. روی فرشستان کاری نمی‌کند."""
from django.conf import settings
from django.db import migrations


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    apps.get_model("seo", "SeoSettings").objects.filter(rewrite_per_day=2).update(rewrite_per_day=1)


class Migration(migrations.Migration):
    dependencies = [("seo", "0005_alter_seosettings_rewrite_enabled")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
