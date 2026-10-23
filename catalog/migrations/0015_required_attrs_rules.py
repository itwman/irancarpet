"""ویژگی‌های لازم (رنگ زمینه، شانه، تراکم، جنس نخ خاب، برند) و قانون‌های «افشان» و «وینتیج» برای دسته و برچسب."""
from django.db import migrations

REQUIRED = ("رنگ زمینه", "شانه", "تراکم", "جنس", "برند")
WORDS = ("افشان", "وینتیج")


def norm(s):
    return " ".join((s or "").replace("‌", " ").replace("ي", "ی").replace("ك", "ک").split())


def forward(apps, schema_editor):
    Attribute = apps.get_model("catalog", "Attribute")
    for a in Attribute.objects.all():
        if any(k in norm(a.label) for k in REQUIRED):
            a.required = True
            a.save(update_fields=["required"])
    Rule = apps.get_model("catalog", "KeywordRule")
    Category = apps.get_model("catalog", "Category")
    Tag = apps.get_model("catalog", "ProductTag")
    for w in WORDS:
        cats = [c for c in Category.objects.all() if w in norm(c.name)]
        tags = [t for t in Tag.objects.all() if norm(t.name) in (w, f"فرش {w}", f"{w} فرش")]
        if not cats and not tags or Rule.objects.filter(keyword=w).exists():
            continue
        r = Rule.objects.create(keyword=w)
        r.categories.set(cats[:2])
        r.tags.set(tags[:3])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0014_bulk_defaults")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
