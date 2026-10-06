from django.db import migrations

OLD = "خرید نقدی و اقساطی، ارسال مستقیم از کاشان"
NEW = "✅ خرید نقدی و اقساطی، ارسال مستقیم از کاشان\n📞 {تلفن}\n{کانال‌ها}"


def seed(apps, schema_editor):
    S = apps.get_model("rajyar", "RajyarSettings")
    Size = apps.get_model("pricing", "Size")
    s, _ = S.objects.get_or_create(pk=1)
    if (s.footer or "").strip() in ("", OLD):
        s.footer = NEW
        s.save(update_fields=["footer"])
    if not s.weekly_sizes.exists():
        sizes = [x for slug in ("12-meter", "9-meter", "6-meter") for x in Size.objects.filter(slug=slug)[:1]]
        s.weekly_sizes.set(sizes)


class Migration(migrations.Migration):
    dependencies = [("rajyar", "0003_channels_auto"), ("pricing", "0004_price_list")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
