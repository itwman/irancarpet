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
    """کد ورود فرستاده می‌شود؟ با قالب «ارسال سریع» (بهتر) یا اگر قالب نیست، با متن ساده از خط اختصاصی."""
    return bool(_cfg("SMSIR_API_KEY") and (_cfg("SMSIR_OTP_TEMPLATE_ID") or _cfg("SMSIR_LINE_NUMBER")))


def otp_mode():
    """«template» | «line» | «» برای نمایش وضعیت در پنل."""
    if not _cfg("SMSIR_API_KEY"):
        return ""
    if _cfg("SMSIR_OTP_TEMPLATE_ID"):
        return "template"
    return "line" if _cfg("SMSIR_LINE_NUMBER") else ""


def record(mobiles, text, ok, error="", kind="other", order=None):
    """ثبت پیامک در «پیامک‌های فرستاده‌شده» تا در پروفایل مشتری و صفحهٔ سفارش دیده شود."""
    try:
        from accounts.utils import normalize_mobile
        from crm.models import SmsLog

        rows = [SmsLog(mobile=m, kind=kind, order=order, text=(text or "")[:2000], ok=bool(ok), error=(error or "")[:300])
                for m in {normalize_mobile(x) for x in mobiles} if m]
        SmsLog.objects.bulk_create(rows, batch_size=500)
    except Exception:  # noqa: BLE001
        log.exception("sms log")


def send_template(mobile, template_id, params, kind="other", order=None, log_it=True):
    """params: dict نام متغیر ← مقدار. خروجی: True اگر sms.ir پذیرفت."""
    ok = _send_template(mobile, template_id, params)
    if log_it and template_id and _cfg("SMSIR_API_KEY"):
        text = f"(قالب {template_id}) " + "، ".join(f"{k}: {v}" for k, v in params.items())
        record([mobile], text, ok, "" if ok else LAST_ERROR["msg"], kind, order)
    return ok


def _send_template(mobile, template_id, params):
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


OTP_TEXT = "کد ورود شما به ایران کارپت: {code}"


def send_otp(mobile, code):
    """کد ورود (ثبت نمی‌شود). اول قالب «ارسال سریع»؛ اگر شمارهٔ قالب خالی است، متن ساده از خط اختصاصی."""
    tpl = _cfg("SMSIR_OTP_TEMPLATE_ID")
    if tpl:
        return send_template(mobile, tpl, {"CODE": code}, log_it=False)
    ok, msg = _send_bulk([mobile], OTP_TEXT.format(code=code))
    if not ok:
        LAST_ERROR["msg"] = msg
        log.warning("sms.ir کد ورود (خط) نرفت: %s", msg)
    return ok


BULK_API = "https://api.sms.ir/v1/send/bulk"


def send_bulk(mobiles, text, kind="other", order=None, log_it=True):
    """پیامک یکسان به چند شماره (حداکثر ۱۰۰ در هر درخواست). خروجی: (موفق؟, پیام). هر پیامک در دفتر پیامک‌ها ثبت می‌شود."""
    mobiles = list(mobiles)
    ok, msg = _send_bulk(mobiles, text)
    if log_it:
        record(mobiles, text, ok, msg, kind, order)
    return ok, msg


def _send_bulk(mobiles, text):
    key, line = _cfg("SMSIR_API_KEY"), _cfg("SMSIR_LINE_NUMBER")
    if not key or not line:
        return False, "کلید API یا شمارهٔ خط پیامک تنظیم نشده است."
    body = json.dumps({"lineNumber": int(line), "messageText": text, "mobiles": list(mobiles), "sendDateTime": None}).encode()
    req = urllib.request.Request(BULK_API, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "text/plain", "X-API-KEY": key,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode() or "{}")
        if data.get("status") == 1:
            return True, ""
        return False, str(data.get("message") or data)[:300]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:300]
