"""آزمون ابزارهای رشد فروش: کد تخفیف، معرفی دوستان، یادآوری پرداخت، خبرم کن، نظر با عکس، صفحه‌های فرود، ایمالز."""
import io
import json
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import Attribute, AttributeTerm, Product, Review
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import Coupon, Order, ShopSettings

from . import jobs
from .models import ProductAlert, SearchLog

MEDIA = tempfile.mkdtemp()


def local(url):
    """نشانی پیامک (کوتاه یا کامل) ← مسیر سایت."""
    url = url.strip()
    if "crpt.ir/" in url or "/s/" in url:
        from crm.links import resolve

        return resolve(url.rstrip("/").split("/")[-1])
    return url.replace("https://irancarpet.net", "")


def jpeg():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 150), (200, 190, 170)).save(buf, "JPEG")
    return SimpleUploadedFile("rug.jpg", buf.getvalue(), content_type="image/jpeg")


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", SMSIR_OTP_TEMPLATE_ID="", STAGING=True, MEDIA_ROOT=MEDIA)
class GrowthTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        self.r1200 = AttributeTerm.objects.create(attribute=self.reeds, name="1200", slug="1200")
        album = Album.objects.create(name="آلبوم", code="A", base_size=s["12-meter"], base_price=Decimal("40000000"),
                                     shipping_fixed=0, waste_value=0)
        album.sizes.set([s["12-meter"], s["6-meter"]])
        self.products = []
        for i in range(5):
            p = Product.objects.create(title=f"فرش 1200 شانه طرح {i}", slug=f"p{i}", album=album, status="publish")
            p.specs.add(self.r1200)
            self.products.append(p)
        sync_album_variations(self.products, reset=True)
        self.p = self.products[0]
        self.v12 = self.p.variations.get(size=s["12-meter"])

    def login(self, mobile="09121234567", name="علی رضایی"):
        self.client.post("/my-account/login/", {"action": "otp", "mobile": mobile, "next": "/"})
        self.client.post("/my-account/verify/", {"code": self.client.session["dev_otp"], "name": name, "next": "/"})

    def checkout(self, **kw):
        d = {"first_name": "علی", "last_name": "رضایی", "mobile": "09121234567", "province": "تهران", "city": "تهران",
             "address": "خیابان آزادی", "postal_code": "", "payment_mode": "full", "gateway": "fake"}
        d.update(kw)
        return self.client.post("/checkout/", d)

    # ---------------------------------------------------------- کد تخفیف
    def test_coupon_in_cart_and_checkout(self):
        Coupon.objects.create(code="welcome", kind="percent", value=10, max_discount=3_000_000, first_order_only=True)
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        price = self.v12.price
        r = self.client.post("/cart/update/", {"go": "coupon", "coupon": "WELCOME"}, follow=True)
        self.assertContains(r, "اعمال شد")
        self.login()
        self.checkout()
        o = Order.objects.get()
        self.assertEqual((o.coupon_code, o.discount), ("WELCOME", 3_000_000))
        self.assertEqual(o.items_total, price - 3_000_000)
        self.assertEqual(o.online_amount, price - 3_000_000)
        pay = o.payments.get()
        self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")
        # فقط اولین خرید
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        r = self.client.post("/cart/update/", {"go": "coupon", "coupon": "welcome"}, follow=True)
        self.assertContains(r, "شما قبلاً از این کد استفاده کرده‌اید")

    def test_coupon_api_and_app_only(self):
        Coupon.objects.create(code="APP5", kind="fixed", value=2_000_000, app_only=True)
        items = [{"variation": self.v12.pk, "qty": 1}]
        d = self.client.post("/api/app/v1/cart/quote/", json.dumps({"items": items, "coupon": "app5"}),
                             content_type="application/json").json()
        self.assertEqual(d["discount"], 2_000_000)
        self.assertEqual(d["total"], d["subtotal"] - 2_000_000)
        # روی سایت قبول نمی‌شود
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        r = self.client.post("/cart/update/", {"go": "coupon", "coupon": "APP5"}, follow=True)
        self.assertContains(r, "فقط برای خرید از اپ")

    def test_referral_reward(self):
        ShopSettings.objects.update_or_create(pk=1, defaults={"referral_enabled": True, "referral_percent": 5,
                                                               "referral_max": 5_000_000, "referral_min_order": 0,
                                                               "referral_reward": 1_000_000})
        self.login("09120000001", "معرف")
        page = self.client.get("/my-account/")
        code = Coupon.objects.get(owner__username="09120000001").code
        self.assertContains(page, code)
        self.client.post("/my-account/logout/")
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        self.client.post("/cart/update/", {"go": "coupon", "coupon": code})
        self.login("09120000002", "دوست")
        self.checkout(mobile="09120000002")
        o = Order.objects.get()
        self.assertEqual(o.coupon_code, code)
        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as sms:
            self.client.get(f"/pay/fake/callback/?pid={o.payments.get().pk}&ok=1")
        gift = Coupon.objects.get(code=f"GIFT{o.number}")
        self.assertEqual((gift.value, gift.for_user.username), (1_000_000, "09120000001"))
        self.assertTrue(sms.called)

    # ---------------------------------------------------------- یادآوری پرداخت
    def test_unpaid_reminder_and_quickpay(self):
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        self.login()
        self.checkout()
        o = Order.objects.get()
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timezone.timedelta(hours=2))
        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as sms:
            self.assertEqual(jobs.remind_unpaid(), 1)
            self.assertEqual(jobs.remind_unpaid(), 0)  # دومی یک روز بعد
        text = sms.call_args[0][1]
        url = local(text.split("پرداخت: ")[1])
        self.client.post("/my-account/logout/")
        r = self.client.get(url)
        self.assertContains(r, "پرداخت سفارش")
        r = self.client.post(url, {"gateway": "fake"})
        pay = o.payments.order_by("-pk").first()
        self.assertRedirects(r, f"/pay/fake/{pay.pk}/", fetch_redirect_response=False)
        r = self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        self.assertTrue(r["Location"].startswith("/o/") and r["Location"].endswith("?paid=1"))
        self.assertContains(self.client.get(r["Location"]), "پرداخت انجام شد")
        self.assertEqual(self.client.get("/o/bad-token/").status_code, 404)

    # ---------------------------------------------------------- خبرم کن
    def test_alerts(self):
        r = self.client.post("/alerts/", {"product": self.p.pk, "kind": "price", "mobile": "۰۹۱۲۳۳۳۴۴۵۵"}, follow=True)
        self.assertContains(r, "اگر قیمت این فرش کم شد")
        a = ProductAlert.objects.get()
        self.assertEqual(a.mobile, "09123334455")
        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as sms:
            self.assertEqual(jobs.run_alerts(), 0)
            Product.objects.filter(pk=self.p.pk).update(min_price=a.price_at - 2_000_000)
            self.assertEqual(jobs.run_alerts(), 1)
        self.assertIn("کم شد", sms.call_args[0][1])
        d = self.client.post("/api/app/v1/alerts/", json.dumps({"product": self.p.pk, "kind": "stock", "mobile": "09123334455"}),
                             content_type="application/json")
        self.assertEqual(d.status_code, 200)

    # ---------------------------------------------------------- نظر با عکس
    def test_review_invite_and_product_review(self):
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        self.login()
        self.checkout()
        o = Order.objects.get()
        Order.objects.filter(pk=o.pk).update(status="completed", created_at=timezone.now() - timezone.timedelta(days=8))
        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as sms:
            self.assertEqual(jobs.invite_reviews(), 1)
        url = local(sms.call_args[0][1].split(": ")[-1])
        self.client.post("/my-account/logout/")
        r = self.client.post(url, {f"rating_{self.p.pk}": "5", f"text_{self.p.pk}": "عالی بود", f"photos_{self.p.pk}": [jpeg()]})
        self.assertRedirects(r, url + "?done=1", fetch_redirect_response=False)
        rv = Review.objects.get()
        self.assertTrue(rv.verified and not rv.is_approved)
        self.assertEqual(rv.photos.count(), 1)
        from catalog.reviews import recompute

        Review.objects.filter(pk=rv.pk).update(is_approved=True)
        recompute(self.p)
        self.p.refresh_from_db()
        self.assertEqual((self.p.rating_count, float(self.p.rating_avg)), (1, 5.0))
        page = self.client.get(self.p.get_absolute_url())
        self.assertContains(page, "فرش در خانهٔ مشتری‌ها")
        self.assertContains(page, "خریدار این فرش")
        # از صفحهٔ فرش: باید وارد شده باشد
        r = self.client.post(f"/product/{self.p.slug}/review/", {"rating": "4", "text": "خوب"})
        self.assertTrue(r["Location"].startswith("/my-account/login/"))

    def test_app_review_with_photos(self):
        r = self.client.post("/api/app/v1/auth/otp/", json.dumps({"mobile": "09125550000"}), content_type="application/json")
        code = r.json()["dev_code"]
        r = self.client.post("/api/app/v1/auth/verify/", json.dumps({"mobile": "09125550000", "code": code, "name": "سارا"}),
                             content_type="application/json")
        h = {"HTTP_AUTHORIZATION": f"Token {r.json()['token']}"}
        r = self.client.post(f"/api/app/v1/products/{self.p.pk}/reviews/",
                             {"rating": "5", "text": "عالی", "photo_0": jpeg(), "photo_1": jpeg()}, **h)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Review.objects.get().photos.count(), 2)

    # ---------------------------------------------------------- صفحه‌های فرود
    def test_landing_pages(self):
        from landing.build import sync
        from landing.models import LandingPage

        sync(log=lambda *_: None)
        lp = LandingPage.objects.get(reeds=self.r1200, size__slug="12-meter")
        self.assertEqual(lp.count, 5)
        self.assertTrue(lp.slug.startswith("فرش-1200-شانه-12-متری"))
        r = self.client.get(lp.get_absolute_url())
        self.assertContains(r, "پرسش‌های پرتکرار")
        self.assertContains(r, "FAQPage")
        self.assertContains(self.client.get("/landing-sitemap1.xml"), "/carpets/")
        size_page = LandingPage.objects.get(reeds=None, color=None, size__slug="6-meter")
        self.assertContains(self.client.get(size_page.get_absolute_url()), "طرح")
        self.assertContains(self.client.get("/reeds-per-meter/1200/"), lp.title) if self.reeds.is_public else None

    # ---------------------------------------------------------- ابزارها
    def test_size_tool_finder_web_and_search_log(self):
        from blog.models import Page

        page = Page.objects.get(template="size_tool")
        self.assertContains(self.client.get(page.get_absolute_url()), "stSizes")
        self.assertEqual(self.client.get("/farsh-yab/").status_code, 200)
        r = self.client.get("/farsh-yab/", {"q": "فرش 12 متری زیر 90 میلیون"})
        self.assertContains(r, "فرش پیدا شد")
        self.client.get("/search/", {"q": "ناموجودترین"})
        self.assertTrue(SearchLog.objects.filter(query="ناموجودترین", source="web", results=0).exists())

    def test_emalls(self):
        from torob import emalls

        with mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertEqual(self.client.post("/wp-json/emalls_ext/v1/products", {"token": "x"}).status_code, 401)
        with mock.patch.object(emalls, "verify", return_value=True):
            d = self.client.post("/wp-json/emalls_ext/v1/products", {"token": "x", "page": 1, "limit": 2}).json()
        self.assertEqual(d["count"], 5)
        self.assertEqual(len(d["products"]), 2)
        self.assertTrue(d["products"][0]["page_url"].startswith("https://irancarpet.net/product/"))

    def test_store_schema(self):
        from core.models import SiteSettings

        s = SiteSettings.load()
        s.address, s.store_open, s.store_close = "کاشان، خیابان امیرکبیر", "09:00", "20:00"
        s.save()
        cache.clear()
        r = self.client.get("/")
        self.assertContains(r, "HomeGoodsStore")
        self.assertContains(r, "فروشگاه حضوری")
