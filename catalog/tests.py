from django.test import TestCase

from blog.models import Page
from core.models import SiteSettings

from .models import Attribute, AttributeTerm, Product


class AttributeFilterTests(TestCase):
    """فیلترها فقط از ویژگی‌های «در فیلترها» ساخته می‌شوند (شانه، تراکم، جنس نخ خاب، رنگ زمینه)."""

    def setUp(self):
        self.reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه", order=1)
        self.pile = Attribute.objects.create(slug="جنس-نخ-خاب", label="جنس نخ خاب", order=3)
        self.brand = Attribute.objects.create(slug="برند", label="برند", show_in_filters=False)
        t = lambda a, n, s: AttributeTerm.objects.create(attribute=a, name=n, slug=s)  # noqa: E731
        self.r700, self.r1200 = t(self.reeds, "700", "700"), t(self.reeds, "1200", "1200")
        self.acr, self.poly = t(self.pile, "اکریلیک", "اکریلیک"), t(self.pile, "پلی‌استر", "پلی-استر")
        self.b = t(self.brand, "ستاره", "setare")
        self.a = Product.objects.create(title="فرش الف", slug="a", status="publish")
        self.a.specs.add(self.r700, self.acr, self.b)
        self.c = Product.objects.create(title="فرش ب", slug="b", status="publish")
        self.c.specs.add(self.r1200, self.poly, self.b)

    def test_site_listing(self):
        r = self.client.get("/search/", {"q": "فرش"})
        self.assertEqual(r.status_code, 200)
        labels = [f["attr"].label for f in r.context["facets"]]
        self.assertEqual(labels, ["شانه", "جنس نخ خاب"])
        self.assertNotContains(r, "<legend>سایز</legend>")
        r = self.client.get("/search/", {"q": "فرش", "جنس-نخ-خاب": "اکریلیک"})
        self.assertEqual([p.slug for p in r.context["products"]], ["a"])
        self.assertEqual(r.context["meta"]["robots"], "noindex,follow")

    def test_api_groups(self):
        d = self.client.get("/api/app/v1/products/filters/").json()
        self.assertEqual([g["label"] for g in d["groups"]], ["شانه", "جنس نخ خاب"])
        self.assertEqual(d["sizes"], [])
        key = f"attr_{self.pile.pk}"
        self.assertEqual(d["groups"][1]["key"], key)
        r = self.client.get("/api/app/v1/products/", {key: self.poly.pk}).json()
        self.assertEqual([x["id"] for x in r["results"]], [self.c.pk])
        # مقدار از ویژگی دیگر با کلید این گروه پذیرفته نمی‌شود
        self.assertEqual(self.client.get("/api/app/v1/products/", {key: self.r700.pk}).json()["count"], 0)


class LicensePageTests(TestCase):
    def test_license_page_loads_seal_only_there(self):
        s = SiteSettings.load()
        s.trust_html = "<a href='https://trustseal.enamad.ir/?id=1'><img src='https://trustseal.enamad.ir/logo.aspx?id=1'></a>"
        s.save()
        page = Page.objects.filter(slug="license").first() or Page.objects.create(title="مجوزها", slug="license")
        page.template, page.content = "license", "<p>متن</p>[trust_seals]"
        page.save()
        r = self.client.get("/license/")
        self.assertContains(r, "trustseal.enamad.ir/logo.aspx")
        self.assertNotContains(r, "[trust_seals]")
        home = self.client.get("/search/", {"q": "فرش"})
        self.assertNotContains(home, "trustseal.enamad.ir")
        self.assertContains(home, 'href="/license/" class="trust-badge"')
        self.assertIn("license_url", self.client.get("/api/app/v1/config/").json())


class PersianSearchTests(TestCase):
    def setUp(self):
        from catalog.models import Attribute, AttributeTerm

        color = Attribute.objects.create(slug="c", label="رنگ زمینه")
        self.laki = AttributeTerm.objects.create(attribute=color, name="لاكي", slug="laki")  # ک و ی عربی
        self.p = Product.objects.create(title="فرش ۷۰۰ شانه نقشه افشان گلریز زمینه لاکی", slug="golriz", status="publish")
        self.p.specs.set([self.laki])
        self.p2 = Product.objects.create(title="فرش 1200 شانه نقشه گلریز زمینه سرمه‌ای", slug="golriz2", status="publish", views=5)
        self.p3 = Product.objects.create(title="فرش 1500 شانه نقشه پائیز زمینه کرم", slug="paeiz", status="publish", sku="155103")

    def titles(self, q):
        from catalog.search import search

        qs, exact = search(Product.objects.all(), q)
        return [p.slug for p in qs.order_by("-_rank", "-views")], exact

    def test_variants(self):
        self.assertEqual(self.titles("گلریز لاکی")[0], ["golriz"])
        self.assertEqual(self.titles("لاكي گلريز")[0], ["golriz"])          # عربی و ترتیب برعکس
        self.assertEqual(self.titles("سرمه ای")[0], ["golriz2"])             # نیم‌فاصله و فاصله
        self.assertEqual(self.titles("سرمهای ۱۲۰۰")[0], ["golriz2"])
        self.assertEqual(self.titles("پاییز")[0], ["paeiz"])                 # ئ و ی
        self.assertEqual(self.titles("۱۵۵۱۰۳")[0], ["paeiz"])               # کد کالا با ارقام فارسی
        got, exact = self.titles("گلریز آبی")
        self.assertFalse(exact)
        self.assertEqual(set(got), {"golriz", "golriz2"})                    # نزدیک‌ترین‌ها

    def test_pages(self):
        r = self.client.get("/search/", {"q": "گلریز لاکی"})
        self.assertContains(r, "/product/golriz/")
        self.assertNotContains(r, "/product/golriz2/")
        api = self.client.get("/api/app/v1/products/", {"q": "لاکی گلریز"}).json()
        data = api.get("data", api)
        self.assertEqual([x["id"] for x in data["results"]], [self.p.pk])
