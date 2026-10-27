"""ایران کارپت: صفحهٔ اصلی «فرش طرح افشان» برچسب است؛ دستهٔ «فرش افشان» با ۳۰۱ به آن می‌رود.

فرش‌های دستهٔ «فرش افشان» برچسب را هم می‌گیرند و قانون کلمهٔ «افشان» برچسب را خودکار می‌زند.
روی فرشستان (SITE_THEME=farshestan) کاری نمی‌کند.
"""
from django.conf import settings
from django.db import migrations


def norm(s):
    return " ".join((s or "").replace("‌", " ").replace("ي", "ی").replace("ك", "ک").split())


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    Category, ProductTag, KeywordRule = (apps.get_model("catalog", m) for m in ("Category", "ProductTag", "KeywordRule"))
    tag = ProductTag.objects.filter(slug="فرش-طرح-افشان").first() or next(
        (t for t in ProductTag.objects.all() if norm(t.name) == "فرش طرح افشان"), None)
    if tag is None:
        return
    url = f"/product-tag/{tag.slug}/"
    for cat in Category.objects.filter(redirect_url=""):
        if norm(cat.name) in ("فرش افشان", "فرش طرح افشان"):
            cat.redirect_url = url
            cat.save(update_fields=["redirect_url"])
            Product = apps.get_model("catalog", "Product")
            ids = set(Product.objects.filter(categories=cat).exclude(status="trash").values_list("pk", flat=True))
            have = set(tag.products.values_list("pk", flat=True))
            tag.products.add(*(ids - have))
    rule = next((r for r in KeywordRule.objects.all() if norm(r.keyword) == "افشان"), None)
    if rule is None:
        rule = KeywordRule.objects.create(keyword="افشان")
    rule.tags.add(tag)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0020_category_redirect")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
