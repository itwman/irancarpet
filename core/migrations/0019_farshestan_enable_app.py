"""روی فرشستان بخش اپ (API اپ موبایل) روشن می‌شود؛ قبلاً در site_profile خاموش شده بود. روی سایت‌های دیگر کاری نمی‌کند."""
from django.conf import settings
from django.db import migrations


def enable_app(apps, schema_editor):
    if settings.SITE_THEME != "farshestan":
        return
    SiteSettings = apps.get_model("core", "SiteSettings")
    for s in SiteSettings.objects.all():
        off = [x for x in (s.features_off or "").replace(" ", ",").split(",") if x and x != "app"]
        if ",".join(off) != (s.features_off or ""):
            s.features_off = ",".join(off)
            s.save(update_fields=["features_off"])


class Migration(migrations.Migration):
    dependencies = [("core", "0018_multisite_brand_features")]
    operations = [migrations.RunPython(enable_app, migrations.RunPython.noop)]
