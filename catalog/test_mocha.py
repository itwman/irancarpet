import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from catalog import mocha
from catalog.models import Category, KeywordRule, Product
from core.models import SiteSettings


class MochaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.get(slug=mocha.SLUG)

    def make(self, i, **kw):
        from core.models import Media

        m = Media.objects.create(file=f"x{i}.jpg", title="x")
        p = Product.objects.create(title=f"فرش ۱۲۰۰ شانه موکا نقشه آوین{i} زمینه صدفی", slug=f"avin-{i}", status="publish",
                                   image=m, min_price=10_000_000, **kw)
        p.categories.add(self.cat)
        return p

    def test_category_seo_and_faq(self):
        self.assertIn("Mocha Mousse", self.cat.description)
        self.assertEqual(self.cat.focus_keyword, "فرش موکا")
        self.assertTrue(self.cat.mirror_auto)
        self.assertTrue(KeywordRule.objects.filter(keyword="موکا", categories=self.cat).exists())
        r = self.client.get(self.cat.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "رنگ موکا دقیقاً چه رنگی است؟")
        self.assertContains(r, '"FAQPage"')

    def test_home_feature_and_mirror_pick(self):
        from mirror.models import MirrorPick, MirrorSettings

        MirrorSettings.objects.update_or_create(pk=1, defaults={"feed_enabled": True})
        s = SiteSettings.load()
        s.feature_enabled, s.feature_category, s.feature_title = True, self.cat, "فرش‌های پالت موکا"
        s.save()
        for i in range(3):
            self.make(i)
        self.assertNotContains(self.client.get("/"), "فرش‌های پالت موکا")  # کمتر از ۴ فرش
        cache.clear()
        p = self.make(9)
        self.assertContains(self.client.get("/"), "فرش‌های پالت موکا")
        self.assertTrue(MirrorPick.objects.filter(product=p).exists())  # دستهٔ «خودکار برای فرشستان»

    def test_mirror_title_with_border(self):
        from mirror.sync import build_title

        row = {"t": "فرش ۱۲۰۰ شانه نقشه جواهر زمینه صدفی حاشیه دلفینی", "d": "جواهر", "c": "صدفی", "r": "1200",
               "specs": [{"attr": "border-color", "name": "دلفینی"}]}
        self.assertIn("زمینه صدفی حاشیه دلفینی", build_title(row, ""))
        row["specs"] = [{"attr": "border-color", "name": "صدفی"}]
        self.assertNotIn("حاشیه", build_title(row, ""))
