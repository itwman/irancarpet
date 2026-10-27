"""دستهٔ «فرش موکا» مجموعه می‌شود: «از پالت موکا» در صفحهٔ هر فرش و ردیف «دیگر فرش‌های پالت موکا»."""
from django.conf import settings
from django.db import migrations


def forward(apps, schema_editor):
    from catalog import mocha as M

    Category = apps.get_model("catalog", "Category")
    cat = Category.objects.filter(slug=M.SLUG).first() or Category.objects.filter(name=M.NAME).first()
    if cat is None or cat.collection_label:
        return
    cat.collection_label = M.LABEL
    cat.collection_note = M.NOTE_FARSHESTAN if getattr(settings, "SITE_THEME", "") == "farshestan" else M.NOTE_IRANCARPET
    cat.save(update_fields=["collection_label", "collection_note"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0022_category_collection")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
