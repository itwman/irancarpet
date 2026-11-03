"""صفحه‌های «فرش سجاده‌ای + رنگ» (گردویی، آبی کاربنی، سبز، فیروزه‌ای، آبی).

در سرچ کنسول این جست‌وجوها نمایش زیاد ولی کلیک تقریباً صفر داشتند چون فقط صفحهٔ تک‌فرش دیده می‌شد.
برای هر رنگ یک صفحهٔ فرود دستی با «سجاده‌ای» و عبارت رنگ در نام فرش ساخته می‌شود؛ اگر برچسب محصول هم‌نام
از وردپرس مانده باشد، canonical آن به صفحهٔ تازه اشاره می‌کند تا دو صفحه سر یک کلمه رقابت نکنند.
"""
from django.db import migrations

COLORS = [
    ("گردویی", "گردویی", "گردویی رنگی گرم و قهوه‌ای است که لک و ردپا را کمتر نشان می‌دهد و با چوب و سنگ مسجد هماهنگ است"),
    ("آبی کاربنی", "کاربنی", "آبی کاربنی آبی تیره و آرامی است که فضای نمازخانه را باوقار و خنک نشان می‌دهد و در رفت‌وآمد زیاد هم کثیف دیده نمی‌شود"),
    ("سبز", "سبز", "سبز رنگ سنتی سجاده و مسجد است و با کاشی، سنگ و چوب هماهنگ می‌شود"),
    ("فیروزه‌ای", "فیروزه", "فیروزه‌ای یادآور کاشی‌های مساجد ایرانی است و نمازخانه را روشن و شاد نشان می‌دهد"),
    ("آبی", "آبی", "آبی و سرمه‌ای رنگ‌هایی آرام و پرطرفدار برای سجاده‌اند و در فضاهای بزرگ و پررفت‌وآمد خوب جواب می‌دهند"),
]


def text(color, note):
    return (f"<p>{note}. فرش سجاده‌ای {color} در ردیف‌های محراب‌دار بافته می‌شود تا صف نماز منظم بماند و برای مسجد، "
            "نمازخانهٔ ادارات و مدارس و اتاق نماز خانه انتخاب مناسبی است.</p>"
            "<p>سجاده‌ای‌های ایران کارپت در ۵۰۰ و ۷۰۰ شانه هستند: ۵۰۰ شانه اقتصادی‌تر و مناسب متراژ زیاد است و ۷۰۰ شانه پرز ضخیم‌تر و "
            "نقش روشن‌تری دارد. فرش را در عرض و طول دلخواه، حتی یک عدد، سفارش دهید؛ برای اندازه‌گیری و انتخاب، راهنمای "
            "<a href=\"/فرش-سجاده-ای-مخصوص-نمازخانه-ها-مساجد/\">فرش سجاده‌ای مسجد و نمازخانه</a> را بخوانید و همهٔ رنگ‌ها را در "
            "<a href=\"/product-category/فرش-سجاده-ای/\">فرش سجاده‌ای</a> ببینید.</p>")


def slugify(title):
    return title.replace("‌", "-").replace(" ", "-")


def forwards(apps, schema_editor):
    from django.conf import settings

    LandingPage = apps.get_model("landing", "LandingPage")
    ProductTag = apps.get_model("catalog", "ProductTag")
    Need = apps.get_model("finder", "Need")
    sajadeh = Need.objects.filter(title="سجاده‌ای").first()
    if sajadeh is None:
        return
    for color, word, note in COLORS:
        title = f"فرش سجاده‌ای {color}"
        slug = slugify(title)
        if not LandingPage.objects.filter(slug=slug).exists():
            LandingPage.objects.create(slug=slug, title=title, style=sajadeh, name_contains=word, auto=False, content=text(color, note))
        # برچسب هم‌نام قدیمی (اگر از وردپرس مانده) با صفحهٔ تازه رقابت نکند
        tag = ProductTag.objects.filter(slug=slug).first()
        if tag is not None and not tag.canonical_url:
            tag.canonical_url = f"{settings.SITE_URL}/carpets/{slug}/"
            tag.save(update_fields=["canonical_url"])


class Migration(migrations.Migration):
    dependencies = [
        ("landing", "0003_name_contains"),
        ("catalog", "0001_initial"),
        ("finder", "0002_defaults"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
