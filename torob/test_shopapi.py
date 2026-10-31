import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from catalog.models import Product
from torob import shopapi
from torob.models import TorobProduct, TorobSettings


class FakeTorob:
    """پاسخ‌های ساختگی Shop API ترب."""

    def __init__(self, products):
        self.products = products
        self.calls = []

    def __call__(self, method, path, token, params=None, body=None, url=None):
        self.calls.append((method, path or url, body))
        if path == "/shop/":
            return {"domain": "irancarpet.net", "name": "ایران کارپت", "shop_status": "active",
                    "product_summary": {"total": len(self.products), "available": 1, "not_accessible": 1,
                                        "not_accessible_errors": [{"error_title": "404:download_http_status_error", "count": 1}]}}
        if path == "/products/":
            if body and body.get("product_ids"):
                return {"next": None, "results": [p for p in self.products if p["product_id"] in body["product_ids"]]}
            return {"next": None, "previous": None, "results": self.products}
        if path in ("/products/deactivate/", "/products/activate/"):
            return {"results": [{"product_id": i, "found": True} for i in body["product_ids"]]}
        raise AssertionError(path)


class ShopApiTests(TestCase):
    def setUp(self):
        cache.clear()
        s = TorobSettings.load()
        s.shop_api_token = "tok"
        s.only_album = False
        s.save()

    def test_sync_compare_and_panel(self):
        p = Product.objects.create(title="فرش تست", slug="فرش-تست", status="publish", wp_id=555)
        fake = FakeTorob([
            {"product_id": "555", "page_url": "https://irancarpet.net/product/%d9%81%d8%b1%d8%b4-%d8%aa%d8%b3%d8%aa/",
             "statuses": [], "price": 1000, "availability": True, "error_title": "", "updated_at": "2026-10-30T08:00:00+00:00"},
            {"product_id": "777", "page_url": "https://irancarpet.net/old-wordpress-page/", "statuses": ["page_not_accessible"],
             "price": 0, "availability": False, "error_title": "404:download_http_status_error", "updated_at": "2026-10-30T08:00:00+00:00"},
        ])
        with mock.patch.object(shopapi, "_call", fake), mock.patch.object(shopapi, "_expected", return_value=(2000, True)):
            st = shopapi.sync(full=True)
        self.assertEqual(st["status"], "active")
        a = TorobProduct.objects.get(torob_id="555")
        self.assertEqual((a.product_id, a.problem, a.site_price), (p.pk, "price", 2000))
        b = TorobProduct.objects.get(torob_id="777")
        self.assertEqual(b.problem, "404")
        self.assertIn(b.site_status, (301, 404))
        self.assertEqual(st["counts"]["price"], 1)

        user = User.objects.create_superuser("a", "a@a.ir", "x")
        self.client.force_login(user)
        r = self.client.get("/panel/torob/?t=price")
        self.assertContains(r, "فرش تست")
        self.assertContains(r, "خارج از دسترس")
        with mock.patch.object(shopapi, "_call", fake):
            self.client.post("/panel/torob/?t=price", {"do": "deactivate", "ids": ["555"]})
        self.assertTrue(any(c[1] == "/products/deactivate/" for c in fake.calls))

    def test_no_token(self):
        s = TorobSettings.load()
        s.shop_api_token = ""
        s.save()
        self.assertFalse(shopapi.due())
        user = User.objects.create_superuser("b", "b@a.ir", "x")
        self.client.force_login(user)
        self.assertContains(self.client.get("/panel/torob/"), "ساخت توکن")
