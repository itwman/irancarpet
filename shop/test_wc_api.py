import base64

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product, Variation
from core.models import Media
from pricing.models import Size, seed_sizes
from shop.models import Order, OrderItem, Payment, ShopSettings
from shop.wc_api import new_keys


class WcApiTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = ShopSettings.load()
        s.manix_enabled = True
        s.save()
        self.key, self.secret = new_keys()
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه هریس", slug="h", status="publish", image=Media.objects.create(file="h.jpg"))
        self.v = Variation.objects.create(product=self.p, size=Size.objects.get(slug="9-meter"))
        base = dict(first_name="علی", last_name="کاشانی", mobile="09121111111", province="اصفهان", city="کاشان", address="x")
        self.o = Order.objects.create(status="deposit_paid", items_total=40_000_000, discount=2_000_000, paid_amount=4_000_000, **base)
        OrderItem.objects.create(order=self.o, product=self.p, variation=self.v, title=self.p.title, size_label="۹ متری",
                                 unit_price=42_000_000, quantity=1)
        Payment.objects.create(order=self.o, gateway="sep", amount=4_000_000, status="ok", verified_at=timezone.now())
        old = Order.objects.create(status="paid", items_total=1, **base)
        Order.objects.filter(pk=old.pk).update(created_at=timezone.make_aware(timezone.datetime(2024, 1, 1)))

    def auth(self, key=None, secret=None):
        raw = f"{key or self.key}:{secret or self.secret}".encode()
        return {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(raw).decode()}

    def test_orders_shape_and_auth(self):
        self.assertEqual(self.client.get("/wp-json/wc/v3/orders").status_code, 401)
        self.assertEqual(self.client.get("/wp-json/wc/v3/orders", **self.auth(secret="cs_bad")).status_code, 401)
        r = self.client.get("/wp-json/wc/v3/orders?per_page=50", **self.auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-WP-Total"], "1")  # سفارش پیش از ۱۴۰۴ داده نمی‌شود
        o = r.json()[0]
        self.assertEqual((o["id"], o["status"], o["local_status"], o["total"], o["discount_total"]),
                         (self.o.number, "processing", "deposit_paid", "40000000", "2000000"))
        li = o["line_items"][0]
        self.assertEqual((li["name"], li["variation_id"], li["quantity"], li["price"]), ("فرش 1200 شانه نقشه هریس - ۹ متری", self.v.pk, 1, 42_000_000))
        self.assertTrue(li["sku"].endswith("-9-meter"))
        pays = next(m["value"] for m in o["meta_data"] if m["key"] == "_manix_payments")
        self.assertEqual([p["amount"] for p in pays], [4_000_000])
        self.assertEqual(o["billing"]["phone"], "09121111111")
        q = f"consumer_key={self.key}&consumer_secret={self.secret}"
        self.assertEqual(len(self.client.get(f"/wp-json/wc/v3/orders?status=completed&{q}").json()), 0)
        self.assertEqual(self.client.get(f"/wp-json/wc/v3/orders/{self.o.number}/?{q}").json()["id"], self.o.number)
        future = (timezone.now() + timezone.timedelta(hours=1)).isoformat()
        self.assertEqual(self.client.get("/wp-json/wc/v3/orders", {"modified_after": future, "consumer_key": self.key,
                                                                   "consumer_secret": self.secret}).json(), [])
        s = ShopSettings.load()
        s.manix_enabled = False
        s.save()
        self.assertEqual(self.client.get("/wp-json/wc/v3/orders", **self.auth()).status_code, 401)

    def test_payment_touches_order_and_panel_keys(self):
        before = Order.objects.get(pk=self.o.pk).updated_at
        Payment.objects.create(order=self.o, gateway="manual", amount=1, status="ok")
        self.assertGreater(Order.objects.get(pk=self.o.pk).updated_at, before)
        boss = get_user_model().objects.create_user("boss", password="x" * 10, is_staff=True, is_superuser=True)
        self.client.force_login(boss)
        self.client.post("/panel/settings/", {"tab": "manix", "do": "manix_keys"})
        html = self.client.get("/panel/settings/?tab=manix").content.decode()
        self.assertIn("cs_", html)
        self.assertNotIn("cs_", self.client.get("/panel/settings/?tab=manix").content.decode())  # فقط یک بار
        self.assertEqual(self.client.get("/wp-json/wc/v3/orders", **self.auth()).status_code, 401)  # کلید قبلی باطل شد


class ManixPhoneOrderTests(TestCase):
    def setUp(self):
        from crm.models import CrmSettings

        seed_sizes()
        s = ShopSettings.load()
        s.manix_enabled = True
        s.save()
        CrmSettings.load()
        self.key, self.secret = new_keys()
        img = Media.objects.create(file="h.jpg")
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه هریس زمینه سرمه‌ای", slug="h", status="publish", image=img)
        self.v9 = Variation.objects.create(product=self.p, size=Size.objects.get(slug="9-meter"))
        self.v12 = Variation.objects.create(product=self.p, size=Size.objects.get(slug="12-meter"))
        self.auth = {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(f"{self.key}:{self.secret}".encode()).decode()}

    def post(self, data):
        import json

        return self.client.post("/wp-json/wc/v3/manix/orders", json.dumps(data), content_type="application/json", **self.auth)

    def payload(self, **kw):
        d = {"ref": "inv-1", "number": 15, "customer": {"name": "مینا رضایی", "mobile": "۰۹۱۲۳۳۳۴۴۴۴", "city": "کاشان"},
             "items": [{"name": "فرش ۱۲۰۰ شانه هریس سرمه ای - ۹ متری", "qty": 1, "price": 30_000_000},
                       {"name": "فرش 700 شانه نقشه آیناز زمینه کرم، ۱۲ متری", "qty": 2, "price": 20_000_000}],
             "discount": 1_000_000, "total": 69_000_000, "payments": [{"id": "t1", "amount": 9_000_000, "date": "2026-10-10T10:00:00"}]}
        d.update(kw)
        return d

    def test_matching_and_normalization(self):
        from shop.manix import key, match_item, parse_size, split_name

        self.assertEqual(key("سرمه ای"), key("سرمه‌ای"))
        self.assertEqual(key("سرمه اي"), key("سرمه‌ای"))
        self.assertEqual(split_name("فرش هریس - ۹ متری")[1].slug, "9-meter")
        self.assertEqual(parse_size("۳ × ۲").slug, "6-meter")
        self.assertEqual(parse_size("کناره ۳ متری").slug, "runner-3x1")
        self.assertEqual(parse_size("۱۲ متری (۴ × ۳)").slug, "12-meter")
        v, p, s = match_item("فرش 1200 شانه نقشه هریس زمینه سرمه‌اي، ۱۲ متری")
        self.assertEqual((v, p), (self.v12, self.p))

    def test_phone_order_with_pay_link_one_sms(self):
        from unittest import mock

        from catalog.models import Product
        from crm.models import SmsLog

        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as sent:
            r = self.post(self.payload(pay_link={"amount": 0}, send_sms=True))
        self.assertEqual(r.status_code, 200, r.content.decode())
        j = r.json()
        o = Order.objects.get(manix_ref="inv-1")
        self.assertEqual((o.src, o.status, o.items_total, o.paid_amount, o.online_amount), ("phone", "deposit_paid", 69_000_000, 9_000_000, 60_000_000))
        self.assertTrue(j["short_url"] and "/o/" in j["pay_url"])
        self.assertTrue(j["sms"])
        self.assertEqual(sent.call_count, 1)
        self.assertEqual(SmsLog.objects.filter(order=o).count(), 1)
        self.assertIn("آمادهٔ پرداخت", SmsLog.objects.get(order=o).text)
        items = list(o.items.order_by("pk"))
        self.assertEqual(items[0].variation, self.v9)                     # «سرمه ای» با فاصله پیدا شد
        draft = Product.objects.get(manix_draft=True)                    # «آیناز» در سایت نبود ← پیش‌نویس
        self.assertEqual((draft.status, items[1].product, items[1].variation.size.slug), ("draft", draft, "12-meter"))
        self.assertTrue(o.can_pay)
        # اجرای دوباره: تکراری نمی‌سازد؛ پرداخت دوم مانیکس ← پرداخت کامل
        self.post(self.payload(payments=[{"id": "t1", "amount": 9_000_000}, {"id": "t2", "amount": 60_000_000}]))
        o.refresh_from_db()
        self.assertEqual((Order.objects.filter(manix_ref="inv-1").count(), o.status, o.paid_amount), (1, "paid", 69_000_000))
        self.assertEqual(Product.objects.filter(manix_draft=True).count(), 1)
        self.assertFalse(o.can_pay)
        # پرداخت‌های مانیکس در API خواندن برنمی‌گردند (حلقه نمی‌سازد)
        q = f"consumer_key={self.key}&consumer_secret={self.secret}"
        row = self.client.get(f"/wp-json/wc/v3/orders/{o.number}/?{q}").json()
        meta = {m["key"]: m["value"] for m in row["meta_data"]}
        self.assertEqual((meta["_manix_payments"], meta["_manix_ref"]), ([], "inv-1"))

    def test_paying_link_marks_paid_and_no_customer_sms(self):
        from unittest import mock

        self.post(self.payload(payments=[], pay_link={"amount": 10_000_000}))
        o = Order.objects.get(manix_ref="inv-1")
        self.assertEqual((o.status, o.online_amount), ("pending", 10_000_000))
        from shop import paymode

        self.assertEqual(paymode.options(o), [])                         # مشتری مبلغ را عوض نمی‌کند
        o.mark_paid(10_000_000)
        o.refresh_from_db()
        self.assertEqual((o.status, o.online_amount, o.can_pay), ("deposit_paid", 0, False))
        with mock.patch("crm.notify.send", return_value=True) as sent:
            from crm.notify import order_paid_now

            order_paid_now(o, 10_000_000, customer=not o.is_phone, admin=False)
        self.assertEqual(sent.call_count, 0)

    def test_errors_and_catalog(self):
        self.assertEqual(self.post({"ref": "x", "customer": {"mobile": "123"}, "items": [{"name": "a", "qty": 1}]}).status_code, 400)
        r = self.client.get("/wp-json/wc/v3/manix/catalog", **self.auth).json()
        names = {x["name"] for x in r}
        self.assertIn("فرش 1200 شانه نقشه هریس زمینه سرمه‌ای - ۹ متری مستطیل (۳.۵ × ۲.۵)", names)
        self.assertEqual(len(r), 2)
