from django.test import TestCase

from blog.models import Post
from installments.models import InstallmentPlan


class LiveBlockTests(TestCase):
    def test_installment_post_renders_live_blocks(self):
        InstallmentPlan.objects.all().delete()
        InstallmentPlan.objects.create(title="چک صیادی", kind="cheque", min_down_percent=30, max_months=12)
        InstallmentPlan.objects.create(title="بازنشستگان", kind="beta", min_down_percent=0, max_months=24)
        Post.objects.create(title="خرید فرش قسطی", slug="aghsat", status="publish",
                            content="<p>قیمت‌ها [price_updated]</p>\n[installment_calc]\n<p>[installment_plans]</p>\n[installment_prices]\n[installment_steps]\n[installment_faq]")
        r = self.client.get("/aghsat/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn("[installment_", html)
        self.assertIn("data-inst-calc", html)
        self.assertIn("دست‌کم ۳۰٪", html)
        self.assertIn("FAQPage", html)
        self.assertIn("شروع خرید اقساطی", html)
        self.assertIn("live-blocks.js", html)

    def test_plain_post_unchanged(self):
        Post.objects.create(title="مقاله", slug="plain", status="publish", content="<p>متن ساده</p>")
        r = self.client.get("/plain/")
        self.assertContains(r, "متن ساده")
        self.assertNotContains(r, "live-blocks.js")


class SizePriceTests(TestCase):
    def setUp(self):
        from decimal import Decimal

        from catalog.models import Product
        from pricing.albums import sync_album_variations
        from pricing.models import Album, Size, seed_sizes

        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="ورژن 700 شانه", code="V", base_size=s["12-meter"],
                                          base_price=Decimal("30000000"), slug="version-700", in_price_list=True)
        self.album.sizes.set([s["12-meter"], s["6-meter"]])
        p = Product.objects.create(title="فرش 700 شانه ورژن", slug="version", album=self.album, status="publish")
        sync_album_variations([p], reset=True)

    def test_size_blocks_and_migration_transform(self):
        import importlib

        mig = importlib.import_module("blog.migrations.0004_size_price_posts")
        old = ("<p>مقدمه</p><p>&nbsp;</p><h2>لیست قیمت فرش ماشینی 6 متری 700 شانه</h2><p></p>"
               "<p>ارسال تمامی سفارشات بالای 10 میلیون تومان رایگان است.</p>"
               "<h2>خرید اقساطی فرش ماشینی</h2><h3>1- لندو</h3><p>قدیمی</p><h2>سوالات متداول</h2>")
        new = mig.transform(old, "قیمت-فرش-ماشینی-6-متری-700-شانه")
        self.assertIn("[size_prices 6-meter 700]", new)
        self.assertIn("[size_faq 6-meter 700]", new)
        self.assertIn("[installment_plans]", new)
        self.assertNotIn("لندو", new)
        self.assertNotIn("10 میلیون", new)
        self.assertNotIn("&nbsp;", new)
        self.assertIn("%currentdate%", mig.title_for("قیمت-فرش-6-متری"))
        Post.objects.create(title="قیمت فرش ۶ متری ۷۰۰ شانه", slug="six", status="publish", content=new,
                            seo_title=mig.title_for("قیمت-فرش-ماشینی-6-متری-700-شانه"))
        r = self.client.get("/six/")
        html = r.content.decode()
        self.assertNotIn("[size_", html)
        self.assertIn("ورژن ۷۰۰ شانه", html)
        self.assertIn("FAQPage", html)
        self.assertIn("ابعاد فرش ۶ متری", html)
        self.assertRegex(html, r"<title>قیمت فرش ماشینی ۶ متری ۷۰۰ شانه [^<%]+</title>")
