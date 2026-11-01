"""آزمون اتصال خودکار بتا (بانک رفاه): کلاینت، روند صفحهٔ سفارش، بازیابی ثبت، پنل."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from catalog.models import Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import Order, Payment

from . import beta
from .models import BetaSale, BetaSettings, InstallmentPlan

NC = "0012345679"


class FakeBank:
    """پاسخ‌های ساختگی سامانهٔ بتا؛ calls: [(method, path, body)]."""

    def __init__(self, credit=50_000_000, consume=None):
        self.credit, self.calls, self.consume_result = credit, [], consume or (200, {"status": 200, "data": 98765})
        self.registered = None

    def __call__(self, method, url, headers, body=None, form=None):
        path = url.split("api.rb24.ir", 1)[1]
        self.calls.append((method, path, body or form, headers))
        if path == "/connect/token":
            return 200, {"access_token": "tok", "expires_in": 3600}
        assert headers["Authorization"] == "Bearer tok" and headers["apikey"] == "KEY"
        if path.endswith("/inquiry"):
            return 200, {"status": 200, "data": {"nationalCode": NC, "credit": self.credit, "cellphone": "09121112233"}}
        if path == "/beta/1.0/date/validate":
            return 200, {"data": {"data": {"1405/09": "آذر - 1405", "1405/10": "دی - 1405"}}}
        if path.endswith("/request"):
            return 200, {"status": 200, "message": ""}
        if path.endswith("/consume"):
            if body.get("otp") != "12345":
                return 200, {"status": 4446, "message": "otp"}
            r = self.consume_result
            if isinstance(r, Exception):
                self.registered = body["requestId"]
                raise r
            return r
        if path.startswith("/beta/1.0/order/") and path.endswith("/installments"):
            return 200, {"status": 200, "data": {"totalRecords": 2, "data": [
                {"id": 1, "amount": 60_000_000, "overdueDate": "2026-11-21T00:00:00", "settelDate": "2026-11-22T00:00:00",
                 "isSetteled": True, "status": 2, "statusTitle": "وصول موفق", "isDeleted": False},
                {"id": 2, "amount": 60_000_000, "overdueDate": "2026-12-21T00:00:00", "settelDate": None,
                 "isSetteled": False, "status": 0, "statusTitle": "ثبت شده", "isDeleted": False}]}}
        if path.startswith("/beta/1.0/order/"):
            rid = path.rsplit("/", 1)[1]
            if rid == self.registered:
                return 200, {"status": 200, "data": {"id": 55555, "title": "x"}}
            return 200, {"status": 4460, "message": "not found"}
        return 404, {}


def setup_beta():
    s = BetaSettings.load()
    s.enabled, s.client_id, s.client_secret, s.api_key = True, "icsd", "SECRET", "KEY"
    s.save()
    cache.clear()
    return s


class ClientTests(TestCase):
    def setUp(self):
        self.s = setup_beta()

    def test_token_cached_and_errors_mapped(self):
        bank = FakeBank()
        with mock.patch.object(beta, "_http", bank):
            self.assertEqual(beta.inquiry(NC)["credit"], 5_000_000)  # ریال ← تومان
            self.assertEqual(beta.months()[0], ("1405/09", "آذر - 1405"))
        self.assertEqual(sum(1 for c in bank.calls if c[1] == "/connect/token"), 1)
        token_call = bank.calls[0]
        self.assertEqual(token_call[2]["client_secret"], "SECRET")
        self.assertEqual(bank.calls[1][3]["TerminalName"], "icsd")
        self.assertNotIn(NC, str(beta.recent_calls()))  # کد ملی در گزارش نیمه است
        with mock.patch.object(beta, "_http", lambda *a, **k: (200, {"status": 4450, "message": "x"})):
            cache.set(beta.TOKEN_KEY, "tok")
            with self.assertRaises(beta.BetaError) as e:
                beta.inquiry(NC)
        self.assertTrue(e.exception.is_customer)
        self.assertIn("اجازه‌نامه", e.exception.customer_text)
        with mock.patch.object(beta, "_http", lambda *a, **k: (200, {"status": 4470})):
            with self.assertRaises(beta.BetaError) as e:
                beta.months()
        self.assertEqual(e.exception.customer_text, beta.SHOP_PROBLEM)
        self.assertIn("فعال نشده", e.exception.admin_text)

    def test_panel_test_button(self):
        staff = get_user_model().objects.create_user("staff", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        r = self.client.get("/panel/settings/?tab=beta")
        self.assertContains(r, "آزمایش اتصال")
        self.assertNotContains(r, "SECRET")
        with mock.patch.object(beta, "_http", FakeBank()):
            r = self.client.post("/panel/settings/", {"tab": "beta", "do": "beta_test"}, follow=True)
        self.assertContains(r, "اتصال برقرار است")
        self.assertContains(r, "آذر - 1405")


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", STAGING=True, SITE_URL="https://irancarpet.net")
class FlowTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        album = Album.objects.create(name="700 شانه", base_size=s["12-meter"], base_price=Decimal("35000000"))
        album.sizes.set([s["12-meter"]])
        p = Product.objects.create(title="فرش 700 شانه", slug="f700", album=album, status="publish")
        sync_album_variations([p], reset=True)
        self.user = get_user_model().objects.create_user("09121234567", first_name="علی", last_name="رضایی")
        self.client.force_login(self.user)
        self.client.post("/cart/add/", {"variation": p.variations.first().pk, "qty": 1})
        self.plan = InstallmentPlan.objects.get(kind="beta")
        self.s = setup_beta()

    def place(self, down=20, months=12):
        data = {"first_name": "علی", "last_name": "رضایی", "mobile": "09121234567", "province": "تهران", "city": "تهران",
                "address": "خیابان آزادی", "payment_mode": "installment", "gateway": "", "inst_plan": self.plan.pk,
                "inst_down": down, "inst_months": months, "inst_step": 1, "inst_holder_name": "علی رضایی",
                "inst_national_code": NC}
        r = self.client.post("/checkout/", data)
        o = Order.objects.get()
        self.assertRedirects(r, o.get_absolute_url() + "?placed=1", fetch_redirect_response=False)
        return o

    def act(self, o, **data):
        return self.client.post(o.get_absolute_url() + "beta/", data, follow=True)

    def test_checkout_asks_only_national_code_and_defers_down(self):
        r = self.client.get("/checkout/")
        self.assertContains(r, "رمزی که بانک رفاه پیامک می‌کند")
        self.assertNotIn("sms_mobile", [k for k, _, _ in self.plan.info_fields])
        o = self.place(down=20)
        self.assertEqual((o.status, o.installment_state), ("on_hold", "review"))  # پیش‌پرداخت بعد از تأیید بتا
        self.assertFalse(Payment.objects.exists())
        with mock.patch.object(beta, "_http", FakeBank()):
            r = self.client.get(o.get_absolute_url() + "?placed=1")
        self.assertContains(r, "تأیید خرید در سامانهٔ بتا")
        self.assertContains(r, "بررسی اعتبار")
        self.assertContains(r, "همین صفحه")

    def test_full_flow_registers_sale(self):
        o = self.place(down=0, months=12)
        bank = FakeBank(credit=200_000_000)  # ۲۰ میلیون تومان در ماه
        with mock.patch.object(beta, "_http", bank):
            r = self.act(o, do="check")
            self.assertContains(r, "کافی است")
            r = self.act(o, do="otp", ym="1405/10")
            self.assertContains(r, "۰۹۱۲•••۲۳۳")  # داخل bdi/LRI
            req = next(c for c in bank.calls if c[1].endswith("/request"))
            o.refresh_from_db()
            self.assertEqual(req[2]["amount"], o.installment["installment"] * 12 * 10)
            self.assertEqual((req[2]["numberOfInstallments"], req[2]["startDateYearMonth"]), (12, "1405/10"))
            r = self.act(o, do="confirm", otp="11111")
            self.assertContains(r, "رمز یک‌بارمصرف درست نیست")
            r = self.act(o, do="confirm", otp="۱۲۳۴۵")
            self.assertContains(r, "ثبت شد")
        cons = [c for c in bank.calls if c[1].endswith("/consume")][-1][2]
        self.assertEqual(cons["amount"], req[2]["amount"])
        o.refresh_from_db()
        sale = BetaSale.objects.get()
        self.assertEqual((sale.sale_id, sale.paid_count), (98765, 1))
        self.assertEqual((o.installment_state, o.status), ("done", "processing"))
        self.assertEqual(o.installment["schedule"][0]["jdate"], "1405/10")
        self.assertEqual(o.installment["schedule"][-1]["jdate"], "1406/09")
        self.assertNotContains(self.client.get(o.get_absolute_url()), "تأیید خرید در سامانهٔ بتا")
        staff = get_user_model().objects.create_user("staff", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        r = self.client.get(f"/panel/orders/{o.pk}/view/")
        self.assertContains(r, "فروش 98765")
        self.assertContains(r, "وصول شد")
        self.assertContains(self.client.get("/panel/beta/"), "98765")

    def test_insufficient_credit_suggests_more_months_and_blocks_otp(self):
        o = self.place(down=0, months=2)
        with mock.patch.object(beta, "_http", FakeBank(credit=100_000_000)):  # ۱۰ میلیون تومان
            r = self.act(o, do="check")
            self.assertContains(r, "کافی نیست")
            r = self.act(o, do="otp", ym="1405/09")
            self.assertContains(r, "بیشتر است")
            sale = BetaSale.objects.get()
            m = __import__("installments.betaflow", fromlist=["x"]).suggest(o, sale)
            self.assertTrue(m and m > 2)
            self.act(o, do="change", months=m, down=0)
            o.refresh_from_db()
            self.assertEqual(o.installment["months"], m)
            r = self.act(o, do="otp", ym="1405/09")
            self.assertContains(r, "پیامک شد")

    def test_lost_response_recovered_by_request_id(self):
        o = self.place(down=0, months=12)
        bank = FakeBank(credit=200_000_000, consume=TimeoutError("timed out"))
        with mock.patch.object(beta, "_http", bank):
            self.act(o, do="check")
            self.act(o, do="otp", ym="1405/09")
            r = self.act(o, do="confirm", otp="12345")
        self.assertContains(r, "ثبت شد")
        self.assertEqual(BetaSale.objects.get().sale_id, 55555)

    def test_daily_inquiry_limit(self):
        self.s.daily_limit = 2
        self.s.save()
        o = self.place()
        with mock.patch.object(beta, "_http", FakeBank()):
            self.act(o, do="check")
            self.act(o, do="check")
            r = self.act(o, do="check")
        self.assertContains(r, "بیش از حد مجاز")

    def test_other_users_cannot_act(self):
        o = self.place()
        other = get_user_model().objects.create_user("09120000000")
        self.client.force_login(other)
        with mock.patch.object(beta, "_http", FakeBank()) as bank:
            r = self.client.post(o.get_absolute_url() + "beta/", {"do": "check"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(bank.calls)

    def test_disabled_keeps_manual_flow(self):
        self.s.enabled = False
        self.s.save()
        plan = InstallmentPlan.objects.get(kind="beta")
        self.assertIn("sms_mobile", [k for k, _, _ in plan.info_fields])
        self.assertTrue(plan.down_at_checkout)
