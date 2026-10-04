"""اطلاع‌رسانی پیامکی سفارش (اختیاری؛ فقط اگر شمارهٔ قالب در .env باشد)."""
from django.conf import settings

from accounts.sms import send_template

from .models import ShopSettings


def order_paid(order, amount):
    if settings.SMSIR_ORDER_TEMPLATE_ID:
        send_template(order.mobile, settings.SMSIR_ORDER_TEMPLATE_ID, {"ORDER": order.number, "AMOUNT": f"{amount:,}"})
    if settings.SMSIR_ADMIN_TEMPLATE_ID:
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, settings.SMSIR_ADMIN_TEMPLATE_ID, {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{amount:,}"})
