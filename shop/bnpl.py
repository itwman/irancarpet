"""درگاه‌های قسطی و کیف‌پولی: ترب‌پی و دیجی‌پی (UPG).

ترب‌پی — خرید ۴ قسطی. از روی افزونهٔ رسمی ووکامرس (نسخهٔ 4.8.7):
  توکن OAuth (password grant، Basic با client id/secret) → payment/v1/token → صفحهٔ ترب‌پی
  → برگشت با POST «state» → verify → settle. لغو سفارش ← cancel. اگر settle نشد، هر ۱۰ دقیقه دوباره.

دیجی‌پی — یک API با پنج «نوع تیکت»: کارت (0)، کیف پول (11)، اعتباری (5)، اقساطی BNPL (13)، کارت اعتباری (24).
  توکن OAuth (password grant، multipart، Basic) → tickets/business?type= → صفحهٔ دیجی‌پی
  → برگشت با POST (result، amount، providerId، trackingCode، type) → purchases/verify.
  اعتباری و اقساطی: سبد کالا لازم است و بعد از ارسال باید «تحویل» اعلام شود (purchases/deliver) تا اقساط شروع شود.

مبالغ سایت تومان است و به هر دو درگاه ریال فرستاده می‌شود.
"""
import base64
import logging
import time
import urllib.parse
import uuid

from django.conf import settings
from django.core.cache import cache

from .gwbase import Base, GatewayError, Result, http

log = logging.getLogger(__name__)


def _basic(user, secret):
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def _rial(toman):
    return int(toman) * 10


def _shop():
    from .models import ShopSettings

    return ShopSettings.load()


def _with_query(url, **params):
    sep = "&" if "?" in url else "?"
    return url + sep + urllib.parse.urlencode(params)


# ════════════════════════════════════════════════════════════════════ ترب‌پی
class TorobPay(Base):
    key = "torobpay"
    full_only = True
    note = "۴ قسط، بدون چک و ضامن؛ کل مبلغ را ترب‌پی می‌پردازد."
    BASE = "https://cpg.torobpay.com/"
    TOKEN_KEY = "torobpay:token"

    @staticmethod
    def is_on(shop):
        return bool(shop.torobpay_enabled and shop.torobpay_client_id and shop.torobpay_client_secret
                    and shop.torobpay_username and shop.torobpay_password)

    @staticmethod
    def available():
        return TorobPay.is_on(_shop())

    # ── HTTP ──
    def _headers(self, s):
        return {"User-Agent": f"TorobPay, {s.torobpay_client_id}", "X-TorobPay-Shop-URL": settings.SITE_URL,
                "X-TorobPay-Plugin-Version": "d_irancarpet"}

    def _token(self, s, fresh=False):
        tok = None if fresh else cache.get(self.TOKEN_KEY)
        if tok:
            return tok
        body = urllib.parse.urlencode({"grant_type": "password", "scope": "online-merchant",
                                       "username": s.torobpay_username, "password": s.torobpay_password}).encode()
        code, data = http("POST", self.BASE + "api/online/v1/oauth/token", body, {
            **self._headers(s), "Authorization": _basic(s.torobpay_client_id, s.torobpay_client_secret),
            "Content-Type": "application/x-www-form-urlencoded"})
        tok = data.get("access_token")
        if not tok:
            raise GatewayError("ورود به ترب‌پی ناموفق بود؛ شناسه، کلید، نام کاربری و رمز را در پنل بررسی کنید.")
        cache.set(self.TOKEN_KEY, tok, max(int(data.get("expires_in") or 3300) - 60, 60))
        return tok

    def api(self, method, path, body=None, params=None, timeout=15):
        s = _shop()
        url = self.BASE + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        for attempt in (0, 1):
            h = {**self._headers(s), "Authorization": f"Bearer {self._token(s, fresh=attempt == 1)}"}
            code, data = http(method, url, body if method != "GET" else None, h, timeout)
            if code != 401:
                return code, data
        return code, data

    @staticmethod
    def error(data, default="ترب‌پی درخواست را نپذیرفت."):
        e = data.get("errorData") or data.get("error") or {}
        if isinstance(e, dict):
            return str(e.get("message") or e.get("errorMessage") or default)
        return default

    # ── واجد بودن ──
    def eligible(self, amount):
        key = f"torobpay:elig:{int(amount)}"
        v = cache.get(key)
        if v is None:
            try:
                code, data = self.api("GET", "api/online/offer/v1/eligible", params={
                    "amount": _rial(amount), "widget_is_active": "false", "badge_is_active": "false",
                    "marquee_bar_is_active": "false", "top_banner_is_active": "false", "slider_is_active": "false",
                    "default_gateway_is_active": "false", "payment_price_parity": "equal"}, timeout=5)
                v = bool(data.get("successful") and (data.get("response") or {}).get("eligible"))
            except GatewayError:
                v = False
            cache.set(key, v, 600 if v else 120)
        return v

    # ── پرداخت ──
    def _cart(self, order):
        items = []
        for it in order.items.select_related("product").all():
            items.append({"name": it.title[:200], "count": it.quantity, "amount": _rial(it.unit_price),
                          "id": it.variation_id or it.product_id or it.pk, "product_id": it.product_id or it.pk,
                          "page_url": settings.SITE_URL + (it.product.get_absolute_url() if it.product_id else "/")})
        total = sum(i["amount"] * i["count"] for i in items)
        return [{"cartId": order.number, "totalAmount": total, "cartItems": items, "taxAmount": 0, "shippingAmount": 0,
                 "isShipmentIncluded": False, "isTaxIncluded": False}]

    def start(self, payment, callback_url):
        o = payment.order
        if o.payment_mode != "full" or payment.amount != o.items_total:
            raise GatewayError("ترب‌پی فقط برای پرداخت کامل سفارش است.")
        tx = f"{int(time.time())}-{payment.pk}"
        mobile = (o.mobile or "").strip()
        body = {
            "amount": _rial(payment.amount), "paymentMethodTypeDto": "INSTALLMENT",
            "returnURL": _with_query(callback_url, pid=payment.pk, tx=tx), "transactionId": tx,
            "mobile": "+98" + mobile[1:] if mobile.startswith("0") else mobile,
            "customer_full_name": f"{o.first_name} {o.last_name}".strip(),
            "province": o.province, "city": o.city, "address": o.address, "postalCode": o.postal_code,
            "cartList": self._cart(o), "discountAmount": _rial(o.discount or 0),
        }
        code, data = self.api("POST", "api/online/payment/v1/token", body)
        payment.raw = {"tx": tx, "token_response": data}
        r = data.get("response") or {}
        url = r.get("paymentPageUrl") or ""
        host = urllib.parse.urlparse(url).hostname or ""
        if not (data.get("successful") and r.get("paymentToken") and (host == "torobpay.com" or host.endswith(".torobpay.com"))):
            raise GatewayError(self.error(data))
        payment.token = r["paymentToken"]
        return {"redirect": url}

    def find_payment(self, params):
        from .models import Payment

        pid = str(params.get("pid", ""))
        return Payment.objects.select_related("order").filter(pk=int(pid), gateway=self.key).first() if pid.isdigit() else None

    def verify(self, payment, params):
        raw = {"state": params.get("state"), "tx": params.get("tx")}
        if params.get("tx") != (payment.raw or {}).get("tx"):
            return Result(False, message="اطلاعات بازگشت از ترب‌پی با این تراکنش نمی‌خواند.", raw=raw)
        if str(params.get("state", "")).upper() != "OK":
            return Result(False, message="پرداخت در ترب‌پی انجام نشد یا لغو شد.", raw=raw)
        code, data = self.api("POST", "api/online/payment/v1/verify", {"paymentToken": payment.token})
        raw["verify"] = data
        if not data.get("successful"):
            return Result(False, message=self.error(data, "ترب‌پی پرداخت را تأیید نکرد."), raw=raw)
        ok, ref = self.settle(payment.token)
        raw["settled"] = ok
        if not ok:
            raw["settle_pending"] = True  # پول تأیید شده؛ jobs دوباره settle می‌زند
            log.warning("torobpay settle pending for payment %s", payment.pk)
        return Result(True, ref_id=ref or payment.raw.get("tx", ""), message="ترب‌پی", raw=raw)

    def status(self, token):
        try:
            code, data = self.api("GET", "api/online/payment/v1/status", params={"paymentToken": token}, timeout=8)
        except GatewayError:
            return ""
        return str((data.get("response") or {}).get("status") or "")

    def settle(self, token):
        """(قطعی شد؟، شمارهٔ تراکنش)"""
        try:
            code, data = self.api("POST", "api/online/payment/v1/settle", {"paymentToken": token})
        except GatewayError:
            data = {}
        if data.get("successful"):
            return True, str((data.get("response") or {}).get("transactionId") or "")
        return self.status(token) == "SETTLE", ""

    def cancel(self, payment):
        """لغو کامل پرداخت (برای سفارش لغوشده). خروجی: (ok، پیام)."""
        code, data = self.api("POST", "api/online/payment/v1/cancel", {"paymentToken": payment.token})
        if data.get("successful") or self.status(payment.token) == "REVERT":
            return True, "پرداخت ترب‌پی لغو شد؛ مبلغ به مشتری برمی‌گردد."
        return False, self.error(data, "ترب‌پی لغو را نپذیرفت.")


TOROB_MIN, TOROB_MAX, TOROB_SHOW_EACH = 20_000, 100_000_000, 20_000_000  # تومان؛ مثل ویجت خود ترب‌پی


def torob_widget(price):
    """«۴ قسط X تومان با ترب‌پی» زیر قیمت؛ None اگر خاموش است. بالای ۲۰ میلیون مبلغ قسط گفته نمی‌شود
    (اعتبار هر مشتری فرق دارد) — همان رفتار ویجت رسمی ترب‌پی."""
    s = _shop()
    if not (s.torobpay_widget and TorobPay.is_on(s)) or not price or not TOROB_MIN <= price <= TOROB_MAX:
        return None
    return {"each": -(-int(price) // 4) if price <= TOROB_SHOW_EACH else 0, "max": TOROB_MAX, "show_each": TOROB_SHOW_EACH}


# ════════════════════════════════════════════════════════════════════ دیجی‌پی
# کلید درگاه → (نوع تیکت، فیلد روشن/خاموش در تنظیمات، اعتباری؟، توضیح)
DIGIPAY_MODES = {
    "dp_ipg": (0, "digipay_ipg", False, "پرداخت با همهٔ کارت‌های بانکی از درگاه دیجی‌پی"),
    "dp_wallet": (11, "digipay_wallet", False, "پرداخت از کیف پول دیجی‌پی"),
    "dp_credit": (5, "digipay_credit", True, "خرید با اعتبار دیجی‌پی؛ بازپرداخت اقساطی"),
    "dp_bnpl": (13, "digipay_bnpl", True, "الان بخرید، بعداً قسطی بپردازید"),
    "dp_ccard": (24, "digipay_ccard", True, "پرداخت با کارت اعتباری دیجی‌پی"),
}
CREDIT_TYPES = {5, 13}  # این‌ها سبد کالا و اعلام تحویل لازم دارند
DIGIPAY_VERSION = "2022-02-02"


class Digipay(Base):
    def __init__(self, key):
        self.key = key
        self.type, self.flag, self.credit, self.note = DIGIPAY_MODES[key]
        self.full_only = self.credit

    @staticmethod
    def creds(shop):
        return bool(shop.digipay_client_id and shop.digipay_client_secret and shop.digipay_username and shop.digipay_password)

    def is_on(self, shop):
        return bool(getattr(shop, self.flag) and self.creds(shop))

    def available(self):
        return self.is_on(_shop())

    def eligible(self, amount):
        if not self.credit:
            return True
        s = _shop()
        return amount >= (s.digipay_credit_min or 0) and (not s.digipay_credit_max or amount <= s.digipay_credit_max)

    # ── HTTP ──
    @staticmethod
    def base(s):
        return "https://uat.mydigipay.info/digipay/api" if s.digipay_sandbox else "https://api.mydigipay.com/digipay/api"

    @staticmethod
    def _token(s, fresh=False):
        key = f"digipay:token:{int(s.digipay_sandbox)}"
        tok = None if fresh else cache.get(key)
        if tok:
            return tok
        boundary = "dp" + uuid.uuid4().hex
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                 for k, v in (("username", s.digipay_username), ("password", s.digipay_password), ("grant_type", "password"))]
        body = ("".join(parts) + f"--{boundary}--\r\n").encode()
        code, data = http("POST", Digipay.base(s) + "/oauth/token", body, {
            "Authorization": _basic(s.digipay_client_id, s.digipay_client_secret),
            "Content-Type": f"multipart/form-data; boundary={boundary}"})
        tok = data.get("access_token")
        if not tok:
            raise GatewayError("ورود به دیجی‌پی ناموفق بود؛ اطلاعات اتصال را در پنل بررسی کنید.")
        cache.set(key, tok, max(int(data.get("expires_in") or 1800) - 60, 60))
        return tok

    @staticmethod
    def api(path, body=None, ticket_type=0, timeout=20):
        s = _shop()
        url = _with_query(Digipay.base(s) + path, type=ticket_type)
        for attempt in (0, 1):
            h = {"Authorization": f"Bearer {Digipay._token(s, fresh=attempt == 1)}", "Agent": "WEB",
                 "Digipay-Version": DIGIPAY_VERSION}
            code, data = http("POST", url, body if body is not None else {}, h, timeout)
            if code != 401:
                return code, data
        return code, data

    @staticmethod
    def ok(data):
        st = (data.get("result") or {}).get("status")
        return str(st) == "0"

    @staticmethod
    def error(data, default="دیجی‌پی درخواست را نپذیرفت."):
        r = data.get("result") or {}
        return str(r.get("message") or r.get("title") or default)

    # ── پرداخت ──
    def _basket(self, order):
        s = _shop()
        seller = s.digipay_seller_id or "irancarpet"
        items = []
        for it in order.items.select_related("product__brand", "product__primary_category").all():
            p = it.product
            items.append({
                "sellerId": seller, "supplierId": seller, "productCode": str(it.variation_id or it.product_id or it.pk),
                "brand": (p.brand.name if p and p.brand_id else "ایران کارپت")[:100], "productType": 1,  # کالای بادوام
                "count": it.quantity, "categoryId": str(getattr(p, "primary_category_id", None) or 0),
            })
        return {"basketId": str(order.number), "items": items}

    def start(self, payment, callback_url):
        o = payment.order
        if self.full_only and (o.payment_mode != "full" or payment.amount != o.items_total):
            raise GatewayError("این روش دیجی‌پی فقط برای پرداخت کامل سفارش است.")
        body = {"amount": _rial(payment.amount), "cellNumber": o.mobile, "providerId": f"IC{payment.pk}",
                "callbackUrl": _with_query(callback_url, pid=payment.pk)}
        if self.type in CREDIT_TYPES:
            body["basketDetailsDto"] = self._basket(o)
        code, data = self.api("/tickets/business", body, self.type)
        payment.raw = {"type": self.type, "ticket_response": data}
        if not (self.ok(data) and data.get("redirectUrl")):
            raise GatewayError(self.error(data))
        payment.token = str(data.get("ticket") or "")[:200]
        return {"redirect": data["redirectUrl"]}

    def find_payment(self, params):
        from .models import Payment

        pid = str(params.get("pid", ""))
        if not pid.isdigit():
            prov = str(params.get("providerId", ""))
            pid = prov[2:] if prov.startswith("IC") else ""
        return (Payment.objects.select_related("order").filter(pk=int(pid), gateway__startswith="dp_").first()
                if pid.isdigit() else None)

    def verify(self, payment, params):
        raw = {k: params.get(k) for k in ("result", "amount", "providerId", "trackingCode", "type", "rrn", "isCredit")}
        tracking = str(params.get("trackingCode") or "")
        if str(params.get("result", "")).upper() != "SUCCESS" or not tracking:
            return Result(False, message="پرداخت در دیجی‌پی انجام نشد یا لغو شد.", raw=raw)
        if str(params.get("providerId", "")) != f"IC{payment.pk}" or str(params.get("amount", "")) != str(_rial(payment.amount)):
            return Result(False, message="مبلغ یا شمارهٔ تراکنش برگشتی از دیجی‌پی با سفارش نمی‌خواند.", raw=raw)
        paid_type = str(params.get("type") or self.type)
        paid_type = int(paid_type) if paid_type.isdigit() else self.type  # مشتری ممکن است در دیجی‌پی روش را عوض کرده باشد
        body = {"trackingCode": tracking, "providerId": f"IC{payment.pk}"}
        data = {}
        for attempt in range(3):
            code, data = self.api("/purchases/verify", body, paid_type)
            if code in (404, 405):  # شکل دیگرِ همین سرویس در بعضی نسخه‌ها
                code, data = self.api(f"/purchases/verify/{urllib.parse.quote(tracking)}", {}, paid_type)
            if str((data.get("result") or {}).get("status")) != "9011":  # «در حال پردازش»
                break
            time.sleep(2)
        raw["verify"] = data
        raw["paid_type"] = paid_type
        if not self.ok(data):
            return Result(False, message=self.error(data, "دیجی‌پی پرداخت را تأیید نکرد."), raw=raw)
        amount = data.get("amount")
        if amount not in (None, "") and str(amount) != str(_rial(payment.amount)):
            return Result(False, message="مبلغ تأییدشدهٔ دیجی‌پی با سفارش نمی‌خواند.", raw=raw)
        return Result(True, ref_id=tracking, card=str(data.get("maskedPan") or ""), message=str(data.get("rrn") or ""), raw=raw)

    @staticmethod
    def deliver(payment):
        """اعلام تحویل برای اعتباری/اقساطی (تا اقساط مشتری شروع شود). خروجی: (ok، پیام) یا None اگر لازم نیست."""
        raw = payment.raw or {}
        cb = raw.get("callback") or {}
        t = cb.get("paid_type", raw.get("type"))
        if t not in CREDIT_TYPES or raw.get("delivered"):
            return None
        o = payment.order
        products = [str(it.variation_id or it.product_id or it.pk) for it in o.items.all()] or [str(o.number)]
        body = {"deliveryDate": int(time.time() * 1000), "invoiceNumber": str(o.number), "trackingCode": payment.ref_id,
                "products": products}
        try:
            code, data = Digipay.api("/purchases/deliver", body, t)
        except GatewayError as e:
            return False, str(e)
        ok = Digipay.ok(data)
        payment.raw = {**raw, "delivered": ok, "deliver": data}
        payment.save(update_fields=["raw"])
        return (True, "تحویل سفارش به دیجی‌پی اعلام شد.") if ok else (False, Digipay.error(data))


# ════════════════════════════════════════════════════════════════════ رویدادهای سفارش
def on_status(order, old):
    """بعد از تغییر وضعیت در پنل: ارسال ← اعلام تحویل دیجی‌پی؛ لغو ← لغو ترب‌پی. خروجی: پیام‌ها برای مدیر."""
    from .models import Payment

    msgs = []
    if old == order.status:
        return msgs
    pays = Payment.objects.filter(order=order, status=Payment.Status.OK)
    if order.status in ("shipped", "completed"):
        for p in pays.filter(gateway__in=["dp_credit", "dp_bnpl", "dp_ccard", "dp_wallet", "dp_ipg"]):
            r = Digipay.deliver(p)
            if r:
                msgs.append((r[0], r[1] if r[0] else f"اعلام تحویل به دیجی‌پی ناموفق بود: {r[1]}"))
    if order.status in ("cancelled", "refunded"):
        for p in pays.filter(gateway="torobpay"):
            if (p.raw or {}).get("cancelled"):
                continue
            try:
                ok, m = TorobPay().cancel(p)
            except GatewayError as e:
                ok, m = False, str(e)
            if ok:
                p.raw = {**(p.raw or {}), "cancelled": True}
                p.save(update_fields=["raw"])
            msgs.append((ok, m if ok else f"لغو در ترب‌پی ناموفق بود: {m}"))
        if pays.filter(gateway__startswith="dp_").exists():
            msgs.append((False, "این سفارش با دیجی‌پی پرداخت شده؛ بازگشت وجه را از پنل دیجی‌پی انجام دهید."))
    return msgs


def retry_settles():
    """پرداخت‌های ترب‌پی که تأیید شده ولی settle نشده‌اند (هر ۱۰ دقیقه، از growth.jobs)."""
    from .models import Payment

    n = 0
    for p in Payment.objects.filter(gateway="torobpay", status=Payment.Status.OK).order_by("-pk")[:50]:
        cb = (p.raw or {}).get("callback") or {}
        if not cb.get("settle_pending"):
            continue
        ok, ref = TorobPay().settle(p.token)
        if ok:
            p.raw = {**p.raw, "callback": {**cb, "settle_pending": False, "settled": True}}
            p.save(update_fields=["raw"])
            n += 1
    return n
