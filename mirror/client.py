"""مقصد (فرشستان): درخواست به خوراک سایت منبع."""
import json
import urllib.error
import urllib.parse
import urllib.request

from .models import MirrorSettings

UA = "Mozilla/5.0 (compatible; FarshestanMirror/1.0)"


class MirrorError(Exception):
    pass


def get_json(path, params=None, timeout=60, body=None):
    s = MirrorSettings.load()
    if not (s.api_key and s.source_url):
        raise MirrorError("نشانی سایت منبع یا کلید اتصال در پنل خالی است")
    url = s.source_url.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"Authorization": f"Token {s.api_key}", "User-Agent": UA, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = "کلید اتصال پذیرفته نشد (یا خوراک در سایت منبع خاموش است)" if e.code == 403 else f"خطای {e.code} از سایت منبع"
        raise MirrorError(msg) from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise MirrorError(f"سایت منبع در دسترس نیست: {e}") from e
    if not out.get("ok"):
        raise MirrorError(out.get("error") or "پاسخ نامعتبر از سایت منبع")
    return out


def get_bytes(url, timeout=60, limit=25 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(limit)
    except (urllib.error.URLError, TimeoutError) as e:
        raise MirrorError(f"عکس دانلود نشد: {e}") from e
