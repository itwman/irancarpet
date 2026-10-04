"""آزمون موتور قیمت با مثال‌های README افزونهٔ «قیمت‌گذاری آلبومی ایران‌کارپت»."""
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product, Variation

from .albums import sync_album_variations
from .models import Album, PricingSettings, Size, seed_sizes


class PricingEngineTests(TestCase):
    def setUp(self):
        seed_sizes()
        PricingSettings.load()
        self.s = {s.slug: s for s in Size.objects.all()}
        # مثال تأییدشدهٔ README: خرید ۲۵ میلیون، سود ۱۰٪، ارسال ۵۰۰ هزار، پرتی ۱۰٪
        self.album = Album.objects.create(
            name="آلبوم نمونه", code="T1", base_size=self.s["12-meter"], base_price=Decimal("25000000"),
            profit_percent=Decimal("10"), shipping_fixed=500_000, waste_type="percent", waste_value=Decimal("10"), round_to=10_000,
        )

    def price(self, slug):
        return self.album.size_price(self.s[slug])

    def test_readme_example(self):
        self.assertEqual(self.price("12-meter"), 28_000_000)
        self.assertEqual(self.price("9-meter"), 23_100_000)
        self.assertEqual(self.price("6-meter"), 14_000_000)
        self.assertEqual(self.price("runner-4x1"), 9_340_000)

    def test_fixed_waste(self):
        self.album.waste_type, self.album.waste_value = "fixed", Decimal("3000000")
        self.assertEqual(self.price("9-meter"), 24_000_000)

    def test_live_album_ورژن(self):
        # آلبوم «۷۰۰ شانه آلبوم ورژن» در سایت وردپرس
        a = Album(name="ورژن", code="V", base_size=self.s["12-meter"], base_price=Decimal("35000000"), profit_percent=Decimal("15"),
                  shipping_fixed=500_000, waste_type="fixed", waste_value=Decimal("3000000"), round_to=10_000)
        self.assertEqual(a.size_price(self.s["12-meter"]), 40_750_000)
        self.assertEqual(a.size_price(self.s["9-meter"]), 33_570_000)
        self.assertEqual(a.size_price(self.s["6-meter"]), 20_380_000)

    def test_exact_multiple_not_bumped(self):
        self.assertEqual(self.album.round_up(Decimal("28000000")), 28_000_000)

    def test_album_change_reprices_products(self):
        p = Product.objects.create(title="تست", slug="test", album=self.album)
        v = Variation.objects.create(product=p, size=self.s["6-meter"])
        self.assertEqual(v.final_price, 14_000_000)
        self.album.profit_percent = Decimal("20")
        self.album.save()
        v.refresh_from_db()
        self.assertEqual(v.final_price, 15_250_000)   # (۲۵م × ۱٫۲ + ۵۰۰ک) × ۶/۱۲

    def test_size_outside_album_uses_manual_price(self):
        self.album.sizes.set([self.s["12-meter"]])
        p = Product.objects.create(title="تست۳", slug="t3", album=self.album)
        v = Variation.objects.create(product=p, size=self.s["6-meter"], manual_price=1_000_000)
        self.assertEqual(v.final_price, 1_000_000)

    def test_sync_album_variations(self):
        self.album.sizes.set([self.s["12-meter"], self.s["6-meter"], self.s["runner-4x1"]])
        self.album.even_sizes.set([self.s["runner-4x1"]])
        p = Product.objects.create(title="تست۴", slug="t4", album=self.album)
        old = Variation.objects.create(product=p, size=self.s["9-meter"], manual_price=5)
        keep = Variation.objects.create(product=p, size=self.s["12-meter"], sale_price=1_000_000)
        sync_album_variations([p], reset=True)
        vs = {v.size.slug: v for v in p.variations.select_related("size")}
        self.assertEqual(set(vs), {"12-meter", "6-meter", "runner-4x1"})
        self.assertFalse(Variation.objects.filter(pk=old.pk).exists())
        self.assertEqual(vs["12-meter"].pk, keep.pk)
        self.assertIsNone(vs["12-meter"].sale_price)
        self.assertTrue(vs["runner-4x1"].is_pair_only)
        p.refresh_from_db()
        self.assertEqual(p.min_price, 28_000_000)   # قیمت محصول آلبومی = قیمت ۱۲ متری


class OwnPriceTests(TestCase):
    """قیمت‌های جدا از آلبوم باید همراه آلبوم تغییر کنند و قابل پاک‌سازی باشند."""

    def setUp(self):
        seed_sizes()
        self.s = {s.slug: s for s in Size.objects.all()}
        self.album = Album.objects.create(name="۷۰۰ شانه", code="A700", base_size=self.s["12-meter"], base_price=Decimal("30000000"))
        self.p = Product.objects.create(title="پلی استر", slug="poly", album=self.album, custom_base_price=Decimal("24000000"))
        self.v12 = Variation.objects.create(product=self.p, size=self.s["12-meter"])
        self.v6 = Variation.objects.create(product=self.p, size=self.s["6-meter"], override_price=Decimal("10000000"))
        self.v12.sale_price = self.v12.final_price - 2_000_000
        self.v12.save()

    def test_album_change_scales_own_prices(self):
        old_final, old_sale = self.v12.final_price, self.v12.sale_price
        self.album.base_price = Decimal("36000000")   # ۲۰٪ بیشتر
        self.album.save()
        self.p.refresh_from_db()
        self.v12.refresh_from_db()
        self.v6.refresh_from_db()
        self.assertEqual(self.p.custom_base_price, Decimal("28800000"))
        self.assertEqual(self.v6.override_price, Decimal("12000000"))
        self.assertEqual(self.v12.final_price, self.album.size_price(self.s["12-meter"], Decimal("28800000")))
        self.assertEqual(self.v12.sale_price, round(old_sale * self.v12.final_price / old_final, -4))
        self.assertTrue(self.v12.on_sale)

    def test_follow_album(self):
        from .overrides import follow_album

        follow_album([self.p])
        self.p.refresh_from_db()
        self.v12.refresh_from_db()
        self.v6.refresh_from_db()
        self.assertIsNone(self.p.custom_base_price)
        self.assertIsNone(self.v6.override_price)
        self.assertIsNone(self.v12.sale_price)
        self.assertEqual(self.v12.final_price, self.album.size_price(self.s["12-meter"]))

    def test_sale_above_final_is_ignored(self):
        Variation.objects.filter(pk=self.v12.pk).update(sale_price=self.v12.final_price + 1)
        self.v12.refresh_from_db()
        self.assertFalse(self.v12.on_sale)
        self.assertEqual(self.v12.price, self.v12.final_price)
