from django.db import migrations


def fill(apps, schema_editor):
    from catalog.search import compact

    Product = apps.get_model("catalog", "Product")
    rows = []
    for p in Product.objects.select_related("album", "brand").prefetch_related("specs", "categories", "tags").iterator(chunk_size=500):
        parts = [p.title, p.english_name, p.sku, p.design_name]
        if p.album_id:
            parts += [p.album.name, p.album.public_name]
        if p.brand_id:
            parts.append(p.brand.name)
        parts += [t.name for t in p.specs.all()] + [c.name for c in p.categories.all()] + [t.name for t in p.tags.all()]
        p.search_title = compact(p.title)[:600]
        p.search_text = "|".join(compact(x) for x in parts if x)[:4000]
        rows.append(p)
        if len(rows) >= 500:
            Product.objects.bulk_update(rows, ["search_title", "search_text"])
            rows = []
    Product.objects.bulk_update(rows, ["search_title", "search_text"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_search_index")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
