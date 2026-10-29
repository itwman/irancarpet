from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.models import SiteSettings
from seo.models import SeoSettings

from . import claims

ABOUT = ("<p>ایران کارپت (irancarpet.net) نخستین فروشگاه آنلاین فرش ماشینی در ایران است که از سال 1387 فعالیت می‌کند و "
         "فروشگاه حضوری آن در کاشان است.</p>")


class ClaimsTests(TestCase):
    def setUp(self):
        cache.clear()
        s = SiteSettings.load()
        s.home_about = ABOUT
        s.trust_points = [["اولین فروشگاه آنلاین فرش ماشینی در ایران", "با بیش از ۱۸ سال سابقه"], ["ارسال رایگان", "به همهٔ ایران"]]
        s.address = "کاشان، م. زجاجی"
        s.save()
        seo = SeoSettings.load()
        seo.llms_about = "فروشگاه از سال ۱۳۸۷ فعال است."
        seo.save()

    def test_scan_and_apply_and_undo(self):
        rows = {r["key"]: r for r in claims.scan()}
        about = next(r for r in rows.values() if r["field"] == "دربارهٔ ایران کارپت")
        self.assertIn("از ۱۳۸۹ در فضای آنلاین فعال است و فروشگاه اینترنتی آن از ۱۳۹۱ کار می‌کند", about["new"])
        self.assertIn("ایران کارپت (irancarpet.net) از ۱۳۸۹", about["new"])
        tp = sorted((r["old"], r["new"]) for r in rows.values() if r["key"].split("|")[2] == "trust_points")
        self.assertEqual(tp, [("اولین فروشگاه آنلاین فرش ماشینی در ایران", "از قدیمی‌ترین فروشگاه‌های آنلاین فرش ماشینی"),
                              ("با بیش از ۱۸ سال سابقه", "فروش آنلاین از ۱۳۹۱")])
        self.assertTrue(any(r["kind"] == "address" and r["new"] == claims.ADDRESS for r in rows.values()))

        user = User.objects.create_superuser("a", "a@a.ir", "x")
        self.client.force_login(user)
        self.assertContains(self.client.get("/panel/content-tools/claims/"), "از قدیمی‌ترین فروشگاه‌های آنلاین")
        post = {"pick": [k for k, r in rows.items() if r["auto"]]}
        for k, r in rows.items():
            post["old_" + k], post["new_" + k] = r["old"], r["new"]
        self.client.post("/panel/content-tools/claims/", post)
        s = SiteSettings.load()
        self.assertNotIn("1387", s.home_about)
        self.assertEqual(s.trust_points[0], ["از قدیمی‌ترین فروشگاه‌های آنلاین فرش ماشینی", "فروش آنلاین از ۱۳۹۱"])
        self.assertEqual(s.trust_points[1], ["ارسال رایگان", "به همهٔ ایران"])
        self.assertEqual(s.address, claims.ADDRESS)
        self.assertEqual(SeoSettings.load().llms_about, "فروشگاه از ۱۳۸۹ فعال است.")
        self.assertEqual([r for r in claims.scan() if r["auto"]], [])

        from content.models import ContentEdit

        edit = ContentEdit.objects.get()
        self.client.post("/panel/content-tools/", {"do": "undo", "edit": edit.pk})
        cache.clear()
        s = SiteSettings.load()
        self.assertEqual(s.home_about, ABOUT)
        self.assertEqual(s.trust_points[0][1], "با بیش از ۱۸ سال سابقه")
