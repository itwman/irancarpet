from django.conf import settings
from django.db import migrations


def forward(apps, schema_editor):
    from catalog import mocha as M

    S = apps.get_model("core", "SiteSettings")
    Category = apps.get_model("catalog", "Category")
    cat = Category.objects.filter(slug=M.SLUG).first()
    s = S.objects.first()
    if s is None or cat is None or s.feature_category_id:
        return
    farshestan = getattr(settings, "SITE_THEME", "") == "farshestan"
    s.feature_enabled, s.feature_category = True, cat
    if farshestan:
        s.feature_title = "مجموعهٔ موکا"
        s.feature_text = "زمینه‌های صدفی، بژ و کرم با نقش‌های قهوه‌ای ملایم و طلایی؛ پالتی گرم و آرام که این روزها در خانه‌های تازه‌چیده‌شده زیاد دیده می‌شود."
        s.feature_button = "دیدن مجموعهٔ موکا"
    else:
        s.feature_title = "فرش‌های پالت موکا"
        s.feature_text = "رنگ گرم و آرام موکا حالا در فرش ماشینی کاشان: زمینهٔ صدفی، بژ و کرم، با حاشیهٔ هم‌رنگ یا دلفینی، سبز و طلایی."
        s.feature_button = "دیدن فرش‌های موکا"
    s.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0020_sitesettings_feature_button_and_more"), ("catalog", "0018_mocha_border")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
