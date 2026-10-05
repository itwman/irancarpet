import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from .client import RajyarError, build_payload, ping, refresh, send
from .models import RajyarPost, RajyarSettings


class Resp:
    def __init__(self, data, status=201):
        self.data, self.status = data, status

    def read(self):
        return json.dumps(self.data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RajyarTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        a = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("45000000"))
        a.sizes.set([s["12-meter"], s["9-meter"]])
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه افشان", slug="afshan", album=a, status="publish")
        sync_album_variations([self.p], reset=True)
        self.s = RajyarSettings.load()
        self.s.enabled, self.s.api_key, self.s.channels = True, "rjy_test_key", "2"
        self.s.save()

    def test_payload_and_send(self):
        body = build_payload(self.p, self.s, publish_at=timezone.now() + timezone.timedelta(hours=2))
        self.assertEqual(body["channels"], [2])
        self.assertEqual(body["external_id"], f"product-{self.p.pk}")
        self.assertIn("۱۲ متری", body["content"])
        self.assertIn("قیمت روز", body["content"])  # قیمت همیشه با تاریخ
        self.assertNotIn("<", body["content"])
        self.assertEqual(body["buttons"][0]["text"], "مشاهده و خرید")
        self.s.price_mode = "none"
        self.assertNotIn("تومان", build_payload(self.p, self.s)["content"])
        self.s.price_mode = "sizes"
        self.s.price_sizes.set(Size.objects.filter(slug="9-meter"))
        c = build_payload(self.p, self.s)["content"]
        self.assertIn("۹ متری", c)
        self.assertNotIn("۱۲ متری", c)
        self.s.price_sizes.clear()
        self.assertIn("+03:30", body["publish_at"])
        self.assertTrue(body["url"].endswith("/product/afshan/"))
        with mock.patch("urllib.request.urlopen", return_value=Resp({"ok": True, "post": {"id": 12, "publications": []}})) as op:
            post = send(self.p, publish_at=timezone.now() + timezone.timedelta(hours=1))
        req = op.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer rjy_test_key")
        self.assertTrue(req.full_url.endswith("/api/v1/posts/"))
        self.assertEqual((post.remote_id, post.status), (12, "scheduled"))
        # وضعیت بعدی
        done = {"post": {"id": 12, "publications": [{"status": "published", "url": "https://t.me/irancarpet/55"}]}}
        with mock.patch("urllib.request.urlopen", return_value=Resp(done, 200)):
            self.assertEqual(refresh(), 1)
        post.refresh_from_db()
        self.assertEqual((post.status, post.links), ("published", ["https://t.me/irancarpet/55"]))

    def test_needs_channels_and_handles_errors(self):
        self.s.channels = ""
        self.s.save()
        with self.assertRaises(RajyarError):
            send(self.p)
        self.s.channels = "2"
        self.s.save()
        import urllib.error

        err = urllib.error.HTTPError("u", 401, "x", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            post = send(self.p)
        self.assertEqual(post.status, "failed")
        self.assertIn("کلید", post.error)

    def test_ping_and_panel_bulk(self):
        chans = [{"id": 1, "name": "تاروپود خبر", "platform": "telegram"}, {"id": 2, "name": "ایران کارپت", "platform": "telegram"}]
        with mock.patch("urllib.request.urlopen", return_value=Resp(chans, 200)):
            ok, msg = ping()
        self.assertTrue(ok)
        self.assertEqual(len(RajyarSettings.load().channels_cache), 2)
        u = get_user_model().objects.create_user("st", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)
        self.assertContains(self.client.get("/panel/settings/?tab=rajyar"), "تاروپود خبر")
        p2 = Product.objects.create(title="فرش دوم", slug="p2", status="publish")
        with mock.patch("urllib.request.urlopen", return_value=Resp({"post": {"id": 3}})) as op:
            r = self.client.post("/panel/products/", {"action": "rajyar", "ids": [self.p.pk, p2.pk], "action_value": "now"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(op.call_count, 2)
        bodies = [json.loads(c[0][0].data) for c in op.call_args_list]
        self.assertNotIn("publish_at", bodies[0])  # اولی فوری
        self.assertIn("publish_at", bodies[1])     # دومی با فاصله
        self.assertTrue(all(b["force_new"] for b in bodies))
        self.assertEqual(RajyarPost.objects.count(), 2)
        self.assertEqual(self.client.get("/panel/rajyar-posts/").status_code, 200)
