from django.db import migrations


def forward(apps, schema_editor):
    from content import defaults as D

    T = apps.get_model("content", "ContentTemplate")
    old = D.OLD_TEMPLATE_BODY.replace("\r\n", "\n").strip()
    for t in T.objects.all():
        if (t.body or "").replace("\r\n", "\n").strip() == old:
            T.objects.filter(pk=t.pk).update(body=D.TEMPLATE_BODY)


class Migration(migrations.Migration):
    dependencies = [("content", "0004_warranty_by_material")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
