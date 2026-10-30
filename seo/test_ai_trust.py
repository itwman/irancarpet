import json
import re

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from blog.models import Page
from core.models import SiteSettings


def jsonld(html):
    out = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        d = json.loads(block)
        out += d if isinstance(d, list) else [d]
    return out


class AiTrustTests(TestCase):
    def setUp(self):
        cache.clear()
        s = SiteSettings.load()
        s.instagram = "https://www.instagram.com/irancarpet.original"
        s.youtube = "https://www.youtube.com/@iran.carpet"
        s.bale_channel = "http://ble.ir/irancarpett"
        s.address = "کاشان، میدان زجاجی، بلوار شهید پکوک"
        s.store_open = __import__("datetime").time(9)
        s.store_close = __import__("datetime").time(21)
        s.save()

    def test_history_page_and_settings_from_migration(self):
        p = Page.objects.get(slug="تاریخچه-ایران-کارپت")
        self.assertIn("web.archive.org/web/20130303125850", p.content)
        self.assertIn("۱۳۹۸/۰۸/۱۱", p.content)
        self.assertIn("sanat.ir/41580", p.content)
        self.assertIn("trustseal.enamad.ir/?id=137774", p.content)
        self.assertLess(p.content.index("منابع دیگر"), p.content.index("<h2>امروز</h2>"))
        r = self.client.get(p.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertIn("/تاریخچه-ایران-کارپت/", self.client.get("/llms.txt").content.decode())
        self.assertIn("تاریخچه-ایران-کارپت", self.client.get("/page-sitemap.xml").content.decode())

    def test_home_schema(self):
        s = SiteSettings.load()
        self.assertEqual(s.bale_channel, "https://ble.ir/irancarpett")
        html = self.client.get("/").content.decode()
        g = {d["@type"]: d for d in jsonld(html)}
        for t in ("OnlineStore", "HomeGoodsStore"):
            self.assertEqual(g[t]["foundingDate"], "2010")
            self.assertIn("IranCarpet", g[t]["alternateName"])
            self.assertEqual(g[t]["email"], "nazeri.it@gmail.com")
            self.assertNotIn("aggregateRating", g[t])
        same = g["OnlineStore"]["sameAs"]
        self.assertEqual(len([u for u in same if "instagram" in u]), 1)
        self.assertIn("https://www.youtube.com/@iran.carpet", same)
        self.assertEqual(g["HomeGoodsStore"]["address"]["streetAddress"], "کاشان، میدان زجاجی، بلوار شهید پکوک")
        self.assertNotIn("چهار هزار و هشتصد", html)

    def test_social_validation(self):
        s = SiteSettings.load()
        s.youtube = "https://www.instagram.com/irancarpet.original/"
        with self.assertRaises(ValidationError) as e:
            s.full_clean()
        self.assertIn("youtube", e.exception.message_dict)

    def test_legacy_pages_redirect(self):
        for slug, to in (("shop", "/store/"), ("__home__", "/"), ("ایران-کارپت-جدید", "/"), ("ایران-کارپت-1403", "/")):
            Page.objects.create(title=slug, slug=slug, status="publish")
            r = self.client.get(f"/{slug}/")
            self.assertEqual((r.status_code, r["Location"]), (301, to), slug)
        cache.clear()
        llms = self.client.get("/llms.txt").content.decode()
        sm = self.client.get("/page-sitemap.xml").content.decode()
        for slug in ("/shop/", "/__home__/", "ایران-کارپت-1403"):
            self.assertNotIn(slug, llms)
            self.assertNotIn(slug, sm)

    def test_sitemap_index_lastmod_is_real(self):
        from django.utils import timezone

        Page.objects.update(modified_at=timezone.now() - timezone.timedelta(days=40))
        body = self.client.get("/sitemap_index.xml").content.decode()
        m = re.search(r"page-sitemap\.xml</loc><lastmod>([^<]+)</lastmod>", body)
        self.assertTrue(m, body)
        self.assertFalse(m.group(1).startswith(timezone.localdate().isoformat()))

    def test_enamad_verify_link(self):
        Page.objects.create(title="مجوزها", slug="license", template="license", status="publish", content="<p>x</p>[trust_seals]")
        r = self.client.get("/license/").content.decode()
        self.assertIn('href="https://trustseal.enamad.ir/?id=137774&amp;code=70XzemtCwKljQtiHa3iOa2RuzITHgk7G"', r)
        self.assertIn("qr.mojavez.ir/track/8260716", r)
        self.assertIn("معتبر تا ۱۴۰۷/۰۵/۱۰", r)
        self.assertIn('href="https://ecunion.ir/landing/8389/business"', r)
        self.assertIn("صفحهٔ عضویت در سایت اتحادیه", r)
        llms = self.client.get("/llms.txt").content.decode()
        self.assertIn("trustseal.enamad.ir/?id=137774", llms)
        self.assertIn("qr.mojavez.ir/track/1470154", llms)
        s = SiteSettings.load()
        s.enamad_url = ""
        s.trust_html = '<a referrerpolicy="origin" target="_blank" href="https://trustseal.enamad.ir/?id=1&amp;code=abc"><img src="x"></a>'
        s.save()
        self.assertEqual(SiteSettings.load().enamad_verify_url, "https://trustseal.enamad.ir/?id=1&code=abc")
