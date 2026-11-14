"""تعداد پرس‌وجوهای صفحهٔ فرش: با زیاد شدن فرصت‌های ویژه، رنگ‌های فرش‌یاب و صفحه‌های فرود نباید بالا برود.

پیش از آبان ۱۴۰۵ هر صفحهٔ فرش روی سرور حدود ۳۵۰ پرس‌وجو می‌زد (هر فرصت ویژه دو پرس‌وجو، هر نیاز رنگی و هر صفحهٔ دستی
یکی، هر ویژگی فرش یکی برای نام ویژگی و…) و ساختنش نزدیک یک ثانیه طول می‌کشید.
"""
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from catalog.models import Attribute, AttributeTerm, Brand, Category, Product, ProductTag
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes


class ProductPageQueryTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه", is_public=True)
        color = Attribute.objects.create(slug="background-color", label="رنگ زمینه", is_public=True)
        pile = Attribute.objects.create(slug="pile", label="جنس نخ خاب", is_public=True)
        r700 = AttributeTerm.objects.create(attribute=reeds, name="700", slug="700")
        acr = AttributeTerm.objects.create(attribute=pile, name="آکریلیک", slug="acr")
        self.colors = [AttributeTerm.objects.create(attribute=color, name=f"رنگ{i}", slug=f"c{i}") for i in range(4)]
        brand = Brand.objects.create(name="برند", slug="brand")
        parent = Category.objects.create(name="فرش ۷۰۰ شانه", slug="carpet-700-reeds")
        cat = Category.objects.create(name="ساده", slug="700-simple", parent=parent)
        tags = [ProductTag.objects.create(name=f"برچسب {i}", slug=f"t{i}") for i in range(5)]
        self.album = Album.objects.create(name="آلبوم", code="A", base_size=s["12-meter"], base_price=Decimal("40000000"),
                                          shipping_fixed=0, waste_value=0)
        self.album.sizes.set([s["12-meter"], s["6-meter"], s["9-meter"], s["rug-225x150"]])
        self.size = s["12-meter"]
        self.products = []
        for i in range(16):
            p = Product.objects.create(title=f"فرش 700 شانه نقشه دلاریس زمینه رنگ{i % 4} {i}", slug=f"p{i}", album=self.album,
                                       status="publish", brand=brand, primary_category=cat)
            p.specs.add(r700, acr, self.colors[i % 4])
            p.categories.add(cat, parent)
            p.tags.add(*tags)
            self.products.append(p)
        sync_album_variations(self.products, reset=True)
        self.url = self.products[0].get_absolute_url()

    def count(self):
        with CaptureQueriesContext(connection) as q:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        return len(q)

    def add_needs_and_offers(self, n):
        from finder.models import Need
        from shop.models import SpecialOffer

        for i in range(n):
            need = Need.objects.create(group="color", title=f"رنگ {i}")
            need.terms.add(self.colors[i % 4])
            SpecialOffer.objects.create(product=self.products[i + 1], size=self.size, percent=10, quantity=3)
        cache.clear()

    def test_query_count_does_not_grow(self):
        self.client.get(self.url)
        small = self.count()
        self.assertLess(small, 40)
        self.add_needs_and_offers(8)
        self.client.get(self.url)  # کش‌های یک‌ساعته (پیوند صفحه‌های فرود، مرتبط‌ها) پر شود
        warm = self.count()
        self.assertLess(warm, small + 6)
        cache.clear()
        self.assertLess(self.count(), 80)  # بار اول هر فرش (گوگل بیشتر همین را می‌بیند)

    def test_offer_still_shown(self):
        from shop.models import SpecialOffer

        SpecialOffer.objects.create(product=self.products[0], size=self.size, percent=10, quantity=3)
        cache.clear()
        r = self.client.get(self.url)
        self.assertContains(r, "فرصت ویژهٔ خرید")
        self.assertContains(r, "۳ تخته")
