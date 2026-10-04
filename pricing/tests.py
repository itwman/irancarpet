"""آزمون موتور قیمت با مثال‌های README افزونهٔ ICSD Price Manager."""
from decimal import Decimal

from django.test import TestCase

from catalog.models import Product, Variation

from .models import Album, PricingSettings, Size, seed_sizes


class PricingEngineTests(TestCase):
    def setUp(self):
        seed_sizes()
        PricingSettings.load()
        self.s = {s.slug: s for s in Size.objects.all()}
        self.album = Album.objects.create(
            name="۱۲۰۰ شانه آرشیدا", code="ARSHIDA_1200", base_size=self.s["12-meter"],
            base_price=Decimal("24000000"), waste_type="fixed", waste_value=Decimal("2000000"),
        )

    def final(self, slug):
        return PricingSettings.load().apply_markup(self.album.purchase_price(self.s[slug]))

    def test_readme_example_1(self):
        self.assertEqual(self.final("12-meter"), 28_100_000)
        self.assertEqual(self.final("6-meter"), 14_300_000)
        self.assertEqual(self.final("9-meter"), 23_500_000)
        self.assertEqual(self.final("runner-4x1"), 9_700_000)
        self.assertEqual(self.final("doormat-85x50"), 1_500_000)
        self.assertEqual(self.final("round-d3"), 21_200_000)

    def test_percent_waste(self):
        self.album.waste_type, self.album.waste_value = "percent", Decimal("10")
        self.assertEqual(int(self.album.purchase_price(self.s["9-meter"])), 19_800_000)

    def test_album_change_reprices_products(self):
        p = Product.objects.create(title="تست", slug="test", album=self.album)
        v = Variation.objects.create(product=p, size=self.s["6-meter"])
        self.assertEqual(v.final_price, 14_300_000)
        self.album.base_price = Decimal("12000000")
        self.album.save()
        v.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(v.final_price, PricingSettings.load().apply_markup(Decimal("6000000")))
        self.assertEqual(p.min_price, v.final_price)

    def test_override_and_custom_base(self):
        p = Product.objects.create(title="تست۲", slug="test2", album=self.album, custom_base_price=Decimal("30000000"))
        v = Variation.objects.create(product=p, size=self.s["6-meter"])
        self.assertEqual(v.purchase_price, 15_000_000)
        v.override_price = Decimal("10000000")
        v.save()
        self.assertEqual(v.final_price, PricingSettings.load().apply_markup(Decimal("10000000")))


class OwnPriceTests(TestCase):
    """قیمت‌های جدا از آلبوم باید همراه آلبوم تغییر کنند و قابل پاک‌سازی باشند."""

    def setUp(self):
        seed_sizes()
        PricingSettings.load()
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
        self.assertEqual(self.v12.purchase_price, 28_800_000)
        self.assertEqual(self.v12.sale_price, round(old_sale * self.v12.final_price / old_final, -4))
        self.assertTrue(self.v12.on_sale)
        self.assertEqual(self.p.min_price, self.v6.final_price)

    def test_follow_album(self):
        from .overrides import follow_album

        follow_album([self.p])
        self.p.refresh_from_db()
        self.v12.refresh_from_db()
        self.v6.refresh_from_db()
        self.assertIsNone(self.p.custom_base_price)
        self.assertIsNone(self.v6.override_price)
        self.assertIsNone(self.v12.sale_price)
        self.assertEqual(self.v12.final_price, PricingSettings.load().apply_markup(Decimal("30000000")))

    def test_sale_above_final_is_ignored(self):
        Variation.objects.filter(pk=self.v12.pk).update(sale_price=self.v12.final_price + 1)
        self.v12.refresh_from_db()
        self.assertFalse(self.v12.on_sale)
        self.assertEqual(self.v12.price, self.v12.final_price)

    def test_retro_command(self):
        from django.core.management import call_command

        from .models import PriceLog

        self.album.base_price = Decimal("36000000")
        Album.objects.filter(pk=self.album.pk).update(base_price=self.album.base_price)   # تغییر به روش قدیم (بدون هم‌نسبت شدن)
        PriceLog.objects.create(album=self.album, old_price=Decimal("30000000"), new_price=Decimal("36000000"), reason="panel_edit")
        call_command("sync_album_overrides", since="2000-01-01 00:00", stdout=open("/dev/null", "w"))
        self.p.refresh_from_db()
        self.assertEqual(self.p.custom_base_price, Decimal("28800000"))
        with self.assertRaises(Exception):
            call_command("sync_album_overrides", since="2000-01-01 00:00", stdout=open("/dev/null", "w"))
