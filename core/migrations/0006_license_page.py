"""برگهٔ «مجوزها» (/license/) و جابه‌جایی کد اینماد از فوتر به همان برگه.

کد نماد اعتماد کند بار می‌شود؛ پس در فوتر فقط تصویر سبک و لینک می‌ماند و کد اصلی
فقط در /license/ اجرا می‌شود.
"""
import re

from django.db import migrations

LICENSE_PAGE = """<p>ایران کارپت فروشگاه اینترنتی رسمی است و نماد اعتماد الکترونیکی دارد. برای دیدن اعتبار نماد، روی آن بزنید تا صفحهٔ رسمی اینماد باز شود.</p>
[trust_seals]
<h2>چرا با خیال راحت خرید کنید</h2>
<ul>
<li>پرداخت فقط از درگاه رسمی بانکی انجام می‌شود.</li>
<li>فرش‌ها مستقیم از کارخانه‌های کاشان ارسال می‌شوند.</li>
<li>پیش از خرید می‌توانید با کارشناس فروش گفتگو کنید.</li>
</ul>"""

ENAMAD = re.compile(r"<a[^>]*enamad\.ir.*?</a>", re.I | re.S)


def forwards(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    s = SiteSettings.objects.filter(pk=1).first()
    if s and s.footer_html and "enamad" in s.footer_html.lower():
        found = ENAMAD.findall(s.footer_html)
        if found:
            if not s.trust_html:
                s.trust_html = "\n".join(found)
            s.footer_html = ENAMAD.sub("", s.footer_html).strip()
            s.save(update_fields=["trust_html", "footer_html"])

    Page = apps.get_model("blog", "Page")
    page = Page.objects.filter(slug="license", parent=None).first()
    if page:
        page.template = "license"
        if "[trust_seals]" not in (page.content or ""):
            page.content = (page.content or "").rstrip() + "\n[trust_seals]"
        page.save(update_fields=["template", "content"])
    elif not Page.objects.filter(template="license").exists():
        Page.objects.create(title="مجوزها و نماد اعتماد", slug="license", template="license", content=LICENSE_PAGE,
                            status="publish",
                            seo_description="مجوزها و نماد اعتماد الکترونیکی (اینماد) فروشگاه اینترنتی فرش ایران کارپت.")


class Migration(migrations.Migration):
    dependencies = [("core", "0005_trust_badge"), ("blog", "0002_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
