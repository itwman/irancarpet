"""صفحه‌های پرنمایش با کلیک کم در سرچ کنسول: عنوان و توضیح بهتر، و جدول زنده به‌جای جدول‌های حذف‌شدهٔ وردپرس.

- مقایسهٔ شانه‌ها (۶ مقاله): «در جدول زیر…» و بعد هیچ ← [reeds_compare …]
- معایب فرش X شانه: زیر تیتر قیمت ← [size_prices 12-meter X]
- قیمت فرش ماشینی / انواع فرش ماشینی / آران و بیدگل / فرش گرد: جدول قیمت روز
- فرش به انگلیسی، فرش چیست، سبک‌های فرش کاشان، مهد فرش، تلفن کارخانه: عنوان و توضیح هم‌راستا با جستجوها
فقط بخش‌های خالی پر می‌شود و متن نوشته‌شده می‌ماند؛ نسخهٔ قبلی هر مقاله پیش‌نویس (noindex) می‌شود.
"""
import re

from django.db import migrations
from django.utils import timezone

H = re.compile(r"<(h[2-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
P = re.compile(r"<p\b[^>]*>.*?</p>", re.I | re.S)
EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _t(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).replace("&nbsp;", " ").strip().translate(EN)


def after_heading(c, test, code, after_p=True):
    """شورت‌کد بعد از اولین تیتری که test را می‌گذراند (و بعد از اولین پاراگرافش، اگر پیش از تیتر بعدی باشد)."""
    for h in H.finditer(c):
        if test(_t(h.group(2))):
            at = h.end()
            if after_p:
                nxt = H.search(c, h.end())
                p = P.search(c, h.end())
                if p and (not nxt or p.start() < nxt.start()):
                    at = p.end()
            return c[:at] + f"\n{code}\n" + c[at:], True
    return c, False


def after_para(c, test, code):
    for p in P.finditer(c):
        if test(_t(p.group(0))):
            return c[:p.end()] + f"\n{code}\n" + c[p.end():], True
    return c, False


def after_first_p(c, code):
    p = P.search(c)
    at = p.end() if p else 0
    return c[:at] + f"\n{code}\n" + c[at:]


def compare(c, nums):
    code = f"[reeds_compare {' '.join(nums)}]"
    c, ok = after_para(c, lambda t: "جدول زیر" in t, code)
    if not ok:
        c, ok = after_heading(c, lambda t: re.search(r"مقایسه|تفاوت|فرق", t), code)
    if not ok:
        c = after_first_p(c, code)
    return c


def stale_heading(c):
    # «قیمت فرش ماشینی به روز و معتبر در مردادماه 1401» ← بدون ماه کهنه
    return re.sub(r"(<h[2-6][^>]*>[^<]*?قیمت[^<]*?)\s*در\s+[؀-ۿ]+\s*ماه\s*\d{4}\s*(</h[2-6]>)", r"\1\2", c)


PAGES = {
    "مقایسه-فرش-1200-شانه-و-فرش-1000-شانه": dict(
        fn=lambda c: after_heading(compare(c, ["1000", "1200"]), lambda t: t.startswith("قیمت فرش 1200 شانه"),
                                   "[size_prices 12-meter 1200]", after_p=False)[0]),
    "مقایسه-فرش-1000-شانه-و-فرش-700-شانه": dict(fn=lambda c: compare(c, ["700", "1000"])),
    "تفاوت-فرش-1500-شانه-و-فرش-1200-شانه": dict(fn=lambda c: compare(c, ["1200", "1500"])),
    "فرق-فرش-700-شانه-با-فرش-1000-شانه": dict(fn=lambda c: compare(c, ["700", "1000"])),
    "فرق-فرش-500-شانه-با-فرش-700-شانه": dict(fn=lambda c: compare(c, ["500", "700"])),
    "فرق-فرش-1200-شانه-با-فرش-1500-شانه": dict(fn=lambda c: compare(c, ["1200", "1500"])),
    "معایب-فرش-700-شانه": dict(fn=lambda c: after_heading(c, lambda t: "قیمت" in t, "[size_prices 12-meter 700]")[0]),
    "معایب-فرش-1000-شانه": dict(fn=lambda c: after_heading(c, lambda t: "قیمت" in t, "[size_prices 12-meter 1000]")[0]),
    "معایب-فرش-1200-شانه": dict(fn=lambda c: after_heading(c, lambda t: "قیمت" in t, "[size_prices 12-meter 1200]")[0]),
    "معایب-فرش-1500-شانه": dict(fn=lambda c: after_heading(c, lambda t: "قیمت" in t, "[size_prices 12-meter 1500]")[0]),
    "قیمت-فرش-ماشینی": dict(
        fn=lambda c: after_heading(
            after_heading(stale_heading(c), lambda t: t.startswith("قیمت فرش ماشینی به روز"),
                          "<p>کمترین و بیشترین قیمت امروز هر شانه (آخرین تغییر قیمت: [price_updated])؛ قیمت همهٔ سایزها و آلبوم‌ها در "
                          "<a href=\"/carpets-price-list/\">لیست قیمت فرش ماشینی</a> است.</p>\n[size_prices 12-meter]\n[size_prices 9-meter]\n[size_prices 6-meter]",
                          after_p=False)[0],
            lambda t: "سوالات متداول" in t, "[size_faq 12-meter]", after_p=False)[0],
        title="قیمت فرش ماشینی امروز %currentdate% به نرخ کارخانه",
        desc="قیمت روز فرش ماشینی ۱۲، ۹ و ۶ متری در هر شانه (۷۰۰ تا ۱۵۰۰)، عوامل مؤثر بر قیمت، فرق قیمت شانه‌ها و پاسخ پرسش‌های رایج؛ "
             "به‌روز با قیمت کارخانه‌های کاشان."),
    "قیمت-انواع-فرش-ماشینی": dict(
        fn=lambda c: after_heading(c, lambda t: "بر اساس شانه" in t, "[reeds_compare 700 1000 1200 1500]")[0]),
    "قیمت-فرش-ماشینی-آران-و-بیدگل": dict(
        fn=lambda c: after_heading(c, lambda t: t.startswith("قیمت فرش ماشینی آران"),
                                   "<p>قیمت امروز فرش ۱۲ متری هر شانه (آخرین تغییر قیمت: [price_updated]):</p>\n[size_prices 12-meter]")[0],
        title="قیمت فرش ماشینی آران و بیدگل %currentdate% | خرید مستقیم از کارخانه",
        desc="قیمت روز فرش ماشینی کارخانه‌های آران و بیدگل و کاشان در هر شانه، شهرک‌های صنعتی فرش آران و بیدگل، "
             "عوامل مؤثر بر قیمت و خرید آنلاین مستقیم با ارسال به سراسر ایران."),
    "فرش-ماشینی-گرد": dict(
        fn=lambda c: after_heading(c, lambda t: t.startswith("قیمت فرش ماشینی گرد"),
                                   "<p>قیمت امروز فرش گرد در هر شانه:</p>\n[size_prices round-d3]\n[size_prices round-d2]")[0]),
    "لغت-و-اصطلاحات-تخصصی-انگلیسی-صنعت-فرش-م": dict(
        fn=lambda c: (
            "<div class=\"lb-quick\">\n<p><b>فرش به انگلیسی چه می‌شود؟</b></p>\n<ul>\n"
            "<li><b>Carpet</b>: فرش و موکت، به‌خصوص فرش بزرگ یا دیوار‌به‌دیوار؛ فرش ماشینی = <b>machine-made carpet</b>.</li>\n"
            "<li><b>Rug</b>: فرش یا قالیچه‌ای که همهٔ کف را نمی‌پوشاند؛ قالی دستباف ایرانی = <b>Persian rug</b> یا <b>hand-knotted rug</b>.</li>\n"
            "<li><b>فرش کردن / فرش شدن</b>: to carpet / to be carpeted؛ برای زمین و خیابانی که با سنگ یا آسفالت فرش می‌شود: <b>to pave / to be paved</b>.</li>\n"
            "<li>تار: <b>warp</b>، پود: <b>weft</b>، پرز یا خاب: <b>pile</b>، گره: <b>knot</b>، شانه (تعداد گره در عرض): <b>reed</b>، تراکم: <b>density</b>.</li>\n"
            "</ul>\n</div>\n" + c),
        title="فرش به انگلیسی: Carpet یا Rug؟ + اصطلاحات تخصصی صنعت فرش",
        desc="فرش به انگلیسی Carpet است یا Rug؟ فرق این دو، معادل «فرش شدن» و «فرش کردن»، و فهرست اصطلاحات تخصصی فرش ماشینی "
             "(شانه، تراکم، پرز، تار و پود) به انگلیسی."),
    "فرش-چیست": dict(
        title="فرش یعنی چه؟ معنی فرش در لغت‌نامه دهخدا، معین، شعر و قرآن",
        desc="معنی فرش در لغت‌نامهٔ دهخدا، فرهنگ معین و عمید، تلفظ درست، فرش در قرآن (فُرُش و مِهاد) و شعرهای فارسی دربارهٔ فرش؛ کوتاه و ساده."),
    "سبک-های-عمدۀ-طرح-فرش-کاشان": dict(
        title="فرش دستباف کاشان: ۸ طرح معروف قالی کاشان، رنگرزی و بافت",
        desc="آشنایی با فرش دستباف کاشان: طرح‌های لچک‌ترنج، افشان، گلدانی، محرابی، شکارگاه و محتشم، نقش‌مایه‌ها، رنگرزی سنتی، "
             "گره و رج‌شمار و اندازه‌های رایج قالی کاشان."),
    "مهد-فرش": dict(
        title="مهد فرش ایران کجاست؟ کاشان، مشهد یا تبریز | ایران کارپت",
        desc="مهد فرش ماشینی ایران کدام شهر است؟ تاریخچهٔ فرش ماشینی، سهم کاشان، مشهد و تبریز در تولید فرش و نکته‌های خرید "
             "مستقیم از کارخانه‌های کاشان."),
    "تلفن-کارخانه-فرش-کاشان": dict(
        fn=lambda c: re.sub(r"\s*به\s+صورت\s+رایگان", "", c),
        title="شماره تلفن کارخانه فرش کاشان برای خرید مستقیم + ساعت کاری",
        desc="شماره تماس برای خرید مستقیم و مشاوره از کارخانه‌های فرش ماشینی کاشان، ساعت کاری، شهرک‌های صنعتی فرش کاشان "
             "و معرفی کارخانه‌ها و برندهای معروف."),
}


def forward(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    today = timezone.now()
    for slug, cfg in PAGES.items():
        post = Post.objects.filter(slug=slug).first()
        if post is None:
            continue
        fields = {}
        fn = cfg.get("fn")
        if fn and not re.search(r"\[(?:reeds_compare|size_prices|size_faq)", post.content or ""):
            new = fn(post.content or "")
            if new != post.content:
                backup = f"{slug}-old-{today:%Y%m%d}"[:255]
                if not Post.objects.filter(slug=backup).exists():
                    Post.objects.create(title=f"[نسخهٔ قبلی] {post.title}"[:300], slug=backup, content=post.content,
                                        excerpt=post.excerpt, status="draft", author_name=post.author_name,
                                        robots="noindex,nofollow", seo_title=post.seo_title, seo_description=post.seo_description)
                fields["content"] = new
        if cfg.get("title"):
            fields["seo_title"] = cfg["title"]
        if cfg.get("desc"):
            fields["seo_description"] = cfg["desc"]
        if fields:
            fields["modified_at"] = today
            Post.objects.filter(pk=post.pk).update(**fields)


class Migration(migrations.Migration):
    dependencies = [("blog", "0006_city_posts")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
