"""ایران کارپت: بخش «ایران کارپت در منابع دیگر» و پیوند استعلام اینماد در برگهٔ تاریخچه.

فقط منبع مستقل (نه رپورتاژ آگهی). روی فرشستان کاری نمی‌کند؛ اگر بخش از قبل باشد دوباره افزوده نمی‌شود.
"""
from django.conf import settings
from django.db import migrations
from django.utils import timezone

SLUG = "تاریخچه-ایران-کارپت"
HOWTOBUY = ("https://how-to-buy.ir/mag/%D8%A8%D9%87%D8%AA%D8%B1%DB%8C%D9%86-%D9%87%D8%A7%DB%8C-%D8%B5%D9%86%D8%B9%D8%AA-"
            "%D8%A7%DB%8C%D8%B1%D8%A7%D9%86-%D8%A8%D9%87-%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8-%D9%85%D8%B4%D8%AA%D8%B1%DB%8C%D8%A7/")
SANAT = "https://www.sanat.ir/41580"
ENAMAD = "https://trustseal.enamad.ir/?id=137774&code=70XzemtCwKljQtiHa3iOa2RuzITHgk7G"

SOURCES = f"""<h2>ایران کارپت در منابع دیگر</h2>
<p>در فهرست «بهترین‌های صنعت ایران به انتخاب مشتریان» سایت صنعت (sanat.ir) در بهمن ۱۴۰۳، «فروشگاه ایران کارپت؛ خرید مستقیم فرش آنلاین از کارخانه فرش کاشان»
رتبهٔ ۵ را گرفت. این فهرست بر پایهٔ پیشنهاد مشتریان در سایت صنعت ساخته می‌شود و همهٔ رشته‌های صنعت را با هم می‌سنجد.</p>
<ul>
<li><a href="{HOWTOBUY}" rel="noopener" target="_blank">بهترین‌های صنعت ایران به انتخاب مشتریان در بهمن ۱۴۰۳ (مجلهٔ هاو تو بای)</a></li>
<li><a href="{SANAT}" rel="noopener" target="_blank">صفحهٔ ایران کارپت در سایت صنعت</a></li>
</ul>

"""
ENAMAD_OLD = "نماد و مجوزهای فروشگاه در <a href=\"/license/\">صفحهٔ مجوزها</a> آمده است.</p>"
ENAMAD_NEW = (f"نماد و مجوزهای فروشگاه در <a href=\"/license/\">صفحهٔ مجوزها</a> آمده است. "
              f"اعتبار نماد را مستقیم در <a href=\"{ENAMAD}\" rel=\"noopener\" target=\"_blank\">سایت اینماد</a> هم می‌توانید بررسی کنید.</p>")


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    Page = apps.get_model("blog", "Page")
    p = Page.objects.filter(parent=None, slug=SLUG).first()
    if p is None:
        return
    c = p.content or ""
    if "sanat.ir" not in c:
        c = c.replace("<h2>امروز</h2>", SOURCES + "<h2>امروز</h2>", 1) if "<h2>امروز</h2>" in c else c + "\n" + SOURCES
    if "trustseal.enamad.ir" not in c:
        c = c.replace(ENAMAD_OLD, ENAMAD_NEW, 1)
    if c != p.content:
        p.content = c
        p.modified_at = timezone.now()
        p.save(update_fields=["content", "modified_at"])


class Migration(migrations.Migration):
    dependencies = [("blog", "0016_history_page")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
