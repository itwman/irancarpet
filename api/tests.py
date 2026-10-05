import json
from decimal import Decimal

from django.test import TestCase, override_settings

from catalog.models import Category, Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import Order, Payment

from .models import AppNotification, Device


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True)
class AppApiTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("35000000"),
                                          shipping_fixed=500_000, waste_value=3_000_000)
        self.album.sizes.set([s["12-meter"], s["9-meter"], s["runner-4x1"]])
        self.album.even_sizes.set([s["runner-4x1"]])
        self.cat = Category.objects.create(name="فرش ۷۰۰ شانه", slug="700")
        self.p = Product.objects.create(title="فرش 700 شانه نقشه سناتور", slug="senator", album=self.album, status="publish")
        self.p.categories.add(self.cat)
        sync_album_variations([self.p], reset=True)
        self.v12 = self.p.variations.get(size=s["12-meter"])
        self.runner = self.p.variations.get(size=s["runner-4x1"])

    def post(self, url, data, token=None):
        h = {"HTTP_AUTHORIZATION": f"Token {token}"} if token else {}
        return self.client.post(url, json.dumps(data), content_type="application/json", **h)

    def login(self, mobile="09121234567"):
        r = self.post("/api/app/v1/auth/otp/", {"mobile": "۰۹۱۲۱۲۳۴۵۶۷"})
        self.assertEqual(r.status_code, 200, r.content)
        code = r.json()["dev_code"]
        r = self.post("/api/app/v1/auth/verify/", {"mobile": mobile, "code": code, "name": "علی رضایی", "device": "Pixel"})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["token"]

    def test_catalog(self):
        c = self.client.get("/api/app/v1/config/", HTTP_X_INSTALL_ID="abc", HTTP_X_APP_VERSION="1.0.0").json()
        self.assertIn("fake", [g["key"] for g in c["gateways"]])
        self.assertTrue(Device.objects.filter(install_id="abc", app_version="1.0.0").exists())
        r = self.client.get("/api/app/v1/products/", {"category": self.cat.pk}).json()
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["results"][0]["price"], 40_750_000)
        self.assertFalse(r["results"][0]["price_is_from"])
        self.assertEqual(r["results"][0]["reeds"], "700")
        self.assertEqual(self.client.get("/api/app/v1/products/", {"q": "سناتور"}).json()["count"], 1)
        d = self.client.get(f"/api/app/v1/products/{self.p.pk}/").json()
        sizes = {x["label"]: x for x in d["sizes"]}
        self.assertEqual(len(sizes), 3)
        runner = next(x for x in d["sizes"] if x["pair_only"])
        self.assertEqual((runner["width"], runner["length"]), (1.0, 4.0))
        self.assertEqual(self.client.get("/api/app/v1/products/99999/").status_code, 404)
        self.assertEqual(self.client.get("/api/app/v1/categories/").json()[0]["count"], 1)
        self.assertEqual(self.client.get("/api/app/v1/home/").status_code, 200)

    def test_cart_quote_pairs(self):
        q = self.post("/api/app/v1/cart/quote/", {"items": [{"variation": self.runner.pk, "qty": 1}, {"variation": self.v12.pk, "qty": 1}]}).json()
        runner = next(x for x in q["lines"] if x["variation"] == self.runner.pk)
        self.assertEqual(runner["qty"], 2)
        self.assertEqual(q["total"], 40_750_000 + 2 * 13_590_000)

    def test_login_order_and_pay(self):
        self.assertEqual(self.client.get("/api/app/v1/orders/").status_code, 401)
        tok = self.login()
        me = self.client.get("/api/app/v1/me/", HTTP_AUTHORIZATION=f"Token {tok}").json()
        self.assertEqual((me["first_name"], me["mobile"]), ("علی", "09121234567"))
        bad = self.post("/api/app/v1/orders/create/", {"items": [{"variation": self.v12.pk, "qty": 1}]}, tok)
        self.assertEqual(bad.status_code, 400)
        self.assertIn("address", bad.json()["errors"])
        r = self.post("/api/app/v1/orders/create/", {
            "items": [{"variation": self.v12.pk, "qty": 1}], "first_name": "علی", "last_name": "رضایی", "mobile": "09121234567",
            "province": "تهران", "city": "تهران", "address": "خیابان آزادی", "postal_code": "۱۲۳۴۵۶۷۸۹۰",
            "payment_mode": "deposit", "gateway": "fake"}, tok)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        order = Order.objects.get(number=data["order"]["number"])
        self.assertEqual(order.online_amount, 4_075_000)
        # مرورگر: صفحهٔ پرداخت → درگاه آزمایشی → برگشت به اپ
        pay_path = data["pay_url"].split("testserver")[1]
        r = self.client.get(pay_path)
        self.assertEqual(r.status_code, 302)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.raw.get("source"), "app")
        r = self.client.post("/pay/fake/callback/", {"pid": payment.pk, "ok": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(f"/app/return/{order.number}/?paid=1"), r["Location"])
        page = self.client.get(r["Location"]).content.decode()
        self.assertIn("intent://order/", page)
        o = self.client.get(f"/api/app/v1/orders/{order.number}/", HTTP_AUTHORIZATION=f"Token {tok}").json()
        self.assertEqual(o["status"], "deposit_paid")
        self.assertEqual(len(self.client.get("/api/app/v1/orders/", HTTP_AUTHORIZATION=f"Token {tok}").json()), 1)
        self.assertEqual(self.client.get("/api/app/v1/pay/bad-token/").status_code, 404)

    def test_wishlist_and_notifications(self):
        tok = self.login()
        w = self.post("/api/app/v1/wishlist/", {"add": [self.p.pk]}, tok).json()
        self.assertEqual(w["ids"], [self.p.pk])
        d = self.client.get(f"/api/app/v1/products/{self.p.pk}/", HTTP_AUTHORIZATION=f"Token {tok}").json()
        self.assertTrue(d["in_wishlist"])
        self.assertEqual(self.post("/api/app/v1/wishlist/", {"remove": [self.p.pk]}, tok).json()["ids"], [])
        AppNotification.objects.create(title="تخفیف پاییزه", body="۱۰٪ تخفیف", kind="deal", product=self.p)
        n = self.client.get("/api/app/v1/notifications/").json()
        self.assertEqual(n[0]["product_id"], self.p.pk)
        self.assertEqual(self.client.get("/api/app/v1/notifications/", {"since": n[0]["created_at"]}).json(), [])
        self.assertEqual(self.post("/api/app/v1/auth/logout/", {}, tok).status_code, 200)
        self.assertEqual(self.client.get("/api/app/v1/me/", HTTP_AUTHORIZATION=f"Token {tok}").status_code, 401)


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True)
class AppInstallmentTests(AppApiTests):
    def test_config_quote_and_pricelist(self):
        c = self.client.get("/api/app/v1/config/").json()
        kinds = [p["kind"] for p in c["installment"]["plans"]]
        self.assertEqual(kinds, ["cheque", "beta"])
        cheque = c["installment"]["plans"][0]
        self.assertIn("cheque_image", [f["key"] for f in cheque["fields"]])
        q = self.client.get("/api/app/v1/installments/quote/", {"plan": cheque["id"], "total": 100_000_000, "down": 50,
                                                                 "months": 2, "step": 1}).json()
        self.assertEqual(q["interest_percent"], 9.0)
        pl = self.client.get("/api/app/v1/pricelist/").json()
        self.assertEqual(pl["groups"][0]["albums"][0]["base_price"], 40_750_000)
        r = self.client.get("/api/app/v1/products/", {"album": self.album.pk}).json()
        self.assertEqual(r["count"], 1)

    def test_installment_order_multipart(self):
        import io as _io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from installments.models import InstallmentPlan

        tok = self.login()
        plan = InstallmentPlan.objects.get(kind="cheque")
        buf = _io.BytesIO()
        Image.new("RGB", (300, 150), (220, 220, 240)).save(buf, "JPEG")
        data = {
            "items": json.dumps([{"variation": self.v12.pk, "qty": 1}]), "first_name": "علی", "last_name": "رضایی",
            "mobile": "09121234567", "province": "تهران", "city": "تهران", "address": "خیابان آزادی",
            "payment_mode": "installment", "gateway": "fake", "inst_plan": plan.pk, "inst_down": 50, "inst_months": 6,
            "inst_step": 1, "inst_holder_name": "علی رضایی", "inst_national_code": "0012345679",
            "inst_cheque_image": SimpleUploadedFile("c.jpg", buf.getvalue(), content_type="image/jpeg"),
        }
        with self.settings(PRIVATE_ROOT=__import__("tempfile").mkdtemp()):
            r = self.client.post("/api/app/v1/orders/create/", data, HTTP_AUTHORIZATION=f"Token {tok}")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertTrue(d["pay_url"])
        inst = d["order"]["installment"]
        self.assertEqual((inst["count"], inst["state"], inst["interest_percent"]), (6, "review", 21.0))
        self.assertEqual(d["order"]["payment_mode"], "installment")
        # بازنشستگان بدون پیش‌پرداخت: بدون درگاه
        beta = InstallmentPlan.objects.get(kind="beta")
        r = self.post("/api/app/v1/orders/create/", {
            "items": [{"variation": self.v12.pk, "qty": 1}], "first_name": "علی", "last_name": "رضایی", "mobile": "09121234567",
            "province": "تهران", "city": "تهران", "address": "خیابان آزادی", "payment_mode": "installment",
            "inst_plan": beta.pk, "inst_down": 0, "inst_months": 12, "inst_step": 1, "inst_holder_name": "علی رضایی",
            "inst_national_code": "0012345679", "inst_pensioner_type": "بازنشسته", "inst_sms_mobile": "09351234567"}, tok)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["pay_url"])
        self.assertEqual(r.json()["order"]["status"], "on_hold")
