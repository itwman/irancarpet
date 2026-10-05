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


class GeoTests(TestCase):
    URL = ("https://www.google.com/maps/place/%D8%A7%DB%8C%D8%B1%D8%A7%D9%86+%DA%A9%D8%A7%D8%B1%D9%BE%D8%AA%E2%80%AD/@33.9966165,51.4547783,17.11z/"
           "data=!4m14!1m7!3m6!1s0x3f9683ab3f3ed897:0xa72e61d95cf3ac94!2sIran+Carpet!8m2!3d33.9552058!4d51.3899835!16s%2Fg%2F11b70h90rq"
           "!3m5!1s0x3f96857d29a7745f:0xa8af4d072ef54cdc!8m2!3d33.9956089!4d51.4582713!16s%2Fg%2F11lkx44sr6?entry=ttu&g_ep=EgoyMDI2MDkzMC4wIKXMDSoASAFQAw%3D%3D")

    def test_parse(self):
        from decimal import Decimal

        from core import geo

        self.assertEqual(geo.from_url(self.URL), (Decimal("33.995609"), Decimal("51.458271")))
        self.assertEqual(geo.coord("۳۳٫۹۹۵۶۰۸۹"), Decimal("33.995609"))
        self.assertEqual(geo.pair("33.9956089, 51.4582713"), (Decimal("33.995609"), Decimal("51.458271")))

    def test_settings_form(self):
        from django.contrib.auth import get_user_model

        from core.models import SiteSettings
        from dashboard.views.settings import FORMS, make_form

        u = get_user_model().objects.create_user("st", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)
        _, fields = FORMS["site"]
        inst = SiteSettings.load()
        data = {f: getattr(inst, f) or "" for f in fields if f not in ("trust_badge",)}
        data.update({"site_name": "ایران کارپت", "title_separator": "-", "latitude": "", "longitude": "", "map_google": self.URL})
        data = {k: v for k, v in data.items() if not isinstance(v, bool) or v}
        form = make_form("site", data)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual((str(obj.latitude), str(obj.longitude)), ("33.995609", "51.458271"))
        data.update({"latitude": "33.9956089", "longitude": "51.4582713", "map_google": ""})
        self.assertTrue(make_form("site", data).is_valid())
        data.update({"latitude": "51.4582713", "longitude": "33.9956089"})  # جابه‌جا
        f = make_form("site", data)
        self.assertTrue(f.is_valid())
        self.assertEqual(str(f.cleaned_data["latitude"]), "33.995609")
