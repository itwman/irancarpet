"""عنوان و توضیح صفحهٔ اول برای پربازدیدترین جستجوی سایت: «خرید مستقیم فرش از کارخانه کاشان».

سرچ کنسول: ۱۴ هزار نمایش در رتبهٔ ۱۰ با ۱.۹٪ کلیک. عنوان قبلی این عبارت را نداشت و توضیحش وعدهٔ
«ارسال رایگان به سراسر کشور» و «تحویل فوری» می‌داد که بی‌شرط درست نیست. فقط اگر عنوان/توضیح همان متن
قدیمی وردپرس (یا خالی) باشد عوض می‌شود؛ متنی که در پنل دستی نوشته شده دست نمی‌خورد.
"""
from django.db import migrations

TITLE = "خرید مستقیم فرش از کارخانه کاشان | فرش ماشینی ایران کارپت"
DESC = ("خرید مستقیم فرش ماشینی از کارخانه‌های کاشان، بی‌واسطه و با قیمت روز هر سایز؛ "
        "فرش ۷۰۰ تا ۱۵۰۰ شانه، خرید نقدی یا اقساطی، ضمانت ۵ ساله و ارسال به سراسر ایران.")
OLD_MARKS = ("بازار فرش آنلاین", "خرید اینترنتی فرش ✅")


def forward(apps, schema_editor):
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first()
    if s is None:
        return
    fields = []
    if not (s.home_title or "").strip() or any(m in s.home_title for m in OLD_MARKS):
        s.home_title = TITLE
        fields.append("home_title")
    d = s.home_description or ""
    if not d.strip() or "ارسال رایگان به سراسر کشور" in d or "تحویل فوری" in d:
        s.home_description = DESC
        fields.append("home_description")
    if fields:
        s.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("core", "0011_facebook")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
