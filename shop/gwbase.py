"""پایهٔ مشترک درگاه‌ها (جدا تا gateways و bnpl همدیگر را دوری import نکنند)."""
import json
import urllib.request

GATEWAY_NAMES = {"sep": "بانک سامان (سپ)", "zarinpal": "زرین‌پال", "fake": "درگاه آزمایشی", "manual": "ثبت دستی",
                 "wordpress": "سایت قبلی (وردپرس)", "torobpay": "ترب‌پی (۴ قسط)",
                 "dp_ipg": "دیجی‌پی (کارت)", "dp_wallet": "کیف پول دیجی‌پی", "dp_credit": "دیجی‌پی اعتباری",
                 "dp_bnpl": "دیجی‌پی اقساطی", "dp_ccard": "کارت اعتباری دیجی‌پی"}


class GatewayError(Exception):
    pass


def post_json(url, data, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "irancarpet",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        try:
            return json.loads(body)
        except ValueError:
            raise GatewayError(f"HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001
        raise GatewayError(str(e)) from e


def http(method, url, body=None, headers=None, timeout=15):
    """(کد HTTP، پاسخ JSON) — بدنهٔ bytes یا dict (که JSON فرستاده می‌شود)."""
    h = {"Accept": "application/json", "User-Agent": "irancarpet", **(headers or {})}
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False).encode()
        h.setdefault("Content-Type", "application/json; charset=UTF-8")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, code = r.read().decode(errors="ignore"), r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read().decode(errors="ignore"), e.code
    except Exception as e:  # noqa: BLE001
        raise GatewayError(f"ارتباط برقرار نشد ({e.__class__.__name__})") from e
    try:
        return code, (json.loads(raw) if raw.strip() else {})
    except ValueError:
        return code, {"_raw": raw[:300]}


class Result:
    def __init__(self, ok, ref_id="", card="", message="", raw=None):
        self.ok, self.ref_id, self.card, self.message, self.raw = ok, ref_id, card, message, raw or {}


class Base:
    """ویژگی‌های مشترک: عنوان در صفحهٔ پرداخت، و اینکه فقط برای «پرداخت کامل» است یا نه."""
    full_only = False  # درگاه‌های قسطی کل مبلغ را می‌پردازند؛ با بیعانه و پیش‌پرداخت جور نیستند
    note = ""

    @property
    def title(self):
        return GATEWAY_NAMES.get(self.key, self.key)

    def eligible(self, amount):
        return True


