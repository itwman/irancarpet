import datetime as dt

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from pricing.models import Size, seed_sizes
from shop import offerflow as OF
from shop.models import SpecialOffer


def at(y, m, d, h=12):
    return timezone.make_aware(dt.datetime(y, m, d, h, 0))


class OfferFlowTests(TestCase):
    """فرش جشنواره‌ای: فرصت تمام‌شده منتظر تصمیم، اعلان و تمدید تا آخر ماه بعد."""

    def setUp(self):
        cache.clear()
        seed_sizes()
        self.size = Size.objects.get(slug="12-meter")
        self.p = Product.objects.create(title="فرش نقشه آوین", slug="avin", status="publish")
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)

    def mk(self, ends, **kw):
        return SpecialOffer.objects.create(product=self.p, size=self.size, starts_at=timezone.now() - dt.timedelta(days=40),
                                           ends_at=ends, **kw)

    def test_next_month_end(self):
        mehr30 = at(2026, 10, 22, 23)
        self.assertEqual(timezone.localtime(OF.next_month_end(mehr30, at(2026, 10, 27))).date(), dt.date(2026, 11, 21))  # ۳۰ آبان
        self.assertEqual(timezone.localtime(OF.next_month_end(mehr30, at(2026, 11, 18))).date(), dt.date(2026, 12, 21))  # ۳۰ آذر

    def test_waiting_ending_renew_close(self):
        now = timezone.now()
        waiting = self.mk(now - dt.timedelta(days=5))
        old = self.mk(now - dt.timedelta(days=90))                       # خیلی قدیمی: اعلان نمی‌شود
        closed = self.mk(now - dt.timedelta(days=2), is_active=False)   # قبلاً «تمدید نمی‌شود» خورده
        ending = self.mk(now + dt.timedelta(days=2))
        self.mk(now + dt.timedelta(days=20))
        self.assertEqual(OF.counts(), {"waiting": 1, "ending": 1})
        bell = self.client.get("/panel/orders/notify/").json()
        item = next(x for x in bell["items"] if "تمدید شود" in x["label"])
        self.assertEqual((item["n"], item["hot"]), (1, True))
        r = self.client.get("/panel/special-offers/?offer_state=waiting")
        self.assertContains(r, "منتظر تصمیم")
        self.assertContains(r, "تمدید شود؟")
        OF.renew(SpecialOffer.objects.filter(pk=waiting.pk))
        waiting.refresh_from_db()
        self.assertGreater(waiting.ends_at, now + dt.timedelta(days=7))
        OF.close(SpecialOffer.objects.filter(pk=ending.pk))
        cache.clear()
        self.assertEqual(OF.counts(), {"waiting": 0, "ending": 0})
        self.assertTrue(SpecialOffer.objects.get(pk=old.pk).is_active)
        self.assertFalse(SpecialOffer.objects.get(pk=closed.pk).is_active)

    def test_daily_sms_once(self):
        from unittest import mock

        self.mk(timezone.now() - dt.timedelta(days=1))
        nine = timezone.localtime().replace(hour=10)
        with mock.patch("crm.notify.admins", return_value=["09120000000"]), mock.patch("crm.notify.send", return_value=True) as send:
            self.assertEqual(OF.daily_admin_sms(nine), 1)
            self.assertEqual(OF.daily_admin_sms(nine), 0)            # روزی یک بار
        self.assertIn("منتظر تمدید", send.call_args[0][1])
        self.assertIn("offer_state=waiting", send.call_args[0][1])
