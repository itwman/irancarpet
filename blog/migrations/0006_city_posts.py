"""مقاله‌های «خرید فرش در [شهر]» (۸۵ صفحه، ۹۰ هزار نمایش در سرچ کنسول با ۱.۸٪ کلیک).

این مقاله‌ها از یک قالب ساخته شده‌اند و چند جای‌شان نادرست یا خالی است:
- «قیمت فرش در شهر شما با ارسال رایگان درب منزل به شرح زیر است:» و بعد هیچ (جدول شورت‌کد حذف شده بود)
  ← جملهٔ درست + جدول قیمت روز ([size_prices 12-meter]).
- «قیمت‌ها را ضمانت می‌کنیم که کمترین قیمت بازار [شهر] باشد» ← حذف (ادعای بی‌پشتوانه).
- بخش «تحویل فرش درب منزل»: هزینه‌های قدیمی ارسال (۱۶۰ هزار تومان و…) ← شرایط امروز ([shipping_info شهر]).
- «سوالات متداول» خالی ← پرسش‌های زنده ([city_faq شهر]).
- توضیح متا با وعدهٔ «ارسال رایگان» ← توضیح دقیق.
عنوان‌ها دست نمی‌خورد. نسخهٔ قبلی هر مقاله به‌صورت پیش‌نویس (noindex) نگه داشته می‌شود.
"""
import re

from django.db import migrations
from django.utils import timezone

H = re.compile(r"<(h[2-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
P = re.compile(r"<p\b[^>]*>.*?</p>", re.I | re.S)


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).replace("&nbsp;", " ").strip()


def city_of(post):
    m = re.match(r"^خرید فرش در\s+(.+?)(?:\s*[|⭐☀️🌎+\-–:؛،]|$)", _text(post.title))
    if m:
        return m.group(1).strip()
    return post.slug.replace("خرید-فرش-در-", "").replace("-", " ").strip()


def transform(content, city):
    c = content or ""

    def p_rule(m):
        t = _text(m.group(0))
        if re.search(r"ضمانت\s*می\s*کنیم\s*که\s*کمترین\s*قیمت", t):
            return ""
        if "به شرح زیر است" in t and "قیمت" in t:
            return (f"<p>قیمت امروز فرش ماشینی ۱۲ متری در هر شانه برای خریداران {city} (همان قیمت سایت؛ "
                    "آخرین تغییر قیمت: [price_updated]):</p>\n[size_prices 12-meter]\n")
        return m.group(0)

    c = P.sub(p_rule, c)

    # بخش «تحویل فرش درب منزل» تا تیتر بعدی
    heads = list(H.finditer(c))
    for i, h in enumerate(heads):
        if "تحویل" in _text(h.group(2)) or "ارسال فرش" in _text(h.group(2)):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(c)
            body = c[h.end():end]
            if re.search(r"هزار\s*تومان|بیعانه|رایگان", _text(body)):
                c = c[:h.end()] + f"\n<p>فرش از کاشان بسته‌بندی و به {city} فرستاده می‌شود. شرایط پرداخت و ارسال امروز:</p>\n[shipping_info {city}]\n" + c[end:]
            break

    # پرسش‌های متداول
    if "[city_faq" not in c:
        fh = next((h for h in H.finditer(c) if "متداول" in _text(h.group(2))), None)
        if fh:
            c = c[:fh.end()] + f"\n[city_faq {city}]\n" + c[fh.end():]
        else:
            dh = next((h for h in H.finditer(c) if "دانستنی" in _text(h.group(2))), None)
            first = H.search(c)
            tag = first.group(1).lower() if first else "h2"
            block = f"\n<{tag}>سوالات متداول خرید فرش در {city}</{tag}>\n[city_faq {city}]\n"
            c = c[:dh.start()] + block + c[dh.start():] if dh else c.rstrip() + block
    return c


def description(city):
    return (f"خرید فرش ماشینی کاشان با ارسال به {city}: قیمت روز هر سایز و شانه، خرید نقدی یا اقساطی، "
            f"ضمانت‌نامه و تحویل درب منزل؛ راهنمای انتخاب فرش برای خریداران {city}.")


def forward(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    today = timezone.now()
    for post in Post.objects.filter(slug__startswith="خرید-فرش-در-").exclude(slug__contains="-old-"):
        if "[city_faq" in (post.content or "") or "[size_prices" in (post.content or ""):
            continue
        city = city_of(post)
        new = transform(post.content, city)
        if new == post.content:
            continue
        backup = f"{post.slug}-old-{today:%Y%m%d}"[:255]
        if not Post.objects.filter(slug=backup).exists():
            Post.objects.create(title=f"[نسخهٔ قبلی] {post.title}"[:300], slug=backup, content=post.content,
                                excerpt=post.excerpt, status="draft", author_name=post.author_name, robots="noindex,nofollow")
        fields = {"content": new, "modified_at": today}
        d = post.seo_description or ""
        if not d.strip() or "رایگان" in d or "ارسال به سراسر ایران" in d or "☀" in d or "⭐" in d:
            fields["seo_description"] = description(city)
        Post.objects.filter(pk=post.pk).update(**fields)


class Migration(migrations.Migration):
    dependencies = [("blog", "0005_retiree_post"), ("core", "0013_honest_seo_claims")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
