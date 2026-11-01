"""سامانهٔ بتا بانک رفاه (بستر تأمین اعتبار، بانکداری باز api.rb24.ir) — نسخهٔ سند ۱.۳.

روند: توکن OAuth2 ← استعلام توان بازپرداخت (کد ملی) ← ماه‌های مجاز شروع ← درخواست رمز یک‌بارمصرف
(بانک به مشتری پیامک می‌کند) ← ثبت فروش با همان رمز (consume) ← جدول اقساط و وضعیت وصول.
همهٔ کلیدها در «پنل ← تنظیمات ← سامانهٔ بتا»؛ هیچ داده‌ای از مشتری جز در همین درخواست‌ها بیرون نمی‌رود.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache
from django.utils import timezone

from .models import BetaSettings

log = logging.getLogger(__name__)
TOKEN_KEY = "beta_token"
LOG_KEY = "beta_calls"

# خطاهای مربوط به خود مشتری (پیام برای مشتری)؛ بقیه یعنی تنظیم فروشگاه یا سامانه مشکل دارد
CUSTOMER = {
    4443: "کد ملی در سامانهٔ بتا درست نیست.",
    4450: "هنوز «اجازه‌نامهٔ استعلام و کسر اقساط» را در سامانهٔ بتا بانک رفاه امضا نکرده‌اید. بعد از امضا، دوباره «بررسی اعتبار» را بزنید.",
    4451: "پروفایل شما در سامانهٔ بتا کامل نیست. پروفایل را در سامانهٔ بتا بانک رفاه تکمیل کنید و دوباره بررسی کنید.",
    4452: "اعتبارسنجی شما در سامانهٔ بتا انجام نشده یا باید دوباره انجام شود. در سامانهٔ بتا اعتبارسنجی را انجام دهید و دوباره بررسی کنید.",
    4453: "سامانهٔ بتا برای شما اعتباری نشان نمی‌دهد (معمولاً به خاطر چک برگشتی، قسط معوق یا مسدودی حساب).",
    4455: "مشخصات شما در سامانهٔ بتا پیدا نشد یا در طرح دیگری ثبت‌نام کرده‌اید.",
    4461: "مبلغ اقساط از اعتبار شما در بتا بیشتر است؛ تعداد قسط یا پیش‌پرداخت را بیشتر کنید.",
    4462: "در بتا بیش از ۳۶ قسط ممکن نیست.",
    4463: "در سامانهٔ بتا بیش از ۸ خرید در ماه از یک فروشگاه ممکن نیست.",
    4444: "رمز یک‌بارمصرف همین حالا برایتان فرستاده شده؛ تا ۲ دقیقه صبر کنید.",
    4446: "رمز یک‌بارمصرف درست نیست یا منقضی شده است.",
    4445: "ماه شروع اقساط در بتا معتبر نیست؛ ماه دیگری انتخاب کنید.",
}
CODES = {
    4403: "کلید API بتا نادرست است", 4404: "دسترسی محدود", 4406: "درخواست تکراری", 4440: "اطلاعات ورودی معتبر نیست",
    4441: "مبلغ یا تعداد اقساط نادرست", 4442: "عنوان فروش نادرست", 4447: "سال و ماه گزارش نادرست", 4460: "شناسهٔ فروش نامعتبر",
    4464: "اقساط در حال پردازش است؛ حذف ممکن نیست", 4466: "اقساط در حال پردازش است؛ ویرایش ممکن نیست", 4468: "شناسهٔ قسط نامعتبر",
    4470: "وب‌سرویس بتا برای این فروشگاه فعال نشده", 4471: "پذیرنده پیدا نشد", 4473: "پذیرنده غیرفعال است",
    4474: "پذیرنده مجاز به ثبت فروش نیست", 4775: "پذیرنده تفاهم‌نامهٔ فعال ندارد", 4476: "کارمزد پذیرنده درست تعریف نشده (مدیریت امور شعب استان)",
    400: "خطای اعتبارسنجی ورودی", 401: "توکن نامعتبر", 403: "مجوز دسترسی ندارید", 500: "خطای سامانهٔ بتا",
}
SHOP_PROBLEM = "اتصال به سامانهٔ بتا الان ممکن نیست. سفارش شما ثبت شده و همکاران ما خرید را در بتا پیگیری می‌کنند."
STATUS = {0: "ثبت‌شده", 1: "در حال وصول", 2: "وصول شد", 3: "وصول نشد"}
STATUS_NAMES = {"created": 0, "inprocess": 1, "success": 2, "rejected": 3}


class BetaError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        self.bank_message = message or ""
        super().__init__(f"{code}: {self.admin_text}")

    @property
    def admin_text(self):
        base = CUSTOMER.get(self.code) or CODES.get(self.code) or "خطای ناشناخته"
        return f"{base} ({self.code}){'؛ ' + self.bank_message if self.bank_message and self.bank_message not in base else ''}"

    @property
    def customer_text(self):
        if self.code in CUSTOMER:
            return CUSTOMER[self.code]
        return SHOP_PROBLEM

    @property
    def is_customer(self):
        return self.code in CUSTOMER


def mask_nc(nc):
    nc = str(nc or "")
    return nc[:3] + "****" + nc[-3:] if len(nc) == 10 else nc


def mask_mobile(m):
    m = str(m or "")
    return m[:4] + "•••" + m[-3:] if len(m) >= 10 else m


def _note(method, path, status, ms, err=""):
    rows = (cache.get(LOG_KEY) or [])[-49:]
    rows.append({"at": timezone.now().isoformat(), "m": method, "path": path, "status": status, "ms": ms, "err": err[:200]})
    cache.set(LOG_KEY, rows, 30 * 24 * 3600)


def recent_calls():
    return list(reversed(cache.get(LOG_KEY) or []))


def _http(method, url, headers, body=None, form=None):
    """خروجی (کد HTTP، JSON)."""
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "{}"
            code = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace") or "{}"
        code = e.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, {"message": raw[:200]}


def token(s=None, fresh=False):
    s = s or BetaSettings.load()
    if not fresh:
        t = cache.get(TOKEN_KEY)
        if t:
            return t
    t0 = timezone.now()
    try:
        code, data = _http("POST", s.base_url.rstrip("/") + "/connect/token", {}, form={
            "grant_type": s.grant_type or "client_credentials", "client_id": s.client_id, "client_secret": s.client_secret})
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _note("POST", "/connect/token", "net", 0, str(e))
        raise BetaError(0, f"اتصال به سرور بانک برقرار نشد: {e}") from e
    ms = int((timezone.now() - t0).total_seconds() * 1000)
    t = data.get("access_token") if isinstance(data, dict) else None
    _note("POST", "/connect/token", code, ms, "" if t else str(data.get("error_description") or data.get("error") or data)[:200])
    if not t:
        raise BetaError(401, "توکن بانکداری باز گرفته نشد؛ client_id و client_secret را بررسی کنید. "
                             + str(data.get("error_description") or data.get("error") or "")[:100])
    cache.set(TOKEN_KEY, t, max(60, int(data.get("expires_in") or 600) - 60))
    return t


def call(method, path, body=None, s=None):
    """درخواست به /beta/1.0/…؛ خروجی data. خطای کسب‌وکار ← BetaError."""
    s = s or BetaSettings.load()
    url = s.base_url.rstrip("/") + "/beta/1.0/" + path.lstrip("/")
    for attempt in (0, 1):
        t = token(s, fresh=bool(attempt))
        headers = {"Authorization": f"Bearer {t}", "apikey": s.api_key, "TerminalName": s.client_id}
        t0 = timezone.now()
        try:
            code, data = _http(method, url, headers, body=body)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _note(method, _safe(path), "net", 0, str(e))
            raise BetaError(0, f"اتصال به سامانهٔ بتا برقرار نشد: {e}") from e
        ms = int((timezone.now() - t0).total_seconds() * 1000)
        if code == 401 and attempt == 0:
            cache.delete(TOKEN_KEY)
            continue
        if not isinstance(data, dict):
            data = {"data": data}
        status = data.get("status")
        try:
            status = int(status) if status not in (None, "") else (200 if code == 200 else code)
        except (TypeError, ValueError):
            status = code
        msg = str(data.get("message") or "")
        if code >= 400 and status == 200:
            status = code
        if code >= 400 and not msg:
            errs = data.get("errors") or data.get("result") or data.get("title")
            msg = json.dumps(errs, ensure_ascii=False)[:200] if errs else ""
        _note(method, _safe(path), status, ms, "" if status == 200 else msg)
        if status != 200:
            raise BetaError(status, msg)
        return data.get("data")
    raise BetaError(401, "توکن پذیرفته نشد")


def _safe(path):
    """کد ملی در گزارش تماس‌ها نیمه نمایش داده شود."""
    parts = path.strip("/").split("/")
    return "/" + "/".join(mask_nc(p) if len(p) == 10 and p.isdigit() else p for p in parts)


# ---------------------------------------------------------------- سرویس‌ها
def inquiry(nc, s=None):
    s = s or BetaSettings.load()
    d = call("POST", f"credit/{nc}/inquiry", s=s) or {}
    return {"credit": s.to_toman(d.get("credit") or 0), "cellphone": str(d.get("cellphone") or "")}


def months(s=None):
    """[(«۱۴۰۵/۰۹», «آذر - ۱۴۰۵»)] ماه‌های مجاز شروع اقساط. خروجی بتا گاهی دو لایه data دارد."""
    d = call("GET", "date/validate", s=s) or {}
    while isinstance(d, dict) and isinstance(d.get("data"), dict):
        d = d["data"]
    if isinstance(d, dict):
        return sorted(((str(k), str(v)) for k, v in d.items()), key=lambda kv: kv[0])
    return []


def request_otp(nc, payload, s=None):
    call("POST", f"credit/{nc}/request", body=payload, s=s)


def consume(nc, payload, otp, request_id, s=None):
    d = call("POST", f"credit/{nc}/consume", body={**payload, "otp": str(otp), "requestId": str(request_id)}, s=s)
    if isinstance(d, dict):
        d = d.get("id") or d.get("orderId")
    return int(d) if str(d or "").isdigit() else None


def by_request(request_id, s=None):
    """فروش ثبت‌شده با شناسهٔ یکتای ما؛ None اگر نیست."""
    try:
        d = call("GET", f"order/{request_id}", s=s)
    except BetaError as e:
        if e.code in (4460, 404, 400):
            return None
        raise
    return d if isinstance(d, dict) and d.get("id") else None


def installments(sale_id, s=None):
    s = s or BetaSettings.load()
    d = call("GET", f"order/{int(sale_id)}/installments", s=s) or {}
    rows = d.get("data") if isinstance(d, dict) else d
    out = []
    for r in rows or []:
        st = r.get("status")
        if isinstance(st, str):
            st = STATUS_NAMES.get(st.lower(), st)
        out.append({
            "id": r.get("id"), "amount": s.to_toman(r.get("amount") or 0),
            "due": str(r.get("overdueDate") or "")[:10], "settled": str(r.get("settelDate") or "")[:10],
            "ok": bool(r.get("isSetteled")), "status": st, "title": r.get("statusTitle") or STATUS.get(st, ""),
            "deleted": bool(r.get("isDeleted")),
        })
    return out


def sales(year_month, s=None):
    d = call("GET", f"order/{year_month}/all", s=s) or {}
    return d.get("data") if isinstance(d, dict) else d


def test(s=None):
    """آزمایش اتصال از پنل: توکن و ماه‌های مجاز. خروجی (ok, پیام)."""
    s = s or BetaSettings.load()
    try:
        token(s, fresh=True)
        ms = months(s)
    except BetaError as e:
        res = (False, e.admin_text)
    else:
        res = (True, "اتصال برقرار است. ماه‌های مجاز شروع اقساط: " + "، ".join(v for _, v in ms) if ms else "اتصال برقرار است.")
    s.last_test = {"at": timezone.now().isoformat(), "ok": res[0], "msg": res[1]}
    s.save(update_fields=["last_test"])
    return res
