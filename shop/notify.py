"""اطلاع‌رسانی پیامکی سفارش (اختیاری؛ فقط اگر شمارهٔ قالب در .env باشد)."""
from accounts.sms import send_template

from . import config
from .models import ShopSettings


def order_paid(order, amount):
    if config.get('SMSIR_ORDER_TEMPLATE_ID'):
        send_template(order.mobile, config.get('SMSIR_ORDER_TEMPLATE_ID'), {"ORDER": order.number, "AMOUNT": f"{amount:,}"})
    if config.get('SMSIR_ADMIN_TEMPLATE_ID'):
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, config.get('SMSIR_ADMIN_TEMPLATE_ID'), {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{amount:,}"})
