"""نام فروشگاه‌های دیگر از عنوان و توضیح صفحه‌های ایران کارپت برداشته می‌شود (تصمیم مدیر سایت).

- ۸۵ مقالهٔ «خرید فرش در [شهر]»: عنوان «… ⭐️ فروشگاه شهر فرش ماشینی در [شهر]🌎» (که H1 هم هست)
  ← «خرید فرش در [شهر]؛ فرش ماشینی کاشان با ارسال به [شهر]»؛ تیتر «شهر فرش [شهر]» در متن ← «تنوع فرش برای خریداران [شهر]».
- برگهٔ /vozaracarpet/: عنوان و توضیح بدون نام «فرش وزرا»؛ متن اطلاعیه (ارتباط نداشتن با فروشگاه‌های دیگر) می‌ماند
  و وعدهٔ «ارسال رایگان» بی‌شرط اصلاح می‌شود.
نشانی‌ها عوض نمی‌شود.
"""
import re

from django.db import migrations
from django.utils import timezone

COMPETITOR = re.compile(r"شهر\s*فرش|آقای\s*فرش|مهد\s*فرش|وزرا")


def _plain(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def city_of(title, slug):
    m = re.match(r"^\s*خرید\s+فرش\s+در\s+(.+?)(?:\s*[|⭐☀️🌎+\-–:؛،!]|$)", title or "")
    return m.group(1).strip() if m else slug.replace("خرید-فرش-در-", "").replace("-", " ").strip()


def heading_fix(content, city):
    def fix(m):
        inner = _plain(m.group(2))
        if re.match(r"^شهر\s*فرش\b", inner):
            return f"<{m.group(1)}>تنوع فرش برای خریداران {city}</{m.group(1)}>"
        return m.group(0)
    return re.sub(r"<(h[2-6])\b[^>]*>(.*?)</\1>", fix, content or "", flags=re.S | re.I)


def clean_desc(d):
    d = re.sub(r"\s*🌎?\s*شهر\s*فرش\s+[^\s|،.]+\s*$", "", d or "")
    d = re.sub(r"فروشگاه\s+شهر\s+فرش(\s+ماشینی)?", "فروش فرش ماشینی", d)
    return d.strip()


def forward(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Page = apps.get_model("blog", "Page")
    now = timezone.now()
    for post in Post.objects.filter(slug__startswith="خرید-فرش-در-").exclude(slug__contains="-old-"):
        city = city_of(post.title, post.slug)
        fields = {}
        if COMPETITOR.search(post.title or ""):
            fields["title"] = f"خرید فرش در {city}؛ فرش ماشینی کاشان با ارسال به {city}"[:300]
        if COMPETITOR.search(post.seo_title or ""):
            fields["seo_title"] = ""
        if COMPETITOR.search(post.seo_description or ""):
            fields["seo_description"] = clean_desc(post.seo_description)
        new = heading_fix(post.content, city)
        if new != post.content:
            fields["content"] = new
        if fields:
            fields["modified_at"] = now
            Post.objects.filter(pk=post.pk).update(**fields)

    page = Page.objects.filter(slug="vozaracarpet").first()
    if page:
        content = re.sub(r"دارای\s+ضمانت\s+و\s+ارسال\s+رایگان\s+می\s*باشد", "دارای ضمانت است و به سراسر ایران ارسال می‌شود",
                         page.content or "")
        Page.objects.filter(pk=page.pk).update(
            content=content,
            seo_title="ایران کارپت شعبه و نمایندگی ندارد؛ پیش از تماس بخوانید",
            seo_description="ایران کارپت فروشگاه اینترنتی فرش ماشینی کاشان است، در هیچ شهری شعبه ندارد و با فروشگاه‌های دیگر "
                            "ارتباطی ندارد؛ خرید آنلاین با ارسال مستقیم از کاشان.",
            focus_keyword="",
            modified_at=now,
        )


class Migration(migrations.Migration):
    dependencies = [("blog", "0008_density_post")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
