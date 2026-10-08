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


class TidyAndCityTests(TestCase):
    def test_tidy(self):
        from blog.tidy import tidy

        html = ('<h1>تیتر اضافه</h1><p>&nbsp;</p><h4>بخش</h4><p>متن [bt_cc]</p><h4></h4>'
                '<h4>سوالات متداول</h4><h5><img src="/a.jpg"></h5><p>آخر</p>')
        out = tidy(html, "عنوان")
        self.assertNotIn("<h1", out)
        self.assertNotIn("[bt_cc]", out)
        self.assertNotIn("&nbsp;", out)
        self.assertIn('alt="عنوان"', out)
        self.assertIn('loading="lazy"', out)
        self.assertIn("<h2>بخش</h2>", tidy("<h4>بخش</h4><p>متن</p>"))  # h4 ← h2 چون h2 نداشت

    def test_city_post_migration_and_render(self):
        import importlib
        import types

        mig = importlib.import_module("blog.migrations.0006_city_posts")
        city = mig.city_of(types.SimpleNamespace(title="خرید فرش در گرگان ☀️ فروشگاه", slug="x"))
        self.assertEqual(city, "گرگان")
        old = ("<h2>قیمت فرش ماشینی در گرگان</h2><p>ما در ایران کارپت کلیه قیمت های فرش ها را ضمانت می کنیم که کمترین قیمت ممکن در بازار فرش گرگان باشد.</p>"
               "<p>قیمت فرش در شهر شما با ارسال رایگان درب منزل به شرح زیر است:</p>"
               "<h2>تحویل فرش درب منزل در گرگان</h2><p>هر تخته فرش 12 متری 160 هزار تومان</p><h2>سوالات متداول</h2>"
               "<h2>دانستنی های جالب در مورد گرگان</h2><p>متن</p>")
        new = mig.transform(old, city)
        self.assertNotIn("کمترین قیمت ممکن", new)
        self.assertNotIn("160 هزار", new)
        self.assertIn("[size_prices 12-meter]", new)
        self.assertIn("[shipping_info گرگان]", new)
        self.assertIn("[city_faq گرگان]", new)
        Post.objects.create(title="خرید فرش در گرگان", slug="gorgan", status="publish", content=new)
        html = self.client.get("/gorgan/").content.decode()
        self.assertNotIn("[city_faq", html)
        self.assertIn("ایران کارپت در گرگان نمایندگی دارد؟", html)
        self.assertIn("پرداخت کامل آنلاین", html)
        self.assertIn("FAQPage", html)


class TopPagesTests(TestCase):
    def test_compare_and_price_transforms(self):
        import importlib

        mig = importlib.import_module("blog.migrations.0007_top_pages")
        c = mig.PAGES["تفاوت-فرش-1500-شانه-و-فرش-1200-شانه"]["fn"]("<p>مقدمه</p><h2>مقایسه</h2><p>در جدول زیر مقایسه کرده‌ایم.</p><p>بعد</p>")
        self.assertIn("در جدول زیر مقایسه کرده‌ایم.</p>\n[reeds_compare 1200 1500]", c)
        c = mig.PAGES["قیمت-فرش-ماشینی"]["fn"]("<p>a</p><h2>قیمت فرش ماشینی به روز و معتبر در مردادماه 1401</h2><h2>سوالات متداول در مورد قیمت فرش ماشینی</h2>")
        self.assertNotIn("1401", c)
        self.assertIn("[size_prices 12-meter]", c)
        self.assertIn("[size_faq 12-meter]", c)
        self.assertIn("Carpet", mig.PAGES["لغت-و-اصطلاحات-تخصصی-انگلیسی-صنعت-فرش-م"]["fn"]("<p>x</p>"))
        self.assertNotIn("رایگان", mig.PAGES["تلفن-کارخانه-فرش-کاشان"]["fn"]("<p>در کمتر از 2 هفته به صورت رایگان ارسال</p>"))

    def test_image_heading_becomes_paragraph(self):
        from blog.tidy import tidy

        out = tidy('<h4><img src="/a.jpg" alt="x"></h4><h4>متن</h4><p>پ</p>')
        self.assertIn('<p class="wp-img"><img', out)
        self.assertIn("<h2>متن</h2>", out)


class ImageSwapTests(TestCase):
    def test_price_and_city_images_become_live_blocks(self):
        Post.objects.create(
            title="خرید فرش در اندیمشک ⭐️ فروشگاه", slug="andimeshk", status="publish",
            content='<p>ما فروشگاهی نداریم. <img class="aligncenter" src="https://irancarpet.net/wp-content/uploads/2020/09/at-city-min.jpg" alt="" /></p>'
                    '<p>قیمت‌ها:<br /><a href="/x/"><img src="/wp-content/uploads/2025/01/price-list-20-10-1403.jpg" alt=""></a></p><p>پایان</p>')
        html = self.client.get("/andimeshk/").content.decode()
        self.assertNotIn("at-city-min.jpg", html)
        self.assertNotIn("price-list-20-10-1403.jpg", html)
        self.assertIn("در اندیمشک شعبه", html)
        self.assertIn("فروشگاه‌های فرش دیگر در اندیمشک", html)
        self.assertNotIn("آقای فرش", html)
        self.assertNotIn("[price_table]", html)

    def test_price_image_dropped_when_page_has_live_prices(self):
        from blog.tidy import tidy

        out = tidy('<p>a<img src="/u/price-list-1.jpg"></p>[size_prices 6-meter]')
        self.assertNotIn("price-list", out)
        self.assertNotIn("[price_table]", out)


class PaginationTests(TestCase):
    def test_out_of_range_page_redirects_to_first(self):
        r = self.client.get("/blog/page/99/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], "/blog/")
        self.assertEqual(self.client.get("/rss").status_code, 301)
        self.assertEqual(self.client.get("/rss/")["Location"], "/feed/")


class NeutralTitleAndPhoneTests(TestCase):
    def test_city_title_neutral_and_old_phone_swapped(self):
        import importlib

        from core.models import SiteSettings

        s = SiteSettings.load()
        s.mobile = "09125347596"
        s.save()
        Post.objects.create(title="خرید فرش در گرگان ☀️ فروشگاه شهر فرش ماشینی در گرگان", slug="خرید-فرش-در-گرگان", status="publish",
                            content="<h2>شهر فرش گرگان</h2><p>با 09371982000 تماس بگیرید.</p>",
                            seo_description="فروش فرش در گرگان 🌎 شهر فرش گرگان")
        mig = importlib.import_module("blog.migrations.0009_neutral_competitor_titles")
        from django.apps import apps

        mig.forward(apps, None)
        p = Post.objects.get(slug="خرید-فرش-در-گرگان")
        self.assertEqual(p.title, "خرید فرش در گرگان؛ فرش ماشینی کاشان با ارسال به گرگان")
        self.assertNotIn("شهر فرش", p.content + p.seo_description)
        html = self.client.get(p.get_absolute_url()).content.decode()
        self.assertNotIn("09371982000", html)
        self.assertIn("09125347596", html)


class ReedsBannerAndSelfLinkTests(TestCase):
    def test_banners_once_and_self_links_unlinked(self):
        def banners():
            return "<p>" + "".join(f'<a href="https://irancarpet.net/product-category/carpet-{r}-reeds/"><img src="/wp-content/uploads/2020/01/{r}-Reeds-min.png" alt="" width="302" height="70" /></a> ' for r in (700, 1000, 1200, 1500)) + "</p>"
        content = ("<p>اگر فرصت کافی برای مطالعه ندارید از طریق لینک های زیر فرش های خود را انتخاب کنید:</p>" + banners()
                   + '<p>متن با <a href="https://irancarpet.net/%D8%AE%D8%B1%DB%8C%D8%AF-%D9%81%D8%B1%D8%B4-%D8%AF%D8%B1-%D8%A8%D8%B1%D9%88%D8%AC%D8%B1%D8%AF/">خرید فرش در بروجرد</a> و <a href="/guarantee/">ضمانت</a>.</p>'
                   + "<p>برای خرید از لینک های زیر اقدام نمایید:</p>" + banners())
        Post.objects.create(title="خرید فرش در بروجرد", slug="خرید-فرش-در-بروجرد", status="publish", content=content)
        html = self.client.get("/خرید-فرش-در-بروجرد/").content.decode()
        self.assertNotIn("-Reeds-min.png", html)
        self.assertEqual(html.count('id="choose-reeds"'), 1)
        self.assertIn('href="#choose-reeds"', html)
        self.assertNotIn("فرصت کافی برای مطالعه", html.split('class="prose', 1)[1])
        self.assertIn("متن با خرید فرش در بروجرد و", html)
        self.assertIn('href="/guarantee/"', html)
        self.assertIn("/product-category/carpet-1200-reeds/", html)


class BlogSearchAndRecsTests(TestCase):
    def setUp(self):
        from decimal import Decimal

        from catalog.models import Attribute, AttributeTerm, Product
        from pricing.albums import sync_album_variations
        from pricing.models import Album, Size, seed_sizes
        from core.models import Media

        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        album = Album.objects.create(name="ورژن 1200 شانه", code="V", base_size=s["12-meter"], base_price=Decimal("30000000"),
                                     slug="v1200", in_price_list=True)
        album.sizes.set([s["12-meter"], s["6-meter"]])
        reeds = Attribute.objects.get_or_create(slug="reeds-per-meter", defaults={"label": "شانه"})[0]
        term = AttributeTerm.objects.create(attribute=reeds, name="1200", slug="1200")
        img = Media.objects.create(file="x.jpg")
        for i in range(5):
            p = Product.objects.create(title=f"فرش 1200 شانه نقشه {i}", slug=f"p{i}", album=album, status="publish", image=img, views=i)
            p.specs.add(term)
        sync_album_variations(list(Product.objects.all()), reset=True)
        Post.objects.create(title="تاریخچه فرش 1200 شانه", slug="history", status="publish",
                            content="<p>تراکم فرش و شانه</p>" + "<h2>بخش</h2><p>" + "متن " * 900 + "</p>" * 1)
        Post.objects.create(title="شستن فرش در خانه", slug="wash", status="publish", content="<p>با آب سرد بشویید.</p>")

    def test_blog_search(self):
        r = self.client.get("/blog/search/", {"q": "شستن فرش"})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("شستن فرش در خانه", html)
        self.assertNotIn("تاریخچه فرش", html.split("post-grid", 1)[1])
        self.assertIn("noindex", html)
        self.assertIn("در فرش‌ها", html)

    def test_post_has_sidebar_recs_and_affiliate_for_learning_posts(self):
        html = self.client.get("/history/").content.decode()
        self.assertIn('action="/blog/search/"', html)
        self.assertIn("فرش 1200 شانه نقشه", html)
        self.assertIn("/product-category/carpet-1200-reeds/", html)

    def test_product_search_shows_article_hits(self):
        html = self.client.get("/search/", {"q": "تراکم"}).content.decode()
        self.assertIn("مقاله‌های مرتبط", html)
        self.assertIn("/history/", html)
