from django.db import migrations, models


def fill(apps, schema_editor):
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first() or S(pk=1)
    s.telegram_channel = s.telegram_channel or "https://t.me/irancarpet"
    s.eitaa_channel = s.eitaa_channel or "https://eitaa.com/irancarpet"
    s.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0003_socials")]

    operations = [
        migrations.AddField("sitesettings", "telegram_channel", models.URLField("کانال تلگرام", blank=True)),
        migrations.AddField("sitesettings", "eitaa_channel", models.URLField("کانال ایتا", blank=True)),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
