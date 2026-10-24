from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mirror", "0002_pick")]

    operations = [
        migrations.AddField(
            model_name="mirrorsettings",
            name="template_ready",
            field=models.BooleanField(default=False, editable=False, verbose_name="قالب متن فرشستان ساخته شده"),
        ),
    ]
