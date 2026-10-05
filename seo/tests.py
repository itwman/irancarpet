import json
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from catalog.models import Attribute, AttributeTerm, Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from . import indexnow
from .models import SeoSettings


class GeoTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("35000000"),
                                          shipping_fixed=500_000, waste_value=3_000_000, slug="version-1200")
        self.album.sizes.set([s["12-meter"], s["9-meter"]])
        self.p = Product.objects.create(title="فرش 1200 شانه ورژن", slug="version", album=self.album, status="publish")
        sync_album_variations([self.p], reset=True)
        pile = Attribute.objects.create(slug="جنس-نخ-خاب", label="جنس نخ خاب")
        self.p.specs.add(AttributeTerm.objects.create(attribute=pile, name="اکریلیک", slug="acrylic"))

    def test_llms_txt(self):
        r = self.client.get("/llms.txt")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/markdown"))
        t = r.content.decode()
        self.assertIn("# ایران کارپت", t)
        self.assertIn("/carpets-price-list/version-1200/", t)
        self.assertIn("40,750,000", t)  # قیمت ۱۲ متری با رقم لاتین
        s = SeoSettings.load()
        s.llms_about = "فروشگاه از سال ۱۳۹۰ فعال است."
        s.save()
        from django.core.cache import cache

        cache.clear()
        self.assertIn("از سال ۱۳۹۰", self.client.get("/llms.txt").content.decode())

    def test_product_schema(self):
        html = self.client.get("/product/version/").content.decode()
        start = html.index('application/ld+json">') + len('application/ld+json">')
        data = json.loads(html[start:html.index("</script>", start)])
        prod = data[0] if isinstance(data, list) else data
        self.assertEqual(prod["material"], "اکریلیک")
        self.assertEqual(prod["additionalProperty"][0]["name"], "جنس نخ خاب")
        self.assertEqual(len(prod["offers"]["offers"]), 2)
        self.assertEqual(prod["offers"]["offers"][0]["priceCurrency"], "IRR")

    def test_key_file(self):
        key = SeoSettings.load().indexnow_key
        self.assertEqual(len(key), 32)
        self.assertEqual(self.client.get(f"/{key}.txt").content.decode(), key)
        self.assertEqual(self.client.get(f"/{'0' * 32}.txt").status_code, 404)

    def test_submit_and_signals(self):
        self.assertFalse(indexnow.active())  # در تست هیچ درخواستی بیرون نمی‌رود
        with mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value.status = 202
            ok, msg = indexnow.submit(["/product/version/"])
        self.assertTrue(ok)
        body = json.loads(op.call_args[0][0].data)
        self.assertEqual(body["urlList"], ["https://irancarpet.net/product/version/"])
        self.assertEqual(body["keyLocation"], f"https://irancarpet.net/{body['key']}.txt")
        self.assertEqual(SeoSettings.load().indexnow_total, 1)
        self.assertIn("/product/version/", indexnow.all_urls())

    @override_settings(TESTING=False, DEBUG=False, STAGING=False)
    def test_queue_on_save(self):
        with mock.patch.object(indexnow, "queue") as q, self.captureOnCommitCallbacks(execute=True):
            self.p.title = "فرش تازه"
            self.p.save()
        self.assertIn("/product/version/", q.call_args[0])
