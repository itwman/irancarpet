"""ترب‌پی و دیجی‌پی با HTTP شبیه‌سازی‌شده: شروع، بازگشت، تأیید، settle، اعلام تحویل، لغو، و «فقط پرداخت کامل»."""
import json
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import override_settings

from . import bnpl
from .models import Order, Payment, ShopSettings
from django.test import TestCase

from . import tests as flow


class FakeHttp:
    """پاسخ‌ها بر اساس انتهای مسیر؛ هر درخواست در calls ثبت می‌شود."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, method, url, body=None, headers=None, timeout=15):
        path = urlparse(url).path
        b = body
        if isinstance(body, bytes):
            try:
                b = json.loads(body)
            except ValueError:
                b = body.decode(errors="ignore")
        self.calls.append((method, url, b, headers or {}))
        for suffix, resp in self.routes.items():
            if path.endswith(suffix):
                return resp(url, b) if callable(resp) else resp
        return 404, {}


@override_settings(PAYMENT_FAKE=False, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True)
class BnplTests(TestCase):
    otp_login = flow.ShopFlowTests.otp_login
    checkout_data = flow.ShopFlowTests.checkout_data

    def setUp(self):
        flow.ShopFlowTests.setUp(self)
        cache.clear()
        s = ShopSettings.load()
        s.sep_enabled = s.zarinpal_enabled = False
        s.torobpay_enabled = True
        s.torobpay_client_id, s.torobpay_client_secret, s.torobpay_username, s.torobpay_password = "cid", "sec", "u", "p"
        s.digipay_client_id, s.digipay_client_secret, s.digipay_username, s.digipay_password = "dcid", "dsec", "du", "dp"
        s.digipay_ipg = s.digipay_bnpl = True
        s.save()
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})  # ۲۰ میلیون
        self.otp_login()

    # ------------------------------------------------------------ ترب‌پی
    def torob_routes(self, **over):
        r = {
            "/oauth/token": (200, {"access_token": "T", "expires_in": 3600}),
            "/offer/v1/eligible": (200, {"successful": True, "response": {"eligible": True}}),
            "/payment/v1/token": (200, {"successful": True, "response": {"paymentToken": "PT",
                                                                          "paymentPageUrl": "https://pay.torobpay.com/x"}}),
            "/payment/v1/verify": (200, {"successful": True, "response": {}}),
            "/payment/v1/settle": (200, {"successful": True, "response": {"transactionId": "TX9"}}),
            "/payment/v1/cancel": (200, {"successful": True}),
            "/payment/v1/status": (200, {"successful": True, "response": {"status": "VERIFY"}}),
        }
        r.update(over)
        return FakeHttp(r)

    def test_torobpay_full_flow_and_cancel(self):
        fh = self.torob_routes()
        with mock.patch.object(bnpl, "http", fh):
            r = self.client.get("/checkout/")
            self.assertContains(r, "ترب‌پی")
            r = self.client.post("/checkout/", self.checkout_data(gateway="torobpay"))
            self.assertRedirects(r, "https://pay.torobpay.com/x", fetch_redirect_response=False)
            pay = Payment.objects.get()
            tok = [c for c in fh.calls if c[1].endswith("/payment/v1/token")][0][2]
            self.assertEqual(tok["amount"], 200_000_000)
            self.assertEqual(tok["mobile"], "+989121234567")
            self.assertEqual(tok["cartList"][0]["totalAmount"], 200_000_000)
            ret = parse_qs(urlparse(tok["returnURL"]).query)
            # بازگشت با تراکنش اشتباه پذیرفته نمی‌شود
            self.client.post(f"/pay/torobpay/callback/?pid={pay.pk}&tx=bad", {"state": "OK"})
            pay.refresh_from_db()
            self.assertEqual(pay.status, "failed")
            pay.status = "init"
            pay.save()
            r = self.client.post(f"/pay/torobpay/callback/?pid={pay.pk}&tx={ret['tx'][0]}", {"state": "OK"})
        pay.refresh_from_db()
        self.assertEqual((pay.status, pay.ref_id, pay.order.status), ("ok", "TX9", "paid"))
        # لغو در پنل ← cancel در ترب‌پی
        order = pay.order
        with mock.patch.object(bnpl, "http", fh):
            order.status = "cancelled"
            msgs = bnpl.on_status(order, "paid")
        self.assertTrue(msgs and msgs[0][0])
        self.assertTrue(any(c[1].endswith("/payment/v1/cancel") for c in fh.calls))

    def test_torobpay_settle_retry(self):
        fh = self.torob_routes(**{"/payment/v1/settle": (200, {"successful": False, "errorData": {"errorCode": 1}})})
        with mock.patch.object(bnpl, "http", fh):
            self.client.post("/checkout/", self.checkout_data(gateway="torobpay"))
            pay = Payment.objects.get()
            self.client.post(f"/pay/torobpay/callback/?pid={pay.pk}&tx={pay.raw['tx']}", {"state": "OK"})
        pay.refresh_from_db()
        self.assertEqual(pay.status, "ok")
        self.assertTrue(pay.raw["callback"]["settle_pending"])
        fh.routes["/payment/v1/settle"] = (200, {"successful": True, "response": {}})
        with mock.patch.object(bnpl, "http", fh):
            self.assertEqual(bnpl.retry_settles(), 1)
            self.assertEqual(bnpl.retry_settles(), 0)

    def test_torobpay_failed_state_and_not_for_deposit(self):
        fh = self.torob_routes()
        with mock.patch.object(bnpl, "http", fh):
            r = self.client.post("/checkout/", self.checkout_data(gateway="torobpay", payment_mode="deposit"))
            self.assertContains(r, "فقط برای پرداخت کامل")
            self.assertFalse(Order.objects.exists())
            self.client.post("/checkout/", self.checkout_data(gateway="torobpay"))
            pay = Payment.objects.get()
            self.client.post(f"/pay/torobpay/callback/?pid={pay.pk}&tx={pay.raw['tx']}", {"state": "FAILED"})
        pay.refresh_from_db()
        self.assertEqual(pay.status, "failed")
        self.assertFalse(any(c[1].endswith("/verify") for c in fh.calls))

    def test_torobpay_hidden_when_not_eligible(self):
        fh = self.torob_routes(**{"/offer/v1/eligible": (200, {"successful": True, "response": {"eligible": False}})})
        with mock.patch.object(bnpl, "http", fh):
            r = self.client.get("/checkout/")
        self.assertNotContains(r, 'value="torobpay"')

    # ------------------------------------------------------------ دیجی‌پی
    def dp_routes(self, **over):
        r = {
            "/oauth/token": (200, {"access_token": "D", "expires_in": 3600}),
            "/tickets/business": (200, {"result": {"status": 0}, "ticket": "TK", "redirectUrl": "https://uat.mydigipay.info/pay/TK"}),
            "/purchases/verify": (200, {"result": {"status": 0}, "trackingCode": "TR1", "amount": 200_000_000, "rrn": "R1",
                                        "maskedPan": "6037**12"}),
            "/purchases/deliver": (200, {"result": {"status": 0}}),
        }
        r.update(over)
        return FakeHttp(r)

    def test_digipay_bnpl_flow_and_deliver(self):
        fh = self.dp_routes()
        with mock.patch.object(bnpl, "http", fh):
            r = self.client.get("/checkout/")
            self.assertContains(r, 'value="dp_bnpl"')
            self.assertContains(r, 'value="dp_ipg"')
            self.assertNotContains(r, 'value="dp_wallet"')  # خاموش
            r = self.client.post("/checkout/", self.checkout_data(gateway="dp_bnpl"))
            self.assertRedirects(r, "https://uat.mydigipay.info/pay/TK", fetch_redirect_response=False)
            pay = Payment.objects.get()
            m, url, body, h = [c for c in fh.calls if "/tickets/business" in c[1]][0]
            self.assertIn("type=13", url)
            self.assertEqual(h["Digipay-Version"], "2022-02-02")
            self.assertEqual((body["amount"], body["providerId"]), (200_000_000, f"IC{pay.pk}"))
            self.assertEqual(body["basketDetailsDto"]["items"][0]["count"], 1)
            tok = [c for c in fh.calls if c[1].endswith("/oauth/token")][0]
            self.assertTrue(tok[3]["Authorization"].startswith("Basic "))
            # مبلغ دست‌کاری‌شده رد می‌شود
            cb = {"result": "SUCCESS", "amount": "100", "providerId": f"IC{pay.pk}", "trackingCode": "TR1", "type": "13"}
            self.client.post(f"/pay/dp_bnpl/callback/?pid={pay.pk}", cb)
            pay.refresh_from_db()
            self.assertEqual(pay.status, "failed")
            pay.status = "init"
            pay.save()
            cb["amount"] = "200000000"
            self.client.post(f"/pay/dp_bnpl/callback/?pid={pay.pk}", cb)
        pay.refresh_from_db()
        self.assertEqual((pay.status, pay.ref_id, pay.order.status), ("ok", "TR1", "paid"))
        v = [c for c in fh.calls if "/purchases/verify" in c[1]][0]
        self.assertEqual(v[2], {"trackingCode": "TR1", "providerId": f"IC{pay.pk}"})
        order = pay.order
        with mock.patch.object(bnpl, "http", fh):
            order.status = "shipped"
            msgs = bnpl.on_status(order, "paid")
            self.assertEqual(msgs, [(True, "تحویل سفارش به دیجی‌پی اعلام شد.")])
            self.assertEqual(bnpl.on_status(order, "processing"), [])  # بار دوم دوباره اعلام نمی‌شود
        d = [c for c in fh.calls if "/purchases/deliver" in c[1]]
        self.assertEqual(len(d), 1)
        self.assertIn("type=13", d[0][1])
        self.assertEqual(d[0][2]["invoiceNumber"], str(order.number))

    def test_digipay_credit_limits_and_failed(self):
        s = ShopSettings.load()
        s.digipay_credit_max = 10_000_000
        s.save()
        fh = self.dp_routes()
        with mock.patch.object(bnpl, "http", fh):
            r = self.client.get("/checkout/")
            self.assertNotContains(r, 'value="dp_bnpl"')  # بالای سقف
            self.client.post("/checkout/", self.checkout_data(gateway="dp_ipg"))
            pay = Payment.objects.get()
            self.client.post(f"/pay/dp_ipg/callback/?pid={pay.pk}", {"result": "FAILED", "providerId": f"IC{pay.pk}"})
        pay.refresh_from_db()
        self.assertEqual(pay.status, "failed")
        body = [c for c in fh.calls if "/tickets/business" in c[1]][0][2]
        self.assertNotIn("basketDetailsDto", body)  # کارت سبد لازم ندارد

    def test_product_widget(self):
        r = self.client.get(self.p.get_absolute_url())
        self.assertContains(r, "torobLine")
        self.assertContains(r, "۴ قسط ۲٬۵۰۰٬۰۰۰ تومان")
