"""ضمانت بر اساس جنس: پلی‌استر ۲ سال، آکریلیک ۷ سال؛ متن قدیمی «۵ ساله» در تنظیمات و صفحهٔ اول اصلاح می‌شود."""
from django.db import migrations


def forward(apps, schema_editor):
    CS = apps.get_model("content", "ContentSettings")
    for s in CS.objects.all():
        if (s.warranty or "").strip() in ("۵ سال ضمانت", "5 سال ضمانت", ""):
            s.warranty = "۲ تا ۷ سال ضمانت"
            s.save(update_fields=["warranty"])
    S = apps.get_model("core", "SiteSettings")
    for s in S.objects.all():
        fields = []
        for f in ("home_description", "home_title", "home_about", "footer_html", "trust_html"):
            v = getattr(s, f, None)
            if isinstance(v, str) and ("ضمانت ۵ ساله" in v or "ضمانت‌نامهٔ ۵ ساله" in v):
                setattr(s, f, v.replace("ضمانت ۵ ساله", "ضمانت ۲ تا ۷ ساله").replace("ضمانت‌نامهٔ ۵ ساله", "ضمانت‌نامهٔ ۲ تا ۷ ساله"))
                fields.append(f)
        if fields:
            s.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("content", "0003_bulk_defaults"), ("core", "0019_farshestan_enable_app")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
