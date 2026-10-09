"""آزمون باشگاه مشتریان: پیامک سفارش، پیگیری پرداخت، کمپین با کد شخصی، گروه‌ها، گزارش و کاربران اسپم."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Profile
from shop.models import Coupon, Order, ShopSettings

from . import campaigns, jobs, notify, segments, spam
from .models import Campaign, CrmSettings, SmsLog

User = get_user_model()
td = timezone.timedelta
OK = mock.patch("accounts.sms.send_bulk", return_value=(True, ""))


def mk(mobile="09121111111", status="pending", total=50_000_000, days=0, **kw):
    o = Order.objects.create(first_name=kw.pop("first_name", "علی"), last_name="رضایی", mobile=mobile, province="تهران",
                             city=kw.pop("city", "تهران"), address="آزادی", items_total=total, online_amount=total, status=status,
                             paid_amount=total if status in ("paid", "completed", "shipped") else 0, **kw)
    if days:
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - td(days=days))
        o.refresh_from_db()
    return o


@override_settings(SMSIR_API_KEY="", STAGING=True)
class CrmTests(TestCase):
    def setUp(self):
        cache.clear()
        s = ShopSettings.load()
        s.admin_mobiles = "09125347596، 0912 000 0000"
        s.save()

    # ---------------------------------------------------------- پیامک سفارش
    def test_render_ignores_unknown_and_bad_braces(self):
        self.assertEqual(notify.render("سلام {name} {nope}", name="علی"), "سلام علی")
        self.assertEqual(notify.render("قیمت {"), "قیمت {")

    def test_order_placed_customer_and_admins(self):
        o = mk()
        with OK as sms:
            notify.order_placed_now(o)
            notify.order_placed_now(o)  # تکرار: مشتری دوباره پیامک نمی‌گیرد
        to = [c[0][0][0] for c in sms.call_args_list]
        self.assertEqual(to.count("09121111111"), 1)
        self.assertEqual(to.count("09125347596"), 2)
        self.assertIn("09120000000", to)
        self.assertIn(str(o.number), sms.call_args_list[0][0][1])
        self.assertIn("/o/", sms.call_args_list[0][0][1])  # پیوند پرداخت بدون ورود
        self.assertEqual(SmsLog.objects.filter(order=o, kind="order").count(), 1)

    def test_order_placed_respects_switches(self):
        s = CrmSettings.load()
        s.order_sms, s.admin_sms = False, False
        s.save()
        with OK as sms:
            notify.order_placed_now(mk())
        self.assertFalse(sms.called)

    def test_status_change_sms(self):
        o = mk(status="paid", tracking_code="RT123")
        o.status = "shipped"
        with OK as sms:
            self.assertTrue(notify.status_changed_now(o, "paid"))
            o.status = "processing"
            self.assertFalse(notify.status_changed_now(o, "paid"))
        self.assertIn("RT123", sms.call_args_list[0][0][1])
        self.assertEqual(sms.call_count, 1)

    def test_paid_hook_uses_crm_without_templates(self):
        from shop import notify as shop_notify

        o = mk(status="paid")
        with mock.patch("crm.notify.order_paid") as crm_paid:
            shop_notify.order_paid(o, 1000)
        crm_paid.assert_called_once_with(o, 1000, customer=True, admin=True)

    # ---------------------------------------------------------- پیگیری پرداخت
    def test_three_step_reminder_with_price_fluctuation(self):
        o = mk(days=0)
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - td(hours=2))
        with OK as sms:
            self.assertEqual(jobs.remind_unpaid(), 1)
            self.assertEqual(jobs.remind_unpaid(), 0)
            Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - td(hours=25))
            self.assertEqual(jobs.remind_unpaid(), 1)
            Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - td(hours=73))
            self.assertEqual(jobs.remind_unpaid(), 1)
            self.assertEqual(jobs.remind_unpaid(), 0)
        self.assertIn("نوسان قیمت", sms.call_args_list[1][0][1])
        self.assertEqual(Order.objects.get(pk=o.pk).reminded_count, 3)

    def test_reminder_skipped_when_later_order_paid(self):
        o = mk()
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - td(hours=2))
        mk(status="paid")
        with OK as sms:
            self.assertEqual(jobs.remind_unpaid(), 0)
        self.assertFalse(sms.called)

    # ---------------------------------------------------------- گروه‌ها و کمپین
    def test_segments(self):
        mk("09121111111", "completed", 200_000_000, days=30)  # وفادار، تازه، فعال
        mk("09122222222", "completed", 50_000_000, days=250)  # در خطر ریزش
        mk("09123333333", "completed", 50_000_000, days=500)  # از دست رفته
        mk("09124444444", "pending", days=3)  # بی‌پرداخت
        u = User.objects.create(username="09125555555")
        Profile.objects.update_or_create(user=u, defaults={"mobile": "09125555555"})
        c = segments.counts()
        self.assertEqual((c["vip"], c["new"], c["active"], c["at_risk"], c["lost"], c["unpaid"], c["registered"]), (1, 1, 1, 1, 1, 1, 1))
        cache.clear()
        self.assertEqual({x["mobile"] for x in segments.audience("inactive", 200)}, {"09122222222", "09123333333"})
        self.assertEqual([x["mobile"] for x in segments.audience("custom", custom="0912 222 2222\n+989122222222,bad")], ["09122222222"])

    def test_campaign_personal_coupons(self):
        mk("09121111111", "completed", days=40, first_name="مریم")
        mk("09122222222", "completed", days=400)
        camp = Campaign.objects.create(title="تخفیف مشتریان قبلی", segment="buyers", discount=2_000_000, min_order=40_000_000)
        Campaign.objects.filter(pk=camp.pk).update(status="sending")
        with OK as sms:
            campaigns.run_sync(camp.pk)
            Campaign.objects.filter(pk=camp.pk).update(status="sending")
            campaigns.run_sync(camp.pk)  # ادامه: دوباره فرستاده نمی‌شود
        camp.refresh_from_db()
        self.assertEqual((camp.status, camp.total, camp.sent, sms.call_count), ("done", 2, 2, 2))
        coupons = Coupon.objects.filter(code__startswith=f"{camp.code_prefix}-")
        self.assertEqual(coupons.count(), 2)
        c = coupons.get(for_mobile="09121111111")
        self.assertEqual((c.kind, c.value, c.min_order, c.usage_limit), ("fixed", 2_000_000, 40_000_000, 1))
        text = [x[0][1] for x in sms.call_args_list if x[0][0] == ["09121111111"]][0]
        self.assertIn(c.code, text)
        self.assertIn("مریم", text)
        self.assertTrue(text.endswith("لغو۱۱"))

    def test_personal_coupon_only_for_its_mobile(self):
        from shop.coupons import check

        c = campaigns.personal_coupon("C9", "09121111111", "t", 2_000_000, 40_000_000, 30)
        owner = User.objects.create(username="09121111111")
        other = User.objects.create(username="09122222222")
        self.assertEqual(check(c.code, other, 50_000_000)[2][:19], "این کد مخصوص شمارهٔ")
        self.assertIn("بالای", check(c.code, owner, 30_000_000)[2])
        self.assertEqual(check(c.code, owner, 50_000_000)[1], 2_000_000)
        self.assertEqual(campaigns.personal_coupon("C9", "09121111111", "t", 1, 1, 1).pk, c.pk)

    def test_campaign_stops_after_repeated_failures(self):
        for i in range(7):
            mk(f"0912000000{i}", "completed", days=10)
        camp = Campaign.objects.create(title="x", segment="buyers", discount=0)
        Campaign.objects.filter(pk=camp.pk).update(status="sending")
        with mock.patch("accounts.sms.send_bulk", return_value=(False, "خط نامعتبر")):
            campaigns.run_sync(camp.pk)
        camp.refresh_from_db()
        self.assertEqual((camp.status, camp.failed, camp.last_error), ("failed", 5, "خط نامعتبر"))

    def test_winback_daily(self):
        s = CrmSettings.load()
        s.winback_auto = True
        s.save()
        mk("09121111111", "completed", days=200)
        mk("09122222222", "completed", days=20)
        with OK as sms:
            self.assertEqual(jobs.winback(), 1)
            cache.delete("crm:winback:day")
            self.assertEqual(jobs.winback(), 0)  # در یک سال فقط یک‌بار
        self.assertIn("WB-", sms.call_args[0][1])

    # ---------------------------------------------------------- اسپم
    def test_spam_candidates(self):
        spammer = User.objects.create(username="xkqzvbtrw@mailinator.xyz", email="x.k.q.z@seo-links.xyz")
        buyer = User.objects.create(username="buyer@gmail.com", email="buyer@gmail.com")
        mk(user=buyer)
        User.objects.create(username="09121234567")
        User.objects.create(username="staffer", is_staff=True)
        withmobile = User.objects.create(username="mm@gmail.com")
        Profile.objects.update_or_create(user=withmobile, defaults={"mobile": "09127777777"})
        self.assertEqual(list(spam.candidates().values_list("pk", flat=True)), [spammer.pk])
        self.assertEqual(spam.level(spammer), "high")
        self.assertEqual(spam.delete_safe(User.objects.all()), 1)
        self.assertEqual(User.objects.count(), 4)

    # ---------------------------------------------------------- پنل
    def test_panel_pages(self):
        admin = User.objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(admin)
        mk("09121111111", "completed", days=20)
        mk("09122222222", "pending", days=1)
        User.objects.create(username="spam@spam.xyz", email="spam@spam.xyz")
        Campaign.objects.create(title="کمپین آزمایشی")
        for url in ["/panel/crm/report/", "/panel/crm/report/?days=0", "/panel/crm/segments/", "/panel/crm/segments/vip/",
                    "/panel/crm-campaigns/", "/panel/crm-campaigns/add/?segment=at_risk&title=x", "/panel/crm-sms/",
                    "/panel/spam-users/", "/panel/spam-users/?level=high", "/panel/settings/?tab=crm"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/panel/crm/segments/nope/").status_code, 404)
        r = self.client.post("/panel/settings/", {"tab": "crm", "do": "crm_test", "which": "remind_text_2", "test_mobile": "09121111111"})
        self.assertEqual(r.status_code, 302)

    def test_panel_status_change_sends_sms(self):
        admin = User.objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(admin)
        o = mk(status="paid")
        data = {k: getattr(o, k) for k in ["first_name", "last_name", "mobile", "email", "province", "city", "address", "postal_code", "note"]}
        data.update(status="shipped", tracking_code="", admin_note="")
        with mock.patch("crm.notify.status_changed") as sc:
            self.client.post(f"/panel/orders/{o.pk}/view/", data)
        sc.assert_called_once()
        self.assertEqual(sc.call_args[0][1], "paid")
