"""آزمون موتور قیمت سایز دلخواه با مثال‌های خود فروشگاه."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from blog.models import Page

from .custom import QuoteError, Rates, as_dict, quote
from .models import Album, Size, seed_sizes

R = Rates(70_150_000 / 12, 55_625_000 / 9, 70_150_000, 55_625_000, "آزمایش", 1)


class CustomSizeTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()

    def test_shop_examples(self):
        q = quote(4, 5, 1, "700", rates=R)  # دو نیمهٔ ۲٫۵×۴، دوخت ۴ متر
        self.assertEqual((q.halved.across, q.halved.along, q.halved.seam), (2.5, 4, 4))
        self.assertEqual(q.total, 139_611_112)
        q = quote(5, 4, 2, "700", rates=R)  # طراحی یک بار، دوخت دو بار
        self.assertEqual(q.total, 271_222_223)
        q = quote(2.98, 1.48, 1, "700", rates=R)  # دو نیمهٔ ۱٫۴۹×۱٫۴۸، پول ۳×۱٫۴۸
        self.assertEqual((q.halved.across, q.halved.along), (1.49, 1.48))
        self.assertEqual(q.total, 30_679_660)
        self.assertEqual(q.pair_offer["qty"], 2)
        q = quote("۱٫۴۸", "۲٫۹۸", "۲", "700", rates=R)  # جفت کامل، بدون دوخت
        self.assertEqual((q.n_whole, q.n_halved, q.total), (2, 0, 53_675_160))

    def test_orientation_alternative_big_and_limits(self):
        q = quote(5, 3, 1, "700", rates=R)  # ۵×۳ یعنی ۳ روی عرض؛ تکی ← دو نیمه + پیشنهاد جفت
        self.assertEqual((q.width, q.length), (3, 5))
        self.assertIsNotNone(q.pair_offer)
        self.assertLess(q.pair_offer["each"], q.pair_offer["each_now"])
        q = quote(4, 5, 1, "1200", rates=R)  # دستگاه ۴ متری: روش اقتصادی بدون ضمانت
        self.assertIsNotNone(q.alternative)
        self.assertTrue(as_dict(q)["alternative"]["total_fa"])
        q = quote(7, 8, 1, "700", rates=R)  # بزرگ: دستگاه ۴ متری
        self.assertEqual(q.loom, 4)
        self.assertTrue(q.notes)
        with self.assertRaises(QuoteError):
            quote(0.3, 2, 1, "700", rates=R)
        with self.assertRaises(QuoteError):
            quote(2, 16, 1, "700", rates=R)
        self.assertEqual(quote(150, 200, 1, "700", rates=R).width, 1.5)  # سانتی‌متر ← متر

    def test_endpoint_and_block(self):
        s = {x.slug: x for x in Size.objects.all()}
        a = Album.objects.create(name="فرش 700 شانه آزمایشی", code="T", base_size=s["12-meter"], base_price=Decimal("50000000"),
                                 profit_percent=Decimal("0"), waste_value=Decimal("2000000"))
        a.sizes.set([s["12-meter"], s["9-meter"]])
        from catalog.models import Product
        from core.models import Media
        from pricing.albums import sync_album_variations

        p = Product.objects.create(title="فرش 700 شانه نقشه آزمون", slug="t", album=a, status="publish", image=Media.objects.create(file="x.jpg"))
        sync_album_variations([p])
        j = self.client.get("/custom-size/quote/", {"w": "2.5", "l": "4", "q": "1", "reeds": "700", "album": a.pk}).json()
        self.assertTrue(j["ok"], j)
        self.assertIn("آزمایشی", j["source"])
        self.assertIn(j["split"], ("length", "width"))  # ۲٫۵×۴ تکی: دو نیمه
        self.assertFalse(self.client.get("/custom-size/quote/", {"w": "0.1", "l": "4"}).json()["ok"])
        Page.objects.create(title="سفارش", slug="custom", status="publish", content="<p>متن</p><p>[custom_size_calc]</p>")
        html = self.client.get("/custom/").content.decode()
        self.assertIn("data-cz", html)
        self.assertIn("قیمت حدودی فرش با سایز دلخواه", html)
