"""اطلاع‌رسانی پیامکی سفارش.

اگر شمارهٔ قالب sms.ir تنظیم شده باشد همان قالب فرستاده می‌شود؛ وگرنه پیامک متنی از خط اختصاصی با متن‌های
«تنظیمات ← پیامک سفارش و باشگاه» (crm.notify).
"""
from accounts.sms import send_template

from . import config
from .models import ShopSettings


def order_paid(order, amount):
    if order.coupon_code:
        from .coupons import reward_referrer

        reward_referrer(order)
    tpl_customer, tpl_admin = config.get('SMSIR_ORDER_TEMPLATE_ID'), config.get('SMSIR_ADMIN_TEMPLATE_ID')
    if not (tpl_customer and tpl_admin):
        try:
            from crm.notify import order_paid as crm_paid

            crm_paid(order, amount, customer=not tpl_customer, admin=not tpl_admin)
        except Exception:  # noqa: BLE001
            pass
    if config.get('SMSIR_ORDER_TEMPLATE_ID'):
        send_template(order.mobile, config.get('SMSIR_ORDER_TEMPLATE_ID'), {"ORDER": order.number, "AMOUNT": f"{amount:,}"},
                      kind="paid", order=order)
    if config.get('SMSIR_ADMIN_TEMPLATE_ID'):
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, config.get('SMSIR_ADMIN_TEMPLATE_ID'), {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{amount:,}"},
                              kind="admin", order=order)


def installment_request(order):
    """درخواست اقساط بدون پرداخت آنلاین → خبر به مدیران (اگر پیامک متنی مدیر روشن است، همان کافی است)."""
    from crm.models import CrmSettings

    if CrmSettings.load().admin_sms:
        return
    if config.get('SMSIR_ADMIN_TEMPLATE_ID'):
        for m in (ShopSettings.load().admin_mobiles or "").split(","):
            m = m.strip()
            if m:
                send_template(m, config.get('SMSIR_ADMIN_TEMPLATE_ID'),
                              {"ORDER": order.number, "NAME": order.full_name[:25], "AMOUNT": f"{order.items_total:,} (اقساطی)"},
                              kind="admin", order=order)


def admin_text(text):
    """پیامک متنی ساده به مدیران (نیاز به شمارهٔ خط پیامک)."""
    from accounts.sms import send_bulk

    mobiles = [m.strip() for m in (ShopSettings.load().admin_mobiles or "").split(",") if m.strip()]
    if mobiles:
        send_bulk(mobiles, text, kind="admin")
