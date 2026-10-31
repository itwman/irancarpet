import base64
import json
import time
import unittest
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from catalog.models import Product
from torob import api_v3
from torob.models import TorobSettings

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # روی سرور لازم نیست
    Ed25519PrivateKey = None


def _b(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


@unittest.skipUnless(Ed25519PrivateKey, "cryptography برای ساخت توکن آزمایشی")
class TorobApiV3Tests(TestCase):
    def setUp(self):
        cache.clear()
        self.key = Ed25519PrivateKey.generate()
        pub = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        patcher = mock.patch.object(api_v3, "TOROB_PUBLIC_KEY", pub)
        patcher.start()
        self.addCleanup(patcher.stop)
        s = TorobSettings.load()
        s.only_album = False
        s.save()
        self.p = Product.objects.create(title="فرش آزمایشی", slug="فرش-آزمایشی", status="publish", wp_id=4242)

    def token(self, aud="testserver", exp=60):
        h, p = _b({"alg": "EdDSA", "typ": "JWT", "v": 1}), _b({"aud": aud, "exp": time.time() + exp, "nbf": time.time() - 5})
        sig = base64.urlsafe_b64encode(self.key.sign(f"{h}.{p}".encode())).rstrip(b"=").decode()
        return f"{h}.{p}.{sig}"

    def post(self, body, token=None):
        return self.client.post("/torob_api/v3/products", json.dumps(body), content_type="application/json",
                                HTTP_X_TOROB_TOKEN=token if token is not None else self.token(), HTTP_X_TOROB_TOKEN_VERSION="1")

    def test_auth(self):
        self.assertEqual(self.post({"page": 1, "sort": "date_added_desc"}, token="").status_code, 401)
        self.assertEqual(self.post({"page": 1, "sort": "date_added_desc"}, token=self.token(aud="other.ir")).status_code, 401)
        self.assertEqual(self.post({"page": 1, "sort": "date_added_desc"}, token=self.token(exp=-600)).status_code, 401)

    def test_requests(self):
        self.assertEqual(self.post({"page": 1}).json()["error"], "sort parameter is not provided")
        self.assertEqual(self.post({}).status_code, 400)
        d = self.post({"page": 1, "sort": "date_added_desc"}).json()
        self.assertEqual((d["api_version"], d["total"], d["current_page"]), ("torob_api_v3", 1, 1))
        item = d["products"][0]
        self.assertEqual(item["page_unique"], str(self.p.pk))   # شناسهٔ سایت، همان که ترب دارد
        self.assertTrue(item["page_url"].startswith("http"))
        self.assertEqual((item["current_price"], item["availability"]), (0, False))  # بی‌قیمت ← ناموجود با قیمت ۰
        self.assertIsInstance(item["spec"], dict)
        d = self.post({"page_uniques": ["4242", "999999"]}).json()       # شناسهٔ قدیمی ووکامرس هم پیدا می‌شود
        self.assertEqual([x["page_unique"] for x in d["products"]], [str(self.p.pk)])
        d = self.post({"page_urls": [item["page_url"]]}).json()
        self.assertEqual(len(d["products"]), 1)
        d = self.post({"sort": "product_id_desc"}).json()
        self.assertIsNone(d["next_cursor"])
        self.assertEqual(len(d["products"]), 1)
        self.assertEqual(api_v3.last_request()["kind"], "cursor")
        self.assertEqual(api_v3.recent_requests()[0]["uniques"], [str(self.p.pk)])
        self.assertEqual(api_v3.preview("4242")["page_unique"], str(self.p.pk))
        self.assertNotIn("%25", json.dumps(api_v3.preview(str(self.p.pk))))
        n = Product.objects.create(title="فرش تازه", slug="فرش-تازه", status="publish")
        d = self.post({"page_uniques": [str(n.pk)]}).json()
        self.assertEqual([x["page_unique"] for x in d["products"]], [str(n.pk)])
