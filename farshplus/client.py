"""کلاینت HTTP برای Connect API فرش پلاس (/api/v1/connect/) — هم‌رفتار با افزونهٔ ووکامرس."""
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

ERRORS = {
    400: "اطلاعات ارسالی توسط فرش پلاس پذیرفته نشد.", 401: "کلید API نامعتبر است یا باطل شده است.",
    403: "آدرس محصول روی دامنهٔ ثبت‌شدهٔ فروشگاه شما نیست.", 404: "مورد درخواستی در فرش پلاس پیدا نشد.",
    413: "حجم ارسال (تصاویر) بیش از حد مجاز است.", 429: "سقف ارسال روزانهٔ محصولات پر شده است؛ بعداً دوباره تلاش می‌شود.",
}


class ApiError(Exception):
    def __init__(self, message, status=0, retryable=False, retry_after=0):
        super().__init__(message)
        self.status, self.retryable, self.retry_after = status, retryable, retry_after


def error_message(code, data):
    if isinstance(data, dict):
        d = data.get("detail")
        if isinstance(d, str) and d.strip():
            return d.strip()[:300]
        parts = []
        for field, msgs in data.items():
            msg = msgs[0] if isinstance(msgs, list) and msgs else msgs
            if isinstance(msg, str) and msg:
                parts.append((f"{field}: " if field != "non_field_errors" else "") + msg)
            if len(parts) >= 3:
                break
        if parts:
            return " | ".join(parts)[:300]
    if code in ERRORS:
        return ERRORS[code]
    if code >= 500:
        return "فرش پلاس موقتاً در دسترس نیست؛ دوباره تلاش می‌شود."
    return f"پاسخ غیرمنتظره از فرش پلاس (کد {code})."


class Client:
    def __init__(self, base_url, api_key, site_url=None):
        self.base = (base_url or "https://farshplus.com").rstrip("/")
        self.key = (api_key or "").strip()
        self.site = (site_url or settings.SITE_URL).rstrip("/")

    def endpoint(self, path):
        return f"{self.base}/api/v1/connect/{path.lstrip('/')}"

    def request(self, method, path, body=None, headers=None, timeout=30):
        if not self.key:
            raise ApiError("کلید API فرش پلاس وارد نشده است.")
        h = {"Authorization": f"Api-Key {self.key}", "X-FP-Site": self.site, "Accept": "application/json",
             "Accept-Language": "fa", "User-Agent": "FarshPlusConnect/django IranCarpet"}
        h.update(headers or {})
        req = urllib.request.Request(self.endpoint(path), data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "ignore")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "ignore")
            try:
                data = json.loads(raw)
            except ValueError:
                data = None
            try:
                ra = int(e.headers.get("Retry-After") or 0)
            except ValueError:
                ra = 0
            raise ApiError(error_message(e.code, data), e.code, e.code >= 500 or e.code == 408, ra) from e
        except Exception as e:  # noqa: BLE001
            raise ApiError(f"خطای شبکه در ارتباط با فرش پلاس: {e}", 0, True) from e

    def me(self):
        return self.request("GET", "me/")

    def upsert_product(self, fields, files=()):
        boundary = "FPCBoundary" + secrets.token_hex(12)
        body = build_multipart(boundary, fields, files)
        return self.request("POST", "products/", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"},
                            timeout=60 if files else 30)

    def delete_product(self, external_id):
        try:
            return self.request("DELETE", f"products/{urllib.parse.quote(str(external_id), safe='')}/")
        except ApiError as e:
            if e.status == 404:
                return {"ok": True, "not_found": True}
            raise

    def get_statuses(self, external_ids):
        ids = ",".join(urllib.parse.quote(str(i), safe="") for i in external_ids)
        return self.request("GET", f"products/?external_ids={ids}")


def _safe(v):
    return str(v).replace("\r", "").replace("\n", "").replace('"', "").replace("\\", "")


def build_multipart(boundary, fields, files):
    eol = b"\r\n"
    out = bytearray()
    for name, value in fields.items():
        if value is None or isinstance(value, (list, dict)):
            continue
        out += f"--{boundary}".encode() + eol
        out += f'Content-Disposition: form-data; name="{_safe(name)}"'.encode() + eol
        out += b"Content-Type: text/plain; charset=UTF-8" + eol + eol
        out += str(value).encode("utf-8") + eol
    for f in files:
        out += f"--{boundary}".encode() + eol
        out += f'Content-Disposition: form-data; name="images"; filename="{_safe(f["filename"])}"'.encode() + eol
        out += f"Content-Type: {_safe(f['type'])}".encode() + eol + eol
        out += f["data"] + eol
    out += f"--{boundary}--".encode() + eol
    return bytes(out)
