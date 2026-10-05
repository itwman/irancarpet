from django.db import migrations, models


def fill(apps, schema_editor):
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first() or S(pk=1)
    s.mobile = s.mobile or "09125347596"
    s.whatsapp = s.whatsapp or "989125347596"
    s.telegram = s.telegram or "https://t.me/itwman"
    s.eitaa = s.eitaa or "https://eitaa.com/itwman"
    s.instagram = s.instagram or "https://www.instagram.com/irancarpet.original"
    s.farshplus = s.farshplus or "https://farshplus.com/@irancarpet/"
    s.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0002_contact_fields")]

    operations = [
        migrations.AddField("sitesettings", "mobile", models.CharField(
            "موبایل پاسخگو", max_length=20, blank=True, help_text="برای تماس و پیامک؛ مثل 09121234567")),
        migrations.AddField("sitesettings", "telegram", models.URLField(
            "تلگرام", blank=True, help_text="نشانی کامل؛ مثل https://t.me/username")),
        migrations.AddField("sitesettings", "eitaa", models.URLField(
            "ایتا", blank=True, help_text="نشانی کامل؛ مثل https://eitaa.com/username")),
        migrations.AddField("sitesettings", "instagram", models.URLField("اینستاگرام", blank=True)),
        migrations.AddField("sitesettings", "farshplus", models.URLField("صفحه در فرش پلاس", blank=True)),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
