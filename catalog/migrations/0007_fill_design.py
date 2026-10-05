import re

from django.db import migrations


def fill(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    rows = []
    for p in Product.objects.filter(design_name="").only("pk", "title", "short_description", "content", "color_count"):
        m = re.search(r"نقشه\s+(.+?)(?:\s+(?:زمینه|رنگ|سایز)\b|$)", p.title or "")
        changed = False
        if m:
            p.design_name = m.group(1).strip(" -–")[:120]
            changed = True
        if p.color_count is None:
            c = re.search(r"([0-9۰-۹]{1,2})\s*رنگ", (p.short_description or "") + " " + (p.content or "")[:3000])
            if c:
                n = int(c.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
                if 2 <= n <= 30:
                    p.color_count, changed = n, True
        if changed:
            rows.append(p)
    Product.objects.bulk_update(rows, ["design_name", "color_count"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_product_content")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
