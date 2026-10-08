from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Product
from shop.models import Coupon, Order

from . import commission as C
from .models import Affiliate, AffiliateSettings, Click, Commission, CommissionTier, CustomerRef, valid_sheba
from .track import COOKIE, attach, clear_cache

User = get_user_model()
M = 1_000_000


def order(user=None, total=100 * M, status="pending", mobile="09121112233", coupon=""):
    return Order.objects.create(user=user, first_name="a", last_name="b", mobile=mobile, province="x", city="y", address="z",
                                items_total=total, status=status, coupon_code=coupon)


class AffiliateTests(TestCase):
    def setUp(self):
        clear_cache()
        self.mu = User.objects.create_user("09350000000")
        self.a = Affiliate.objects.create(user=self.mu, code="sara", name="سارا", mobile="09350000000", status="active")
        self.cust = User.objects.create_user("09121112233")
        self.p = Product.objects.create(title="فرش گلریز", slug="golriz", status="publish")

    # ----------------------------------------------------------- پیوند کوتاه و کوکی
    def test_short_host_redirects(self):
        r = self.client.get("/sara", HTTP_HOST="crpt.ir")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith("/?ref=sara"))
        r = self.client.get(f"/sara/{self.p.pk}", HTTP_HOST="crpt.ir")
        self.assertIn("/product/golriz/?ref=sara", r["Location"])
        r = self.client.get("/nobody", HTTP_HOST="crpt.ir")
        self.assertNotIn("ref=", r["Location"])

    def test_ref_param_sets_cookie_and_click(self):
        r = self.client.get("/product/golriz/?ref=sara&x=1", HTTP_USER_AGENT="Mozilla/5.0 (iPhone)")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/product/golriz/?x=1")
        self.assertIn(COOKIE, r.cookies)
        self.assertEqual(Click.objects.get().product, self.p)
        self.client.get("/product/golriz/?ref=sara&x=1", HTTP_USER_AGENT="Mozilla/5.0 (iPhone)")
        self.assertEqual(Click.objects.count(), 1)  # تکراری در نیم ساعت شمرده نمی‌شود

    def test_bots_not_counted(self):
        r = self.client.get("/?ref=sara", HTTP_USER_AGENT="TelegramBot (like TwitterBot)")
        self.assertEqual(r.status_code, 302)
        self.assertNotIn(COOKIE, r.cookies)
        self.assertFalse(Click.objects.exists())

    def test_login_binds_customer(self):
        self.client.get("/?ref=sara", HTTP_USER_AGENT="Mozilla/5.0")
        self.client.force_login(self.cust)
        self.client.get("/my-account/", HTTP_USER_AGENT="Mozilla/5.0")
        ref = CustomerRef.objects.get(user=self.cust)
        self.assertEqual(ref.affiliate, self.a)
        self.assertGreater(ref.expires_at, timezone.now() + timezone.timedelta(days=59))
        # سفارش از اپ (بی‌کوکی) هم به نام همکار است
        c = attach(order(self.cust))
        self.assertEqual(c.source, Commission.Source.ACCOUNT)

    def test_expired_binding_ignored(self):
        CustomerRef.objects.create(user=self.cust, affiliate=self.a, clicked_at=timezone.now() - timezone.timedelta(days=70),
                                   expires_at=timezone.now() - timezone.timedelta(days=10))
        self.assertIsNone(attach(order(self.cust)))

    def test_self_referral_ignored(self):
        self.assertIsNone(attach(order(self.mu, mobile="09350000000"), {"affiliate": self.a}))
        self.assertIsNone(attach(order(None, mobile="09350000000"), {"affiliate": self.a}))

    # ----------------------------------------------------------- پورسانت
    def test_status_flow_and_whole_tier(self):
        o1 = order(self.cust, 100 * M)
        c = attach(o1, {"affiliate": self.a})
        self.assertEqual(c.status, "waiting")
        o1.status = "paid"
        o1.save()
        C.sync(o1)
        c.refresh_from_db()
        self.assertEqual((c.status, c.percent, c.amount), ("pending", Decimal("1.50"), 1_500_000))
        # فروش دوم: جمع ۲۰۰ میلیون ← پلهٔ ۲٪ برای هر دو سفارش
        o2 = order(self.cust, 100 * M, status="paid")
        c2 = attach(o2, {"affiliate": self.a})
        c.refresh_from_db()
        self.assertEqual((c.percent, c.amount, c2.__class__.objects.get(pk=c2.pk).amount), (Decimal("2.00"), 2 * M, 2 * M))
        o1.status = "completed"
        o1.save()
        C.sync(o1)
        c.refresh_from_db()
        self.assertEqual(c.status, "approved")
        o2.status = "cancelled"
        o2.save()
        C.sync(o2)
        c.refresh_from_db()
        self.assertEqual((Commission.objects.get(pk=c2.pk).status, c.amount), ("cancelled", 1_500_000))

    def test_bracket_mode(self):
        s = AffiliateSettings.load()
        s.tier_mode = "bracket"
        s.save()
        clear_cache()
        attach(order(self.cust, 200 * M, status="paid"), {"affiliate": self.a})
        c = Commission.objects.get()
        self.assertEqual(c.amount, 150 * M * 15 // 1000 + 50 * M * 2 // 100)  # ۲٫۲۵ + ۱ میلیون

    def test_custom_percent(self):
        self.a.custom_percent = Decimal("4")
        self.a.save()
        c = attach(order(self.cust, 50 * M, status="paid"), {"affiliate": self.a})
        c.refresh_from_db()
        self.assertEqual(c.amount, 2 * M)

    def test_resync_after_bulk_update(self):
        o = order(self.cust, 10 * M)
        attach(o, {"affiliate": self.a})
        Order.objects.filter(pk=o.pk).update(status="completed")
        self.assertEqual(C.resync_all(), 1)
        self.assertEqual(Commission.objects.get().status, "approved")

    def test_coupon_attribution_and_self_use(self):
        from .views import activate

        activate(self.a)
        self.a.refresh_from_db()
        self.assertEqual(self.a.coupon.code, "SARA")
        c = attach(order(self.cust, 10 * M, coupon="SARA"))
        self.assertEqual(c.source, "coupon")
        from shop.coupons import check

        self.assertTrue(check("SARA", self.mu, 10 * M)[2])  # همکار نمی‌تواند کد خودش را بزند
        self.assertFalse(check("SARA", self.cust, 10 * M)[2])
        self.a.status = "blocked"
        self.a.save()
        from .views import _coupon_for

        _coupon_for(self.a, AffiliateSettings.load())
        self.assertFalse(Coupon.objects.get(code="SARA").is_active)

    def test_tier_info(self):
        cur, nxt, left = C.tier_info(120 * M)
        self.assertEqual((cur["percent"], nxt["min"], left), (Decimal("1.5"), 150 * M, 30 * M))

    # ----------------------------------------------------------- صفحه‌ها
    def test_signup_and_dashboard(self):
        u = User.objects.create_user("09129998877")
        self.client.force_login(u)
        self.assertContains(self.client.get("/affiliate/"), "ثبت‌نام همکاری")
        r = self.client.post("/affiliate/", {"name": "علی رضایی", "code": "Ali_Home", "terms": "1"})
        self.assertEqual(r.status_code, 302)
        a = Affiliate.objects.get(user=u)
        self.assertEqual((a.code, a.status), ("ali_home", "pending"))
        self.assertContains(self.client.get("/my-account/affiliate/"), "درخواستتان ثبت شد")
        a.status = "active"
        a.save()
        r = self.client.get("/my-account/affiliate/")
        self.assertContains(r, "crpt.ir/ali_home")
        r = self.client.get("/my-account/affiliate/products/?q=گلریز")
        self.assertEqual(r.json()["items"][0]["link"], f"https://crpt.ir/ali_home/{self.p.pk}")
        r = self.client.post("/my-account/affiliate/link/", {"url": "https://irancarpet.net/carpets-price-list/?utm_source=x"})
        link = r.json()["link"]
        self.assertTrue(link.startswith("https://crpt.ir/ali_home/x"))
        r = self.client.get("/" + link.split("crpt.ir/")[1], HTTP_HOST="crpt.ir")
        self.assertIn("/carpets-price-list/?ref=ali_home", r["Location"])
        self.assertEqual(self.client.post("/my-account/affiliate/link/", {"url": "https://evil.com/"}).status_code, 400)

    def test_panel_pages(self):
        admin = User.objects.create_superuser("adm", password="x")
        self.client.force_login(admin)
        attach(order(self.cust, 10 * M, status="paid"), {"affiliate": self.a})
        for key in ("affiliates", "affiliate-commissions", "affiliate-payouts", "commission-tiers"):
            self.assertEqual(self.client.get(f"/panel/{key}/").status_code, 200, key)
        self.assertEqual(self.client.get(f"/panel/affiliates/{self.a.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/panel/settings/?tab=affiliate").status_code, 200)
        Commission.objects.update(status="approved")
        r = self.client.post("/panel/affiliates/", {"action": "payout", "ids": [self.a.pk], "action_value": "123"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Commission.objects.get().status, "approved")  # کمتر از حداقل تسویه
        AffiliateSettings.objects.update(min_payout=0)
        self.client.post("/panel/affiliates/", {"action": "payout", "ids": [self.a.pk], "action_value": "123"})
        self.assertEqual(Commission.objects.get().status, "paid")

    def test_sheba(self):
        self.assertTrue(valid_sheba("IR820540102680020817909002"))
        self.assertFalse(valid_sheba("IR820540102680020817909003"))

    def test_tiers_seeded(self):
        self.assertEqual(list(CommissionTier.objects.values_list("percent", flat=True))[:4],
                         [Decimal("1.5"), Decimal("2"), Decimal("2.5"), Decimal("3")])


class LandingTests(TestCase):
    def test_states_and_home_link(self):
        r = self.client.get("/affiliate/")
        self.assertContains(r, 'name="mobile"')
        self.assertContains(r, "/my-account/login/?next=/my-account/affiliate/")
        self.assertContains(r, "FAQPage")
        self.assertContains(self.client.get("/"), 'href="/affiliate/"')
        u = User.objects.create_user("09120001111")
        Affiliate.objects.create(user=u, code="ali", name="علی", mobile="09120001111", status="active")
        self.client.force_login(u)
        r = self.client.get("/affiliate/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ورود به پنل همکاری")
        self.assertNotContains(r, 'name="terms"')

    def test_disabled_hides(self):
        AffiliateSettings.objects.update_or_create(pk=1, defaults={"enabled": False})
        self.assertEqual(self.client.get("/affiliate/").status_code, 404)
        self.assertNotContains(self.client.get("/"), "همکار فروش ایران کارپت شوید")
