import json
from decimal import Decimal

from django.core.cache import cache

from catalog.models import Product
from pricing.models import M2_SLUG, Album, Size, seed_sizes
from django.test import TestCase, override_settings

from shop import tests as flow
from shop.models import Order, ShopSettings


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True)
class M2Tests(TestCase):
    """فرش متری: آلبوم «متری»، ماشین‌حساب، سبد، سفارش، لیست قیمت، ترب و اپ."""
    otp_login = flow.ShopFlowTests.otp_login
    checkout_data = flow.ShopFlowTests.checkout_data

    def setUp(self):
        flow.ShopFlowTests.setUp(self)
        cache.clear()
        self.album = Album.objects.create(name="کناره 500 شانه", code="K500", base_size=Size.objects.get(slug="12-meter"),
                                          base_price=Decimal("2000000"), profit_percent=Decimal("15"), round_to=10_000, unit="m2",
                                          slug="kenare-500")
        self.k = Product.objects.create(title="کناره فرش برشی 500 شانه نقشه حوض زمینه سرمه ای", slug="kenare", status="publish", album=self.album)
        from pricing.albums import sync_album_variations

        sync_album_variations([Product.objects.select_related("album").get(pk=self.k.pk)])
        self.k.refresh_from_db()
        self.v = self.k.variations.get()
        ShopSettings.objects.update(free_shipping_min=1_000_000)

    def test_album_and_product(self):
        self.album.refresh_from_db()
        self.assertEqual(self.album.base_size.slug, M2_SLUG)
        self.assertEqual(list(self.album.sizes.values_list("slug", flat=True)), [M2_SLUG])
        self.assertEqual((self.v.size.slug, self.v.price), (M2_SLUG, 2_300_000))  # ۲ میلیون + ۱۵٪
        self.assertEqual((self.k.price_unit, self.k.min_price), ("m2", 2_300_000))
        r = self.client.get(self.k.get_absolute_url())
        self.assertContains(r, "قیمت هر متر مربع")
        self.assertContains(r, 'name="length"')
        self.assertContains(r, "۵۰ سانت")
        self.assertContains(r, '"MTK"')

    def test_cart_rules_and_order(self):
        # عرض ۰٫۵ و طول ۱٫۵ ← کمتر از ۲ متر
        self.client.post("/cart/add/", {"variation": self.v.pk, "width": "0.50", "length": "۱٫۵"})
        self.assertFalse(self.client.session.get("cart"))
        # بدون عرض و طول هم پذیرفته نمی‌شود
        self.client.post("/cart/add/", {"variation": self.v.pk, "qty": 1})
        self.assertFalse(self.client.session.get("cart"))
        self.client.post("/cart/add/", {"variation": self.v.pk, "width": "0.50", "length": "۲٫۳۰", "qty": 2})
        self.client.post("/cart/add/", {"variation": self.v.pk, "width": "1.20", "length": "1.5"})  # پهن: کمترین ۱٫۵
        cart = self.client.session["cart"]
        self.assertEqual(cart[f"{self.v.pk}@0.50x2.30"], 2)
        self.assertIn(f"{self.v.pk}@1.20x1.50", cart)
        r = self.client.get("/cart/")
        # ۰٫۵ × ۲٫۳ = ۱٫۱۵ متر مربع × ۲٬۳۰۰٬۰۰۰ = ۲٬۶۴۵٬۰۰۰ ← ۲٬۷۰۰٬۰۰۰ (گرد به ۱۰۰ هزار)
        self.assertContains(r, "۲٬۷۰۰٬۰۰۰")
        self.assertContains(r, "۵٫۴۰۰٬۰۰۰".replace("٫", "٬"))
        self.otp_login()
        self.client.post("/checkout/", self.checkout_data())
        o = Order.objects.get()
        it = o.items.get(width=Decimal("0.50"))
        self.assertEqual((it.length, it.unit_price, it.quantity), (Decimal("2.30"), 2_700_000, 2))
        self.assertIn("عرض ۰٫۵ × طول ۲٫۳ متر", it.size_label)
        self.assertEqual(o.shipping_mode, "cod")  # فرش متری ارسال رایگان ندارد
        self.assertIn("پس‌کرایه", o.admin_note)

    def test_pricelist_torob_and_app(self):
        r = self.client.get("/carpets-price-list/")
        self.assertContains(r, "قیمت کناره و فرش سجاده‌ای")
        self.assertContains(r, "۲٬۳۰۰٬۰۰۰")
        r = self.client.get(self.album.get_absolute_url())
        self.assertContains(r, "قیمت هر متر مربع")
        from torob.feed import format_row
        from torob.models import TorobSettings

        row = format_row(self.k, TorobSettings.load())
        self.assertIn("(قیمت هر متر مربع)", row["title"])
        d = self.client.post("/api/app/v1/cart/quote/", json.dumps({"items": [
            {"variation": self.v.pk, "qty": 1, "width": 0.5, "length": 2.3}, {"variation": self.v.pk, "qty": 1}]}),
            content_type="application/json").json()
        self.assertEqual(d["lines"][0]["unit_price"], 2_700_000)
        self.assertTrue(d["lines"][1]["problem"])  # بدون اندازه
        p = self.client.get(f"/api/app/v1/products/{self.k.pk}/").json()
        self.assertEqual(p["m2"]["price"], 2_300_000)
