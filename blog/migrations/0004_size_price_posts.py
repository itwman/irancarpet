"""مقاله‌های «قیمت فرش ماشینی X متری (Y شانه)»: جدول‌های قیمت خالی ← جدول زنده.

در وردپرس جدول قیمت و پرسش‌های متداول این مقاله‌ها با شورت‌کد افزونه ساخته می‌شد که هنگام انتقال حذف شد؛
الان زیر «لیست قیمت …» و «سوالات متداول» چیزی نیست. سرچ کنسول: «قیمت فرش ۶ متری» ۱۰ هزار نمایش در رتبهٔ ۸
با ۰.۳٪ کلیک.

- متن نوشتاری مقاله می‌ماند؛ جدول قیمت روز ([size_prices]) و پرسش‌های زنده ([size_faq]) جای خالی‌ها می‌نشیند.
- بخش قدیمی «خرید اقساطی» (روش‌هایی که دیگر نیست) با شرایط واقعی امروز ([installment_plans]) عوض می‌شود.
- پاراگراف‌های خالی و وعدهٔ قدیمی «ارسال رایگان بالای ۱۰ میلیون» حذف می‌شود.
- عنوان سئو ماه و سال روز را می‌گیرد (%currentdate%)؛ مقاله‌ای که در رتبهٔ ۱-۲ است عنوانش دست نمی‌خورد.
- نسخهٔ قبلی هر مقاله به‌صورت پیش‌نویس (noindex) نگه داشته می‌شود.
"""
import re

from django.db import migrations
from django.utils import timezone

FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
SLUGS = [
    "قیمت-فرش-6-متری",
    "قیمت-فرش-ماشینی-6-متری",
    "قیمت-فرش-ماشینی-9-متری",
    "قیمت-فرش-ماشینی-12-متری",
    "قیمت-فرش-ماشینی-12-متری-1200-شانه",
    "قیمت-فرش-ماشینی-9-متری-1200-شانه",
    "قیمت-فرش-ماشینی-12-متری-700-شانه",
    "قیمت-فرش-ماشینی-9-متری-700-شانه",
    "قیمت-فرش-ماشینی-6-متری-700-شانه",
    "قیمت-فرش-ماشینی-12-متری-1000-شانه",
    "قیمت-فرش-ماشینی-9-متری-1000-شانه",
    "قیمت-فرش-ماشینی-6-متری-1000-شانه",
    "قیمت-فرش-ماشینی-12-متری-1200-شانه-2",
    "قیمت-فرش-ماشینی-9-متری-1200-شانه-2",
    "قیمت-فرش-ماشینی-6-متری-1200-شانه",
    "قیمت-فرش-ماشینی-9-متری-1500-شانه",
    "قیمت-فرش-ماشینی-6-متری-1500-شانه",
    "قیمت-فرش-ماشینی-12-متری-1500-شانه",
]
KEEP_TITLE = {"قیمت-فرش-ماشینی-9-متری-1200-شانه-2"}  # رتبهٔ ۱.۷ در سرچ کنسول
SIZE = {"6": "6-meter", "9": "9-meter", "12": "12-meter"}

EMPTY_P = re.compile(r"<p[^>]*>(?:\s|&nbsp;|\xa0|<br\s*/?>)*</p>", re.I)
H = re.compile(r"<(h[2-4])\b[^>]*>(.*?)</\1>", re.I | re.S)


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).replace("&nbsp;", " ").strip()


def _after_first_p(html, start=0):
    i = html.find("</p>", start)
    return i + 4 if i >= 0 else -1


def transform(content, slug):
    m = re.search(r"-(\d+)-متری(?:-(\d+)-شانه)?", slug)
    size, reeds = SIZE[m.group(1)], m.group(2)
    tag = f"{size} {reeds}" if reeds else size
    c = EMPTY_P.sub("", content or "")
    # وعدهٔ قدیمی ارسال رایگان
    c = re.sub(r"<p\b[^>]*>.*?</p>", lambda x: "" if re.search(r"بالای\s*(?:10|۱۰)\s*میلیون", _text(x.group(0))) else x.group(0),
               c, flags=re.S)

    # بخش قدیمی «خرید اقساطی فرش ماشینی» تا تیتر h2 بعدی
    hs = list(H.finditer(c))
    for i, h in enumerate(hs):
        if h.group(1).lower() == "h2" and "اقساط" in _text(h.group(2)) and "خرید" in _text(h.group(2)):
            end = next((x.start() for x in hs[i + 1:] if x.group(1).lower() == "h2"), len(c))
            c = (c[:h.end()] + "\n<p>خرید قسطی همین فرش‌ها با قیمت نقدی روز ممکن است؛ شرایط امروز هر روش:</p>\n"
                 "[installment_plans]\n" + c[end:])
            break

    # جدول هر شانه زیر تیتر «… X متری Y شانه» (در مقاله‌های کلی سایز)
    if not reeds:
        for h in reversed(list(H.finditer(c))):
            t = _text(h.group(2)).translate(EN)
            mm = re.search(r"(\d+)\s*شانه", t)
            if h.group(1).lower() in ("h3", "h4") and "قیمت" in t and mm and mm.group(1) in ("700", "1000", "1200", "1500"):
                at = _after_first_p(c, h.end())
                nxt = H.search(c, h.end())
                if at < 0 or (nxt and nxt.start() < at):
                    at = h.end()
                c = c[:at] + f"\n[size_prices {size} {mm.group(1)}]\n" + c[at:]

    # تیتر خالیِ «… نقدی و اقساطی»
    for h in reversed(list(H.finditer(c))):
        nxt = H.search(c, h.end())
        body = c[h.end():nxt.start() if nxt else len(c)]
        if "اقساط" in _text(h.group(2)) and not _text(body) and "[installment_plans]" not in c:
            c = (c[:h.end()] + "\n<p>قیمت نقد همان جدول‌های بالاست؛ برای خرید قسطی، شرایط امروز هر روش:</p>\n[installment_plans]\n"
                 + c[h.end():])

    # جدول خلاصه: زیر تیتر «لیست قیمت …» اگر هست، وگرنه بعد از پاراگراف اول
    lead = (f"\n<p>قیمت‌های زیر هر روز از قیمت فروش ایران کارپت خوانده می‌شود (آخرین تغییر قیمت: [price_updated]).</p>\n"
            f"[size_prices {tag}]\n")
    lh = next((h for h in H.finditer(c) if h.group(1).lower() == "h2" and "لیست قیمت" in _text(h.group(2))), None)
    at = lh.end() if lh else _after_first_p(c)
    c = c[:at] + lead + c[at:] if at > 0 else lead + c

    # پرسش‌های متداول
    faq = f"\n[size_faq {tag}]\n"
    fh = next((h for h in H.finditer(c) if "سوالات متداول" in _text(h.group(2)) or "پرسش" in _text(h.group(2)) and "متداول" in _text(h.group(2))), None)
    if fh:
        c = c[:fh.end()] + faq + c[fh.end():]
    else:
        c = c.rstrip() + "\n<h2>سوالات متداول</h2>" + faq
    return c


def title_for(slug):
    m = re.search(r"-(\d+)-متری(?:-(\d+)-شانه)?", slug)
    name = f"قیمت فرش ماشینی {m.group(1)} متری".translate(FA)
    if m.group(2):
        return f"{name} {m.group(2).translate(FA)} شانه %currentdate% %sep% %sitename%"
    return f"{name} امروز %currentdate% + لیست قیمت"


def desc_for(slug):
    m = re.search(r"-(\d+)-متری(?:-(\d+)-شانه)?", slug)
    name = f"فرش ماشینی {m.group(1)} متری".translate(FA) + (f" {m.group(2)} شانه".translate(FA) if m.group(2) else "")
    return (f"قیمت روز {name} در هر لیست قیمت، از ارزان‌ترین تا گران‌ترین؛ "
            + ("ابعاد، تفاوت قیمت شانه‌ها" if not m.group(2) else "ابعاد، جنس نخ")
            + " و خرید نقدی یا اقساطی مستقیم از کاشان.")


def forward(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    today = timezone.now()
    for slug in SLUGS:
        post = Post.objects.filter(slug=slug).first()
        if post is None or "[size_prices" in (post.content or "") or "<table" in (post.content or ""):
            continue
        backup = f"{slug}-old-{today:%Y%m%d}"[:255]
        if not Post.objects.filter(slug=backup).exists():
            Post.objects.create(title=f"[نسخهٔ قبلی] {post.title}"[:300], slug=backup, content=post.content,
                                excerpt=post.excerpt, status="draft", author_name=post.author_name, robots="noindex,nofollow")
        post.content = transform(post.content, slug)
        fields = ["content", "modified_at"]
        if slug not in KEEP_TITLE:
            post.seo_title = title_for(slug)
            fields.append("seo_title")
        d = post.seo_description or ""
        if not d.strip() or "ارسال رایگان" in d or "☀" in d:
            post.seo_description = desc_for(slug)
            fields.append("seo_description")
        post.modified_at = today
        post.save(update_fields=fields)


class Migration(migrations.Migration):
    dependencies = [("blog", "0003_installment_post")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
