"""آزمون مسیر خرید: سبد، ورود پیامکی، تسویه، پرداخت (درگاه آزمایشی، سامان و زرین‌پال شبیه‌سازی‌شده)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import Profile
from catalog.models import Product, Variation
from pricing.models import PricingSettings, Size, seed_sizes

from . import gateways
from .models import Order, Payment, ShopSettings


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True,
                   SEP_TERMINAL_ID="12345678", ZARINPAL_MERCHANT_ID="x" * 36)
class ShopFlowTests(TestCase):
    def setUp(self):
        seed_sizes()
        PricingSettings.load()
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه هانا", slug="hana")
        s6 = Size.objects.get(slug="6-meter")
        s12 = Size.objects.get(slug="12-meter")
        self.v6 = Variation.objects.create(product=self.p, size=s6, manual_price=20_000_000)
        self.v12 = Variation.objects.create(product=self.p, size=s12, manual_price=40_000_000)
        self.pair = Variation.objects.create(product=self.p, size=s6, manual_price=10_000_000, pair_only=True)
        self.p.refresh_price_cache()

    # ---------------------------------------------------------- کمک‌ها
    def otp_login(self, mobile="09121234567", name="علی رضایی"):
        r = self.client.post("/my-account/login/", {"action": "otp", "mobile": mobile, "next": "/checkout/"})
        self.assertEqual(r.status_code, 302)
        code = self.client.session["dev_otp"]
        r = self.client.post("/my-account/verify/", {"code": code, "name": name, "next": "/checkout/"})
        self.assertRedirects(r, "/checkout/", fetch_redirect_response=False)

    def checkout_data(self, **kw):
        d = {"first_name": "علی", "last_name": "رضایی", "mobile": "۰۹۱۲۱۲۳۴۵۶۷", "province": "تهران", "city": "تهران",
             "address": "خیابان آزادی", "postal_code": "1234567890", "payment_mode": "full", "gateway": "fake"}
        d.update(kw)
        return d

    # ---------------------------------------------------------- سبد
    def test_cart_add_and_pair_only(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.client.post("/cart/add/", {"variation": self.pair.pk, "qty": 1})
        cart = self.client.session["cart"]
        self.assertEqual(cart[str(self.v6.pk)], 1)
        self.assertEqual(cart[str(self.pair.pk)], 2)
        r = self.client.get("/cart/")
        self.assertContains(r, "۴۰٬۰۰۰٬۰۰۰")  # ۲۰ + ۲×۱۰ میلیون

    def test_unavailable_variation_rejected(self):
        self.v6.is_available = False
        self.v6.save()
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.assertFalse(self.client.session.get("cart"))

    # ---------------------------------------------------------- ورود
    def test_checkout_requires_login_and_otp_creates_user(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        r = self.client.get("/checkout/")
        self.assertRedirects(r, "/my-account/login/?next=/checkout/", fetch_redirect_response=False)
        self.otp_login()
        u = get_user_model().objects.get(username="09121234567")
        self.assertEqual(u.first_name, "علی")
        self.assertEqual(u.profile.mobile, "09121234567")
        self.assertEqual(self.client.get("/checkout/").status_code, 200)

    def test_wrong_otp_and_password_login_with_wp_hash(self):
        User = get_user_model()
        u = User.objects.create(username="old_customer", email="a@b.com")
        # هش phpass وردپرس برای رمز «test12345»
        import hashlib

        from core.hashers import ITOA64, _encode64
        salt, pw = "abcdefgh", b"test12345"
        h = hashlib.md5(salt.encode() + pw).digest()
        for _ in range(1 << ITOA64.index("B")):
            h = hashlib.md5(h + pw).digest()
        u.password = "phpass$$P$B" + salt + _encode64(h, 16)
        u.save()
        Profile.objects.create(user=u, mobile="09351112233")
        r = self.client.post("/my-account/login/", {"action": "password", "identifier": "۰۹۳۵۱۱۱۲۲۳۳", "password": "test12345"})
        self.assertEqual(r.status_code, 302)
        self.client.post("/my-account/logout/")
        r = self.client.post("/my-account/login/", {"action": "password", "identifier": "a@b.com", "password": "bad"})
        self.assertContains(r, "رمز درست نیست")

    def test_otp_rate_limit(self):
        self.client.post("/my-account/login/", {"action": "otp", "mobile": "09121234567"})
        r = self.client.post("/my-account/login/", {"action": "otp", "mobile": "09121234567"})
        self.assertContains(r, "کمتر از یک دقیقه")

    # ---------------------------------------------------------- پرداخت
    def test_full_payment_fake_gateway_free_shipping(self):
        ShopSettings.objects.update_or_create(pk=1, defaults={"free_shipping_min": 50_000_000})
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 2})  # ۸۰ میلیون
        self.otp_login()
        r = self.client.post("/checkout/", self.checkout_data())
        order = Order.objects.get()
        self.assertEqual(order.shipping_mode, "free")
        self.assertEqual(order.online_amount, 80_000_000)
        self.assertEqual(order.number, Order.NUMBER_START)
        pay = order.payments.get()
        self.assertRedirects(r, f"/pay/fake/{pay.pk}/", fetch_redirect_response=False)
        r = self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        self.assertRedirects(r, f"/my-account/orders/{order.number}/?paid=1", fetch_redirect_response=False)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.paid_amount, 80_000_000)
        r = self.client.get(f"/my-account/orders/{order.number}/?paid=1")
        self.assertContains(r, "سفارشتان ثبت شد")
        self.assertFalse(self.client.session.get("cart"))
        # کال‌بک تکراری چیزی را دوباره حساب نمی‌کند
        self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        order.refresh_from_db()
        self.assertEqual(order.paid_amount, 80_000_000)

    def test_full_payment_below_threshold_is_cod(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        self.client.post("/checkout/", self.checkout_data())
        self.assertEqual(Order.objects.get().shipping_mode, "cod")

    def test_deposit_payment(self):
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 2})
        self.otp_login()
        self.client.post("/checkout/", self.checkout_data(payment_mode="deposit"))
        order = Order.objects.get()
        self.assertEqual(order.online_amount, 8_000_000)
        self.assertEqual(order.shipping_mode, "cod")  # بیعانه همیشه پس‌کرایه
        pay = order.payments.get()
        self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        order.refresh_from_db()
        self.assertEqual(order.status, "deposit_paid")
        self.assertEqual(order.remaining, 72_000_000)

    def test_failed_payment_then_retry(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        self.client.post("/checkout/", self.checkout_data())
        order = Order.objects.get()
        pay = order.payments.get()
        self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=0")
        order.refresh_from_db()
        self.assertEqual(order.status, "pending")
        r = self.client.post(f"/my-account/orders/{order.number}/pay/", {"gateway": "fake"})
        self.assertEqual(order.payments.count(), 2)
        self.assertEqual(r.status_code, 302)

    def test_sep_flow_mocked(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        with mock.patch.object(gateways, "post_json", return_value={"status": 1, "token": "TKN"}) as pj:
            r = self.client.post("/checkout/", self.checkout_data(gateway="sep"))
            sent = pj.call_args[0][1]
        self.assertEqual(sent["Amount"], 200_000_000)  # ریال
        self.assertContains(r, 'action="https://sep.shaparak.ir/OnlinePG/OnlinePG"')
        pay = Payment.objects.get()
        verify = {"ResultCode": 0, "Success": True, "TransactionDetail": {"RRN": "999", "OrginalAmount": 200_000_000, "AffectiveAmount": 200_000_000, "MaskedPan": "6037**1234"}}
        with mock.patch.object(gateways, "post_json", return_value=verify):
            r = self.client.post("/pay/sep/callback/", {"State": "OK", "Status": "2", "RefNum": "REF1", "ResNum": pay.res_num})
        pay.refresh_from_db()
        self.assertEqual(pay.status, "ok")
        self.assertEqual(pay.order.status, "paid")
        # همان RefNum برای تراکنش دیگر پذیرفته نمی‌شود
        pay2 = Payment.objects.create(order=pay.order, gateway="sep", amount=pay.amount)
        with mock.patch.object(gateways, "post_json", return_value=verify):
            self.client.post("/pay/sep/callback/", {"State": "OK", "Status": "2", "RefNum": "REF1", "ResNum": pay2.res_num})
        pay2.refresh_from_db()
        self.assertEqual(pay2.status, "failed")

    def test_sep_amount_mismatch_reverses(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        with mock.patch.object(gateways, "post_json", return_value={"status": 1, "token": "TKN"}):
            self.client.post("/checkout/", self.checkout_data(gateway="sep"))
        pay = Payment.objects.get()
        calls = []

        def fake(url, data, timeout=20):
            calls.append(url)
            return {"ResultCode": 0, "Success": True, "TransactionDetail": {"OrginalAmount": 1000, "AffectiveAmount": 1000}}
        with mock.patch.object(gateways, "post_json", side_effect=fake):
            self.client.post("/pay/sep/callback/", {"State": "OK", "Status": "2", "RefNum": "R9", "ResNum": pay.res_num})
        pay.refresh_from_db()
        self.assertEqual(pay.status, "failed")
        self.assertTrue(any("Reverse" in u for u in calls))

    def test_zarinpal_flow_mocked(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        with mock.patch.object(gateways, "post_json", return_value={"data": {"code": 100, "authority": "A000123"}}):
            r = self.client.post("/checkout/", self.checkout_data(gateway="zarinpal"))
        self.assertEqual(r["Location"], "https://payment.zarinpal.com/pg/StartPay/A000123")
        with mock.patch.object(gateways, "post_json", return_value={"data": {"code": 100, "ref_id": 777, "card_pan": "6219**1111"}}):
            self.client.get("/pay/zarinpal/callback/?Authority=A000123&Status=OK")
        self.assertEqual(Order.objects.get().status, "paid")
        self.assertEqual(Payment.objects.get().ref_id, "777")

    def test_other_users_order_hidden_and_tracking(self):
        self.client.post("/cart/add/", {"variation": self.v6.pk, "qty": 1})
        self.otp_login()
        self.client.post("/checkout/", self.checkout_data())
        order = Order.objects.get()
        self.client.post("/my-account/logout/")
        self.otp_login(mobile="09130000000")
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)
        r = self.client.post("/track-order/", {"number": str(order.number), "mobile": "09121234567"})
        self.assertContains(r, "در انتظار پرداخت")

    def test_legacy_urls(self):
        self.assertEqual(self.client.get("/checkout-2/").status_code, 301)
        r = self.client.get("/my-account/orders/")
        self.assertRedirects(r, "/my-account/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/cart/").status_code, 200)
