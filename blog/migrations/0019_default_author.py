"""ایران کارپت: نویسندهٔ پیش‌فرض مقاله‌ها. متن معرفی از پنل ← نویسندگان قابل ویرایش است. روی فرشستان کاری نمی‌کند."""
from django.conf import settings
from django.db import migrations

BIO = ("مدیر فروش ایران کارپت در کاشان و مدیرعامل شرکت توسعه هوشمند فرش ایرانیان که برای صنعت فرش و نساجی نرم‌افزار می‌سازد. "
       "مقاله‌های راهنمای خرید، قیمت و مشخصات فنی فرش ماشینی مجلهٔ ایران کارپت را می‌نویسد یا بازبینی می‌کند.")


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    Author = apps.get_model("blog", "Author")
    if Author.objects.exists():
        return
    Author.objects.create(name="محمدعلی ناظری", slug="محمدعلی-ناظری", role="مدیر فروش ایران کارپت", bio=BIO,
                          knows_about="فرش ماشینی، قیمت فرش ماشینی، فرش کاشان، شانه و تراکم فرش، خرید اقساطی فرش",
                          is_default=True, sort_order=1)


class Migration(migrations.Migration):
    dependencies = [("blog", "0018_author")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
