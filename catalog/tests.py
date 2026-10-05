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
