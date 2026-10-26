from django.db import migrations


def forward(apps, schema_editor):
    """فرش‌هایی که «فقط این سایزها» دارند: سایزهایشان دوباره با همان انتخاب ساخته می‌شود (قبلاً سایز خارج از آلبوم نادیده گرفته می‌شد)."""
    from catalog.models import Product
    from pricing.albums import sync_album_variations

    ps = list(Product.objects.filter(album__isnull=False, only_sizes__isnull=False).distinct().select_related("album"))
    if ps:
        sync_album_variations(ps)


class Migration(migrations.Migration):
    dependencies = [("pricing", "0010_album_m2"), ("catalog", "0019_product_price_unit"), ("shop", "0019_orderitem_dims")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
