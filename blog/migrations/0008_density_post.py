"""«تراکم فرش ماشینی چیست؟» (۳۹۰۰ نمایش، ۱.۳٪ کلیک): جدول زندهٔ تراکم و قیمت هر شانه زیر «تراکم‌های موجود در بازار»،
و رفع جملهٔ اشتباهِ پایانی («در این مقاله سعی کردیم به قیمت فرش ۶ متری بپردازیم»)."""
import re

from django.db import migrations
from django.utils import timezone

SLUG = "تراکم-فرش-ماشینی-چیست؟"
H = re.compile(r"<(h[2-6])\b[^>]*>(.*?)</\1>", re.I | re.S)


def transform(c):
    c = re.sub(r"به\s+قیمت\s+فرش\s+(?:6|۶)\s+متری\s+بپردازیم", "به تراکم و شانهٔ فرش ماشینی بپردازیم", c or "")
    if "[reeds_compare" in c:
        return c
    for h in H.finditer(c):
        if "تراکم های موجود" in re.sub(r"<[^>]+>", "", h.group(2)).replace("‌", " "):
            return c[:h.end()] + "\n<p>تراکم رایج و قیمت امروز هر شانه در فرش‌های ایران کارپت:</p>\n[reeds_compare 700 1000 1200 1500]\n" + c[h.end():]
    return c


def forward(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    post = Post.objects.filter(slug=SLUG).first()
    if post is None:
        return
    new = transform(post.content)
    fields = {}
    if new != post.content:
        fields["content"] = new
    d = post.seo_description or ""
    if not d.strip() or len(d) < 70:
        fields["seo_description"] = ("تراکم فرش ماشینی یعنی چه و چه فرقی با شانه دارد؟ تراکم رایج فرش ۷۰۰، ۱۰۰۰، ۱۲۰۰ و ۱۵۰۰ شانه، "
                                     "اثر تراکم بر زیبایی، دوام و قیمت، و راه فهمیدن تراکم از پشت فرش.")
    if not (post.seo_title or "").strip() or "تراکم فرش به چه معناست" in (post.seo_title or ""):
        fields["seo_title"] = "تراکم فرش ماشینی چیست؟ فرق تراکم و شانه + جدول تراکم هر شانه"
    if fields:
        fields["modified_at"] = timezone.now()
        Post.objects.filter(pk=post.pk).update(**fields)


class Migration(migrations.Migration):
    dependencies = [("blog", "0007_top_pages")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
