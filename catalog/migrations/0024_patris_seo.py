"""صفحهٔ برند پاتریس: «فرش پاتریس» در سرچ کنسول ۳٬۶۰۰ نمایش با جایگاه ۶ ولی نرخ کلیک ۰٫۵٪ داشت.

فقط اگر عنوان و توضیح دستی خالی باشد پر می‌شود (متن دستی پنل دست نمی‌خورد)؛ هیچ ادعایی دربارهٔ کارخانهٔ سازنده نمی‌کند.
"""
from django.db import migrations

TITLE = "فرش پاتریس؛ قیمت روز همهٔ طرح‌ها و خرید آنلاین"
DESC = ("خرید فرش پاتریس با قیمت روز: همهٔ طرح‌ها و رنگ‌های پاتریس با قیمت هر سایز، خرید نقدی یا اقساطی و ارسال به همهٔ شهرهای ایران.")
INTRO = ("<p>همهٔ طرح‌های فرش پاتریس را این‌جا با قیمت روز هر سایز می‌بینید. برای مقایسه با برندهای دیگر، شانه، تراکم و جنس نخ هر فرش را "
         "در صفحهٔ همان فرش ببینید؛ فرش را می‌توانید نقدی یا اقساطی بخرید و به همهٔ شهرهای ایران فرستاده می‌شود.</p>")


def forwards(apps, schema_editor):
    Brand = apps.get_model("catalog", "Brand")
    b = Brand.objects.filter(slug="patris").first()
    if b is None:
        return
    fields = []
    if not (b.seo_title or "").strip():
        b.seo_title = TITLE
        fields.append("seo_title")
    if not (b.seo_description or "").strip():
        b.seo_description = DESC
        fields.append("seo_description")
    if not (b.description or "").strip():
        b.description = INTRO
        fields.append("description")
    if fields:
        b.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0023_mocha_collection")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
