"""آزمون پیامک کوتاه فرصت ویژه، امتیاز گیرنده‌ها و ارسال مرحله‌ای."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from core.models import Media
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import Order, OrderItem, SpecialOffer

from . import texts
from .campaigns import message, next_waves, offer_vars, run_sync
from .models import Campaign, CrmSettings, SmsLog
from .smart import plan, sms_parts


class SmartTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.s = s
        a = Album.objects.create(name="700", code="A", base_size=s["12-meter"], base_price=Decimal("30000000"))
        a.sizes.set([s["12-meter"], s["9-meter"]])
        img = Media.objects.create(file="x.jpg")
        self.p = Product.objects.create(title="فرش 700 شانه نقشه پارادایس زمینه سرمه ای - پلی استر", slug="par", album=a,
                                        status="publish", image=img)
        self.other = Product.objects.create(title="فرش 1200 شانه نقشه افشان زمینه کرم", slug="af", album=a, status="publish", image=img)
        sync_album_variations([self.p, self.other])
        self.o = SpecialOffer.objects.create(product=self.p, size=s["9-meter"], percent=20, quantity=1)
        u = get_user_model().objects.create_user("u")
        # خریدار همین نقشه با سایز دیگر (ست) و خریدار نقشهٔ دیگر
        o1 = Order.objects.create(user=u, first_name="a", last_name="b", mobile="09120000001", items_total=1, status="paid")
        OrderItem.objects.create(order=o1, product=self.p, variation=self.p.variations.get(size=s["12-meter"]), title="x", unit_price=1)
        o2 = Order.objects.create(user=u, first_name="a", last_name="b", mobile="09120000002", items_total=1, status="paid")
        OrderItem.objects.create(order=o2, product=self.other, variation=self.other.variations.get(size=s["9-meter"]), title="x", unit_price=1)
        self.numbers = "\n".join(["09120000003", "09120000002", "09120000001", "09120000004"])

    def test_short_text_is_two_sms(self):
        v = offer_vars(self.o)
        self.assertEqual(v["product"], "پارادایس سرمه ای ۷۰۰ شانه، ۹ متری مستطیل")
        self.assertEqual(v["left"], "فقط ۱ تخته")
        text = message(texts.OFFER, {"name": "محمدعلی"}, None, "لغو۱۱", **{**v, "link": "https://crpt.ir/l/ab3k9xq"})
        self.assertLessEqual(sms_parts(text), 2)
        old = message(texts.OFFER_OLD, {"name": "محمدعلی"}, None, "لغو۱۱", **{**v, "product": self.p.title, "left": "فقط یک تخته باقی مانده.",
                                                                              "link": "https://crpt.ir/l/ab3k9xq"})
        self.assertGreaterEqual(sms_parts(old), 4)

    def test_ranking_and_waves(self):
        CrmSettings.objects.update_or_create(pk=1, defaults={"wave1_per_piece": 2, "wave2_per_piece": 1, "wave_gap_hours": 48})
        c = Campaign.objects.create(title="ف", segment="custom", custom_numbers=self.numbers, discount=0, text=texts.OFFER, offer=self.o,
                                    status=Campaign.Status.SENDING)
        p = plan(c)
        self.assertEqual(p["ranked"][0][0], "09120000001")  # ست
        self.assertTrue(p["ranked"][0][3])
        self.assertEqual(p["waves"], [2, 1, 1])
        sent = []
        with mock.patch("crm.campaigns.send", side_effect=lambda m, t, *a, **k: sent.append((m, t)) or True):
            run_sync(c.pk)
        c.refresh_from_db()
        self.assertEqual(c.status, "waiting")
        self.assertEqual([m for m, _ in sent], ["09120000001", "09120000002"])
        self.assertIn("برای ست با فرش پارادایس", sent[0][1])
        self.assertNotIn("برای ست", sent[1][1])
        # هنوز وقت مرحلهٔ بعد نشده
        self.assertEqual(next_waves(), 0)
        # فرش فروخته شد: مرحلهٔ بعد لازم نیست
        SpecialOffer.objects.filter(pk=self.o.pk).update(is_active=False)
        from shop.offers import clear

        clear()
        self.assertEqual(next_waves(timezone.now() + timezone.timedelta(hours=49)), 0)
        c.refresh_from_db()
        self.assertEqual(c.status, "done")
        self.assertIn("پیامک لازم نداشتند", c.last_error)

    def test_next_wave_and_freq_cap(self):
        CrmSettings.objects.update_or_create(pk=1, defaults={"wave1_per_piece": 2, "wave2_per_piece": 0, "freq_cap_days": 7})
        other = Campaign.objects.create(title="قبلی", segment="custom", discount=0, text="x")
        SmsLog.objects.create(mobile="09120000004", kind="campaign", campaign=other, text="x", ok=True)
        c = Campaign.objects.create(title="ف", segment="custom", custom_numbers=self.numbers, discount=0, text=texts.OFFER, offer=self.o,
                                    status=Campaign.Status.SENDING)
        sent = []

        def fake(m, t, kind, campaign=None, **k):
            sent.append(m)
            SmsLog.objects.create(mobile=m, kind=kind, campaign=campaign, text=t, ok=True)
            return True

        with mock.patch("crm.campaigns.send", side_effect=fake):
            run_sync(c.pk)
            c.refresh_from_db()
            self.assertEqual(c.status, "waiting")
            self.assertEqual(next_waves(timezone.now() + timezone.timedelta(hours=49)), 1)
            run_sync(c.pk)
        c.refresh_from_db()
        self.assertEqual(c.status, "done")
        self.assertEqual(len(sent), 3)  # ۴ نفر منهای کسی که ۷ روز اخیر پیامک گرفته
        self.assertNotIn("09120000004", sent)

    def test_panel_pages(self):
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        c = Campaign.objects.create(title="ف", segment="custom", custom_numbers=self.numbers, discount=0, text=texts.OFFER, offer=self.o)
        self.assertContains(self.client.get(f"/panel/crm/campaigns/{c.pk}/plan/"), "ست")
        d = self.client.get("/panel/crm/sms-preview/", {"text": texts.OFFER, "offer": self.o.pk, "segment": "custom",
                                                         "custom": self.numbers, "discount": "0"}).json()
        self.assertEqual((d["parts"], d["recipients"]), (2, 4))
        self.assertIn("پارادایس", d["text"])
        self.assertEqual(self.client.get(f"/panel/crm-campaigns/{c.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/panel/settings/?tab=crm").status_code, 200)
