"""آزمون آمار بازدید، منبع ورود و گزارش کمپین پیامکی."""
import json
from decimal import Decimal  # noqa: F401
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from crm.models import Campaign, ShortLink, SmsLog
from shop.models import Order

from . import reports, rollup
from .models import DailyStat, DailyTotal, Hit
from .sources import classify

UA = {"HTTP_USER_AGENT": "Mozilla/5.0 (Linux; Android 13) AppleWebKit Chrome Mobile Safari"}


class SourceTests(TestCase):
    def test_classify(self):
        own = {"irancarpet.net"}
        self.assertEqual(classify("https://www.google.com/", own), ("search", "گوگل"))
        self.assertEqual(classify("https://www.google.co.uk/search", own), ("search", "گوگل"))
        self.assertEqual(classify("https://l.instagram.com/?u=x", own), ("social", "اینستاگرام"))
        self.assertEqual(classify("android-app://org.telegram.messenger/", own), ("social", "تلگرام"))
        self.assertEqual(classify("https://torob.com/p/1/", own), ("compare", "ترب"))
        self.assertEqual(classify("https://irancarpet.net/blog/", own), ("internal", ""))
        self.assertEqual(classify("https://news.example.ir/a", own), ("referral", "news.example.ir"))
        self.assertEqual(classify("", own), ("direct", ""))


class BeaconTests(TestCase):
    def setUp(self):
        cache.clear()

    def beacon(self, p="/", r="", pid=0, origin="http://testserver", **extra):
        return self.client.post("/t/", json.dumps({"p": p, "r": r, "pid": pid}), content_type="text/plain",
                                HTTP_ORIGIN=origin, **{**UA, **extra})

    def test_session_source_and_cookies(self):
        self.assertEqual(self.beacon("/فرش/", "https://www.google.com/").status_code, 204)
        h = Hit.objects.get()
        self.assertEqual((h.src, h.src_name, h.entry, h.new, h.device, h.path), ("search", "گوگل", True, True, "m", "/فرش/"))
        self.beacon("/cart/", "http://testserver/فرش/", pid=5)
        h2 = Hit.objects.latest("pk")
        self.assertEqual((h2.src, h2.entry, h2.new, h2.product_id), ("search", False, False, 5))
        self.assertEqual(h.visitor, h2.visitor)
        self.beacon("/?utm_source=instagram&utm_medium=story&utm_campaign=mehr", "")
        h3 = Hit.objects.latest("pk")
        self.assertEqual((h3.src, h3.src_name, h3.medium, h3.utm_campaign, h3.entry), ("utm", "instagram", "story", "mehr", True))

    def test_rejects_foreign_bots_and_staff(self):
        self.beacon("/", origin="https://evil.example")
        self.beacon("/", HTTP_USER_AGENT="Googlebot/2.1")
        self.beacon("/panel/orders/")
        staff = get_user_model().objects.create_user("s", password="x", is_staff=True)
        self.client.force_login(staff)
        self.beacon("/")
        self.assertEqual(Hit.objects.count(), 0)

    def test_rollup_and_report(self):
        self.beacon("/", "https://www.google.com/")
        self.beacon("/a/", "http://testserver/")
        y = timezone.localdate() - timezone.timedelta(days=1)
        Hit.objects.update(day=y)
        self.assertEqual(rollup.run(), 1)
        t = DailyTotal.objects.get(day=y)
        self.assertEqual((t.views, t.visits, t.visitors), (2, 1, 1))
        self.assertEqual(DailyStat.objects.get(day=y).src, "search")
        r = reports.traffic(y, timezone.localdate())
        self.assertEqual(r["t"]["visits"], 1)
        self.assertEqual(r["groups"][0]["src"], "search")
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        for p in ("today", "7", "365"):
            self.assertEqual(self.client.get("/panel/stats/", {"p": p}).status_code, 200)


class CampaignTrackingTests(TestCase):
    def setUp(self):
        cache.clear()

    @mock.patch("crm.campaigns.send", return_value=True)
    def test_personal_links_click_visit_order(self, send):
        from crm.campaigns import run_sync

        c = Campaign.objects.create(title="آزمایش", segment="custom", custom_numbers="09120000001\n09120000002", discount=0,
                                    text="سلام {name} {link}", link_path="/فرش-جشنواره-ای/", status=Campaign.Status.SENDING)
        run_sync(c.pk)
        for m in ("09120000001", "09120000002"):
            SmsLog.objects.create(mobile=m, kind="campaign", campaign=c, text="x", ok=True)
        links = ShortLink.objects.filter(campaign=c)
        self.assertEqual(links.count(), 2)
        texts = [a[0][1] for a in send.call_args_list]
        self.assertTrue(all(f"/s/{link.code}/" in t or f"/l/{link.code}" in t for link, t in zip(links.order_by("pk"), texts)))
        link = links.get(mobile="09120000001")
        r = self.client.get(f"/s/{link.code}/", **UA)
        self.assertIn(f"sl={link.code}", r["Location"])
        r = self.client.get(r["Location"], **UA)
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("sl=", r["Location"])
        link.refresh_from_db()
        self.assertEqual(link.clicks, 1)
        self.assertIsNotNone(link.first_click_at)
        self.client.post("/t/", json.dumps({"p": "/فرش-جشنواره-ای/", "r": ""}), content_type="text/plain",
                         HTTP_ORIGIN="http://testserver", **UA)
        h = Hit.objects.get()
        self.assertEqual((h.src, h.campaign_id, h.link_id), ("sms", c.pk, link.pk))
        # سفارش در همین مرورگر به کمپین نسبت داده می‌شود
        from django.test import RequestFactory

        from stats.track import attach_order

        u = get_user_model().objects.create_user("b")
        o = Order.objects.create(user=u, first_name="a", last_name="b", mobile="09120000001", items_total=50_000_000, status="paid")
        req = RequestFactory().post("/checkout/", **UA)
        req.COOKIES = {k: v.value for k, v in self.client.cookies.items()}
        req.user = u
        attach_order(req, o)
        o.refresh_from_db()
        self.assertEqual((o.src, o.sms_campaign_id), ("sms", c.pk))
        # بات کلیک حساب نمی‌شود
        self.client.get(f"/فرش-جشنواره-ای/?sl={link.code}", HTTP_USER_AGENT="TelegramBot (like TwitterBot)")
        link.refresh_from_db()
        self.assertEqual(link.clicks, 1)
        r = reports.campaign(c)
        self.assertEqual((r["sent"], r["clicked"], r["att_orders"], r["week_orders"]), (2, 1, 1, 1))
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        self.assertContains(self.client.get(f"/panel/crm/campaigns/{c.pk}/report/"), "کلیک‌کننده‌ها")
        self.assertContains(self.client.get("/panel/crm-campaigns/"), f"/panel/crm/campaigns/{c.pk}/report/")


class BotFilterTests(__import__("django.test", fromlist=["TestCase"]).TestCase):
    """بازدید بی‌نشانهٔ انسان (h=0) یا مرورگر خودکار در آمار نمی‌آید و در «بازدید مشکوک» شمرده می‌شود."""

    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

    def setUp(self):
        from django.test import Client

        self.client = Client(enforce_csrf_checks=True)  # مثل مرورگر واقعی: /t/ باید بدون توکن CSRF کار کند

    def post(self, **d):
        import json

        r = self.client.post("/t/", json.dumps({"p": "/carpets/x/", "r": "", **d}), content_type="text/plain",
                                HTTP_USER_AGENT=self.UA, HTTP_ORIGIN="http://testserver", HTTP_REFERER="http://testserver/carpets/x/")
        self.assertEqual(r.status_code, 204)
        return r

    def test_human_counted_bot_separated(self):
        from django.core.cache import cache

        from stats.models import BotDay, Hit

        cache.clear()
        self.post(h=0)
        self.post(h=1, wd=1)
        self.post(h=1, ch="142")                        # سرآیند کروم ۱۴۱، خود مرورگر ۱۴۲: یک نسخه فرق مجاز است
        self.assertEqual(Hit.objects.count(), 1)
        Hit.objects.all().delete()
        self.client.cookies.clear()
        cache.clear()
        self.post(h=1, ch="120")                        # نام مرورگر جعلی
        self.assertEqual(Hit.objects.count(), 0)
        self.assertEqual(BotDay.objects.get().n, 3)
        self.post(h=1)
        self.assertEqual(Hit.objects.filter(kind="v").count(), 1)
        self.client.cookies.clear()
        self.post()                                     # صفحهٔ قدیمی بی‌فیلد h: مثل قبل
        self.assertEqual(Hit.objects.filter(kind="v").count(), 2)
        from stats.reports import _bots
        from django.utils import timezone

        d = timezone.localdate()
        self.assertEqual(_bots(d, d)["total"], 3)
        from io import StringIO

        from django.core.management import call_command

        from stats.models import Probe

        self.post(h=1, ch="141", ev="pointermove", t=1500, tz="Asia/Tehran", lg="fa-IR,fa", sc="1920x1080", hc=8, gl="ANGLE (Intel)")
        self.assertEqual(Probe.objects.count(), 7)
        self.assertTrue(Probe.objects.filter(ua="W141", ev="pointermove", t=1500, hc=8, sus=False).exists())
        out = StringIO()
        call_command("bot_probe", stdout=out)
        self.assertIn("direct=7", out.getvalue())


class BotSignalTests(__import__("django.test", fromlist=["TestCase"]).TestCase):
    """نشانه‌های ربات‌های بازدید آبان ۱۴۰۵: userAgentData نیست، SwiftShader، منطقهٔ زمانی شانگهای با ماوس آنی."""

    WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
    AND = "Mozilla/5.0 (Linux; Android 13; SM-A536E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
    IPH = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"

    def check(self, ua, **d):
        from django.test import RequestFactory

        from stats.track import suspect

        return suspect(RequestFactory().post("/t/", HTTP_USER_AGENT=ua), {"h": 1, **d})

    def test_signals(self):
        human = {"ev": "pointermove", "t": 1800, "tz": "Asia/Tehran", "lg": "fa-IR,fa,en-US"}
        self.assertFalse(self.check(self.WIN, ch="116", **human))
        self.assertFalse(self.check(self.AND, **{**human, "ev": "touchstart"}))          # موبایل بی‌userAgentData (وب‌ویو برنامه‌ها)
        self.assertFalse(self.check(self.IPH, **{**human, "ev": "touchstart"}))
        self.assertFalse(self.check(self.WIN, ch="116", **{**human, "tz": "Europe/Berlin", "lg": "de-DE,fa"}))  # ایرانی خارج از کشور
        self.assertFalse(self.check(self.WIN, ch=""))                                    # صفحهٔ قدیمی بی‌ev
        bot = {"ev": "pointermove", "t": 120, "tz": "Asia/Shanghai", "lg": "en-US", "sc": "1280x1200"}
        self.assertTrue(self.check(self.WIN, ch="", **bot))                              # کروم ۱۱۶ بی‌userAgentData
        self.assertTrue(self.check(self.WIN, ch="116", **bot))                           # شانگهای + ماوس آنی + بی‌فارسی
        self.assertTrue(self.check(self.WIN, ch="116", **{**human, "gl": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)))"}))
