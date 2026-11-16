"""پاکسازی ممیزی سئو، آبان ۱۴۰۵: عنوان‌ها، آرشیوهای تکراری، کناره‌های هم‌فرش، پیوندهای ریدایرکت‌شده و فرش‌های تکراری."""
import importlib
from decimal import Decimal
from io import StringIO
from urllib.parse import unquote

from django.apps import apps
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from blog.models import Post
from catalog.models import Attribute, AttributeTerm, Brand, Category, Product, ProductTag
from core.models import SiteSettings
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from seo.models import Redirect

MIG = importlib.import_module("core.migrations.0027_clean_title_junk_merge_archives")


class CleanTitleTests(TestCase):
    def test_clean(self):
        c = MIG.clean
        self.assertEqual(c("خرید و قیمت فرش 700 شانه نقشه دلاریس - پلی استر ☀️ ارزان!"),
                         "خرید و قیمت فرش 700 شانه نقشه دلاریس - پلی استر")
        self.assertEqual(c("فرش 700 شانه ☀️ خرید آنلاین و قیمت فرش ماشینی 700 شانه ارزان"),
                         "فرش 700 شانه | خرید آنلاین و قیمت فرش ماشینی 700 شانه ارزان")
        self.assertEqual(c("%title% ☀️ ارزان! %sep% %sitename%"), "%title% %sep% %sitename%")
        self.assertEqual(c("✅ فرش کرم ⭐️ قیمت روز - ارزان!"), "فرش کرم | قیمت روز")
        self.assertEqual(c("فرش ۱۲ متری (۳ × ۴) – قیمت"), "فرش ۱۲ متری (۳ × ۴) – قیمت")

    def test_migration(self):
        p = Product.objects.create(title="فرش الف", slug="a", seo_title="خرید و قیمت فرش الف ☀️ ارزان!")
        cat = Category.objects.create(name="دسته", slug="cat", seo_title="فرش ⭐ دسته")
        post = Post.objects.create(title="مقاله", slug="post", seo_title="مقاله ☀️ ارزان!")
        s = SiteSettings.load()
        s.title_templates = {"pt_product_title": "خرید و قیمت %title% ☀️ ارزان!", "pt_post_title": "%title% ⭐"}
        s.save()
        # دو فرش متفاوت با یک عنوان سئو؛ و دو فرش واقعاً هم‌نام
        x1 = Product.objects.create(title="دلاریس پلی استر", slug="x1", seo_title="دلاریس")
        x2 = Product.objects.create(title="دلاریس آکریلیک", slug="x2", seo_title="دلاریس")
        y1 = Product.objects.create(title="پانیذ", slug="y1", seo_title="پانیذ")
        y2 = Product.objects.create(title="پانیذ", slug="y2", seo_title="پانیذ")
        MIG.forwards(apps, None)
        for o in (p, cat, post, x1, x2, y1, y2):
            o.refresh_from_db()
        self.assertEqual(p.seo_title, "خرید و قیمت فرش الف")
        self.assertEqual(cat.seo_title, "فرش | دسته")
        self.assertEqual(post.seo_title, "مقاله ☀️ ارزان!")  # مقاله‌ها دست نمی‌خورند
        tpl = SiteSettings.objects.get(pk=1).title_templates
        self.assertEqual(tpl["pt_product_title"], "خرید و قیمت %title%")
        self.assertEqual(tpl["pt_post_title"], "%title% ⭐")
        self.assertEqual((x1.seo_title, x2.seo_title), ("", ""))
        self.assertEqual((y1.seo_title, y2.seo_title), ("پانیذ", "پانیذ"))

    def test_farshestan_untouched(self):
        p = Product.objects.create(title="فرش الف", slug="a", seo_title="فرش الف ☀️ ارزان!")
        with self.settings(SITE_THEME="farshestan"):
            MIG.forwards(apps, None)
        p.refresh_from_db()
        self.assertIn("☀", p.seo_title)


class MergeArchiveTests(TestCase):
    def setUp(self):
        self.r700 = Category.objects.create(name="۷۰۰ شانه", slug="carpet-700-reeds")
        self.hb = Category.objects.create(name="برجسته", slug="carpet-700-reeds-carpet-high-bulk", parent=self.r700)
        picks = Attribute.objects.create(slug="picks-per-meter", label="تراکم", is_public=True)
        self.t2550 = AttributeTerm.objects.create(attribute=picks, name="2550", slug="2550")
        self.tag = ProductTag.objects.create(name="مهرآوران", slug="فرش-700-شانه-برجسته-مهرآوران")
        for i in range(3):
            p = Product.objects.create(title=f"فرش {i}", slug=f"p{i}")
            p.categories.add(self.hb)
            p.tags.add(self.tag)
            p.specs.add(self.t2550)

    def test_merge(self):
        MIG.forwards(apps, None)
        self.tag.refresh_from_db()
        self.t2550.refresh_from_db()
        self.assertEqual(self.tag.redirect_url, "/product-category/carpet-700-reeds/carpet-700-reeds-carpet-high-bulk/")
        self.assertEqual(self.t2550.redirect_url, "/product-category/carpet-700-reeds/")
        r = self.client.get("/picks-per-meter/2550/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), "/product-category/carpet-700-reeds/")

    def test_not_merged_when_sets_differ(self):
        other = Product.objects.create(title="فرش بیرون", slug="out")
        other.tags.add(self.tag)  # این فرش در دسته نیست ← برچسب صفحهٔ خودش را نگه می‌دارد
        MIG.forwards(apps, None)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.redirect_url, "")


class RunnerMergeTests(TestCase):
    def test_runner_duplicates(self):
        from landing import build
        from landing.models import LandingPage

        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        album = Album.objects.create(name="آلبوم", code="A", base_size=s["12-meter"], base_price=Decimal("40000000"),
                                     shipping_fixed=0, waste_value=0)
        album.sizes.set([s["12-meter"], s["runner-4x1"], s["runner-3x1"], s["runner-2x1"]])
        ps = [Product.objects.create(title=f"فرش {i}", slug=f"p{i}", album=album, status="publish") for i in range(5)]
        sync_album_variations(ps, reset=True)
        build.sync(log=lambda *_: None)
        live = {lp.size.slug: lp for lp in build.live().filter(size__type="runner")}
        self.assertEqual(list(live), ["runner-4x1"])  # از سه کنارهٔ هم‌فرش یکی ماند
        gone = LandingPage.objects.get(size__slug="runner-2x1", reeds=None, color=None)
        self.assertFalse(gone.is_active)
        r = self.client.get(f"/carpets/{gone.slug}/page/3/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), f"/carpets/{live['runner-4x1'].slug}/")
        build.sync(log=lambda *_: None)  # دوباره ساخته نمی‌شود
        self.assertEqual(Redirect.objects.filter(origin="landing_merge").count(), 2)


class FixLinksTests(TestCase):
    def test_fix_links(self):
        Brand.objects.create(name="شاه پسند", slug="shahpasand-carpet")
        Redirect.objects.create(source="brand/فرش-شاه-پسند", target="/brand/shahpasand-carpet/")
        html = ('<p><a href="https://irancarpet.net/brand/فرش-شاه-پسند/">شاه پسند</a> '
                '<a href="/brand/shahpasand-carpet/">درست</a> <a href="/نیست-اصلا/">ناموجود</a> '
                '<a href="https://example.com/brand/فرش-شاه-پسند/">بیرونی</a></p>')
        p = Product.objects.create(title="فرش", slug="f", content=html)
        out = StringIO()
        call_command("fix_internal_links", stdout=out)
        p.refresh_from_db()
        self.assertEqual(p.content, html)  # بی --apply فقط گزارش
        self.assertIn("پیوند ریدایرکت‌شده: 1", out.getvalue())
        call_command("fix_internal_links", "--apply", stdout=StringIO())
        p.refresh_from_db()
        self.assertIn('href="https://irancarpet.net/brand/shahpasand-carpet/"', p.content)
        self.assertIn('href="/نیست-اصلا/"', p.content)
        self.assertIn('href="https://example.com/brand/فرش-شاه-پسند/"', p.content)


class DupProductsTests(TestCase):
    def test_dup(self):
        a = Product.objects.create(title="فرش پانیذ گردویی", slug="panizh", views=50)
        b = Product.objects.create(title="فرش پانیذ  گردویی", slug="panizh-2", views=10)
        c = Product.objects.create(title="فرش یکتا", slug="unique")
        out = StringIO()
        call_command("dup_products", stdout=out)
        self.assertIn("فرش تکراری که ۳۰۱ می‌شود: 1", out.getvalue())
        b.refresh_from_db()
        self.assertEqual(b.status, "publish")
        call_command("dup_products", "--apply", stdout=StringIO())
        for o in (a, b, c):
            o.refresh_from_db()
        self.assertEqual((a.status, b.status, c.status), ("publish", "draft", "publish"))
        r = self.client.get("/product/panizh-2/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(unquote(r["Location"]), "/product/panizh/")

    def test_same_name_other_album_is_not_merged(self):
        seed_sizes()
        size = Size.objects.get(slug="12-meter")
        mehr = Album.objects.create(name="700 شانه ساده آلبوم مهر", code="M", base_size=size, base_price=Decimal("1"), shipping_fixed=0, waste_value=0)
        jahan = Album.objects.create(name="700 شانه ساده آلبوم جهان", code="J", base_size=size, base_price=Decimal("1"), shipping_fixed=0, waste_value=0)
        a = Product.objects.create(title="فرش نیلا", slug="nila-2", album=mehr, views=5)
        b = Product.objects.create(title="فرش نیلا", slug="nila-3", album=jahan, views=9)
        old = Product.objects.create(title="فرش نیلا", slug="nila", stock_status="outofstock", views=90)
        call_command("dup_products", "--apply", stdout=StringIO())
        for o in (a, b, old):
            o.refresh_from_db()
        self.assertEqual((a.status, b.status, old.status), ("publish", "publish", "draft"))
        self.assertEqual(a.seo_title, "فرش نیلا | آلبوم مهر")
        self.assertEqual(b.seo_title, "فرش نیلا | آلبوم جهان")
        self.assertEqual(unquote(self.client.get("/product/nila/")["Location"]), "/product/nila-3/")  # بی‌آلبوم ← پربازدیدترین زنده


class DeadProductsTests(TestCase):
    def test_dead(self):
        seed_sizes()
        size = Size.objects.get(slug="12-meter")
        album = Album.objects.create(name="آلبوم", code="A", base_size=size, base_price=Decimal("1"), shipping_fixed=0, waste_value=0)
        cat = Category.objects.create(name="۷۰۰ شانه", slug="c700")
        live = Product.objects.create(title="فرش 700 شانه نقشه نیلا زمینه کرم", slug="nila", album=album, views=5)
        dead = Product.objects.create(title="فرش 700 شانه نقشه نیلا زمینه کرم قدیمی", slug="nila-old", stock_status="outofstock",
                                      design_name="نیلا", primary_category=cat)
        live.design_name = "نیلا"
        live.save()
        nodesign = Product.objects.create(title="فرش بی‌نام", slug="x", stock_status="outofstock", primary_category=cat)
        popular = Product.objects.create(title="فرش پربازدید", slug="pop", stock_status="outofstock", views=500, primary_category=cat)
        out = StringIO()
        call_command("dead_products", stdout=out)
        self.assertIn("فرش‌هایی که ۳۰۱ می‌شوند: 2", out.getvalue())
        call_command("dead_products", "--apply", stdout=StringIO())
        for o in (live, dead, nodesign, popular):
            o.refresh_from_db()
        self.assertEqual((live.status, dead.status, nodesign.status, popular.status), ("publish", "draft", "draft", "publish"))
        self.assertEqual(unquote(self.client.get("/product/nila-old/")["Location"]), "/product/nila/")
        self.assertEqual(unquote(self.client.get("/product/x/")["Location"]), "/product-category/c700/")
