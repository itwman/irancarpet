"""استقلال برند سایت‌های دیگر روی همین کد (فرشستان): هیچ ردّی از ایران کارپت به بازدیدکننده نرسد."""
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from blog.models import Page, Post, PostRewrite
from core.models import SiteSettings

FS = {"SITE_URL": "https://farshestan.ir"}


class Base(TestCase):
    def setUp(self):
        cache.clear()
        s = SiteSettings.load()
        s.brand_name, s.site_name = "فرشستان", "فرشستان"
        s.save()
        self.addCleanup(cache.clear)


@override_settings(**FS)
class GuardTests(Base):
    def test_pages_and_sms_never_say_irancarpet(self):
        Post.objects.create(title="راهنمای خرید", slug="rahnama", content="<p>خرید از ایران کارپت در irancarpet.net</p>")
        html = Client().get("/rahnama/").content.decode()
        self.assertNotIn("ایران کارپت", html)
        self.assertNotIn("irancarpet.net", html)
        self.assertIn("خرید از فرشستان در farshestan.ir", html)
        from accounts import sms

        with mock.patch("accounts.sms._send_bulk", return_value=(True, "")) as m:
            sms.send_bulk(["09120000000"], "سفارش شما در ایران کارپت ثبت شد")
        self.assertEqual(m.call_args[0][1], "سفارش شما در فرشستان ثبت شد")

    def test_rewrite_queue_off(self):
        from blog import rewrite

        self.assertEqual(rewrite.run(), {})
        self.assertEqual(rewrite.import_dir("/nowhere"), {})

    def test_live_links(self):
        from core.templatetags.brand import live_filter

        Post.objects.create(title="سایز", slug="سایز-فرش", content="x")
        s = SiteSettings.load()
        s.features_off = "finder"
        s.save()
        cache.clear()
        self.assertFalse(live_filter("/farsh-yab/"))
        self.assertFalse(live_filter("/خرید-فرش-قسطی-از-کارخانه-فرش-کاشان/"))
        self.assertTrue(live_filter("/سایز-فرش/"))
        self.assertTrue(live_filter("/cart/"))


class MainSiteUntouchedTests(Base):
    def test_irancarpet_keeps_its_name(self):
        SiteSettings.objects.update(brand_name="")
        cache.clear()
        Post.objects.create(title="راهنما", slug="rahnama", content="<p>خرید از ایران کارپت</p>")
        self.assertIn("خرید از ایران کارپت", Client().get("/rahnama/").content.decode())
        with self.assertRaises(Exception):
            call_command("brand_clean", stdout=StringIO())


@override_settings(**FS)
class CleanTests(Base):
    def setUp(self):
        super().setUp()
        SiteSettings.objects.update(
            enamad_url="https://trustseal.enamad.ir/?id=137774&code=x", trust_since="فعال در فضای آنلاین از ۱۳۸۹ و فروش اینترنتی از ۱۳۹۱",
            alt_names="Iran Carpet، IranCarpet، ایران‌کارپت، irancarpet.net", founding_date="2010",
            licenses="پروانهٔ کسب | https://qr.mojavez.ir/track/1470154\nمجوز خود فرشستان | https://example.ir/1",
            youtube="https://www.youtube.com/@iran.carpet", home_title="خرید فرش | فرش ماشینی ایران کارپت")
        self.history = Page.objects.create(title="تاریخچهٔ ایران کارپت", slug="تاریخچه-ایران-کارپت", content="x")
        self.about = Page.objects.create(title="درباره ایران کارپت", slug="about-us", content="<p>پورتال فرش ماشینی ایران</p>")
        self.mocha = Post.objects.create(title="فرش موکا", slug="فرش-موکا", content="<p>متن ایران کارپت</p>")
        PostRewrite.objects.create(post=self.mocha, status=PostRewrite.Status.PUBLISHED, published_at=timezone.now(),
                                   title="فرش موکا", content="<p>متن ایران کارپت</p>",
                                   old={"title": "فرش موکا", "content": "<p>متن خود فرشستان</p>"})
        self.post = Post.objects.create(title="ارسال", slug="ersal", content="<p>ارسال ایران کارپت از کاشان</p>")

    def test_report_then_apply(self):
        out = StringIO()
        call_command("brand_clean", stdout=out)
        self.assertIn("هنوز چیزی تغییر نکرده", out.getvalue())
        self.assertEqual(SiteSettings.load().enamad_url[:30], "https://trustseal.enamad.ir/?i")   # گزارش دست نمی‌زند
        self.mocha.refresh_from_db()
        self.assertIn("ایران کارپت", self.mocha.content)

        call_command("brand_clean", "--apply", stdout=StringIO())
        s = SiteSettings.load()
        self.assertEqual((s.enamad_url, s.trust_since, s.alt_names, s.founding_date, s.youtube), ("", "", "", "", ""))
        self.assertEqual(s.licenses, "مجوز خود فرشستان | https://example.ir/1")
        self.assertEqual(s.home_title, "خرید فرش | فرش ماشینی فرشستان")
        self.mocha.refresh_from_db()
        self.assertEqual(self.mocha.content, "<p>متن خود فرشستان</p>")                  # بازنویسی ایران کارپت برگشت
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "<p>ارسال فرشستان از کاشان</p>")
        for p in (self.history, self.about):                                           # دربارهٔ خود ایران کارپت
            p.refresh_from_db()
            self.assertEqual(p.status, "draft")
        from seo.models import SeoSettings

        self.assertFalse(SeoSettings.load().rewrite_enabled)
        r = Client().get("/about-us/")
        self.assertEqual((r.status_code, r["Location"]), (301, "/"))
