"""فیلترهای فروشگاه فقط بر اساس شانه، تراکم، جنس نخ خاب و رنگ زمینه.

ویژگی‌ها با عنوان (یا نامک) شناسایی می‌شوند؛ بقیهٔ ویژگی‌ها از فیلتر خارج می‌شوند
(از پنل «ویژگی‌ها ← در فیلترها» قابل تغییر است).
"""
from django.db import migrations

WANTED = [  # (ترتیب, کلیدهای عنوان بی‌فاصله, نامک‌ها)
    (1, ("شانه",), ("reeds-per-meter", "reeds")),
    (2, ("تراکم",), ("picks-per-meter", "density")),
    (3, ("خاب",), ("pile", "pile-material", "yarn")),
    (4, ("رنگزمینه",), ("background-color", "bg-color")),
]


def norm(s):
    return "".join((s or "").replace("‌", "").replace("ي", "ی").replace("ك", "ک").split())


def match(a):
    label, slug = norm(a.label), (a.slug or "").lower()
    for order, keys, slugs in WANTED:
        if slug in slugs or any(k in label or k in norm(a.slug) for k in keys):
            return order
    return None


def forwards(apps, schema_editor):
    Attribute = apps.get_model("catalog", "Attribute")
    attrs = list(Attribute.objects.all())
    found = {a.pk: match(a) for a in attrs}
    if not any(found.values()):
        return  # چیزی پیدا نشد؛ تنظیمات فعلی دست نمی‌خورد
    for a in attrs:
        order = found[a.pk]
        a.show_in_filters = order is not None
        if order is not None:
            a.order = order
        a.save(update_fields=["show_in_filters", "order"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_auto_codes")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
