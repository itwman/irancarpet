"""نیازهای پیش‌فرض فرش‌یاب، بر اساس دسته‌ها و ویژگی‌های فعلی ایران کارپت. همه از پنل قابل تغییرند."""
from django.db import migrations
from django.db.models import Q

# (گروه، عنوان، توضیح، کلمه‌های مشتری، {قاعده‌ها})
NEEDS = [
    ("feel", "ضخیم و کلفت", "پرز بلند و نرم زیر پا", "ضخیم، کلفت، پرزدار، پرز بلند، نرم، تپل، گرم، ضخامت بالا",
     {"reeds": ["700", "1000"], "ex_cat_suffix": ["-carpet-high-bulk"], "ex_kw": "برجسته"}),
    ("feel", "ظریف و ریزبافت", "نقش‌های ریز و دقیق، تراکم بالا", "ظریف، ریزبافت، ریز بافت، ریز نقش، تراکم بالا، باکیفیت، لوکس، نازک",
     {"reeds": ["1200", "1500"]}),
    ("feel", "برجسته", "نقش‌ها روی فرش برجسته‌اند", "برجسته، سه بعدی، سه‌بعدی، های بالک، هایبالک",
     {"cat_suffix": ["-carpet-high-bulk"], "kw": "برجسته"}),
    ("feel", "ساده (غیر برجسته)", "سطح یکدست و صاف", "غیر برجسته، غیربرجسته، ساده، صاف، تخت، یکدست",
     {"cats": ["700-reeds-simple", "1000-reeds-simple", "1200-reeds-simple", "فرش-1500-شانه-ساده"], "ex_kw": "برجسته"}),
    ("feel", "اقتصادی", "قیمت مناسب، کیفیت خوب", "ارزان، ارزون، اقتصادی، قیمت مناسب، مقرون به صرفه، کم هزینه، ارزان قیمت",
     {"cats": ["carpet-under-the-price", "carpet-500-reeds", "فرش-350-شانه"]}),

    ("style", "سنتی و کلاسیک", "لچک ترنج، افشان، شاه‌عباسی", "سنتی، کلاسیک، ایرانی، اصیل، قدیمی، لچک ترنج، افشان، شاه عباسی",
     {"kw": "لچک، ترنج، افشان، شاه عباسی، شاه‌عباسی، سنتی، کلاسیک، کاشان، حوض، خشتی، ماهی، بته، شکارگاه"}),
    ("style", "مدرن و امروزی", "طرح‌های خلوت و شیک", "مدرن، امروزی، شیک، مینیمال، ساده و شیک، اسپرت",
     {"cats": ["special-design-carpet"], "kw": "مدرن، اسپرت، مینیمال"}),
    ("style", "وینتیج", "کهنه‌نما با رنگ‌های ملایم", "وینتیج، وینتج، کهنه نما، کهنه‌نما، رنگ و رو رفته، vintage",
     {"cats": ["vintage"], "kw": "وینتیج"}),
    ("style", "فرانسوی", "گل‌های درشت، حال‌وهوای اروپایی", "فرانسوی، فرانسه، اروپایی، کلاسیک اروپایی",
     {"cats": ["french-design", "french-carpet"], "kw": "فرانسوی"}),
    ("style", "گبه", "طرح عشایری و ساده", "گبه، عشایری، روستایی",
     {"cats": ["gabbeh"], "kw": "گبه"}),
    ("style", "ورساچه", "طرح‌های طلایی و لوکس", "ورساچه، ورساچی، versace",
     {"cats": ["versace-carpet-فرش-طرح-ورساچه"], "kw": "ورساچه"}),

    ("use", "اتاق کودک", "فانتزی و شاد", "کودک، بچه، اتاق بچه، اتاق کودک، فانتزی، کارتونی، نوجوان",
     {"cats": ["فرش-فانتزی"], "kw": "کودک، فانتزی"}),
    ("use", "کناره و راهرو", "باریک و بلند", "کناره، راهرو، باریک، دراز",
     {"cats": ["kenareh"], "kw": "کناره"}),
    ("use", "فرش گرد", "برای فضاهای خاص", "گرد، دایره، دایره ای، دایره‌ای",
     {"cats": ["circle-rugs"], "kw": "گرد"}),
    ("use", "سجاده‌ای", "سجاده و جانماز", "سجاده، سجاده‌ای، جانماز، نماز",
     {"cats": ["فرش-سجاده-ای"], "kw": "سجاده"}),
    ("use", "پادری", "جلوی در و آشپزخانه", "پادری، جلوی در، جلو در، دم در",
     {"cats": ["پادری"], "kw": "پادری"}),
    ("use", "گلیم فرش", "سبک و نازک", "گلیم، گلیم فرش",
     {"cats": ["گلیم-فرش"], "kw": "گلیم"}),
]

COLORS = [
    ("قرمز و لاکی", "#A8232F", "قرمز، لاکی، سرخ، زرشکی، عنابی، اناری، قرمز لاکی"),
    ("سرمه‌ای و آبی", "#1F3566", "سرمه، سرمه‌ای، سرمه ای، آبی، کاربنی، نیلی، فیروزه، فیروزه‌ای"),
    ("کرم و روشن", "#E8DAC2", "کرم، شیری، استخوانی، بژ، سفید، صدفی، روشن"),
    ("طوسی و نقره‌ای", "#9C9EA6", "طوسی، نقره، نقره‌ای، خاکستری، دودی، سیلور"),
    ("سبز", "#3D7A4E", "سبز، یشمی، زیتونی، پسته‌ای، پسته ای"),
    ("قهوه‌ای و گردویی", "#6E4A2F", "قهوه، قهوه‌ای، قهوه ای، گردویی، شکلاتی، مسی، عسلی"),
    ("صورتی و گلبهی", "#E5A3B1", "صورتی، گلبهی، کالباسی، رز، پودری"),
    ("یاسی و بنفش", "#7D5A9E", "یاسی، بنفش، ارغوانی، بادمجانی"),
    ("زرد و طلایی", "#D4A23A", "زرد، طلایی، خردلی، لیمویی"),
    ("مشکی و تیره", "#26262B", "مشکی، سیاه، ذغالی، تیره"),
]


def forwards(apps, schema_editor):
    Need = apps.get_model("finder", "Need")
    Category = apps.get_model("catalog", "Category")
    Attribute = apps.get_model("catalog", "Attribute")
    AttributeTerm = apps.get_model("catalog", "AttributeTerm")
    if Need.objects.exists():
        return
    reeds_attr = Attribute.objects.filter(Q(slug="reeds-per-meter") | Q(label="شانه")).first()
    color_attr = Attribute.objects.filter(Q(slug="background-color") | Q(label="رنگ زمینه") | Q(slug="رنگ-زمینه")).first()

    def cats(slugs=(), suffixes=()):
        q = Q(pk__in=[])
        if slugs:
            q |= Q(slug__in=list(slugs))
        for s in suffixes:
            q |= Q(slug__endswith=s)
        return list(Category.objects.filter(q))

    for i, (group, title, sub, words, r) in enumerate(NEEDS):
        n = Need.objects.create(group=group, title=title, subtitle=sub, keywords=words, order=i,
                                title_keywords=r.get("kw", ""), exclude_keywords=r.get("ex_kw", ""))
        found = cats(r.get("cats", ()), r.get("cat_suffix", ()))
        if found:
            n.categories.set(found)
        ex = cats((), r.get("ex_cat_suffix", ()))
        if ex:
            n.exclude_categories.set(ex)
        if r.get("reeds") and reeds_attr:
            n.terms.set(list(AttributeTerm.objects.filter(attribute=reeds_attr, name__in=r["reeds"])))

    for i, (title, swatch, words) in enumerate(COLORS):
        first = words.split("،")[0].strip()
        Need.objects.create(group="color", title=title, swatch=swatch, keywords=words, order=i,
                            term_attribute=color_attr, term_keywords=words,
                            # اگر رنگ زمینه در ویژگی‌ها ثبت نشده بود، از عنوان فرش
                            title_keywords=f"زمینه {first}")


class Migration(migrations.Migration):
    dependencies = [("finder", "0001_initial"), ("catalog", "0004_filter_attrs")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
