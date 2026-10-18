"""درگاه‌های پرداخت: سامان (سپ)، زرین‌پال، ترب‌پی، دیجی‌پی (پنج حالت) و درگاه آزمایشی.

مبالغ در سایت به تومان است و به درگاه‌ها به ریال فرستاده می‌شود.
"""
import json
import logging
import urllib.request

from django.conf import settings

from . import config

log = logging.getLogger(__name__)

from .gwbase import GATEWAY_NAMES, Base, GatewayError, Result, http, post_json  # noqa: F401,E402


# ----------------------------------------------------------------- سامان
class Sep(Base):
    key = "sep"
    TOKEN_URL = "https://sep.shaparak.ir/onlinepg/onlinepg"
    PAY_URL = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
    VERIFY_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"
    REVERSE_URL = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/ReverseTransaction"
    STATUS = {
        "1": "پرداخت توسط خریدار لغو شد.", "2": "", "3": "پرداخت انجام نشد.", "4": "کاربر در زمان مقرر پرداخت نکرد.",
        "5": "اطلاعات ارسالی نامعتبر است.", "8": "آی‌پی سرور برای درگاه مجاز نیست.", "10": "توکن نامعتبر است.",
        "11": "این کارت فعال نیست.",
    }

    @staticmethod
    def available():
        return bool(config.get('SEP_TERMINAL_ID'))

    def start(self, payment, callback_url):
        data = post_json(self.TOKEN_URL, {
            "action": "token", "TerminalId": config.get('SEP_TERMINAL_ID'), "Amount": payment.amount * 10,
            "ResNum": payment.res_num, "RedirectUrl": callback_url, "CellNumber": payment.order.mobile,
        })
        payment.raw = {"token_response": data}
        if str(data.get("status")) != "1" or not data.get("token"):
            raise GatewayError(data.get("errorDesc") or "درگاه سامان توکن نداد.")
        payment.token = data["token"]
        return {"form": self.PAY_URL, "fields": {"Token": data["token"], "token": data["token"], "GetMethod": ""}}

    def find_payment(self, params):
        from .models import Payment

        res = str(params.get("ResNum", ""))
        if res.startswith("IC") and res[2:].isdigit():
            return Payment.objects.select_related("order").filter(pk=int(res[2:]), gateway=self.key).first()
        return None

    def verify(self, payment, params):
        status = str(params.get("Status", ""))
        state = str(params.get("State", ""))
        ref = str(params.get("RefNum", ""))
        raw = {k: params.get(k) for k in ("State", "Status", "RefNum", "ResNum", "RRN", "TraceNo", "Amount", "SecurePan")}
        if not ref or (status != "2" and state.upper() != "OK"):
            return Result(False, message=self.STATUS.get(status) or "پرداخت انجام نشد.", raw=raw)
        from .models import Payment

        if Payment.objects.filter(gateway=self.key, ref_id=ref, status="ok").exclude(pk=payment.pk).exists():
            return Result(False, message="این تراکنش قبلاً استفاده شده است.", raw=raw)
        data = post_json(self.VERIFY_URL, {"RefNum": ref, "TerminalNumber": int(config.get('SEP_TERMINAL_ID'))})
        raw["verify"] = data
        detail = data.get("TransactionDetail") or {}
        amounts = {detail.get("OrginalAmount"), detail.get("AffectiveAmount")}
        if data.get("ResultCode") in (0, 2) and data.get("Success", True) and payment.amount * 10 in amounts:
            return Result(True, ref_id=ref, card=str(detail.get("MaskedPan") or params.get("SecurePan") or ""),
                          message=str(detail.get("RRN") or params.get("RRN") or ""), raw=raw)
        if data.get("ResultCode") in (0, 2):
            # مبلغ نخواند: برگشت وجه
            try:
                raw["reverse"] = post_json(self.REVERSE_URL, {"RefNum": ref, "TerminalNumber": int(config.get('SEP_TERMINAL_ID'))})
            except GatewayError:
                pass
        return Result(False, message=data.get("ResultDescription") or "تأیید پرداخت ناموفق بود.", raw=raw)


# --------------------------------------------------------------- زرین‌پال
class Zarinpal(Base):
    key = "zarinpal"

    @staticmethod
    def available():
        return bool(config.get('ZARINPAL_MERCHANT_ID'))

    @property
    def base(self):
        return "https://sandbox.zarinpal.com" if config.zarinpal_sandbox() else "https://payment.zarinpal.com"

    def start(self, payment, callback_url):
        o = payment.order
        meta = {"mobile": o.mobile, "order_id": str(o.number)}
        if o.email:
            meta["email"] = o.email
        data = post_json(self.base + "/pg/v4/payment/request.json", {
            "merchant_id": config.get('ZARINPAL_MERCHANT_ID'), "amount": payment.amount * 10, "currency": "IRR",
            "callback_url": callback_url, "description": f"سفارش {o.number} ایران کارپت", "metadata": meta,
        })
        payment.raw = {"request": data}
        d = data.get("data") or {}
        if d.get("code") != 100 or not d.get("authority"):
            errs = data.get("errors") or {}
            raise GatewayError((errs.get("message") if isinstance(errs, dict) else "") or "زرین‌پال درخواست را نپذیرفت.")
        payment.token = d["authority"]
        return {"redirect": f"{self.base}/pg/StartPay/{d['authority']}"}

    def find_payment(self, params):
        from .models import Payment

        a = params.get("Authority")
        return Payment.objects.select_related("order").filter(gateway=self.key, token=a).first() if a else None

    def verify(self, payment, params):
        raw = {"Status": params.get("Status"), "Authority": params.get("Authority")}
        if params.get("Status") != "OK":
            return Result(False, message="پرداخت لغو شد یا ناموفق بود.", raw=raw)
        data = post_json(self.base + "/pg/v4/payment/verify.json", {
            "merchant_id": config.get('ZARINPAL_MERCHANT_ID'), "amount": payment.amount * 10, "authority": payment.token,
        })
        raw["verify"] = data
        d = data.get("data") or {}
        if d.get("code") in (100, 101):
            return Result(True, ref_id=str(d.get("ref_id", "")), card=d.get("card_pan", ""), raw=raw)
        errs = data.get("errors") or {}
        return Result(False, message=(errs.get("message") if isinstance(errs, dict) else "") or "تأیید پرداخت ناموفق بود.", raw=raw)


# ------------------------------------------------------------- آزمایشی
class Fake(Base):
    key = "fake"
    note = "فقط برای آزمایش؛ پول واقعی جابه‌جا نمی‌شود."

    @staticmethod
    def available():
        return settings.PAYMENT_FAKE

    def start(self, payment, callback_url):
        payment.token = f"fake-{payment.pk}"
        return {"redirect": f"/pay/fake/{payment.pk}/"}

    def find_payment(self, params):
        from .models import Payment

        pk = str(params.get("pid", ""))
        return Payment.objects.select_related("order").filter(pk=int(pk), gateway=self.key).first() if pk.isdigit() else None

    def verify(self, payment, params):
        if params.get("ok") == "1":
            return Result(True, ref_id=f"TEST{payment.pk:06d}", card="6037-99**-****-1234", raw=dict(params.items()))
        return Result(False, message="پرداخت آزمایشی لغو شد.", raw=dict(params.items()))


from .bnpl import DIGIPAY_MODES, Digipay, TorobPay  # noqa: E402

ALL = {g.key: g for g in (Sep(), Zarinpal(), TorobPay(), *(Digipay(k) for k in DIGIPAY_MODES), Fake())}


def enabled(shop_settings, amount=None, mode=None):
    """درگاه‌های فعال. amount (تومان): درگاهی که این مبلغ را نمی‌پذیرد کنار می‌رود.
    mode: اگر «پرداخت کامل» نیست، درگاه‌های قسطی کنار می‌روند."""
    out = []
    if shop_settings.sep_enabled and Sep.available():
        out.append(ALL["sep"])
    if shop_settings.zarinpal_enabled and Zarinpal.available():
        out.append(ALL["zarinpal"])
    out += [g for g in ALL.values() if isinstance(g, (TorobPay, Digipay)) and g.is_on(shop_settings)]
    if Fake.available():
        out.append(ALL["fake"])
    if mode and mode != "full":
        out = [g for g in out if not g.full_only]
    if amount:
        out = [g for g in out if g.eligible(amount)]
    return out


def for_order(order):
    """درگاه‌های صفحهٔ پرداختِ یک سفارش ثبت‌شده (قسطی‌ها فقط اگر «پرداخت کامل» ممکن است)."""
    from .models import ShopSettings
    from .paymode import options

    shop = ShopSettings.load()
    full_ok = order.payment_mode == "full" or any(o["mode"] == "full" for o in options(order, shop))
    return enabled(shop, amount=order.items_total, mode=None if full_ok else order.payment_mode)


def mode_for(gateway_key, mode):
    """انتخاب درگاه قسطی یعنی «پرداخت کامل» (کل مبلغ را همان درگاه می‌دهد)."""
    g = ALL.get(gateway_key or "")
    return "full" if g is not None and g.full_only else mode
