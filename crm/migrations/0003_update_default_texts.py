"""متن‌های پیش‌فرض قبلی که دست نخورده‌اند به متن تازه (بیعانه/پیش‌پرداخت، امتیاز) به‌روز می‌شوند."""
from django.db import migrations

PAIRS = {'order_text': ('{name} عزیز، سفارش {number} در ایران کارپت ثبت شد. مبلغ: {total} تومان.\nاگر پرداخت ناتمام ماند، از این پیوند کامل کنید: {pay_link}\nپیگیری: {link}', '{name} عزیز، سفارش {number} در ایران کارپت ثبت شد. {due_line}.\nاگر پرداخت ناتمام ماند: {pay_link}'), 'paid_text': ('{name} عزیز، پرداخت {paid} تومانی سفارش {number} انجام شد و سفارش شما در صف آماده\u200cسازی است.\nپیگیری: {link}', '{name} عزیز، پرداخت {paid} تومانی سفارش {number} انجام شد و سفارش شما در صف آماده\u200cسازی است.{points_line}\nپیگیری: {link}'), 'remind_text_1': ('{name} عزیز، سفارش {number} شما در ایران کارپت ثبت شده ولی هنوز پرداخت نشده. فرش\u200cهای انتخابی\u200cتان را برایتان نگه داشته\u200cایم. پرداخت: {pay_link}', '{name} عزیز، سفارش {number} شما هنوز پرداخت نشده و فرش\u200cهایتان را برایتان نگه داشته\u200cایم. {due_line}. پرداخت: {pay_link}'), 'remind_text_2': ('{name} عزیز، به\u200cدلیل نوسان قیمت مواد اولیه، قیمت فرش\u200cها ممکن است به\u200cزودی تغییر کند. سفارش {number} هنوز با قیمت ثبت\u200cشده برایتان نگه داشته شده؛ برای تکمیل، پرداخت را انجام دهید. پرداخت: {pay_link}', '{name} عزیز، به\u200cدلیل نوسان قیمت\u200cها، قیمت فرش\u200cها ممکن است به\u200cزودی تغییر کند. سفارش {number} هنوز با قیمت ثبت\u200cشده برایتان نگه داشته شده؛ برای تکمیل سفارش، {due} را پرداخت کنید. پرداخت: {pay_link}'), 'remind_text_3': ('{name} عزیز، امروز آخرین فرصت پرداخت سفارش {number} با قیمت ثبت\u200cشده است. پرداخت: {pay_link}', '{name} عزیز، امروز آخرین فرصت پرداخت سفارش {number} با قیمت ثبت\u200cشده است. {due_line}. پرداخت: {pay_link}')}


def forward(apps, schema_editor):
    S = apps.get_model("crm", "CrmSettings")
    for s in S.objects.all():
        changed = []
        for field, (old, new) in PAIRS.items():
            if getattr(s, field) == old:
                setattr(s, field, new)
                changed.append(field)
        if changed:
            s.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [("crm", '0002_shortlink_campaign_album_campaign_event_date_and_more')]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
