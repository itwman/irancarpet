import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, KeywordRule, Product, ProductTag
from content.finglish import tight
from content.models import ContentEdit
from pricing.models import Album, Size, seed_sizes


class TagCleanupTests(TestCase):
    """برچسب «فرش طرح افشان»: دستهٔ هم‌موضوع با ۳۰۱ به آن می‌رود و فقط فرش‌های افشان در آن می‌مانند."""

    def setUp(self):
        seed_sizes()
        self.tag = ProductTag.objects.create(name="فرش طرح افشان", slug="فرش-طرح-افشان")
        self.cat = Category.objects.create(name="فرش افشان", slug="afshan")
        self.album = Album.objects.create(name="700", code="A7", base_size=Size.objects.get(slug="12-meter"), base_price=10_000_000)
        self.album.default_tags.add(self.tag)
        mk = lambda t, s, tag=True: self._p(t, s, tag)  # noqa: E731
        self.a1 = mk("فرش ۷۰۰ شانه نقشه افشان پارسا زمینه کرم", "a1")
        self.v1 = mk("فرش ۷۰۰ شانه نقشه آوین زمینه کرم", "v1")
        self.v2 = mk("فرش ۷۰۰ شانه نقشه آوین زمینه لاکی", "v2")
        self.s1 = mk("فرش ۷۰۰ شانه نقشه سروش زمینه کرم", "s1")
        self.m1 = mk("فرش ۷۰۰ شانه نقشه افشان شاهی زمینه دودی", "m1", tag=False)
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)

    def _p(self, title, slug, tag):
        from content.render import design_from_title

        p = Product.objects.create(title=title, slug=slug, status="publish", design_name=design_from_title(title))
        if tag:
            p.tags.add(self.tag)
        return p

    def test_whole_word_rule(self):
        self.assertFalse(KeywordRule.has("ناز", "فرش نقشه نازنین زمینه کرم"))
        self.assertTrue(KeywordRule.has("افشان", "فرش نقشه افشان‌پارسا، زمینه کرم"))
        self.assertTrue(KeywordRule.has("فرش وینتیج", "فرش  وینتیج طوسی"))

    def test_migration_redirects_category_and_rule(self):
        self.m1.categories.add(self.cat)
        mig = importlib.import_module("catalog.migrations.0021_afshan_tag_main")
        mig.forward(apps, None)
        self.cat.refresh_from_db()
        self.assertEqual(self.cat.get_absolute_url(), "/product-tag/فرش-طرح-افشان/")
        r = self.client.get("/product-category/afshan/page/3/")
        from urllib.parse import unquote

        self.assertEqual((r.status_code, unquote(r["Location"])), (301, "/product-tag/فرش-طرح-افشان/"))
        self.assertIn(self.tag, self.m1.tags.all())                     # فرش دستهٔ افشان برچسب گرفت
        self.assertTrue(KeywordRule.objects.filter(keyword="افشان", tags=self.tag).exists())
        from seo.sitemaps import sections

        self.assertNotIn(self.cat, list(sections()["product_cat"][0]))

    def test_cleanup_keep_design_and_undo(self):
        url = f"/panel/tags/cleanup/?tag={self.tag.pk}"
        r = self.client.get(url)
        d = r.context["d"]
        self.assertEqual((d["word"], d["total"], d["keep"], d["missing"]), ("افشان", 4, 1, [self.m1.pk]))
        self.assertEqual([(g["label"], g["n"]) for g in d["groups"]], [("آوین", 2), ("سروش", 1)])
        self.assertContains(r, "کدام فرش‌ها واقعاً")
        self.client.post("/panel/tags/cleanup/", {"tag": self.tag.pk, "word": "افشان", "apply": "1", "keep": [tight("آوین")],
                                                  "add": "1", "albums": "1"})
        self.assertEqual(set(self.tag.products.all()), {self.a1, self.v1, self.v2, self.m1})
        self.assertTrue(KeywordRule.objects.filter(keyword="آوین", tags=self.tag).exists())
        self.assertFalse(self.album.default_tags.exists())
        # فرش تازهٔ «آوین» از قانون، برچسب افشان می‌گیرد
        self.assertIn(self.tag, [t for r in KeywordRule.matches("فرش نقشه آوین زمینه بژ") for t in r.tags.all()])
        edit = ContentEdit.objects.latest("pk")
        self.client.post("/panel/content-tools/", {"do": "undo", "edit": edit.pk})
        self.assertEqual(set(self.tag.products.all()), {self.a1, self.v1, self.v2, self.s1})

    def test_product_page_links_tag(self):
        for i in range(4):
            Product.objects.create(title=f"فرش نقشه افشان {i}", slug=f"x{i}", status="publish").tags.add(self.tag)
        r = self.client.get(self.a1.get_absolute_url())
        self.assertContains(r, 'href="/product-tag/فرش-طرح-افشان/"')
