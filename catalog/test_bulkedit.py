from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, KeywordRule, Product, ProductTag
from content.models import ContentEdit


class BulkEditTests(TestCase):
    """ویرایش گروهی: دسته/برچسب به همه یا از همه، دستهٔ اصلی جایگزین، کلمهٔ عنوان، قانون و برگرداندن."""

    def setUp(self):
        self.c700 = Category.objects.create(name="فرش 700 شانه", slug="c700")
        self.vint = Category.objects.create(name="فرش وینتیج", slug="vint")
        self.mocha = Category.objects.get(slug="فرش-موکا")
        KeywordRule.objects.get_or_create(keyword="موکا")[0].categories.add(self.mocha)
        self.tag = ProductTag.objects.create(name="فرش طرح افشان", slug="afshan")
        self.ps = []
        for i, t in enumerate(["فرش 700 شانه نقشه وینتیج هما زمینه کرم", "فرش 700 شانه نقشه وینتیج مینو زمینه نقره ای",
                               "فرش 700 شانه نقشه وینتیج آوا زمینه بژ"]):
            p = Product.objects.create(title=t, slug=f"p{i}", status="publish", primary_category=self.vint)
            p.categories.add(self.c700, self.vint)
            if i == 0:
                p.tags.add(self.tag)
            self.ps.append(p)
        for i in range(6):
            Product.objects.create(title=f"فرش 1200 شانه نقشه افشان {i} زمینه کرم", slug=f"other{i}", status="publish")
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)
        self.ids = ",".join(str(p.pk) for p in self.ps)

    def test_page_and_apply_and_undo(self):
        r = self.client.get("/panel/products/bulk-edit/", {"ids": [p.pk for p in self.ps]})
        d = r.context["d"]
        self.assertEqual([(x["obj"].name, x["n"]) for x in d["cats"]], [("فرش 700 شانه", 3), ("فرش وینتیج", 3)])
        self.assertEqual([(x["obj"].name, x["n"]) for x in d["tags"]], [("فرش طرح افشان", 1)])
        self.assertEqual(d["words"], ["وینتیج"])                     # کلمهٔ مشترک کمیاب
        self.client.post("/panel/products/bulk-edit/", {
            "ids": self.ids, f"c_{self.vint.pk}": "remove", f"t_{self.tag.pk}": "remove", "add_tags": ["برچسب تازه"],
            "word": "موکا", "rule": "وینتیج"})
        p = Product.objects.get(pk=self.ps[0].pk)
        self.assertEqual(p.title, "فرش 700 شانه موکا نقشه وینتیج هما زمینه کرم")
        self.assertEqual(set(p.categories.all()), {self.c700, self.mocha})       # قانون «موکا» دستهٔ موکا را داد
        self.assertEqual(p.primary_category, self.c700)                          # دستهٔ اصلی برداشته شد ← دستهٔ دیگر
        self.assertEqual([t.name for t in p.tags.all()], ["برچسب تازه"])
        self.assertTrue(KeywordRule.objects.filter(keyword="وینتیج", tags__name="برچسب تازه").exists())
        edit = ContentEdit.objects.latest("pk")
        self.client.post("/panel/content-tools/", {"do": "undo", "edit": edit.pk})
        p.refresh_from_db()
        self.assertEqual(p.title, "فرش 700 شانه نقشه وینتیج هما زمینه کرم")
        self.assertEqual(set(p.categories.all()), {self.c700, self.vint})
        self.assertEqual(p.primary_category, self.vint)
        self.assertEqual(list(p.tags.all()), [self.tag])

    def test_all_filtered_and_primary(self):
        r = self.client.get("/panel/products/bulk-edit/", {"all": "1", "categories": self.vint.pk})
        self.assertEqual(r.context["d"]["n"], 3)
        self.client.post("/panel/products/bulk-edit/", {"ids": self.ids, "primary": self.mocha.pk})
        for p in Product.objects.filter(pk__in=[x.pk for x in self.ps]):
            self.assertEqual(p.primary_category, self.mocha)
            self.assertIn(self.mocha, p.categories.all())                        # دستهٔ اصلی جزو دسته‌ها هم شد
