"""اطلاع‌رسانی پیامکی سفارش (اختیاری؛ فقط اگر شمارهٔ قالب در .env باشد)."""
from accounts.sms import send_template

from . import config
from .models import ShopSettings


def order_paid(order, amount):
    if order.coupon_code:
        from .coupons import reward_referrer

        reward_referrer(order)
    if config.get('SMSIR_ORDER_TEMPLATE_ID'):
        send_template(order.mobile, config.get('SMSIR_ORDER_TEMPLATE_ID'), {"ORDER": order.number, "AMOUNT": f"{amount:,}"})
    if config.get('SMSIR_ADMIN_TEMPLATE_ID'):
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, config.get('SMSIR_ADMIN_TEMPLATE_ID'), {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{amount:,}"})


def installment_request(order):
    """درخواست اقساط بدون پرداخت آنلاین → خبر به مدیران."""
    if config.get('SMSIR_ADMIN_TEMPLATE_ID'):
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, config.get('SMSIR_ADMIN_TEMPLATE_ID'),
                              {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{order.items_total:,} (اقساطی)"})


def admin_text(text):
    """پیامک متنی ساده به مدیران (نیاز به شمارهٔ خط پیامک)."""
    from accounts.sms import send_bulk

    mobiles = [m.strip() for m in (ShopSettings.load().admin_mobiles or "").split(",") if m.strip()]
    if mobiles:
        send_bulk(mobiles, text)
