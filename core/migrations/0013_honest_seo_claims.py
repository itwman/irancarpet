"""وعده‌های نادرست در عنوان و توضیح سئو (از دورهٔ وردپرس).

«ارسال رایگان به سراسر کشور» بی‌شرط نیست (فقط سفارش‌های بالای سقف با پرداخت کامل آنلاین)، و «۳۰٪ زیر قیمت»
عددی است که پشتوانه ندارد. گوگل وعدهٔ نادرست در نتیجهٔ جستجو را نشانهٔ کم‌اعتمادی می‌داند و خریدار هم بعد از
کلیک ناامید می‌شود. فقط همین عبارت‌ها عوض می‌شود؛ بقیهٔ متن دست نمی‌خورد.
"""
import re

from django.db import migrations

MODELS = [("catalog", "Category"), ("catalog", "ProductTag"), ("catalog", "Brand"), ("catalog", "AttributeTerm"),
          ("catalog", "Product"), ("blog", "BlogCategory"), ("blog", "BlogTag"), ("blog", "Post"), ("blog", "Page")]

RULES = [
    (re.compile(r"ارسال\s+رایگان\s+(به\s+)"), r"ارسال \1"),
    (re.compile(r"(?:به\s+همراه|همراه\s+با|با)\s+ارسال\s+رایگان"), "با ارسال به سراسر ایران"),
    (re.compile(r"\+\s*ارسال\s+رایگان"), "+ ارسال به سراسر ایران"),
    (re.compile(r"ارسال\s+رایگان"), "ارسال به سراسر ایران"),
    (re.compile(r"\s*(?:مشاوره\s+و\s+خرید\s+با\s+)?(?:30|۳۰)\s*[%٪]\s*زیر\s*قیمت(?:\s+بازار(?:\s+فرش)?)?\s*!?"), " مستقیم از کارخانه"),
]


def fix(text):
    if not text:
        return text
    out = text
    for rx, repl in RULES:
        out = rx.sub(repl, out)
    out = re.sub(r"ارسال به سراسر ایران(\s*[⚡️✅☀️⭐️🌎|،,+-]*\s*)ارسال به سراسر (?:کشور|ایران)", r"ارسال به سراسر ایران", out)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    return out


def forward(apps, schema_editor):
    for app, name in MODELS:
        M = apps.get_model(app, name)
        qs = M.objects.filter(seo_title__regex=r"ارسال\s+رایگان|زیر\s*قیمت") | M.objects.filter(
            seo_description__regex=r"ارسال\s+رایگان|زیر\s*قیمت")
        for obj in qs.distinct():
            t, d = fix(obj.seo_title), fix(obj.seo_description)
            if t != obj.seo_title or d != obj.seo_description:
                obj.seo_title, obj.seo_description = t, d
                M.objects.filter(pk=obj.pk).update(seo_title=t, seo_description=d)
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first()
    if s and s.title_templates:
        tpl = {k: fix(v) if isinstance(v, str) else v for k, v in s.title_templates.items()}
        if tpl != s.title_templates:
            S.objects.filter(pk=1).update(title_templates=tpl)


class Migration(migrations.Migration):
    dependencies = [("core", "0012_home_direct_title"), ("catalog", "0012_product_seller_variation_stock_qty"), ("blog", "0005_retiree_post")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
