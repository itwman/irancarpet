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
