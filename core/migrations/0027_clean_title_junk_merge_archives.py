"""ایران کارپت، آبان ۱۴۰۵ — پاکسازی عنوان‌های سئو و یکی کردن آرشیوهای تکراری (بندهای ۱ و ۳ ممیزی سئو).

۱) عنوان‌های دورهٔ وردپرس پر از «☀️ ارزان!»، ⭐ و ✅ بودند (حدود ۳٬۱۴۸ فرش و ۵۵ دسته). گوگل این نشانه‌ها را اغلب حذف
   می‌کند یا عنوان را از نو می‌نویسد و ابزارهای ممیزی آن را «عنوان اسپم» می‌شمارند. فقط نشانه‌ها و «ارزان!» برداشته
   می‌شود؛ بقیهٔ عنوان، نام فرش، متن، قیمت و نشانی دست نمی‌خورند. نشانه‌ای که میان دو عبارت بود جایش «|» می‌گذارد.
   فقط فرش‌ها، دسته‌ها، برچسب‌ها، برندها، مقدار ویژگی‌ها و الگوی عنوان همین‌ها؛ مقاله‌ها و برگه‌ها نه.
۲) آرشیوهایی که دقیقاً همان فرش‌های یک دسته را نشان می‌دهند با ۳۰۱ به آن دسته می‌روند (برچسب «۷۰۰ شانه برجسته مهرآوران»،
   برچسب «گبه»، دستهٔ «زیر قیمت»، شانهٔ ۳۲۰ و تراکم ۷۵۰ گلیم، تراکم «۵۰ رج» دستباف و تراکم ۲۵۵۰ = ۷۰۰ شانه).
   فقط اگر همهٔ فرش‌های منتشرشدهٔ مبدأ در مقصد هم باشند. از پنل (فیلد «انتقال دائمی به») برگشت‌پذیر است.
فقط روی ایران کارپت.
"""
import re

from django.conf import settings
from django.db import migrations

MODELS = [("catalog", "Product"), ("catalog", "Category"), ("catalog", "ProductTag"), ("catalog", "Brand"),
          ("catalog", "AttributeTerm")]
SKIP_TPL = ("pt_post", "pt_page", "tax_category", "tax_post_tag", "pt_attachment")  # مقاله و برگه دست نمی‌خورد

# پیکان‌ها، ☀ ⭐ ✅ ✔ و شکلک‌ها — با نویسهٔ واقعی (نه \\u…) تا الگو در MySQL هم همین معنا را بدهد
SYMBOLS = (chr(0x2190) + "-" + chr(0x21FF) + chr(0x2300) + "-" + chr(0x23FF) + chr(0x2460) + "-" + chr(0x24FF)
           + chr(0x25A0) + "-" + chr(0x27BF) + chr(0x2900) + "-" + chr(0x297F) + chr(0x2B00) + "-" + chr(0x2BFF)
           + chr(0x1F000) + "-" + chr(0x1FAFF))
EMOJI = re.compile("[" + SYMBOLS + chr(0xFE0F) + chr(0x200D) + chr(0x20E3) + "]+")
SEP = r"|\-–—،,:؛"
JUNK_RX = "[" + SYMBOLS + "]" + r"|ارزان\s*!"


def clean(text):
    if not text or not re.search(JUNK_RX, text):
        return text
    s = re.sub(r"\s*ارزان\s*[!！]+", " ", text)
    s = EMOJI.sub(" ¦ ", s)
    s = re.sub(rf"\s*¦\s*(?=[{SEP}%])", " ", s)       # نشانه کنار جداکنندهٔ موجود: فقط حذف
    s = re.sub(rf"(?<=[{SEP}])\s*¦\s*", " ", s)
    s = re.sub(r"^(\s*¦\s*)+|(\s*¦\s*)+$", "", s)
    s = re.sub(r"(\s*¦\s*)+", " | ", s)
    s = re.sub(r"\s*[!！]+\s*$", "", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" " + SEP.replace("\\", ""))
    return s or text


def clean_titles(apps):
    for app, name in MODELS:
        M = apps.get_model(app, name)
        for pk, t in M.objects.filter(seo_title__regex=JUNK_RX).values_list("pk", "seo_title").iterator(chunk_size=500):
            new = clean(t)
            if new != t:
                M.objects.filter(pk=pk).update(seo_title=new)
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first()
    if s and s.title_templates:
        tpl = {k: (clean(v) if isinstance(v, str) and not k.startswith(SKIP_TPL) else v) for k, v in s.title_templates.items()}
        if tpl != s.title_templates:
            S.objects.filter(pk=1).update(title_templates=tpl)


def split_shared_titles(apps):
    """فرش‌های متفاوتی که در وردپرس یک «عنوان سئو» گرفته بودند (مثلاً نسخهٔ پلی‌استر و آکریلیک یک نقشه): عنوان سئوی
    دستی‌شان خالی می‌شود تا از نام خود فرش ساخته شود و هر کدام عنوان یکتای خودش را داشته باشد. فرش‌هایی که نامشان هم
    یکی است (تکراری واقعی) اینجا دست نمی‌خورند؛ فرمان dup_products فهرستشان را برای تصمیم می‌دهد."""
    from collections import defaultdict

    Product = apps.get_model("catalog", "Product")
    groups = defaultdict(list)
    for pk, st, title in (Product.objects.filter(status="publish").exclude(seo_title="")
                          .values_list("pk", "seo_title", "title").iterator(chunk_size=1000)):
        groups[re.sub(r"\s+", " ", st).strip()].append((pk, re.sub(r"[\s\u200c]+", " ", title).strip()))
    for rows in groups.values():
        if len(rows) > 1 and len({t for _, t in rows}) > 1:
            Product.objects.filter(pk__in=[pk for pk, _ in rows]).update(seo_title="")


# (نوع مبدأ، مبدأ، مسیر دستهٔ مقصد)
MERGES = [
    ("tag", "فرش-700-شانه-برجسته-مهرآوران", "carpet-700-reeds/carpet-700-reeds-carpet-high-bulk"),
    ("tag", "گبه", "gabbeh"),
    ("cat", "carpet-under-the-price", "off-carpet"),
    ("term", ("reeds-per-meter", "320"), "گلیم-فرش"),
    ("term", ("picks-per-meter", "750"), "گلیم-فرش"),
    ("term", ("picks-per-meter", "50-رج"), "carpets/capets-handmade"),
    ("term", ("picks-per-meter", "2550"), "carpet-700-reeds"),
]


def merge_archives(apps):
    Category = apps.get_model("catalog", "Category")
    ProductTag = apps.get_model("catalog", "ProductTag")
    AttributeTerm = apps.get_model("catalog", "AttributeTerm")
    Product = apps.get_model("catalog", "Product")

    def cat_by_path(path):
        node = None
        for seg in path.split("/"):
            node = Category.objects.filter(parent=node, slug=seg).first()
            if node is None:
                return None
        return node

    def descendants(cat):
        ids, frontier = [cat.pk], [cat.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            ids += frontier
        return ids

    pub = Product.objects.filter(status="publish")
    for kind, src, target_path in MERGES:
        target = cat_by_path(target_path)
        if target is None or target.redirect_url:
            continue
        if kind == "tag":
            obj = ProductTag.objects.filter(slug=src, redirect_url="").first()
            ids = set(pub.filter(tags=obj).values_list("pk", flat=True)) if obj else set()
        elif kind == "cat":
            obj = Category.objects.filter(slug=src, redirect_url="").first()
            ids = set(pub.filter(categories__in=descendants(obj)).values_list("pk", flat=True)) if obj else set()
        else:
            obj = AttributeTerm.objects.filter(attribute__slug=src[0], slug=src[1], redirect_url="").first()
            ids = set(pub.filter(specs=obj).values_list("pk", flat=True)) if obj else set()
        if not obj or not ids:
            continue
        in_target = set(pub.filter(categories__in=descendants(target)).values_list("pk", flat=True))
        if not ids <= in_target:  # مبدأ فرشی دارد که در دسته نیست ← یکی نیستند، دست نمی‌خورد
            continue
        url = f"/product-category/{target_path}/"
        type(obj).objects.filter(pk=obj.pk).update(redirect_url=url)


def forwards(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    clean_titles(apps)
    split_shared_titles(apps)
    merge_archives(apps)


class Migration(migrations.Migration):
    dependencies = [("core", "0026_trust_since"), ("catalog", "0025_redirect_url_tag_term"),
                    ("landing", "0006_merge_color_size_duplicates")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
