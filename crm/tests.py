"""آزمون باشگاه مشتریان: پیامک سفارش، پیگیری پرداخت، کمپین با کد شخصی، گروه‌ها، گزارش و کاربران اسپم."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Profile
from shop.models import Coupon, Order, ShopSettings

from . import campaigns, jobs, links, notify, points, segments, spam
from .models import CartSnapshot, Campaign, CrmSettings, ProductView, ShortLink, SmsLog

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
        for which in ["remind_text_1", "remind_text_2", "order_text", "birthday_text", "album_text"]:
            with OK as sms:
                r = self.client.post("/panel/settings/", {"tab": "crm", "do": "crm_test", "which": which, "test_mobile": "09121111111"},
                                     follow=True)
            self.assertContains(r, "پیامک نمونه به", msg_prefix=which)
            self.assertNotIn("{", sms.call_args[0][1])
        self.assertContains(self.client.get("/panel/settings/?tab=crm"), "crpt.ir/k/")
        self.assertEqual(self.client.get("/panel/crm-points/").status_code, 200)

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


@override_settings(SMSIR_API_KEY="", STAGING=True, PAYMENT_FAKE=True)
class CrmMoreTests(TestCase):
    def setUp(self):
        cache.clear()

    def customer(self, mobile="09121111111", name="مریم"):
        u = User.objects.create(username=mobile, first_name=name)
        Profile.objects.update_or_create(user=u, defaults={"mobile": mobile})
        return u

    # ---------------------------------------------------------- پیوند کوتاه
    def test_short_links(self):
        url = links.shorten("https://irancarpet.net/my-account/club/", "k")
        self.assertRegex(url, r"^https://crpt\.ir/k/[a-z0-9]{7}$")
        self.assertEqual(links.shorten("/my-account/club/", "k"), url)  # تکراری ساخته نمی‌شود
        code = url.rsplit("/", 1)[1]
        r = self.client.get(f"/k/{code}", HTTP_HOST="crpt.ir")
        self.assertEqual(r["Location"], "https://irancarpet.net/my-account/club/")
        s = CrmSettings.load()
        s.short_links = False
        s.save()
        url2 = links.shorten("/my-account/club/", "k")
        self.assertEqual(url2, f"https://irancarpet.net/s/{code}/")
        self.assertRedirects(self.client.get(f"/s/{code}/"), "/my-account/club/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/s/nope123/").status_code, 404)
        self.assertEqual(ShortLink.objects.get(code=code).hits, 2)

    # ---------------------------------------------------------- بیعانه / پیش‌پرداخت
    def test_pay_link_follows_chosen_mode_and_can_switch(self):
        from growth.jobs import quickpay_url
        from shop import paymode

        sh = ShopSettings.load()
        sh.allow_full, sh.allow_deposit, sh.deposit_percent = True, True, 10
        sh.save()
        o = mk(total=48_500_000, payment_mode="deposit")
        Order.objects.filter(pk=o.pk).update(online_amount=4_850_000)
        o.refresh_from_db()
        ctx = notify.context(o)
        self.assertEqual(ctx["due"], "بیعانه")
        self.assertIn("بیعانه", ctx["due_line"])
        self.assertTrue(ctx["pay_link"].startswith("https://crpt.ir/o/"))
        url = quickpay_url(o).replace("https://irancarpet.net", "")
        page = self.client.get(url)
        self.assertContains(page, "چطور پرداخت می‌کنید")
        self.assertEqual([m["mode"] for m in paymode.options(o)], ["full", "deposit"])
        self.client.post(url, {"gateway": "fake", "mode": "deposit"})
        self.assertEqual(o.payments.get().amount, 4_850_000)
        self.client.post(url, {"gateway": "fake", "mode": "full"})
        o.refresh_from_db()
        self.assertEqual((o.payment_mode, o.online_amount, o.payments.order_by("-pk").first().amount), ("full", 48_500_000, 48_500_000))

    def test_installment_prepayment_label(self):
        o = mk(total=60_000_000, payment_mode="installment")
        Order.objects.filter(pk=o.pk).update(online_amount=15_000_000)
        o.refresh_from_db()
        ctx = notify.context(o)
        self.assertEqual(ctx["due"], "پیش‌پرداخت")
        self.assertIn("پیش‌پرداخت", ctx["due_line"])
        from shop import paymode

        self.assertEqual(paymode.options(o), [])

    # ---------------------------------------------------------- امتیاز و باشگاه
    def test_points_redeem_and_refund_on_expiry(self):
        mk(status="completed", total=25_500_000)
        mk(status="completed", total=50_000_000)
        mk(status="cancelled", total=90_000_000)
        self.assertEqual(points.balance("09121111111"), 75)
        self.assertIn("کمترین", points.redeem("09121111111", 75)[1])
        mk(status="paid", total=30_000_000)
        c, err = points.redeem("09121111111", 100)
        self.assertEqual((err, c.value, c.for_mobile, c.code[:3]), ("", 1_000_000, "09121111111", "PT-"))
        self.assertEqual(points.balance("09121111111"), 5)
        Coupon.objects.filter(pk=c.pk).update(ends_at=timezone.now() - td(days=1))
        self.assertEqual(points.balance("09121111111"), 105)

    def test_club_page_redeem_and_birthday(self):
        u = self.customer()
        mk(status="completed", total=120_000_000)
        self.client.force_login(u)
        r = self.client.get("/my-account/club/")
        self.assertContains(r, "۱۲۰")
        self.assertContains(self.client.get("/my-account/"), "/my-account/club/")
        r = self.client.post("/my-account/club/", {"do": "redeem", "points": "۱۰۰"}, follow=True)
        self.assertContains(r, "PT-")
        self.client.post("/my-account/club/", {"do": "birthday", "month": "7", "day": "15"})
        self.client.post("/my-account/club/", {"do": "birthday", "month": "7", "day": "17"})
        u.profile.refresh_from_db()
        self.assertEqual((u.profile.birth_month, u.profile.birth_day), (7, 15))
        self.assertContains(self.client.get("/my-account/club/"), "مهر")

    def test_paid_sms_mentions_points(self):
        o = mk(status="paid", total=48_000_000)
        with OK as sms:
            notify.order_paid_now(o, 48_000_000, admin=False)
        self.assertIn("۴۸ امتیاز", sms.call_args[0][1])

    def test_birthday_gift(self):
        import jdatetime

        j = jdatetime.date.fromgregorian(date=timezone.localtime().date())
        u = self.customer()
        Profile.objects.filter(user=u).update(birth_month=j.month, birth_day=j.day)
        with OK as sms:
            self.assertEqual(jobs.birthday(), 1)
            cache.delete("crm:birthday:day")
            self.assertEqual(jobs.birthday(), 0)
        self.assertIn("BD-", sms.call_args[0][1])
        self.assertTrue(Coupon.objects.filter(code__startswith="BD-", for_mobile="09121111111").exists())

    # ---------------------------------------------------------- سبد رهاشده
    def test_abandoned_cart_reminder_and_restore(self):
        u = self.customer()
        CartSnapshot.objects.create(user=u, data={"77": 2}, updated_at=timezone.now() - td(hours=4))
        with OK as sms:
            self.assertEqual(jobs.abandoned_carts(), 1)
            self.assertEqual(jobs.abandoned_carts(), 0)
        link = sms.call_args[0][1].split(": ")[-1]
        path = links.resolve(link.rsplit("/", 1)[1])
        self.assertTrue(path.startswith("/cart/restore/"))
        self.assertRedirects(self.client.get(path), "/cart/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["cart"], {"77": 2})
        # ورود در دستگاه دیگر: سبد ذخیره‌شده برمی‌گردد
        from django.test import Client

        c2 = Client()
        c2.force_login(u)
        self.assertEqual(c2.session["cart"], {"77": 2})

    def test_cart_reminder_skipped_after_order(self):
        u = self.customer()
        CartSnapshot.objects.create(user=u, data={"77": 1}, updated_at=timezone.now() - td(hours=4))
        mk(user=u)
        with OK as sms:
            self.assertEqual(jobs.abandoned_carts(), 0)
        self.assertFalse(sms.called)

    # ---------------------------------------------------------- نظر با عکس و آلبوم
    def _catalog(self):
        from decimal import Decimal

        from catalog.models import Product
        from pricing.models import Album, Size, seed_sizes

        seed_sizes()
        s12 = Size.objects.get(slug="12-meter")
        album = Album.objects.create(name="آلبوم ۱۲۰۰ شانه طاها", code="T", base_size=s12, base_price=Decimal("40000000"),
                                     shipping_fixed=0, waste_value=0, public_name="فرش ۱۲۰۰ شانه طاها")
        p = Product.objects.create(title="فرش طاها", slug="taha", album=album, status="publish")
        return album, p

    def test_review_reward(self):
        from catalog.models import Review, ReviewPhoto

        _, p = self._catalog()
        r = Review.objects.create(product=p, author_name="مریم ر.", mobile="09121111111", content="عالی", is_approved=True, verified=True)
        Review.objects.create(product=p, author_name="بی‌عکس", mobile="09122222222", content="خوب", is_approved=True, verified=True)
        ReviewPhoto.objects.create(review=r, image="reviews/x.jpg")
        with OK as sms:
            self.assertEqual(jobs.review_rewards(), 1)
            self.assertEqual(jobs.review_rewards(), 0)
        self.assertIn("RV-", sms.call_args[0][1])
        self.assertEqual(sms.call_args[0][0], ["09121111111"])

    def test_album_price_notice(self):
        from django.test import RequestFactory

        from shop.models import OrderItem

        from .panel import _album_notice

        album, p = self._catalog()
        viewer = self.customer("09121111111", "سارا")
        ProductView.objects.create(user=viewer, product=p)
        o = mk("09122222222")
        OrderItem.objects.create(order=o, product=p, title="فرش طاها", unit_price=1, quantity=1)
        buyer = mk("09123333333", "completed")
        OrderItem.objects.create(order=buyer, product=p, title="فرش طاها", unit_price=1, quantity=1)
        self.customer("09124444444")  # ندیده
        req = RequestFactory().post("/", {"action_value": "شنبه ۲۶ مهر"})
        from pricing.models import Album

        msg = _album_notice(req, Album.objects.filter(pk=album.pk))
        self.assertIn("۲ نفر", msg)
        camp = Campaign.objects.get(segment="album")
        Campaign.objects.filter(pk=camp.pk).update(status="sending")
        with OK as sms:
            campaigns.run_sync(camp.pk)
        self.assertEqual(sorted(c[0][0][0] for c in sms.call_args_list), ["09121111111", "09122222222"])
        text = sms.call_args_list[0][0][1]
        self.assertIn("فرش ۱۲۰۰ شانه طاها", text)
        self.assertIn("شنبه ۲۶ مهر", text)
        self.assertFalse(Coupon.objects.exists())

    def test_product_view_tracked(self):
        _, p = self._catalog()
        u = self.customer()
        self.client.force_login(u)
        self.client.get(p.get_absolute_url())
        self.assertTrue(ProductView.objects.filter(user=u, product=p).exists())


@override_settings(SMSIR_API_KEY="", STAGING=True)
class CustomerProfileTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser("admin", "a@a.com", "x")

    def test_all_sms_logged_once_and_otp_not_logged(self):
        from accounts import sms

        o = mk()
        with mock.patch("accounts.sms._send_bulk", return_value=(True, "")):
            sms.send_bulk(["9121111111"], "متن اقساط", kind="inst", order=o)
            notify.send("09121111111", "متن سفارش", SmsLog.Kind.ORDER, o)
        with mock.patch("accounts.sms._send_bulk", return_value=(False, "اعتبار کافی نیست")):
            sms.send_bulk(["09121111111"], "بی‌اعتبار")
        with mock.patch("accounts.sms._send_template", return_value=True), mock.patch("accounts.sms._cfg", return_value="1"):
            sms.send_otp("09121111111", "12345")
            sms.send_template("09121111111", "77", {"ORDER": o.number}, kind="paid", order=o)
        logs = list(SmsLog.objects.order_by("pk").values_list("kind", "ok", "order_id"))
        self.assertEqual(logs, [("inst", True, o.pk), ("order", True, o.pk), ("other", False, None), ("paid", True, o.pk)])
        self.assertFalse(SmsLog.objects.filter(text__contains="12345").exists())
        self.assertEqual(SmsLog.objects.get(ok=False).error, "اعتبار کافی نیست")

    def test_customer_profile_page(self):
        self.client.force_login(self.admin)
        u = User.objects.create(username="09121111111", first_name="مریم")
        Profile.objects.update_or_create(user=u, defaults={"mobile": "09121111111"})
        o1 = mk(status="completed", total=60_000_000, days=40, first_name="مریم")
        mk(status="pending", total=30_000_000, user=u, first_name="مریم")
        mk("09129999999", status="completed")  # مشتری دیگر
        SmsLog.objects.create(mobile="09121111111", kind="order", order=o1, text="سفارش ثبت شد آزمایشی", ok=True)
        r = self.client.get("/panel/crm/customer/09121111111/")
        self.assertContains(r, "مریم")
        self.assertContains(r, "سفارش ثبت شد آزمایشی")
        self.assertContains(r, f"/panel/orders/{o1.pk}/view/")
        self.assertEqual(len(r.context["orders"]), 2)
        self.assertRedirects(self.client.get("/panel/crm/customer/9121111111/"), "/panel/crm/customer/09121111111/",
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get("/panel/crm/customer/09129999999/").status_code, 200)  # مهمان، بدون حساب
        self.assertEqual(self.client.get("/panel/crm/customer/123/").status_code, 404)
        self.assertEqual(self.client.get("/panel/crm/customer/09127777777/").status_code, 404)
        self.client.post("/panel/crm/customer/09121111111/", {"do": "note", "text": "آخر ماه تماس بگیرید"})
        with OK:
            self.client.post("/panel/crm/customer/09121111111/", {"do": "sms", "text": "سلام، فرش شما آماده است"})
        r = self.client.get("/panel/crm/customer/09121111111/")
        self.assertContains(r, "آخر ماه تماس بگیرید")
        self.assertTrue(SmsLog.objects.filter(kind="manual", text__contains="آماده است").exists())

    def test_links_from_orders_customers_and_search(self):
        self.client.force_login(self.admin)
        o = mk(status="paid", first_name="سوسن")
        SmsLog.objects.create(mobile="09121111111", kind="paid", order=o, text="پرداخت انجام شد آزمایشی", ok=False, error="خط نامعتبر")
        self.assertContains(self.client.get("/panel/orders/"), "/panel/crm/customer/09121111111/")
        r = self.client.get(f"/panel/orders/{o.pk}/view/")
        self.assertContains(r, "پیامک‌های این سفارش")
        self.assertContains(r, "پرداخت انجام شد آزمایشی")
        self.assertContains(r, "خط نامعتبر")
        self.assertContains(r, "/panel/crm/customer/09121111111/")
        u = User.objects.create(username="09121111111")
        self.assertContains(self.client.get("/panel/customers/"), "/panel/crm/customer/09121111111/")
        self.assertContains(self.client.get(f"/panel/customers/{u.pk}/edit/"), "/panel/crm/customer/09121111111/")
        self.assertRedirects(self.client.get("/panel/crm/segments/?q=۰۹۱۲۱۱۱۱۱۱۱"), "/panel/crm/customer/09121111111/",
                             fetch_redirect_response=False)
        self.assertContains(self.client.get("/panel/crm/segments/?q=سوسن"), "/panel/crm/customer/09121111111/")
        self.assertContains(self.client.get("/panel/crm-sms/"), "/panel/crm/customer/09121111111/")
