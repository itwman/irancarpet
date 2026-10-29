"""ایران کارپت: برگهٔ «تاریخچهٔ ایران کارپت» با پیوند به نسخه‌های آرشیو اینترنت (سابقهٔ مستند به‌جای ادعای بی‌سند).

روی فرشستان (SITE_THEME=farshestan) کاری نمی‌کند. اگر برگه‌ای با همین نامک باشد، دست نمی‌خورد.
"""
from django.conf import settings
from django.db import migrations
from django.utils import timezone

SLUG = "تاریخچه-ایران-کارپت"
TITLE = "تاریخچهٔ ایران کارپت"
A1389 = "https://web.archive.org/web/20100505144341/http://irancarpet.org/"
A1391 = "https://web.archive.org/web/20130303125850/http://shop.irancarpet.org/"
A1392 = "https://web.archive.org/web/20130605054421/http://irancarpet.net/"

CONTENT = f"""<p>ایران کارپت فروشگاه اینترنتی فرش ماشینی کاشان است. این صفحه سابقهٔ برند را فقط با تاریخ‌هایی می‌گوید که سند دارند؛
کنار هر تاریخ پیوند نسخهٔ بایگانی‌شدهٔ همان روز در <a href="https://web.archive.org/" rel="nofollow noopener" target="_blank">آرشیو اینترنت (Wayback Machine)</a> آمده تا خودتان بررسی کنید.</p>

<h2>خلاصه</h2>
<ul>
<li>فعالیت آنلاین برند: از اردیبهشت ۱۳۸۹</li>
<li>فروشگاه اینترنتی و پروانهٔ کسب: از ۱۳۹۱</li>
<li>دامنهٔ irancarpet.net: از ۱۳۹۲</li>
<li>نماد اعتماد الکترونیکی irancarpet.net: از ۱۳۹۸</li>
</ul>

<h2>۱۳۸۹: شروع با irancarpet.org</h2>
<p>ایران کارپت کارش را در اینترنت با سایت irancarpet.org شروع کرد. نخستین نسخه، سایتی برای معرفی فرش‌های ماشینی کاشان بود و هنوز فروش اینترنتی نداشت.
قدیمی‌ترین نسخهٔ بایگانی‌شدهٔ آن مال اردیبهشت ۱۳۸۹ است.</p>
<p><a href="{A1389}" rel="nofollow noopener" target="_blank">نسخهٔ اردیبهشت ۱۳۸۹ irancarpet.org در آرشیو اینترنت</a></p>

<h2>۱۳۹۱: افتتاح فروشگاه اینترنتی</h2>
<p>در اسفند ۱۳۹۱ فروشگاه اینترنتی ایران کارپت روی shop.irancarpet.org باز شد؛ بنر «افتتاح فروشگاه» در همان نسخهٔ بایگانی‌شده دیده می‌شود.
از این تاریخ مشتری‌ها می‌توانستند فرش را در سایت ببینند، قیمت هر سایز را بدانند و سفارش بدهند. پروانهٔ کسب فروشگاه هم از ۱۳۹۱ است.</p>
<p><a href="{A1391}" rel="nofollow noopener" target="_blank">نسخهٔ اسفند ۱۳۹۱ shop.irancarpet.org (افتتاح فروشگاه) در آرشیو اینترنت</a></p>

<h2>۱۳۹۲: انتقال به irancarpet.net</h2>
<p>از خرداد ۱۳۹۲ سایت و فروشگاه روی نشانی تازهٔ irancarpet.net کار می‌کند؛ همان نشانی‌ای که امروز هم سایت اصلی ایران کارپت است.</p>
<p><a href="{A1392}" rel="nofollow noopener" target="_blank">نسخهٔ خرداد ۱۳۹۲ irancarpet.net در آرشیو اینترنت</a></p>

<h2>۱۳۹۸: نماد اعتماد الکترونیکی</h2>
<p>نماد اعتماد الکترونیکی irancarpet.net در تاریخ ۱۳۹۸/۰۸/۱۱ اعطا شد. نماد و مجوزهای فروشگاه در <a href="/license/">صفحهٔ مجوزها</a> آمده است.</p>

<h2>امروز</h2>
<p>ایران کارپت فرش ماشینی را مستقیم از کارخانه‌های کاشان، با قیمت روشن برای هر سایز، به‌صورت نقدی و اقساطی می‌فروشد و به سراسر ایران می‌فرستد.
فروشگاه حضوری ایران کارپت در کاشان، میدان زجاجی، بلوار شهید پکوک است.</p>
<ul>
<li><a href="/store/">دیدن فرش‌ها</a></li>
<li><a href="/carpets-price-list/">لیست قیمت روز</a></li>
<li><a href="/license/">مجوزها و نماد اعتماد</a></li>
</ul>
"""


def forward(apps, schema_editor):
    if settings.SITE_THEME == "farshestan":
        return
    Page = apps.get_model("blog", "Page")
    if Page.objects.filter(parent=None, slug=SLUG).exists():
        return
    now = timezone.now()
    Page.objects.create(title=TITLE, slug=SLUG, content=CONTENT, status="publish", template="history", menu_order=90,
                        published_at=now, modified_at=now, seo_title="تاریخچهٔ ایران کارپت؛ از ۱۳۸۹ تا امروز",
                        seo_description="سابقهٔ مستند ایران کارپت: فعالیت آنلاین از ۱۳۸۹ با irancarpet.org، افتتاح فروشگاه اینترنتی در ۱۳۹۱، "
                                        "irancarpet.net از ۱۳۹۲ و نماد اعتماد از ۱۳۹۸؛ با پیوند به آرشیو اینترنت.")


class Migration(migrations.Migration):
    dependencies = [("blog", "0015_post_rec_source")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
