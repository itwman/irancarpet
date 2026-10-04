from django.db import migrations, models


def fill_slugs(apps, schema_editor):
    from django.utils.text import slugify

    from pricing.models import public_title

    Album = apps.get_model("pricing", "Album")
    used = set()
    for a in Album.objects.order_by("pk"):
        base = slugify(public_title(a.name, a.public_name), allow_unicode=True)[:150] or (a.code or f"album-{a.pk}").lower()
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)
        a.slug = slug
        a.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [("pricing", "0003_auto_codes")]

    operations = [
        migrations.AddField("album", "in_price_list", models.BooleanField("نمایش در لیست قیمت سایت", default=True)),
        migrations.AddField("album", "public_name", models.CharField(
            "نام در لیست قیمت", max_length=160, blank=True, help_text="خالی = «فرش» + نام آلبوم؛ مثلاً «فرش 700 شانه ورجین مهرآوران»")),
        migrations.AddField("album", "slug", models.SlugField(
            "نامک صفحهٔ لیست", max_length=160, allow_unicode=True, blank=True,
            help_text="آدرس: /carpets-price-list/نامک/ — خالی بگذارید تا از نام ساخته شود")),
        migrations.AddField("album", "list_intro", models.TextField(
            "متن معرفی در صفحهٔ لیست", blank=True, help_text="HTML ساده؛ زیر فهرست فرش‌ها نمایش داده می‌شود")),
        migrations.AddField("album", "seo_title", models.CharField(
            "عنوان سئو", max_length=300, blank=True,
            help_text="خالی = خودکار. متغیرها: %title% %currentmonth% %currentyear% %sitename%")),
        migrations.AddField("album", "seo_description", models.TextField("توضیحات متا", blank=True, help_text="خالی = خودکار از قیمت‌ها")),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
    ]
