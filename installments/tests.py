"""آزمون خرید اقساطی: محاسبهٔ راس‌گیری، تاریخ چک‌ها، تسویه حساب با مدارک، تأیید از پنل، لیست قیمت."""
import datetime as dt
import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from blog.models import Page
from catalog.models import Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.models import Order, Payment

from .calc import QuoteError, add_jalali_months, quote
from .models import InstallmentPlan
from .orders import valid_national_code

TMP = tempfile.mkdtemp()


def cheque_image():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (400, 200), (230, 235, 245)).save(buf, "JPEG")
    return SimpleUploadedFile("cheque.jpg", buf.getvalue(), content_type="image/jpeg")


class CalcTests(TestCase):
    def setUp(self):
        self.cheque = InstallmentPlan.objects.get(kind="cheque")
        self.beta = InstallmentPlan.objects.get(kind="beta")

    def test_defaults_created(self):
        self.assertEqual((self.cheque.monthly_rate, self.cheque.min_down_percent, self.cheque.max_months), (Decimal("6"), 50, 12))
        self.assertEqual((self.beta.monthly_rate, self.beta.min_down_percent, self.beta.min_months, self.beta.max_months),
                         (Decimal("7"), 0, 2, 24))
        self.assertTrue(Page.objects.filter(template="installment").exists())
        self.assertTrue(Page.objects.filter(template="price_list", slug="carpets-price-list").exists())

    def test_ras_examples(self):
        # یک ماهه: ۶٪ ؛ دو قسط ماهانه: راس ۴۵ روز → ۹٪
        q = quote(self.cheque, 100_000_000, 50, 1, 1, start=dt.date(2026, 10, 5))
        self.assertEqual((q["ras_days"], q["interest_percent"], q["installment"]), (30, 6, 53_000_000))
        q = quote(self.cheque, 100_000_000, 50, 2, 1, start=dt.date(2026, 10, 5))
        self.assertEqual((q["ras_days"], q["interest_percent"], q["count"]), (45, 9, 2))
        self.assertEqual(q["installment"], 27_300_000)  # ۵۴٫۵ میلیون ÷ ۲، گرد به بالا تا ۱۰۰ هزار
        # دوماهه در ۱۲ ماه: ۶ چک در ماه‌های ۲..۱۲ → راس ۲۱۰ روز → ۴۲٪
        q = quote(self.cheque, 100_000_000, 50, 12, 2, start=dt.date(2026, 10, 5))
        self.assertEqual((q["count"], q["ras_days"], q["interest_percent"]), (6, 210, 42))
        # بازنشستگان: بدون پیش‌پرداخت، ۲ ماه، ۷٪ → راس ۴۵ روز = ۱۰٫۵٪
        q = quote(self.beta, 10_000_000, 0, 2, 1, start=dt.date(2026, 10, 5))
        self.assertEqual((q["down"], q["interest_percent"], q["installment"]), (0, 10.5, 5_600_000))

    def test_dates_start_14_days_after_order(self):
        q = quote(self.cheque, 100_000_000, 50, 2, 1, start=dt.date(2026, 10, 5))  # ۱۳ مهر ۱۴۰۵
        self.assertEqual([r["jdate"] for r in q["schedule"]], ["1405/08/27", "1405/09/27"])

    def test_jalali_month_end(self):
        import jdatetime

        self.assertEqual(add_jalali_months(jdatetime.date(1405, 6, 31), 1), jdatetime.date(1405, 7, 30))
        self.assertEqual(add_jalali_months(jdatetime.date(1405, 11, 30), 1).month, 12)

    def test_limits(self):
        with self.assertRaises(QuoteError):
            quote(self.cheque, 100_000_000, 40, 6, 1)  # پیش‌پرداخت کمتر از ۵۰٪
        with self.assertRaises(QuoteError):
            quote(self.cheque, 100_000_000, 50, 13, 1)
        with self.assertRaises(QuoteError):
            quote(self.cheque, 100_000_000, 50, 3, 2)  # دوماهه باید زوج باشد
        with self.assertRaises(QuoteError):
            quote(self.beta, 100_000_000, 0, 1, 1)  # بازنشستگان از ۲ ماه
        with self.assertRaises(QuoteError):
            quote(self.beta, 100_000_000, 0, 4, 2)  # دوماهه برای بازنشستگان فعال نیست

    def test_national_code(self):
        self.assertTrue(valid_national_code("0012345679"))
        self.assertTrue(valid_national_code("۰۰۱۲۳۴۵۶۷۹"))
        self.assertFalse(valid_national_code("0012345678"))
        self.assertFalse(valid_national_code("1111111111"))

    def test_quote_api_and_page(self):
        r = self.client.get("/installments/quote/", {"plan": self.cheque.pk, "total": "100000000", "down": 50, "months": 2, "step": 1})
        self.assertEqual(r.json()["interest_percent"], 9.0)
        self.assertEqual(self.client.get("/installments/quote/", {"plan": self.cheque.pk, "total": "1000", "months": 99}).status_code, 400)
        page = Page.objects.get(template="installment")
        r = self.client.get(page.get_absolute_url())
        self.assertContains(r, "اقساط با چک صیادی")
        self.assertContains(r, "FAQPage")


@override_settings(PAYMENT_FAKE=True, SMSIR_API_KEY="", STAGING=True, PRIVATE_ROOT=TMP, SITE_URL="https://irancarpet.net")
class CheckoutTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="700 شانه ورجین مهرآوران", base_size=s["12-meter"], base_price=Decimal("35000000"))
        self.album.sizes.set([s["12-meter"], s["6-meter"]])
        self.p = Product.objects.create(title="فرش 700 شانه نقشه سناتور", slug="senator", album=self.album, status="publish")
        sync_album_variations([self.p], reset=True)
        self.v12 = self.p.variations.get(size=s["12-meter"])
        self.user = get_user_model().objects.create_user("09121234567", first_name="علی", last_name="رضایی")
        self.client.force_login(self.user)
        self.client.post("/cart/add/", {"variation": self.v12.pk, "qty": 1})
        self.cheque = InstallmentPlan.objects.get(kind="cheque")
        self.beta = InstallmentPlan.objects.get(kind="beta")

    def data(self, **kw):
        d = {"first_name": "علی", "last_name": "رضایی", "mobile": "09121234567", "province": "تهران", "city": "تهران",
             "address": "خیابان آزادی", "payment_mode": "installment", "gateway": "fake"}
        d.update(kw)
        return d

    def test_cheque_requires_documents_then_pays_down(self):
        self.assertContains(self.client.get("/checkout/"), "خرید اقساطی")
        r = self.client.post("/checkout/", self.data(inst_plan=self.cheque.pk, inst_down=50, inst_months=6, inst_step=1,
                                                      inst_holder_name="علی رضایی", inst_national_code="0012345678"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "کد ملی درست نیست")
        self.assertContains(r, "تصویر یک برگ چک را بارگذاری کنید")
        self.assertFalse(Order.objects.exists())
        r = self.client.post("/checkout/", self.data(inst_plan=self.cheque.pk, inst_down=50, inst_months=6, inst_step=1,
                                                      inst_holder_name="علی رضایی", inst_national_code="0012345679",
                                                      inst_cheque_image=cheque_image()))
        self.assertEqual(r.status_code, 302)
        o = Order.objects.get()
        total = self.v12.price
        self.assertEqual((o.payment_mode, o.status, o.installment_state), ("installment", "pending", "review"))
        self.assertEqual(o.online_amount, o.installment["down"])
        self.assertEqual(o.installment["count"], 6)
        self.assertEqual(o.installment["interest_percent"], 21.0)
        self.assertGreater(o.grand_total, total)
        self.assertTrue(o.installment_info["cheque_image"].endswith("cheque_image.jpg"))
        # پرداخت پیش‌پرداخت
        pay = Payment.objects.get(order=o)
        self.client.get(f"/pay/fake/callback/?pid={pay.pk}&ok=1")
        o.refresh_from_db()
        self.assertEqual(o.status, "deposit_paid")
        self.assertEqual(o.remaining, o.grand_total - o.installment["down"])
        page = self.client.get(o.get_absolute_url()).content.decode()
        self.assertIn("تا تأیید ما چک ننویسید", page)
        # تصویر چک فقط برای کارمندان
        self.assertEqual(self.client.get(f"/panel/installment-file/{o.pk}/cheque_image/").status_code, 404)
        staff = get_user_model().objects.create_user("staff", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        r = self.client.get(f"/panel/installment-file/{o.pk}/cheque_image/")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/jpeg"))
        self.assertContains(self.client.get(f"/panel/orders/{o.pk}/view/"), "تأیید درخواست")
        self.client.post(f"/panel/orders/{o.pk}/installment/", {"state": "approved"})
        o.refresh_from_db()
        self.assertEqual(o.installment_state, "approved")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(o.get_absolute_url()), "درخواست اقساط شما تأیید شد")

    def test_beta_without_down_payment_needs_no_gateway(self):
        r = self.client.post("/checkout/", self.data(gateway="", inst_plan=self.beta.pk, inst_down=0, inst_months=12, inst_step=1,
                                                      inst_holder_name="علی رضایی", inst_national_code="0012345679",
                                                      inst_pensioner_type="بازنشسته", inst_sms_mobile="09351234567"))
        o = Order.objects.get()
        self.assertRedirects(r, o.get_absolute_url() + "?placed=1", fetch_redirect_response=False)
        self.assertEqual((o.status, o.online_amount, o.installment_state), ("on_hold", 0, "review"))
        self.assertEqual(o.installment_info["sms_mobile"], "09351234567")
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(self.client.session.get("cart"))
        self.assertContains(self.client.get(o.get_absolute_url() + "?placed=1"), "درخواست خرید اقساطی ثبت شد")
        staff = get_user_model().objects.create_user("staff", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        self.client.post(f"/panel/orders/{o.pk}/installment/", {"state": "approved"})
        o.refresh_from_db()
        self.assertEqual(o.status, "processing")

    def test_approval_timing_opens_payment_after_approval(self):
        self.cheque.down_timing = "approval"
        self.cheque.save()
        self.client.post("/checkout/", self.data(gateway="", inst_plan=self.cheque.pk, inst_down=60, inst_months=4, inst_step=2,
                                                 inst_holder_name="علی رضایی", inst_national_code="0012345679",
                                                 inst_cheque_image=cheque_image()))
        o = Order.objects.get()
        self.assertEqual((o.status, o.installment["count"]), ("on_hold", 2))
        self.assertFalse(o.can_pay)
        staff = get_user_model().objects.create_user("staff", is_staff=True, is_superuser=True)
        self.client.force_login(staff)
        self.client.post(f"/panel/orders/{o.pk}/installment/", {"state": "approved"})
        o.refresh_from_db()
        self.assertTrue(o.can_pay)

    def test_price_list_pages(self):
        r = self.client.get("/carpets-price-list/")
        self.assertContains(r, "فرش 700 شانه ورجین مهرآوران")
        self.assertContains(r, "FAQPage")
        self.assertNotContains(r, "[icap_price_list]")
        price = self.album.size_price(self.album.base_size)
        self.assertContains(r, f"{price:,}".replace(",", "٬").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
        self.album.refresh_from_db()
        r = self.client.get(self.album.get_absolute_url())
        self.assertContains(r, "فرش‌های این لیست")
        self.assertContains(r, "نقشه سناتور")
        self.assertIn("price_list-sitemap.xml", self.client.get("/sitemap_index.xml").content.decode())
        self.album.in_price_list = False
        self.album.save()
        self.client.logout()
        self.assertEqual(self.client.get(self.album.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get("/carpets-price-list/"), "ورجین مهرآوران")
