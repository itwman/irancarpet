"""ایران کارپت: ضمانت همهٔ فرش‌های آکریلیک ۷ سال (پلی‌استر ۲ سال). فرشستان دست نمی‌خورد."""
from django.conf import settings
from django.db import migrations


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    C = apps.get_model("content", "ContentSettings")
    c = C.objects.filter(pk=1).first()
    if c and ("۵" in (c.warranty_acrylic or "") or "5" in (c.warranty_acrylic or "") or not (c.warranty_acrylic or "").strip()):
        C.objects.filter(pk=1).update(warranty_acrylic="۷ سال ضمانت")


class Migration(migrations.Migration):
    dependencies = [("content", "0007_color_synonyms")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
