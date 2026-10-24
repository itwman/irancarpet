from django.conf import settings
from django.db import migrations


def forward(apps, schema_editor):
    from catalog import mocha as M

    Category = apps.get_model("catalog", "Category")
    Attribute = apps.get_model("catalog", "Attribute")
    KeywordRule = apps.get_model("catalog", "KeywordRule")
    farshestan = getattr(settings, "SITE_THEME", "") == "farshestan"
    text = M.FARSHESTAN if farshestan else M.IRANCARPET
    cat = Category.objects.filter(slug=M.SLUG, parent=None).first() or Category.objects.filter(name=M.NAME).first()
    if cat is None:
        cat = Category.objects.create(slug=M.SLUG, name=M.NAME, order=-1, mirror_auto=not farshestan, **text)
    elif not cat.description:
        for k, v in text.items():
            setattr(cat, k, v)
        cat.save()
    if not farshestan and not KeywordRule.objects.filter(keyword=M.KEYWORD).exists():
        r = KeywordRule.objects.create(keyword=M.KEYWORD)
        r.categories.set([cat])
    if not Attribute.objects.filter(slug="border-color").exists() and not Attribute.objects.filter(label="رنگ حاشیه").exists():
        color = Attribute.objects.filter(label__contains="رنگ زمینه").first()
        Attribute.objects.create(slug="border-color", label="رنگ حاشیه", is_public=True, show_in_filters=True,
                                 order=(color.order + 1) if color else 50)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0017_category_mirror_auto")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
