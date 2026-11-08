"""ایران کارپت: نویسندهٔ مقاله‌های فرش دستباف (نسرین سمساریان) و تخصص فرش ماشینی برای محمدعلی ناظری.
عکس‌ها از پنل ← نویسندگان مجله گذاشته می‌شوند. روی فرشستان کاری نمی‌کند."""
from django.conf import settings
from django.db import migrations

NASRIN_BIO = ("دانش‌آموختهٔ کارشناسی حقوق و علاقه‌مند به هنرهای ایرانی و فرش دستباف. "
              "مقاله‌های مجلهٔ ایران کارپت دربارهٔ تاریخ، طرح و نقش، نگهداری و بازار فرش دستباف، گلیم و گبه را می‌نویسد.")


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    Author = apps.get_model("blog", "Author")
    Author.objects.filter(slug="محمدعلی-ناظری").update(
        knows_about="فرش ماشینی، قیمت فرش ماشینی، فرش کاشان، شانه و تراکم فرش، جنس نخ فرش، خرید اقساطی فرش")
    if not Author.objects.filter(slug="نسرین-سمساریان").exists():
        Author.objects.create(
            name="نسرین سمساریان", slug="نسرین-سمساریان", role="نویسندهٔ مقاله‌های فرش دستباف", bio=NASRIN_BIO,
            knows_about="فرش دستباف، تاریخ فرش ایران، طرح و نقش فرش، گلیم و گبه، نگهداری فرش دستباف",
            title_words="دستباف، قالی، گلیم، گبه، جاجیم، پازیریک", title_skip="ماشینی، قالیچه، قالین", sort_order=2)


class Migration(migrations.Migration):
    dependencies = [("blog", "0021_author_title_words")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
