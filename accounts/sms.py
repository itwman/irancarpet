"""ارسال پیامک با sms.ir (وب‌سرویس نسخهٔ ۱، ارسال قالبی/تأییدی)."""
import json
import logging
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
API = "https://api.sms.ir/v1/send/verify"


def configured():
    return bool(settings.SMSIR_API_KEY and settings.SMSIR_OTP_TEMPLATE_ID)


def send_template(mobile, template_id, params):
    """params: dict نام متغیر ← مقدار. خروجی: True اگر sms.ir پذیرفت."""
    if not settings.SMSIR_API_KEY or not template_id:
        return False
    body = json.dumps({
        "mobile": mobile, "templateId": int(template_id),
        "parameters": [{"name": k, "value": str(v)} for k, v in params.items()],
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "text/plain", "X-API-KEY": settings.SMSIR_API_KEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode() or "{}")
        if data.get("status") == 1:
            return True
        log.warning("sms.ir رد کرد: %s", data)
    except Exception as e:  # noqa: BLE001
        log.warning("sms.ir خطا: %s", e)
    return False


def send_otp(mobile, code):
    return send_template(mobile, settings.SMSIR_OTP_TEMPLATE_ID, {"CODE": code})
