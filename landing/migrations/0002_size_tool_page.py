from django.db import migrations

CONTENT = """<p>طول و عرض اتاق را بدهید تا ببینید چه سایز فرشی، یک تخته یا جفت، برای آن مناسب است و فرش‌های همان سایز چند است.</p>
[size_tool]
<h2>قاعدهٔ انتخاب سایز فرش</h2>
<ul>
<li>بین لبهٔ فرش و دیوار ۳۰ تا ۶۰ سانتی‌متر فاصله بگذارید.</li>
<li>برای پذیرایی‌های بزرگ، دو فرش هم‌اندازه کنار هم (جفت) رایج‌ترین انتخاب است.</li>
<li>اگر مبلمان روی فرش می‌آید، دست‌کم پایه‌های جلویی مبل روی فرش باشد.</li>
</ul>"""


def forwards(apps, schema_editor):
    Page = apps.get_model("blog", "Page")
    if not Page.objects.filter(template="size_tool").exists():
        Page.objects.create(title="چه سایز فرشی برای اتاق من مناسب است؟", slug="محاسبه-سایز-فرش", template="size_tool",
                            content=CONTENT, seo_description="ابزار رایگان انتخاب سایز فرش: ابعاد اتاق را بدهید تا سایز مناسب فرش، "
                                                             "تک یا جفت، و قیمت فرش‌های همان سایز را ببینید.")


class Migration(migrations.Migration):
    dependencies = [("landing", "0001_initial"), ("blog", "0002_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
