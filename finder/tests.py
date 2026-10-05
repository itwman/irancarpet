import io
import json
import shutil
import tempfile
from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from catalog.models import Attribute, AttributeTerm, Category, Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from . import engine
from .models import FinderRequest, Need

TMP = tempfile.mkdtemp()


def red_jpeg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 400), (170, 30, 40)).save(buf, "JPEG")
    return SimpleUploadedFile("rug.jpg", buf.getvalue(), content_type="image/jpeg")


@override_settings(PRIVATE_ROOT=TMP, SMSIR_API_KEY="", STAGING=True)
class FinderTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        Need.objects.all().delete()  # نیازهای پیش‌فرض مهاجرت
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        color = Attribute.objects.create(slug="background-color", label="رنگ زمینه")
        r700 = AttributeTerm.objects.create(attribute=reeds, name="700", slug="700")
        r1200 = AttributeTerm.objects.create(attribute=reeds, name="1200", slug="1200")
        red = AttributeTerm.objects.create(attribute=color, name="لاکی", slug="laki")
        cream = AttributeTerm.objects.create(attribute=color, name="کرم", slug="cream")
        bulk = Category.objects.create(name="برجسته ۷۰۰", slug="carpet-700-reeds-carpet-high-bulk")

        def album(name, price, code):
            a = Album.objects.create(name=name, code=code, base_size=s["12-meter"], base_price=Decimal(price), shipping_fixed=0, waste_value=0)
            a.sizes.set([s["12-meter"], s["6-meter"]])
            return a

        def prod(title, slug, a, *specs, views=0):
            p = Product.objects.create(title=title, slug=slug, album=a, status="publish", views=views)
            p.specs.add(*specs)
            sync_album_variations([p], reset=True)
            return p

        cheap, dear = album("ارزان", "30000000", "A"), album("گران", "90000000", "B")
        self.thick_red = prod("فرش 700 شانه افشان لاکی", "thick-red", cheap, r700, red, views=5)
        self.bulk_red = prod("فرش 700 شانه برجسته لاکی", "bulk-red", cheap, r700, red)
        self.bulk_red.categories.add(bulk)
        self.fine_cream = prod("فرش 1200 شانه مدرن کرم", "fine-cream", dear, r1200, cream)
        self.thick = Need.objects.create(group="feel", title="ضخیم و کلفت", keywords="ضخیم، کلفت")
        self.thick.terms.set([r700])
        self.thick.exclude_categories.set([bulk])
        self.thick.exclude_keywords = "برجسته"
        self.thick.save()
        self.simple = Need.objects.create(group="feel", title="ساده", keywords="غیر برجسته، ساده")  # بی‌قاعده
        self.bulk = Need.objects.create(group="feel", title="برجسته", keywords="برجسته", title_keywords="برجسته")
        self.trad = Need.objects.create(group="style", title="سنتی", keywords="سنتی، کلاسیک", title_keywords="افشان، لچک")
        self.red = Need.objects.create(group="color", title="قرمز و لاکی", swatch="#A8232F", keywords="قرمز، لاکی",
                                       term_attribute=color, term_keywords="قرمز، لاکی")
        self.cream = Need.objects.create(group="color", title="کرم", swatch="#E8DAC2", keywords="کرم",
                                         term_attribute=color, term_keywords="کرم")
        cache.clear()

    def test_understand(self):
        w = engine.understand("یه فرش ضخیم و کلفت قرمز ۶ متری زیر ۴۰ میلیون می‌خوام")
        self.assertEqual({n.title for n in w.needs}, {"ضخیم و کلفت", "قرمز و لاکی"})
        self.assertEqual(w.max_price, 40_000_000)
        self.assertEqual(w.sizes[0].slug, "6-meter")
        w = engine.understand("غیر برجسته")  # نباید «برجسته» فهمیده شود
        self.assertEqual(w.needs, [])
        w = engine.understand("بین ۲۰ تا ۳۵ میلیون، ۱۲۰۰ شانه")
        self.assertEqual((w.min_price, w.max_price), (20_000_000, 35_000_000))
        self.assertEqual(w.reeds[0].name, "1200")
        w = engine.understand("فرش ۳ در ۴")
        self.assertEqual(w.sizes[0].slug, "12-meter")

    def test_search(self):
        def ids(**g):
            return [x["id"] for x in self.client.get("/api/app/v1/finder/search/", g).json()["results"]]

        self.assertEqual(ids(q="ضخیم و کلفت"), [self.thick_red.pk])
        self.assertEqual(set(ids(q="قرمز")), {self.thick_red.pk, self.bulk_red.pk})
        self.assertEqual(set(ids(needs=f"{self.red.pk},{self.cream.pk}")), {self.thick_red.pk, self.bulk_red.pk, self.fine_cream.pk})
        self.assertEqual(ids(needs=f"{self.red.pk},{self.trad.pk}"), [self.thick_red.pk])
        d = self.client.get("/api/app/v1/finder/search/", {"q": "فرش ۶ متری زیر ۲۰ میلیون"}).json()
        self.assertTrue(d["results"])
        self.assertTrue(all(r["price"] <= 20_000_000 and r["size_label"] for r in d["results"]))
        self.assertIn("6 متری", [c["label"] for c in d["understood"]])
        # چیزی پیدا نشد → نزدیک‌ترین‌ها
        d = self.client.get("/api/app/v1/finder/search/", {"q": "کرم سنتی"}).json()
        self.assertTrue(d["relaxed"])
        self.assertTrue(d["results"])
        r = self.client.get("/api/app/v1/finder/search/", {"q": "قرمز سنتی"}).json()["results"][0]
        self.assertEqual(set(r["why"]), {"قرمز و لاکی", "سنتی"})

    def test_config(self):
        d = self.client.get("/api/app/v1/finder/config/").json()
        titles = [n["title"] for g in d["groups"] for n in g["needs"]]
        self.assertIn("ضخیم و کلفت", titles)
        self.assertNotIn("ساده", titles)  # بی‌قاعده نمایش داده نمی‌شود
        self.assertTrue(d["sizes"])

    def login(self):
        r = self.client.post("/api/app/v1/auth/otp/", json.dumps({"mobile": "09121112233"}), content_type="application/json")
        code = r.json()["dev_code"]
        r = self.client.post("/api/app/v1/auth/verify/", json.dumps({"mobile": "09121112233", "code": code, "name": "مینا"}),
                             content_type="application/json")
        return {"HTTP_AUTHORIZATION": f"Token {r.json()['token']}"}

    def test_photo_request_flow(self):
        h = self.login()
        self.assertEqual(self.client.post("/api/app/v1/finder/requests/", {"text": "x"}).status_code, 401)
        r = self.client.post("/api/app/v1/finder/requests/", {"text": "همین فرش را ۹ متری می‌خواهم", "photo": red_jpeg(),
                                                            "wanted": json.dumps({"needs": [self.thick.pk]})}, **h)
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertIn("قرمز و لاکی", d["color_names"])
        self.assertEqual([p["id"] for p in d["auto"]], [self.thick_red.pk])
        req = FinderRequest.objects.get(pk=d["id"])
        self.assertEqual(req.mobile, "09121112233")
        # عکس فقط برای خود مشتری و کارمندان
        self.assertEqual(self.client.get(f"/api/app/v1/finder/requests/{req.pk}/photo/", **h).status_code, 200)
        self.assertEqual(self.client.get(f"/api/app/v1/finder/requests/{req.pk}/photo/").status_code, 401)
        self.assertEqual(self.client.get(d["photo"].replace("https://irancarpet.net", "")).status_code, 200)  # پیوند امضاشده
        self.assertEqual(self.client.get(f"/api/app/v1/finder/requests/{req.pk}/photo/?t=bad").status_code, 404)
        self.assertEqual(self.client.get(f"/panel/finder-photo/{req.pk}/").status_code, 404)
        # پاسخ کارشناس
        from finder.services import after_reply

        req.reply = "این دو طرح خیلی شبیه فرش شماست."
        req.save()
        req.products.add(self.bulk_red)
        after_reply(req)
        req.refresh_from_db()
        self.assertEqual(req.status, "answered")
        lst = self.client.get("/api/app/v1/finder/requests/", **h).json()
        self.assertEqual(lst["unread"], 1)
        self.assertEqual(lst["results"][0]["products"][0]["id"], self.bulk_red.pk)
        self.client.post(f"/api/app/v1/finder/requests/{req.pk}/seen/", **h)
        self.assertEqual(self.client.get("/api/app/v1/finder/requests/", **h).json()["unread"], 0)

    def test_panel(self):
        from django.contrib.auth import get_user_model

        u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)
        self.assertEqual(self.client.get("/panel/finder-needs/").status_code, 200)
        self.assertContains(self.client.get(f"/panel/finder-needs/{self.thick.pk}/"), "افشان لاکی")
        req = FinderRequest.objects.create(mobile="09120000000", text="فرش قرمز")
        self.assertEqual(self.client.get("/panel/finder-requests/").status_code, 200)
        self.assertEqual(self.client.get(f"/panel/finder-requests/{req.pk}/").status_code, 200)

    def test_finder_payment_return(self):
        from shop.models import Order
        from shop.views import app_return_url

        o = Order(number=1234)
        self.assertEqual(app_return_url(o, "app-finder", True), "/app/return/1234/?paid=1&app=finder")
        self.assertEqual(app_return_url(o, "app", False), "/app/return/1234/?paid=0")
