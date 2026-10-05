from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from catalog.models import Attribute, AttributeTerm, Category, Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import ShopSettings

from . import render as R
from .models import ContentEdit, ContentSettings, ContentTemplate, InfoBlock
from .views import match_images


def png(name):
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (40, 40), (120, 30, 60)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class Base(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="1500 شانه", code="A15", base_size=s["12-meter"], base_price=Decimal("50000000"),
                                          company="شاه پسند")
        self.album.sizes.set([s["12-meter"], s["6-meter"]])
        self.cat = Category.objects.create(name="فرش 1500 شانه", slug="carpet-1500")
        self.reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه", is_public=True)
        self.dens = Attribute.objects.create(slug="density", label="تراکم")
        self.pile = Attribute.objects.create(slug="pile", label="جنس نخ خاب")
        self.color = Attribute.objects.create(slug="ground-color", label="رنگ زمینه", is_public=True)
        self.t1500 = AttributeTerm.objects.create(attribute=self.reeds, name="1500", slug="1500")
        self.t4500 = AttributeTerm.objects.create(attribute=self.dens, name="4500", slug="4500")
        self.tpile = AttributeTerm.objects.create(attribute=self.pile, name="100% آکریلیک هیت ست شده با ضمانت", slug="acr")
        self.navy = AttributeTerm.objects.create(attribute=self.color, name="سرمه ای", slug="navy")
        self.cream = AttributeTerm.objects.create(attribute=self.color, name="کرم", slug="cream")
        self.p = self.make("فرش 1500 شانه برجسته نقشه آرشان زمینه سرمه ای", "arshan-navy", self.navy)
        ContentTemplate.objects.all().delete()
        InfoBlock.objects.all().delete()
        from .defaults import BLOCKS, TEMPLATE_BODY, TEMPLATE_BULLETS, TEMPLATE_TITLE

        self.tpl = ContentTemplate.objects.create(name="عمومی", is_default=True, body=TEMPLATE_BODY, bullets=TEMPLATE_BULLETS,
                                                  title_pattern=TEMPLATE_TITLE)
        for i, (t, o, b) in enumerate(BLOCKS):
            InfoBlock.objects.create(title=t, body=b, order=i, is_open=o)
        sh = ShopSettings.load()
        sh.free_shipping_min, sh.allow_full, sh.allow_deposit, sh.deposit_percent = 50_000_000, True, True, 10
        sh.save()
        R.clear_cache()

    def make(self, title, slug, color, **kw):
        p = Product.objects.create(title=title, slug=slug, album=self.album, status="publish", primary_category=self.cat,
                                   design_name=R.design_from_title(title), color_count=8, **kw)
        p.specs.set([self.t1500, self.t4500, self.tpile, color])
        p.categories.set([self.cat])
        sync_album_variations([p], reset=True)
        return p


class RenderTests(Base):
    def test_template_text(self):
        from installments.models import InstallmentPlan

        InstallmentPlan.objects.update(is_active=False)
        self.p.use_template = True
        doc = R.build(self.p)
        self.assertTrue(doc["templated"])
        html, bullets = doc["html"], doc["bullets"]
        self.assertIn("<h2>معرفی فرش آرشان زمینه سرمه ای</h2>", html)
        self.assertIn("کارخانهٔ شاه پسند", html)               # برند از کارخانهٔ آلبوم
        self.assertIn("۶٬۷۵۰٬۰۰۰ گره", html)                    # شانه × تراکم
        self.assertIn('class="price-lines"', html)              # قیمت روز سایزها
        self.assertIn("۱۰۰٪ آکریلیک هیت ست", html)
        self.assertNotIn("با ضمانت", html)
        self.assertEqual(html.count('href="/product-category/carpet-1500/"'), 1)
        self.assertNotIn("<h2><a", html)                         # لینک در تیتر نیست
        self.assertIn("گل برجسته", bullets)
        self.assertIn("ارسال رایگان با پرداخت کامل آنلاین (برای سفارش‌های بالای ۵۰ میلیون تومان)", bullets)
        self.assertNotIn("{", html + bullets)
        self.assertNotIn("[[", html + bullets)
        self.assertNotIn("جفتی", html)                           # سرمه‌ای جزو رنگ‌های جفتی نیست
        titles = [b["title"] for b in doc["blocks"]]
        self.assertIn("ارسال و تحویل", titles)
        self.assertNotIn("خرید اقساطی", titles)                 # روش اقساط فعالی نیست ← بخش پنهان
        ship = next(b for b in doc["blocks"] if b["title"] == "ارسال و تحویل")["html"]
        self.assertIn("حدود ۲۰۰ تا ۵۰۰ هزار تومان", ship)
        pay = next(b for b in doc["blocks"] if b["title"].startswith("پرداخت"))["html"]
        self.assertIn("۱۰٪ بیعانه", pay)
        self.assertIn("۵٪ مبلغ سفارش", pay)

    def test_settings_drive_text(self):
        self.p.use_template = True
        sh = ShopSettings.load()
        sh.free_shipping_min = 80_000_000
        sh.save()
        self.assertIn("بالای ۸۰ میلیون تومان", R.build(self.p)["bullets"])
        sh.allow_full = False
        sh.save()
        self.assertNotIn("ارسال رایگان", R.build(self.p)["bullets"])
        cream = self.make("فرش 1500 شانه نقشه آرشان زمینه کرم", "arshan-cream", self.cream, use_template=True)
        self.assertIn("معمولاً جفتی", R.build(cream)["html"])
        cs = ContentSettings.load()
        cs.pair_colors = "آبی"
        cs.save()
        self.assertNotIn("جفتی", R.build(cream)["html"])

    def test_engine_rules(self):
        ctx = R.Ctx(self.p)
        out = R.render("## تیتر\nالف {تعداد_رنگ_نیست}\nب [[ج {ناموجود}]]د\n- {لینک:دسته} و {لینک:دسته|دوباره}\n**پررنگ**", ctx)
        self.assertNotIn("الف", out)                     # متغیر خالی ← خط حذف
        self.assertIn("<p>بد", out.replace(" ", "").replace("<p>ب", "<p>ب"))
        self.assertIn("<li><a href=\"/product-category/carpet-1500/\">فرش ۱۵۰۰ شانه</a> و دوباره</li>", out)  # هر نشانی یک بار
        self.assertIn("<strong>پررنگ</strong>", out)
        self.assertEqual(R.render("## تنها\n{ناموجود}", R.Ctx(self.p)), "")  # تیتر بی‌محتوا حذف
        self.assertEqual(R.render("<b>{نقشه}</b>", R.Ctx(self.p)), "<p>&lt;b&gt;آرشان&lt;/b&gt;</p>")  # بی‌خطر

    def test_manual_text_untouched(self):
        self.p.content = '<p>متن قدیمی <a href="/product-category/carpet-1500/">دسته</a></p>'
        self.p.short_description = "خلاصهٔ قدیمی"
        doc = R.build(self.p)
        self.assertFalse(doc["templated"])
        self.assertEqual(doc["html"], self.p.content)
        self.assertTrue(doc["blocks"])                  # بخش‌های مشترک برای متن دستی هم می‌آید

    def test_siblings_and_page(self):
        other = self.make("فرش 1500 شانه نقشه آرشان زمینه کرم", "arshan-cream", self.cream)
        self.make("فرش 1500 شانه نقشه کاملیا زمینه کرم", "kamelia-cream", self.cream)
        sib = R.color_siblings(self.p)
        self.assertEqual({x["product"].pk for x in sib}, {self.p.pk, other.pk})
        Product.objects.filter(pk=self.p.pk).update(use_template=True)
        r = self.client.get("/product/arshan-navy/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("رنگ‌های دیگر نقشهٔ آرشان", html)
        self.assertIn("/product/arshan-cream/", html)
        self.assertIn("info-blocks", html)
        self.assertIn("ارسال رایگان با پرداخت کامل آنلاین", html)
        api = self.client.get(f"/api/app/v1/products/{self.p.pk}/").json()
        data = api.get("data", api)
        self.assertIn("ارسال و تحویل", data["content_text"])
        self.assertEqual(len(data["colors"]), 2)
        self.assertTrue(data["info_blocks"])

    def test_helpers(self):
        self.assertEqual(R.design_from_title("فرش 1500 شانه برجسته نقشه باغ آیینه زمینه بژ"), "باغ آیینه")
        got = match_images([(1, "arshan-سرمه-ای-1"), (2, "ارشان کرم"), (3, "arshan_ابی_نفتی"), (4, "IMG_200")],
                           ["سرمه‌ای", "کرم", "آبی", "آبی نفتی"])
        self.assertEqual(got, {0: [1], 1: [2], 2: [], 3: [3]})


class PanelTests(Base):
    def setUp(self):
        super().setUp()
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)

    def test_bulk_create(self):
        ids = []
        for name in ("آرشان-کرم.png", "arshan-سرمه-ای.png", "other.png"):
            r = self.client.post("/panel/media/upload/", {"file": png(name)})
            ids.append(r.json()["files"][0]["value"])
        data = {"step": "preview", "album": self.album.pk, "design": "نگین", "color_count": "9", "embossed": "1",
                "colors": [self.navy.pk, self.cream.pk], "new_colors": "یشمی", "media_ids": ",".join(ids), "status": "publish"}
        r = self.client.post("/panel/products/bulk/", data)
        self.assertEqual(r.status_code, 200)
        rows = r.context["rows"]
        self.assertEqual([x["title"] for x in rows],
                         ["فرش ۱۵۰۰ شانه برجسته نقشه نگین زمینه سرمه ای", "فرش ۱۵۰۰ شانه برجسته نقشه نگین زمینه کرم",
                          "فرش ۱۵۰۰ شانه برجسته نقشه نگین زمینه یشمی"])
        self.assertEqual(rows[0]["imgs"], [int(ids[1])])
        self.assertEqual(rows[1]["imgs"], [int(ids[0])])
        post = {k: v for k, v in data.items() if k not in ("colors", "new_colors")}
        post.update({"step": "create", "rows_n": 3, "row_0": str(self.navy.pk), "row_1": str(self.cream.pk), "row_2": "new:یشمی",
                     "make_0": "1", "make_1": "1", "make_2": "1", "title_0": rows[0]["title"], "title_1": rows[1]["title"],
                     "title_2": rows[2]["title"], "img_0": [ids[1]], "img_1": [ids[0], ids[2]]})
        r = self.client.post("/panel/products/bulk/", post)
        self.assertEqual(r.status_code, 302)
        made = Product.objects.filter(design_name="نگین").order_by("pk")
        self.assertEqual(made.count(), 3)
        cream = made.get(title__contains="کرم")
        self.assertTrue(cream.use_template)
        self.assertEqual(cream.image_id, int(ids[0]))
        self.assertEqual(cream.images.count(), 2)
        self.assertEqual(set(cream.specs.values_list("pk", flat=True)), {self.t1500.pk, self.t4500.pk, self.tpile.pk, self.cream.pk})
        self.assertTrue(cream.variations.exists() and cream.min_price)
        self.assertTrue(AttributeTerm.objects.filter(attribute=self.color, name="یشمی").exists())
        self.assertEqual(len(R.color_siblings(cream)), 3)

    def test_preview_and_lists(self):
        self.assertEqual(self.client.get(f"/panel/content-templates/{self.tpl.pk}/preview/").status_code, 200)
        self.assertEqual(self.client.get(f"/panel/content-templates/{self.tpl.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/panel/info-blocks/").status_code, 200)
        self.assertEqual(self.client.get("/panel/products/bulk/").status_code, 200)
        self.assertEqual(self.client.get("/panel/settings/?tab=content").status_code, 200)
        self.assertEqual(self.client.get(f"/panel/products/{self.p.pk}/edit/").status_code, 200)

    def test_replace_and_undo(self):
        Product.objects.filter(pk=self.p.pk).update(content="<p>ارسال رایگان به سراسر کشور</p>")
        r = self.client.get("/panel/content-tools/", {"do": "preview", "find": "ارسال رایگان به سراسر کشور", "replace": "ارسال سریع",
                                                     "field": "content"})
        self.assertEqual(r.context["hit_products"], 1)
        self.client.post("/panel/content-tools/", {"do": "replace", "find": "ارسال رایگان به سراسر کشور", "replace": "ارسال سریع",
                                                  "field": "content"})
        self.p.refresh_from_db()
        self.assertEqual(self.p.content, "<p>ارسال سریع</p>")
        e = ContentEdit.objects.get()
        self.client.post("/panel/content-tools/", {"do": "undo", "edit": e.pk})
        self.p.refresh_from_db()
        self.assertIn("سراسر کشور", self.p.content)

    def test_link_audit_and_fix(self):
        html = ('<h2><a href="/product-category/carpet-1500/">تیتر</a></h2><p><a href="https://irancarpet.net/">فروشگاه فرش</a> '
                '<a href="/no-such-page-xyz/">اینجا</a> <a href="/product-category/carpet-1500/">بار دوم</a></p>')
        Product.objects.filter(pk=self.p.pk).update(content=html)
        with self.settings(SITE_URL="https://irancarpet.net"):
            r = self.client.get("/panel/content-tools/", {"do": "audit"})
            kinds = r.context["kinds"]
            for k in ("home", "heading", "vague", "broken"):
                self.assertEqual(kinds[k]["n"], 1, k)
            self.client.post("/panel/content-tools/", {"do": "fix", "kind": ["home", "heading", "vague", "broken", "repeat"]})
        self.p.refresh_from_db()
        self.assertNotIn("irancarpet.net/", self.p.content)
        self.assertNotIn("no-such-page", self.p.content)
        self.assertIn("<h2>تیتر</h2>", self.p.content)
        self.assertEqual(self.p.content.count("<a "), 1)          # فقط لینک دستهٔ دوم (اولی در تیتر بود) می‌ماند
        self.assertIn("فروشگاه فرش", self.p.content)

    def test_bulk_actions(self):
        from dashboard.registry import REGISTRY

        Product.objects.filter(pk=self.p.pk).update(design_name="")
        REGISTRY["products"].actions["use_template"][1](None, Product.objects.filter(pk=self.p.pk))
        self.p.refresh_from_db()
        self.assertTrue(self.p.use_template)
        self.assertEqual(self.p.design_name, "آرشان")
