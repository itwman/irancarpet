"""تنظیمات درگاه و پیامک: اول از پنل مدیریت (دیتابیس)، اگر خالی بود از فایل .env"""
from django.conf import settings

MAP = {
    "SEP_TERMINAL_ID": "sep_terminal_id",
    "ZARINPAL_MERCHANT_ID": "zarinpal_merchant_id",
    "SMSIR_API_KEY": "smsir_api_key",
    "SMSIR_OTP_TEMPLATE_ID": "smsir_otp_template_id",
    "SMSIR_ORDER_TEMPLATE_ID": "smsir_order_template_id",
    "SMSIR_ADMIN_TEMPLATE_ID": "smsir_admin_template_id",
    "SMSIR_LINE_NUMBER": "smsir_line_number",
}


def get(name):
    from .models import ShopSettings

    field = MAP.get(name)
    if field:
        val = (getattr(ShopSettings.load(), field, "") or "").strip()
        if val:
            return val
    return getattr(settings, name, "")


def zarinpal_sandbox():
    from .models import ShopSettings

    return ShopSettings.load().zarinpal_sandbox or settings.ZARINPAL_SANDBOX
