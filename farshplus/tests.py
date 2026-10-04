import tempfile
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Product, Variation
from core.models import Media
from pricing.models import PricingSettings, Size, seed_sizes

from . import sync
from .client import ApiError, build_multipart
from .models import FarshPlusItem, FarshPlusSettings


class FakeClient:
    def __init__(self):
        self.calls = []
        self.next_error = None

    def upsert_product(self, fields, files=()):
        self.calls.append(("upsert", fields, len(files)))
        if self.next_error:
            e, self.next_error = self.next_error, None
            raise e
        return {"id": 77, "url": "https://farshplus.com/p/77/", "status": "PUBLISHED", "created": True}

    def delete_product(self, ext):
        self.calls.append(("delete", ext))
        return {"ok": True}

    def me(self):
        return {"page": {"name": "ایران کارپت"}, "limits": {"daily_products": 200, "max_images": 5, "max_image_mb": 8}}

    def get_statuses(self, ids):
        return {"results": {}}


@override_settings(STAGING=False, SITE_URL="https://irancarpet.net")
class FarshPlusTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.media_override.enable()
        import os
        os.makedirs(os.path.join(self.tmp.name, "2024/01"))
        with open(os.path.join(self.tmp.name, "2024/01/a.jpg"), "wb") as f:
            f.write(b"\xff\xd8fakejpeg")
        seed_sizes()
        PricingSettings.load()
        s = FarshPlusSettings.load()
        s.api_key = "fpk_test_x"
        s.checked_at = timezone.now()
        s.last_refresh_at = timezone.now()
        s.save()
        self.media = Media.objects.create(file="2024/01/a.jpg", title="a")
        self.p = Product.objects.create(title="فرش ۱۲۰۰ شانه هانا", slug="فرش-هانا", image=self.media, short_description="<p>توضیح</p>")
        Variation.objects.create(product=self.p, size=Size.objects.get(slug="6-meter"), manual_price=20_000_000)
        self.p.refresh_price_cache()
        self.fake = FakeClient()
        self.patch = mock.patch.object(sync, "client", return_value=self.fake)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.media_override.disable()
        self.tmp.cleanup()

    def test_new_product_upsert_and_no_image_resend(self):
        item = sync.get_item(self.p)
        sync.queue(item, "manual")
        msg = sync.process(item)
        self.assertIn("ایجاد", msg)
        kind, fields, nfiles = self.fake.calls[0]
        self.assertEqual(fields["external_id"], f"dj-{self.p.pk}")
        self.assertEqual(fields["url"], "https://irancarpet.net/product/%D9%81%D8%B1%D8%B4-%D9%87%D8%A7%D9%86%D8%A7/")
        self.assertEqual(fields["price"], "20000000")
        self.assertEqual(fields["currency"], "IRT")
        self.assertEqual(fields["in_feed"], "1")
        self.assertEqual(nfiles, 1)
        item.refresh_from_db()
        self.assertEqual((item.post_id, item.status, item.queued), (77, "PUBLISHED", False))
        # بدون تغییر، اسکن چیزی در صف نمی‌گذارد؛ با تغییر قیمت در صف می‌رود و تصویر دوباره فرستاده نمی‌شود
        self.assertEqual(sync.scan(), 0)
        Variation.objects.filter(product=self.p).update(manual_price=21_000_000)
        v = self.p.variations.get(); v.save(); self.p.refresh_price_cache()
        self.assertEqual(sync.scan(), 1)
        sync.process(FarshPlusItem.objects.get())
        self.assertEqual(self.fake.calls[-1][2], 0)
        self.assertEqual(self.fake.calls[-1][1]["price"], "21000000")

    def test_rate_limit_pauses_everything(self):
        item = sync.get_item(self.p)
        sync.queue(item, "bulk")
        self.fake.next_error = ApiError("سقف", 429, retry_after=7200)
        n = sync.run(out=lambda m: None)
        self.assertEqual(n, 0)
        s = FarshPlusSettings.load()
        self.assertTrue(s.paused)
        self.assertGreater(s.rate_limited_until, timezone.now() + timedelta(minutes=110))
        item.refresh_from_db()
        self.assertTrue(item.queued)
        self.assertEqual(self.fake.calls[0][1]["in_feed"], "0")  # ارسال گروهی بی‌صدا
        calls = len(self.fake.calls)
        sync.run(out=lambda m: None)
        self.assertEqual(len(self.fake.calls), calls)  # تا پایان توقف درخواستی نمی‌رود

    def test_out_of_stock_hides_remote(self):
        item = FarshPlusItem.objects.create(product=self.p, external_id="123", post_id=5, status="PUBLISHED")
        Variation.objects.filter(product=self.p).update(is_available=False)
        self.p.refresh_price_cache()
        self.assertEqual(sync.scan(), 1)
        sync.process(FarshPlusItem.objects.get())
        self.assertEqual(self.fake.calls[-1], ("delete", "123"))
        item.refresh_from_db()
        self.assertEqual(item.status, "HIDDEN")
        self.assertEqual(sync.scan(), 0)

    def test_retry_then_error(self):
        item = sync.get_item(self.p)
        sync.queue(item)
        self.fake.next_error = ApiError("network", 0, retryable=True)
        with self.assertRaises(ApiError):
            sync.process(item)
        item.refresh_from_db()
        self.assertTrue(item.queued)
        self.assertEqual(item.attempts, 1)
        self.assertIsNotNone(item.next_try_at)

    @override_settings(STAGING=True)
    def test_staging_never_sends(self):
        sync.queue(sync.get_item(self.p))
        self.assertEqual(sync.run(out=lambda m: None), 0)
        self.assertEqual(self.fake.calls, [])

    def test_queue_all_unsent_and_new_product_auto(self):
        self.assertEqual(sync.queue_all_unsent(), 1)
        self.assertEqual(FarshPlusItem.objects.get().mode, "bulk")
        FarshPlusItem.objects.all().delete()
        s = FarshPlusSettings.load()
        s.last_scan_at = timezone.now() - timedelta(minutes=5)
        s.save()
        Product.objects.filter(pk=self.p.pk).update(modified_at=timezone.now())
        self.assertEqual(sync.scan(), 1)

    def test_multipart(self):
        body = build_multipart("B", {"title": "فرش", "skip": None}, [{"filename": "a.jpg", "type": "image/jpeg", "data": b"x"}])
        self.assertIn('name="title"'.encode(), body)
        self.assertIn("فرش".encode(), body)
        self.assertNotIn(b"skip", body)
        self.assertIn(b'name="images"; filename="a.jpg"', body)
