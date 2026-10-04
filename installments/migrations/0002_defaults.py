"""دو روش اقساط پیش‌فرض + برگه‌های «لیست قیمت» و «خرید اقساطی» (همه از پنل قابل ویرایش)."""
from decimal import Decimal

from django.db import migrations

CHEQUE_DESC = """<p>با پرداخت دست‌کم نیمی از مبلغ سبد به‌صورت آنلاین، بقیه را تا ۱۲ ماه با چک صیادی بپردازید؛ چک‌ها ماهانه یا دوماه‌یک‌بار.</p>
<ul>
<li>اول تصویر یک برگ از دسته‌چک خودتان را همراه مشخصات می‌فرستید؛ <strong>تا تأیید ما چک ننویسید</strong>.</li>
<li>بعد از تأیید، چک‌ها را با همان مبلغ و تاریخ جدول اقساط می‌نویسید، در سامانهٔ صیاد ثبت می‌کنید و برای ما پست می‌کنید.</li>
<li>تاریخ اولین چک یک دوره بعد از آماده‌شدن فرش (حدود دو هفته پس از سفارش) است.</li>
</ul>"""

BETA_DESC = """<p>ویژهٔ بازنشستگان و مستمری‌بگیرانی که حقوقشان را از بانک رفاه می‌گیرند؛ خرید از راه سامانهٔ «بتا» و کسر قسط از حقوق.</p>
<ul>
<li>پیش‌پرداخت دلخواه است (حتی صفر)؛ هرچه پیش‌پرداخت بیشتر باشد، قسط کمتر می‌شود.</li>
<li>مدت اقساط از ۲ تا ۲۴ ماه، به انتخاب خودتان.</li>
<li>مشخصات بازنشسته یا مستمری‌بگیر، کد ملی و شماره‌ای که پیامک بانک به آن می‌رود را وارد کنید؛ ما خرید را در سامانهٔ بتا ثبت می‌کنیم و شما پیامک تأیید بانک را تأیید می‌کنید.</li>
</ul>"""

PRICE_PAGE = """<p>قیمت روز فرش ماشینی کاشان را اینجا ببینید؛ همهٔ قیمت‌ها مستقیم از قیمت‌گذاری فروشگاه خوانده می‌شوند و با هر تغییر قیمت کارخانه به‌روز می‌شوند. روی هر لیست بزنید تا قیمت همهٔ سایزها و فرش‌های همان لیست را ببینید.</p>
[icap_price_list]
<h2>قیمت فرش ماشینی به چه چیزهایی بستگی دارد؟</h2>
<p>تراکم بافت (تعداد شانه و تراکم)، جنس نخ (اکریلیک، ابریشم مصنوعی، پلی‌استر)، برند کارخانه و سایز فرش مهم‌ترین عوامل قیمت‌اند. قیمت سایزهای مختلف یک لیست به نسبت متراژ از قیمت ۱۲ متری محاسبه می‌شود.</p>"""

INSTALLMENT_PAGE = """<p>فرش ماشینی دلخواهتان را الان بخرید و هزینه‌اش را در چند قسط بپردازید. پیش از ثبت سفارش، جدول کامل اقساط با مبلغ و تاریخ هر قسط را می‌بینید.</p>
[installment_plans]
<h2>سود اقساط چطور حساب می‌شود؟</h2>
<p>سود با <strong>راس‌گیری</strong> محاسبه می‌شود: میانگین فاصلهٔ سررسید قسط‌ها (به روز) تقسیم بر ۳۰، ضرب در درصد سود ماهانه. مثلاً اگر مانده را در دو قسط ماهانه بدهید، راس اقساط ۴۵ روز است و با سود ماهی ۶٪، سود کل ۹٪ می‌شود. هرچه پیش‌پرداخت بیشتر و مدت کوتاه‌تر باشد، سود کمتری می‌پردازید.</p>"""


def forwards(apps, schema_editor):
    Plan = apps.get_model("installments", "InstallmentPlan")
    if not Plan.objects.exists():
        Plan.objects.create(
            title="اقساط با چک صیادی", kind="cheque", sort_order=1,
            summary="۵۰٪ پیش‌پرداخت آنلاین، بقیه تا ۱۲ ماه با چک صیادی",
            monthly_rate=Decimal("6"), min_down_percent=50, max_down_percent=90, down_step=5,
            min_months=1, max_months=12, allow_monthly=True, allow_bimonthly=True, first_due_days=14,
            round_to=100_000, down_timing="checkout",
            ask_holder_name=True, ask_national_code=True, ask_cheque_image=True,
            description=CHEQUE_DESC,
            submit_note="از یک برگ سفید دسته‌چکتان عکس واضح بگیرید (مبلغ و تاریخ را ننویسید). چک باید صیادی و به نام خودتان باشد.",
            review_note="مدارک شما رسید و در حال بررسی است. تا تأیید ما چک ننویسید؛ نتیجه را با پیامک خبر می‌دهیم.",
            approved_note="درخواست اقساط شما تأیید شد. چک‌ها را دقیقاً با مبلغ و تاریخ جدول زیر بنویسید، در سامانهٔ صیاد ثبت کنید و برای ما پست کنید.",
            approved_sms="{name} عزیز، درخواست اقساط سفارش {order} در ایران کارپت تأیید شد. جدول چک‌ها: {link}",
            rejected_sms="{name} عزیز، متأسفانه درخواست اقساط سفارش {order} در ایران کارپت تأیید نشد. برای راهنمایی با ما تماس بگیرید.",
        )
        Plan.objects.create(
            title="اقساط بازنشستگان (سامانهٔ بتا بانک رفاه)", kind="beta", sort_order=2,
            summary="بدون پیش‌پرداخت یا با پیش‌پرداخت دلخواه، ۲ تا ۲۴ ماه",
            monthly_rate=Decimal("7"), min_down_percent=0, max_down_percent=90, down_step=5,
            min_months=2, max_months=24, allow_monthly=True, allow_bimonthly=False, first_due_days=14,
            round_to=100_000, down_timing="checkout",
            ask_holder_name=True, ask_national_code=True, ask_pensioner_type=True, ask_sms_mobile=True,
            description=BETA_DESC,
            submit_note="مشخصات باید با اطلاعات حقوق‌بگیری در بانک رفاه یکی باشد. پیامک تأیید خرید از طرف بانک به همین شماره می‌آید.",
            review_note="درخواست شما رسید. خرید را در سامانهٔ بتا ثبت می‌کنیم؛ منتظر پیامک بانک رفاه باشید و آن را تأیید کنید.",
            approved_note="خرید اقساطی شما در سامانهٔ بتا تأیید شد. اقساط طبق جدول زیر از حقوق کسر می‌شود.",
            approved_sms="{name} عزیز، خرید اقساطی سفارش {order} در ایران کارپت تأیید شد. {link}",
            rejected_sms="{name} عزیز، خرید اقساطی سفارش {order} در سامانهٔ بتا تأیید نشد. برای راهنمایی با ما تماس بگیرید.",
        )

    Page = apps.get_model("blog", "Page")
    price = Page.objects.filter(slug="carpets-price-list", parent=None).first()
    if price:
        price.template = "price_list"
        if not (price.content or "").strip() or price.content.strip() == "[icap_price_list]":
            price.content = PRICE_PAGE
        if "[" in (price.seo_description or ""):
            price.seo_description = ""
        price.save()
    else:
        Page.objects.create(title="لیست قیمت فرش ماشینی", slug="carpets-price-list", template="price_list", content=PRICE_PAGE)
    if not Page.objects.filter(template="installment").exists():
        Page.objects.create(title="خرید اقساطی فرش ماشینی", slug="خرید-اقساطی-فرش", template="installment",
                            content=INSTALLMENT_PAGE,
                            seo_description="خرید اقساطی فرش ماشینی کاشان با چک صیادی یا ویژهٔ بازنشستگان (سامانهٔ بتا بانک رفاه)؛ "
                                            "محاسبهٔ آنلاین اقساط و تاریخ چک‌ها پیش از خرید.")


class Migration(migrations.Migration):
    dependencies = [("installments", "0001_initial"), ("blog", "0002_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
