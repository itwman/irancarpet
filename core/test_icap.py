from decimal import Decimal

from django.test import TestCase

from catalog.models import Product, Variation
from core.wp.icap import import_icap
from pricing.models import Album, Size, seed_sizes

SIZES = ('a:3:{i:0;a:7:{s:3:"key";s:3:"12m";s:5:"label";s:3:"L12";s:4:"area";d:12;s:11:"billed_area";d:12;s:7:"is_base";b:1;s:13:"special_waste";b:0;s:9:"even_only";b:0;}'
         'i:1;a:7:{s:3:"key";s:2:"9m";s:5:"label";s:2:"L9";s:4:"area";d:8.75;s:11:"billed_area";d:9;s:7:"is_base";b:0;s:13:"special_waste";b:1;s:9:"even_only";b:0;}'
         'i:2;a:7:{s:3:"key";s:11:"kenareh-1x4";s:5:"label";s:1:"K";s:4:"area";d:4;s:11:"billed_area";d:4;s:7:"is_base";b:0;s:13:"special_waste";b:0;s:9:"even_only";b:1;}}')


class FakeWP:
    def __init__(self):
        self.meta = {
            900: {"_icap_buy_price": "35000000", "_icap_profit_percent": "15", "_icap_shipping_fixed": "500000",
                  "_icap_waste_type": "fixed", "_icap_waste_value": "3000000", "_icap_round_to": "10000",
                  "_icap_enabled_sizes": 'a:3:{i:0;s:3:"12m";i:1;s:2:"9m";i:2;s:11:"kenareh-1x4";}',
                  "_icap_even_sizes": 'a:1:{i:0;s:11:"kenareh-1x4";}'},
            701: {"_regular_price": "20000000", "_sale_price": "18000000", "_price": "18000000"},
        }

    def option(self, name, default=None):
        return {"icap_standard_sizes": SIZES, "woocommerce_currency": "IRT"}.get(name, default)

    def posts(self, post_type, statuses=("publish",), extra=""):
        return [{"ID": 900, "post_title": "700 ورژن", "menu_order": 0}] if post_type == "icap_album" else []

    def postmeta(self, ids, keys=None):
        return {i: {k: v for k, v in self.meta.get(i, {}).items() if not keys or k in keys} for i in ids}

    def rows(self, sql, params=None):
        return [{"post_id": 100, "meta_value": "900"}]


class IcapImportTests(TestCase):
    def setUp(self):
        seed_sizes()
        s12 = Size.objects.get(slug="12-meter")
        self.old = Album.objects.create(name="ارزی", code="MNS-1", base_size=s12, base_price=Decimal("1000"))
        self.p1 = Product.objects.create(title="پلی", slug="p1", wp_id=100, album=self.old, custom_base_price=Decimal("5"))
        Variation.objects.create(product=self.p1, size=s12, wp_id=501, sale_price=1, manual_price=1)
        Variation.objects.create(product=self.p1, size=Size.objects.get(slug="6-meter"), wp_id=502)
        self.p2 = Product.objects.create(title="بی‌آلبوم", slug="p2", wp_id=200, album=self.old)
        self.v2 = Variation.objects.create(product=self.p2, size=s12, wp_id=701)

    def test_import(self):
        import_icap(FakeWP(), log=lambda m: None)
        self.p1.refresh_from_db()
        a = self.p1.album
        self.assertEqual(a.code, "ICAP-900")
        self.assertIsNone(self.p1.custom_base_price)
        prices = {v.size.slug: (v.final_price, v.sale_price, v.is_pair_only) for v in self.p1.variations.select_related("size")}
        self.assertEqual(prices, {"12-meter": (40_750_000, None, False), "9-meter": (33_570_000, None, False),
                                  "runner-4x1": (13_590_000, None, True)})
        self.assertEqual(self.p1.min_price, 40_750_000)
        self.v2.refresh_from_db()
        self.assertEqual((self.v2.final_price, self.v2.sale_price), (20_000_000, 18_000_000))
        self.assertFalse(Album.objects.filter(code="MNS-1").exists())

    def test_dry_run_changes_nothing(self):
        import_icap(FakeWP(), log=lambda m: None, dry_run=True)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.album_id, self.old.pk)
