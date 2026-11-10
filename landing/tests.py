"""صفحه‌های «فرش N شانه» به‌عنوان صفحهٔ اصلی هر شانه، و صفحه‌های فرود نقشه/سبک/قالیچه (مهاجرت 0005)."""
import importlib
from urllib.parse import unquote
from decimal import Decimal

from django.apps import apps
from django.core.cache import cache
from django.test import TestCase

from catalog.models import Attribute, AttributeTerm, Category, Product, ProductTag
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from .models import LandingPage

MIG = importlib.import_module("landing.migrations.0005_reeds_hubs_design_pages")


class ReedsHubTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه", is_public=True)
        self.r700 = AttributeTerm.objects.create(attribute=self.reeds, name="700", slug="700")
        self.cat = Category.objects.create(name="فرش ۷۰۰ شانه", slug="carpet-700-reeds",
                                           seo_title="فرش 700 شانه ☀️ خرید آنلاین و قیمت فرش ماشینی 700 شانه ارزان")
        self.tag = ProductTag.objects.create(name="فرش طرح افشان", slug="فرش-طرح-افشان")
        album = Album.objects.create(name="آلبوم", code="A", base_size=s["12-meter"], base_price=Decimal("40000000"),
                                     shipping_fixed=0, waste_value=0)
        album.sizes.set([s["12-meter"], s["6-meter"], s["rug-225x150"]])
        self.products = []
        for i in range(5):
            p = Product.objects.create(title=f"فرش 700 شانه نقشه افشان {i}", slug=f"p{i}", album=album, status="publish")
            p.specs.add(self.r700)
            p.categories.add(self.cat)
            p.tags.add(self.tag)
            self.products.append(p)
        sync_album_variations(self.products, reset=True)

    def run_migration(self):
        MIG.forwards(apps, None)
        from landing import build

        build.sync(log=lambda *_: None)

    def test_reeds_hub(self):
        self.run_migration()
        self.cat.refresh_from_db()
        self.assertIn("راهنمای خرید فرش ۷۰۰ شانه", self.cat.description)
        self.assertNotIn("☀", self.cat.seo_title)
        # آرشیو تکراری شانه با ۳۰۱ به دسته می‌رود و پیوندهای سایت هم مستقیم به دسته‌اند
        self.r700.refresh_from_db()
        self.assertEqual(self.r700.get_absolute_url(), "/product-category/carpet-700-reeds/")
        r = self.client.get("/reeds-per-meter/700/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), "/product-category/carpet-700-reeds/")
        r = self.client.get("/product-category/carpet-700-reeds/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "راهنمای خرید فرش ۷۰۰ شانه")
        self.assertNotContains(r, "[reeds_compare")          # بلوک زنده ساخته شده، نه متن خام
        self.assertContains(r, "/carpets/فرش-700-شانه-12-متری/")  # پیوند به صفحه‌های فرود همان شانه
        self.assertContains(r, "FAQPage")
        # متنی که از پنل نوشته شده دست نمی‌خورد
        self.cat.description = "<p>متن خودم</p>"
        self.cat.save()
        self.run_migration()
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.description, "<p>متن خودم</p>")

    def test_design_and_rug_pages(self):
        self.run_migration()
        lp = LandingPage.objects.get(slug="فرش-افشان")
        self.assertEqual(lp.count, 5)
        self.assertContains(self.client.get("/carpets/فرش-افشان/"), "فرش افشان چیست؟")
        # برچسب هم‌موضوع با صفحهٔ تازه یکی شد
        r = self.client.get("/product-tag/فرش-طرح-افشان/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), "/carpets/فرش-افشان/")
        rug = LandingPage.objects.get(slug="فرش-3-متری")
        self.assertEqual(rug.size.slug, "rug-225x150")
        self.assertEqual(self.client.get("/carpets/فرش-3-متری/").status_code, 200)
        # کمتر از ۴ فرش ← صفحه ساخته نمی‌شود
        self.assertFalse(LandingPage.objects.filter(slug="فرش-خشتی").exists())
        self.assertFalse(LandingPage.objects.filter(slug="قالیچه-1-5-متری").exists())
        # صفحهٔ فرش به صفحهٔ نقشه پیوند می‌دهد
        r = self.client.get(self.products[0].get_absolute_url())
        self.assertContains(r, "/carpets/فرش-افشان/")
        self.assertNotContains(r, "/product-tag/فرش-طرح-افشان/")

    def test_farshestan_untouched(self):
        with self.settings(SITE_THEME="farshestan"):
            MIG.forwards(apps, None)
        self.assertFalse(LandingPage.objects.filter(slug="فرش-افشان").exists())
        self.assertEqual(AttributeTerm.objects.get(pk=self.r700.pk).redirect_url, "")


class MergeDuplicatesTests(TestCase):
    def test_color_and_size_duplicates(self):
        from finder.models import Need

        seed_sizes()
        mig = importlib.import_module("landing.migrations.0006_merge_color_size_duplicates")
        cream = Need.objects.create(group="color", title="کرم و روشن")
        red = Need.objects.create(group="color", title="قرمز و لاکی")
        LandingPage.objects.create(slug="فرش-کرم", title="فرش کرم", color=cream, count=10)
        LandingPage.objects.create(slug="فرش-قرمز", title="فرش قرمز", color=red, count=2)   # کم‌فرش؛ مقصد نمی‌شود
        LandingPage.objects.create(slug="فرش-12-متری", title="فرش ۱۲ متری", size=Size.objects.get(slug="12-meter"), count=9)
        color = Attribute.objects.create(slug="background-color", label="رنگ زمینه", is_public=True)
        beige = AttributeTerm.objects.create(attribute=color, name="بژ", slug="بژ")
        green_cream = AttributeTerm.objects.create(attribute=color, name="کرم سبز", slug="کرم-سبز")
        red_t = AttributeTerm.objects.create(attribute=color, name="قرمز", slug="قرمز")
        t_cream = ProductTag.objects.create(name="فرش زمینه کرم", slug="فرش-زمینه-کرم")
        t12 = ProductTag.objects.create(name="فرش 12 متری", slug="فرش-12-متری")
        mig.forwards(apps, None)
        for o in (beige, green_cream, red_t, t_cream, t12):
            o.refresh_from_db()
        self.assertEqual(beige.redirect_url, "/carpets/فرش-کرم/")
        self.assertEqual(t_cream.redirect_url, "/carpets/فرش-کرم/")
        self.assertEqual(t12.redirect_url, "/carpets/فرش-12-متری/")
        self.assertEqual(green_cream.redirect_url, "")   # رنگ ترکیبی صفحهٔ خودش را نگه می‌دارد
        self.assertEqual(red_t.redirect_url, "")         # صفحهٔ مقصد زنده نیست
        r = self.client.get("/background-color/بژ/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), "/carpets/فرش-کرم/")
