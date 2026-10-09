"""برگهٔ «تماس با ما» (/contact-us/): متن دورهٔ وردپرس (نام قدیمی «بازار فرش ایران»، رنگ‌های دستی، ایمیل شخصی) جای خود را به
بلوک‌های زندهٔ [contact_info] (شماره‌ها، پیام‌رسان‌ها، نشانی، ساعت کاری و نقشه از تنظیمات سایت) و [contact_form] می‌دهد.
اگر نشانی فروشگاه در تنظیمات خالی است، نشانی همان برگهٔ قدیمی آنجا ثبت می‌شود. فقط اگر متن فعلی هنوز همان متن قدیمی باشد عوض می‌شود.
"""
from django.db import migrations

OLD_MARKS = ("بازار فرش ایران", "nazeri.it@gmail.com")
ADDRESS = "کاشان، خیابان طالقانی، خیابان آزادگان، خیابان پکوک، نبش فرعی ۴"

TITLE = "تماس با ایران کارپت"
SEO_TITLE = "تماس با ایران کارپت؛ تلفن، واتساپ، نشانی فروشگاه کاشان و فرم پیام"
SEO_DESC = ("شماره‌های تماس و واتساپ ایران کارپت، نشانی و ساعت کاری فروشگاه کاشان، و فرم پیام؛ پاسخ پیام‌ها با پیامک به موبایل شما "
            "فرستاده می‌شود.")
CONTENT = """<p>برای مشاورهٔ خرید، پیگیری سفارش یا خرید اقساطی، تلفنی یا در واتساپ با کارشناس فروش صحبت کنید، به فروشگاه ما در کاشان سر بزنید، یا پایین همین صفحه پیام بگذارید.</p>
<p>[contact_info]</p>
<p>[contact_form]</p>
<h2>شاید جوابتان اینجا باشد</h2>
<ul>
<li><strong>قیمت امروز فرش‌ها:</strong> <a href="/carpets-price-list/">لیست قیمت همهٔ سایزها و شانه‌ها</a></li>
<li><strong>وضعیت سفارش و کد رهگیری:</strong> بعد از ورود به حساب کاربری، در «سفارش‌های من»</li>
<li><strong>شرایط اقساط و مدارک:</strong> <a href="/خرید-اقساطی-فرش/">خرید اقساطی فرش</a></li>
<li><strong>هزینه و زمان ارسال:</strong> <a href="/free-delivery/">ارسال فرش به سراسر ایران</a> و <a href="/prepayment/">پرداخت بیعانه</a></li>
<li><strong>پرسش‌های دیگر:</strong> <a href="/faq/">پرسش‌های متداول</a> و <a href="/rules/">قوانین و مقررات</a></li>
</ul>"""


def forward(apps, schema_editor):
    S = apps.get_model("core", "SiteSettings")
    s = S.objects.filter(pk=1).first()
    if s and not (s.address or "").strip():
        S.objects.filter(pk=1).update(address=ADDRESS, store_city=s.store_city or "کاشان")
    for model in ("Page", "Post"):
        M = apps.get_model("blog", model)
        for obj in M.objects.filter(slug="contact-us"):
            if any(m in (obj.content or "") for m in OLD_MARKS):
                M.objects.filter(pk=obj.pk).update(title=TITLE, seo_title=SEO_TITLE, seo_description=SEO_DESC, content=CONTENT)


class Migration(migrations.Migration):
    dependencies = [("blog", "0013_about_us_page"), ("core", "0015_alter_sitesettings_trust_points")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
