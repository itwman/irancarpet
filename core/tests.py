from django.test import TestCase

from core.hashers import phpass_check
from core.utils.php import php_unserialize
from core.wp.html import clean_content


class UtilTests(TestCase):
    def test_unserialize(self):
        self.assertEqual(php_unserialize('a:1:{i:0;s:7:"noindex";}'), {0: "noindex"})
        self.assertEqual(php_unserialize('a:1:{s:4:"name";s:6:"فرش";}')["name"], "فرش")

    def test_phpass(self):
        # هش نمونهٔ وردپرس برای رمز "test"
        self.assertTrue(phpass_check("test", "$P$B9bDQkmqBdPHPIQDO4T1tCWRTQtFvy1"))
        self.assertFalse(phpass_check("wrong", "$P$B9bDQkmqBdPHPIQDO4T1tCWRTQtFvy1"))

    def test_autop(self):
        self.assertEqual(clean_content("الف\n\nب"), "<p>الف</p>\n<p>ب</p>")


class AutoDescriptionTests(TestCase):
    """توضیح متای یکتا و ۱۲۰ تا ۱۶۰ حرفی برای صفحه‌های بدون توضیح دستی یا با توضیح تکراری."""

    def setUp(self):
        from django.core.cache import cache
        from decimal import Decimal

        from catalog.models import Attribute, AttributeTerm, Category, Product
        from pricing.albums import sync_album_variations
        from pricing.models import Album, Size, seed_sizes

        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        album = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("45000000"))
        album.sizes.set([s["12-meter"], s["9-meter"]])
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        pile = Attribute.objects.create(slug="pile", label="جنس نخ خاب")
        self.cat = Category.objects.create(name="فرش ۱۲۰۰ شانه", slug="c1200")
        shared = "فرش ماشینی با ضمانت و ارسال رایگان به سراسر کشور و کیفیت عالی و رنگ ثابت"
        self.items = []
        for i, color in enumerate(["کرم", "لاکی"]):
            p = Product.objects.create(title=f"فرش 1200 شانه نقشه افشان زمینه {color}", slug=f"p{i}", album=album,
                                       status="publish", seo_description=shared)
            p.specs.add(AttributeTerm.objects.get_or_create(attribute=reeds, name="1200", slug="1200")[0],
                        AttributeTerm.objects.get_or_create(attribute=pile, name="100% آکریلیک هیت ست", slug="acr")[0])
            p.categories.add(self.cat)
            sync_album_variations([p], reset=True)
            p.refresh_price_cache()
            self.items.append(p)

    def test_product_descriptions_unique_and_sized(self):
        from core import seo

        ds = [seo.build(p, "product")["description"] for p in self.items]
        self.assertEqual(len(set(ds)), 2)  # متن مشترک کنار گذاشته شد
        for d in ds:
            self.assertTrue(120 <= len(d) <= 160, (len(d), d))
            self.assertIn("قیمت ۱۲ متری", d)
        # توضیح دستی یکتا دست نمی‌خورد
        p = self.items[0]
        p.seo_description = "توضیح دستی یکتا و کامل دربارهٔ همین فرش افشان کرم، برای آزمایش اینکه سایت آن را تغییر نمی‌دهد."
        p.save()
        self.assertEqual(seo.build(p, "product")["description"], p.seo_description)

    def test_category_description(self):
        from core import seo

        d = seo.build(self.cat, "product_cat")["description"]
        self.assertTrue(110 <= len(d) <= 160, (len(d), d))
        self.assertIn("۲ طرح", d)
        self.assertNotEqual(seo.build(self.cat, "product_cat", page=2)["description"], d)
