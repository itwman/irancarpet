"""ارسال پیامک با sms.ir (وب‌سرویس نسخهٔ ۱، ارسال قالبی/تأییدی)."""
import json
import logging
import urllib.request


log = logging.getLogger(__name__)
API = "https://api.sms.ir/v1/send/verify"
LAST_ERROR = {"msg": ""}


def _cfg(name):
    from shop import config

    return config.get(name)


def configured():
    return bool(_cfg("SMSIR_API_KEY") and _cfg("SMSIR_OTP_TEMPLATE_ID"))


def send_template(mobile, template_id, params):
    """params: dict نام متغیر ← مقدار. خروجی: True اگر sms.ir پذیرفت."""
    key = _cfg("SMSIR_API_KEY")
    if not key or not template_id:
        return False
    body = json.dumps({
        "mobile": mobile, "templateId": int(template_id),
        "parameters": [{"name": k, "value": str(v)} for k, v in params.items()],
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "text/plain", "X-API-KEY": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode() or "{}")
        if data.get("status") == 1:
            return True
        log.warning("sms.ir رد کرد: %s", data)
        LAST_ERROR["msg"] = str(data.get("message") or data)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        log.warning("sms.ir خطا: %s %s", e, body)
        LAST_ERROR["msg"] = f"HTTP {e.code}: {body[:200]}"
    except Exception as e:  # noqa: BLE001
        log.warning("sms.ir خطا: %s", e)
        LAST_ERROR["msg"] = str(e)
    return False


def send_otp(mobile, code):
    return send_template(mobile, _cfg("SMSIR_OTP_TEMPLATE_ID"), {"CODE": code})
