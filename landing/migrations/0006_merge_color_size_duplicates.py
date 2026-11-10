"""ایران کارپت، آبان ۱۴۰۵ — یکی کردن صفحه‌های تکراری رنگ و سایز با صفحه‌های فرود.

صفحه‌های قدیمی وردپرس که دقیقاً همان موضوع یک صفحهٔ فرود را دارند، با ۳۰۱ به آن می‌روند تا دو صفحه سر یک کلمه رقابت
نکنند و اعتبار پیوندهای بیرونی‌شان (مثلاً ۲۱ پیوند به «فرش زمینه بژ») به صفحهٔ فرود برسد:
  /background-color/کرم/ و /product-tag/فرش-زمینه-کرم/ و «بژ»  ← /carpets/فرش-کرم/
  /product-tag/فرش-12-متری/                                   ← /carpets/فرش-12-متری/
  و همین‌طور سرمه‌ای، طوسی، سبز، قهوه‌ای، مشکی، یاسی، زرد، ۶ و ۹ متری و گرد قطر ۱.۵.
فقط رنگی که نامش همان نام صفحهٔ فرود است (به‌اضافهٔ بژ ← کرم)؛ رنگ‌های ترکیبی و خاص (کرم‌سبز، فیلی، لاکی، دلفینی…) صفحهٔ خودشان را
نگه می‌دارند. فقط اگر صفحهٔ فرود مقصد زنده باشد (دست‌کم ۴ فرش). فقط روی ایران کارپت؛ از پنل (فیلد «انتقال دائمی به») برگشت‌پذیر است.
"""
from django.conf import settings
from django.db import migrations

MIN = 4
EXTRA = {"بژ": "کرم"}  # نام دیگر ← نام صفحهٔ فرود
SIZE_TAGS = {"فرش-12-متری": "12-meter", "فرش-6-متری": "6-meter", "فرش-9-متری": "9-meter", "فرش-گرد-قطر-1-و-نیم": "round-d150"}


def norm(s):
    return (s or "").replace("‌", "").replace("-", "").replace(" ", "").strip()


def forwards(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    LandingPage = apps.get_model("landing", "LandingPage")
    Need = apps.get_model("finder", "Need")
    Size = apps.get_model("pricing", "Size")
    ProductTag = apps.get_model("catalog", "ProductTag")
    AttributeTerm = apps.get_model("catalog", "AttributeTerm")

    def page_url(**kw):
        lp = LandingPage.objects.filter(is_active=True, count__gte=MIN, reeds=None, style=None, name_contains="", **kw).first()
        return f"/carpets/{lp.slug}/" if lp else ""

    # رنگ‌ها: «کرم و روشن» ← صفحهٔ «فرش کرم»
    by_color = {}
    for need in Need.objects.filter(group="color"):
        url = page_url(color=need, size=None)
        if url:
            by_color[norm(need.title.split(" و ")[0])] = url
    for alias, target in EXTRA.items():
        if norm(target) in by_color:
            by_color[norm(alias)] = by_color[norm(target)]

    for term in AttributeTerm.objects.filter(attribute__slug="background-color", redirect_url=""):
        url = by_color.get(norm(term.name)) or by_color.get(norm(term.slug))
        if url:
            AttributeTerm.objects.filter(pk=term.pk).update(redirect_url=url)
    for tag in ProductTag.objects.filter(slug__startswith="فرش-زمینه-", redirect_url=""):
        url = by_color.get(norm(tag.slug.replace("فرش-زمینه-", "", 1)))
        if url:
            ProductTag.objects.filter(pk=tag.pk).update(redirect_url=url)

    # سایزها
    for slug, size_slug in SIZE_TAGS.items():
        size = Size.objects.filter(slug=size_slug).first()
        url = page_url(color=None, size=size) if size else ""
        if url:
            ProductTag.objects.filter(slug=slug, redirect_url="").update(redirect_url=url)


class Migration(migrations.Migration):
    dependencies = [("landing", "0005_reeds_hubs_design_pages")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
