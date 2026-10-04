from decimal import Decimal

from django.test import TestCase

from catalog.models import Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from .models import TorobSettings


class TorobFeedTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        a = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("35000000"), shipping_fixed=500_000)
        a.sizes.set([s["12-meter"], s["6-meter"]])
        self.p = Product.objects.create(title="فرش پلی", slug="poly", album=a, status="publish", wp_id=66171, short_description="<p>توضیح</p>")
        sync_album_variations([self.p], reset=True)
        self.plain = Product.objects.create(title="بی‌آلبوم", slug="plain", status="publish")

    def test_page(self):
        r = self.client.get("/wp-json/torob/products/?page=1")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["count"], 1)
        row = d["products"][0]
        self.assertEqual((row["page_unique"], row["current_price"], row["old_price"], row["availability"]), (66171, 40_750_000, 0, "instock"))
        self.assertTrue(row["page_url"].endswith("/product/poly/"))
        self.assertEqual(row["short_desc"], "توضیح")

    def test_single_and_settings(self):
        s = TorobSettings.load()
        s.decrease_rate, s.round_to = Decimal("10"), 1000
        s.save()
        d = self.client.post("/wp-json/torob/products/", {"page_unique": "66171"}).json()
        self.assertEqual(d["products"][0]["current_price"], 36_675_000)
        d = self.client.get("/wp-json/torob/products/", {"page_url": "https://irancarpet.net/product/poly/?utm_source=torob"}).json()
        self.assertEqual(d["count"], 1)
        s.excluded.add(self.p)
        self.assertEqual(self.client.get("/wp-json/torob/products/", {"page_unique": "66171"}).json()["count"], 0)

    def test_other_wp_json_still_gone(self):
        self.assertEqual(self.client.get("/wp-json/wp/v2/posts").status_code, 410)
