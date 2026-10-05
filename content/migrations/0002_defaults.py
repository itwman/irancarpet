from django.db import migrations


def seed(apps, schema_editor):
    from content import defaults as D

    T = apps.get_model("content", "ContentTemplate")
    B = apps.get_model("content", "InfoBlock")
    if not T.objects.exists():
        T.objects.create(name="قالب عمومی فرش ماشینی", is_default=True, title_pattern=D.TEMPLATE_TITLE,
                         bullets=D.TEMPLATE_BULLETS, body=D.TEMPLATE_BODY)
    if not B.objects.exists():
        for i, (title, is_open, body) in enumerate(D.BLOCKS):
            B.objects.create(title=title, body=body, order=(i + 1) * 10, is_open=is_open)
    apps.get_model("content", "ContentSettings").objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
