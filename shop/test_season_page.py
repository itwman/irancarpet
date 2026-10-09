"""آزمون صفحهٔ فرش جشنواره‌ای، فصل شلوغ و توقف سفارش، و کمپین‌های خودکار."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Attribute, AttributeTerm, Product
from core.models import Media
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from . import season
from .models import ShopSettings, SpecialOffer
from .offers import clear

OK = mock.patch("accounts.sms.send_bulk", return_value=(True, ""))


@override_settings(STAGING=True, SMSIR_API_KEY="")
class OffersPageAndSeasonTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        a = Album.objects.create(name="1200", code="A", base_size=s["12-meter"], base_price=Decimal("50000000"))
        a.sizes.set([s["12-meter"], s["9-meter"]])
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        t1200 = AttributeTerm.objects.create(attribute=reeds, name="1200", slug="1200")
        img = Media.objects.create(file="x.jpg")
        self.offers = []
        for i in range(30):
            p = Product.objects.create(title=f"فرش افشان {i}", slug=f"p{i}", album=a, status="publish", image=img)
            p.specs.add(t1200)
            sync_album_variations([p])
            size = s["9-meter"] if i % 3 else s["12-meter"]
            self.offers.append(SpecialOffer.objects.create(product=p, size=size, percent=10 + i, quantity=1))
        clear()

    def test_offers_page(self):
        r = self.client.get("/فرش-جشنواره-ای/")
        self.assertContains(r, "فرش جشنواره‌ای و زیر قیمت")
        self.assertEqual(len(r.context["offers"]), 24)
        self.assertEqual(r.context["offers"][0].percent, 39)  # بیشترین تخفیف اول
        self.assertContains(r, "FAQPage")
        self.assertContains(r, 'rel="next"')
        r2 = self.client.get("/فرش-جشنواره-ای/?page=2")
        self.assertEqual(len(r2.context["offers"]), 6)
        r3 = self.client.get("/فرش-جشنواره-ای/?size=12-meter&sort=cheap")
        self.assertEqual(r3.context["count"], 10)
        self.assertContains(r3, "noindex")
        self.assertEqual(self.client.get("/فرش-جشنواره-ای/?page=9").status_code, 302)
        self.assertEqual(self.client.get("/offers/").status_code, 301)
        home = self.client.get("/")
        self.assertEqual(len(home.context["offers"]), 8)
        self.assertContains(home, "همهٔ ۳۰ فرصت")
        # فرصت زمان‌دار اول؛ بقیه هر روز می‌چرخند
        from datetime import date

        from core.views import _home_offers

        SpecialOffer.objects.filter(pk=self.offers[0].pk).update(ends_at=timezone.now() + timezone.timedelta(days=2))
        clear()
        d1 = _home_offers(date(2026, 10, 9))["offers"]
        d2 = _home_offers(date(2026, 10, 10))["offers"]
        self.assertEqual((len(d1), d1[0].pk, d2[0].pk), (8, self.offers[0].pk, self.offers[0].pk))
        self.assertNotEqual({o.pk for o in d1[1:]}, {o.pk for o in d2[1:]})

    def test_season_windows(self):
        self.assertTrue(season.in_window((12, 20), (12, 1), (1, 15)))
        self.assertTrue(season.in_window((1, 3), (12, 1), (1, 15)))
        self.assertFalse(season.in_window((1, 20), (12, 1), (1, 15)))
        self.assertTrue(season.in_window((10, 5), (10, 1), (11, 30)))
        sh = ShopSettings.load()
        with mock.patch("shop.season.today_md", return_value=(12, 10)):
            st = season.state(shop=sh)
            self.assertTrue(st["paused"])
            self.assertFalse(st["busy"])

    def test_pause_blocks_made_to_order_but_not_offers(self):
        from shop.cart import Line

        p = self.offers[0].product
        v12 = p.variations.get(size__slug="12-meter")
        v9 = p.variations.get(size__slug="9-meter")
        offer_line, normal = Line(v12, 1), Line(v9, 1)
        self.assertIsNotNone(offer_line.offer)
        with mock.patch("shop.season.today_md", return_value=(12, 10)):
            self.assertEqual(season.blocked_lines([offer_line, normal]), [normal])
            self.assertIn("فرصت ویژه", season.pause_error([normal]))
            self.assertEqual(season.pause_error([offer_line]), "")
            page = self.client.get(p.get_absolute_url())
            self.assertContains(page, "پذیرفته نمی‌شود")
        with mock.patch("shop.season.today_md", return_value=(10, 10)):
            self.assertEqual(season.pause_error([normal]), "")
            self.assertContains(self.client.get(p.get_absolute_url()), "دی و بهمن")

    def test_weekly_offer_and_calendar(self):
        from crm import jobs
        from crm.models import AutoCampaign, Campaign, CrmSettings, SmsLog
        from shop.models import Order

        for i in range(3):
            Order.objects.create(first_name="علی", last_name="ر", mobile=f"0912000000{i}", province="x", city="x", address="x",
                                 items_total=50_000_000, status="completed", paid_amount=50_000_000)
        s = CrmSettings.load()
        now = timezone.localtime().replace(hour=12)
        s.offer_sms_weekday = now.weekday()
        s.save()
        self.assertEqual(jobs.weekly_offer(now), 1)
        self.assertEqual(jobs.weekly_offer(now), 0)  # هفته‌ای یکی
        camp = Campaign.objects.get(offer__isnull=False)
        self.assertEqual(camp.offer.percent, 39)
        with OK as sms:
            from crm.campaigns import resume_sending

            resume_sending()
        camp.refresh_from_db()
        self.assertEqual((camp.status, camp.sent), ("done", 3))
        text = sms.call_args[0][1]
        self.assertIn("٪", text)
        self.assertIn("یک تخته", text)
        # تقویم
        import jdatetime

        j = jdatetime.date.fromgregorian(date=now.date())
        t = j + jdatetime.timedelta(days=1)
        AutoCampaign.objects.all().delete()
        a = AutoCampaign.objects.create(title="آزمایش", month=t.month, day=t.day, hour=10, segment="buyers", discount=2_000_000,
                                        text="{name} عزیز، کد {code} تا {until}")
        from shop.models import ShopSettings as SS

        sh = SS.load()
        sh.admin_mobiles = "09125347596"
        sh.save()
        with OK as sms:
            self.assertEqual(jobs.auto_campaigns(now), 0)  # فقط پیش‌نمایش
            self.assertIn("پیش‌نمایش", sms.call_args[0][1])
            jobs.auto_campaigns(now)
            self.assertEqual(sms.call_count, 1)  # پیش‌نمایش یک‌بار
        tomorrow = now + timezone.timedelta(days=1)
        self.assertEqual(jobs.auto_campaigns(tomorrow.replace(hour=9)), 0)  # پیش از ساعت
        self.assertEqual(jobs.auto_campaigns(tomorrow.replace(hour=10)), 1)
        self.assertEqual(jobs.auto_campaigns(tomorrow.replace(hour=11)), 0)
        c = Campaign.objects.get(title__startswith="آزمایش")
        self.assertEqual((c.status, c.discount), ("sending", 2_000_000))
        a.refresh_from_db()
        self.assertEqual(a.last_run_year, t.year)
        self.assertTrue(SmsLog.objects.filter(kind="admin").exists())

    def test_panel_calendar(self):
        admin = get_user_model().objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(admin)
        from crm.models import AutoCampaign

        self.assertGreaterEqual(AutoCampaign.objects.count(), 9)  # تقویم پیش‌فرض
        a = AutoCampaign.objects.first()
        for url in ["/panel/crm-calendar/", f"/panel/crm-calendar/{a.pk}/", "/panel/settings/?tab=shop", "/panel/settings/?tab=crm"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
