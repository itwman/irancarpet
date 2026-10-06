import io
import json
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from catalog.models import Category, Product, ProductTag, Variation
from core.models import Media
from pricing.models import Album, PriceLog, PricingSettings, Size, seed_sizes
from shop import config, gateways
from shop.models import Order, ShopSettings

from .models import ActivityLog


class PanelTests(TestCase):
    def setUp(self):
        seed_sizes()
        PricingSettings.load()
        U = get_user_model()
        self.boss = U.objects.create_user("boss", password="x" * 10, is_staff=True, is_superuser=True)
        self.staff = U.objects.create_user("staff", password="x" * 10, is_staff=True)
        self.cust = U.objects.create_user("cust", password="x" * 10)
        self.s12 = Size.objects.get(slug="12-meter")
        self.album = Album.objects.create(name="آلبوم آزمایشی", code="T1", base_size=self.s12, base_price=Decimal("24000000"),
                                          profit_percent=Decimal("15"), shipping_fixed=500_000, round_to=100_000,
                                          waste_type="fixed", waste_value=Decimal("2000000"))
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه آزمایش", slug="test-p", album=self.album)
        Variation.objects.create(product=self.p, size=self.s12)
        self.p.refresh_price_cache()

    def test_access(self):
        r = self.client.get("/panel/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/my-account/login/", r["Location"])
        self.client.force_login(self.cust)
        self.assertEqual(self.client.get("/panel/").status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/panel/").status_code, 200)
        self.assertEqual(self.client.get("/panel/system/").status_code, 302)  # پنل فنی فقط مدیر کل
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get("/panel/system/").status_code, 200)

    def test_product_edit_with_sizes_and_gallery(self):
        self.client.force_login(self.staff)
        r = self.client.get(f"/panel/products/{self.p.pk}/edit/")
        self.assertContains(r, "۲۸٬۱۰۰٬۰۰۰")  # قیمت نهایی ۱۲ متری طبق فرمول آلبوم
        m = Media.objects.create(file="2024/01/a.jpg", title="a")
        v = self.p.variations.get()
        s6 = Size.objects.get(slug="6-meter")
        data = {
            "title": "فرش تازه", "slug": "", "english_name": "", "short_description": "", "content": "<p>متن</p>",
            "status": "publish", "published_at": "۱۴۰۵/۰۷/۱۲ ۱۰:۳۰", "menu_order": "0", "album": self.album.pk,
            "custom_base_price": "", "sale_status": "available", "primary_category": "", "brand": "", "image": "", "sku": "",
            "seo_title": "", "seo_description": "", "focus_keyword": "", "robots": "", "canonical_url": "",
            "v-TOTAL_FORMS": "2", "v-INITIAL_FORMS": "1", "v-MIN_NUM_FORMS": "0", "v-MAX_NUM_FORMS": "1000",
            "v-0-id": v.pk, "v-0-product": self.p.pk, "v-0-size": self.s12.pk, "v-0-is_available": "on", "v-0-sale_price": "26,000,000",
            "v-0-menu_order": "0", "v-0-override_price": "", "v-0-manual_price": "",
            "v-1-size": s6.pk, "v-1-is_available": "on", "v-1-menu_order": "۱", "v-1-override_price": "", "v-1-manual_price": "", "v-1-sale_price": "",
            "f-TOTAL_FORMS": "0", "f-INITIAL_FORMS": "0", "f-MIN_NUM_FORMS": "0", "f-MAX_NUM_FORMS": "1000",
            "gallery": str(m.pk),
        }
        r = self.client.post(f"/panel/products/{self.p.pk}/edit/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:3000])
        self.p.refresh_from_db()
        self.assertEqual(self.p.title, "فرش تازه")
        self.assertEqual(self.p.variations.count(), 2)
        self.assertEqual(self.p.variations.get(size=self.s12).sale_price, 26_000_000)
        self.assertEqual(self.p.variations.get(size=s6).final_price, 14_100_000)
        self.assertEqual(self.p.min_price, 26_000_000)   # محصول آلبومی: قیمت سایز پایه
        self.assertEqual(self.p.image_id, m.pk)
        from django.utils import timezone
        self.assertEqual(timezone.localtime(self.p.published_at).hour, 10)
        self.assertTrue(ActivityLog.objects.filter(section="محصولات").exists())

    def test_album_percent_bulk_and_log(self):
        self.client.force_login(self.staff)
        self.client.post("/panel/albums/", {"action": "percent", "action_value": "۱۰", "ids": [self.album.pk]})
        self.album.refresh_from_db()
        self.assertEqual(self.album.base_price, Decimal("26400000"))
        self.assertTrue(PriceLog.objects.filter(album=self.album, reason__startswith="bulk_percent").exists())
        self.p.refresh_from_db()
        self.assertGreater(self.p.min_price, 28_100_000)

    def test_generic_create_with_auto_slug_and_autocomplete(self):
        self.client.force_login(self.staff)
        r = self.client.post("/panel/categories/add/", {"name": "فرش کودک", "slug": "", "description": "", "order": "0",
                                                        "seo_title": "", "seo_description": "", "focus_keyword": "", "robots": "", "canonical_url": ""})
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        c = Category.objects.get(name="فرش کودک")
        self.assertEqual(c.slug, "فرش-کودک")
        j = self.client.get("/panel/ac/category/?q=کودک").json()
        self.assertEqual(j["results"][0]["value"], str(c.pk))
        r = self.client.post("/panel/ac/product_tag/", data=json.dumps({"text": "برچسب تازه"}), content_type="application/json")
        self.assertTrue(ProductTag.objects.filter(name="برچسب تازه").exists())
        self.assertEqual(self.client.post("/panel/ac/product/", data="{}", content_type="application/json").status_code, 403)

    def test_settings_gateways_and_secret_kept(self):
        self.client.force_login(self.staff)
        self.client.post("/panel/settings/", {"tab": "gateways", "sep_enabled": "on", "sep_terminal_id": "۱۲۳۴۵۶۷۸",
                                              "zarinpal_enabled": "on", "zarinpal_merchant_id": "abc-merchant"})
        self.assertTrue(gateways.Sep.available())
        self.assertEqual(config.get("ZARINPAL_MERCHANT_ID"), "abc-merchant")
        # ذخیرهٔ دوباره با مرچنت خالی، مقدار قبلی را پاک نمی‌کند
        self.client.post("/panel/settings/", {"tab": "gateways", "sep_enabled": "on", "sep_terminal_id": "12345678",
                                              "zarinpal_enabled": "on", "zarinpal_merchant_id": ""})
        self.assertEqual(ShopSettings.load().zarinpal_merchant_id, "abc-merchant")
        self.client.post("/panel/settings/", {"tab": "sms", "smsir_api_key": "KEY", "smsir_otp_template_id": "100200",
                                              "smsir_order_template_id": "", "smsir_admin_template_id": ""})
        from accounts import sms
        self.assertTrue(sms.configured())

    def test_settings_trust_points(self):
        self.client.force_login(self.staff)
        r = self.client.post("/panel/settings/", {"tab": "site", "site_name": "ایران کارپت", "tagline": "", "title_separator": "-",
                                                  "home_title": "", "home_description": "", "phone": "", "whatsapp": "", "email": "",
                                                  "address": "", "footer_html": "", "tp_title": ["ارسال رایگان", ""], "tp_sub": ["بالای ۵۰ میلیون", ""]})
        self.assertEqual(r.status_code, 302)
        from core.models import SiteSettings
        self.assertEqual(SiteSettings.load().trust_points, [["ارسال رایگان", "بالای ۵۰ میلیون"]])

    def test_manual_payment(self):
        o = Order.objects.create(first_name="a", last_name="b", mobile="09120000000", province="تهران", city="تهران", address="x",
                                 items_total=10_000_000, payment_mode="deposit", status="deposit_paid", paid_amount=1_000_000)
        self.client.force_login(self.staff)
        self.client.post(f"/panel/orders/{o.pk}/view/", {"form": "pay", "amount": "9,000,000", "method": "cod", "note": ""})
        o.refresh_from_db()
        self.assertEqual(o.paid_amount, 10_000_000)
        self.assertEqual(o.remaining, 0)
        self.assertEqual(o.payments.get().gateway, "manual")

    def test_staff_flag_only_by_superuser(self):
        self.client.force_login(self.staff)
        self.client.post(f"/panel/customers/{self.cust.pk}/edit/", {"first_name": "مشتری", "is_active": "on", "is_staff": "on"})
        self.cust.refresh_from_db()
        self.assertEqual(self.cust.first_name, "مشتری")
        self.assertFalse(self.cust.is_staff)
        self.client.force_login(self.boss)
        self.client.post(f"/panel/customers/{self.cust.pk}/edit/", {"first_name": "مشتری", "is_active": "on", "is_staff": "on", "mobile": "09121112233"})
        self.cust.refresh_from_db()
        self.assertTrue(self.cust.is_staff)
        self.assertEqual(self.cust.profile.mobile, "09121112233")

    def test_list_filters_search_and_csv(self):
        self.client.force_login(self.staff)
        r = self.client.get("/panel/products/?q=آزمایش&d_from=۱۴۰۰/۰۱/۰۱&status=publish")
        self.assertContains(r, "آزمایش")
        r = self.client.get("/panel/products/?export=csv")
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")

    def test_media_upload(self):
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), "red").save(buf, "JPEG")
        with tempfile.TemporaryDirectory() as d, override_settings(MEDIA_ROOT=d):
            self.client.force_login(self.staff)
            r = self.client.post("/panel/media/upload/", {"file": SimpleUploadedFile("قالی.jpg", buf.getvalue(), "image/jpeg")})
            j = r.json()
            self.assertEqual(len(j["files"]), 1)
            m = Media.objects.get(pk=j["files"][0]["value"])
            self.assertEqual((m.width, m.height), (40, 30))
            r = self.client.post("/panel/media/upload/", {"file": SimpleUploadedFile("bad.exe", b"x")})
            self.assertEqual(r.status_code, 400)


class MultiFilterTests(TestCase):
    def test_specs_or_within_and_across(self):
        from django.contrib.auth import get_user_model

        from catalog.models import Attribute, AttributeTerm, Product, ProductTag

        color = Attribute.objects.create(slug="color", label="رنگ زمینه")
        reeds = Attribute.objects.create(slug="reeds", label="شانه")
        laki = AttributeTerm.objects.create(attribute=color, name="لاکی", slug="laki")
        red = AttributeTerm.objects.create(attribute=color, name="قرمز", slug="red")
        cream = AttributeTerm.objects.create(attribute=color, name="کرم", slug="cream")
        r15 = AttributeTerm.objects.create(attribute=reeds, name="1500", slug="1500")
        tag = ProductTag.objects.create(name="فرش ۱۲ متری", slug="t12")
        ps = {}
        for slug, terms in (("a", [laki, r15]), ("b", [red]), ("c", [cream, r15])):
            ps[slug] = Product.objects.create(title=slug, slug=slug)
            ps[slug].specs.set(terms)
        ps["a"].tags.set([tag])
        u = get_user_model().objects.create_user("s", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)

        def titles(qs):
            r = self.client.get("/panel/products/" + qs)
            return sorted(row["obj"].title for row in r.context["rows"])

        self.assertEqual(titles(f"?specs={laki.pk}&specs={red.pk}"), ["a", "b"])        # یا
        self.assertEqual(titles(f"?specs={laki.pk}&specs={red.pk}&specs={r15.pk}"), ["a"])  # و
        self.assertEqual(titles(f"?tags={tag.pk}"), ["a"])
        r = self.client.get(f"/panel/products/?cols_set=1&cols=tags&cols=attr_{color.pk}&specs={laki.pk}")
        self.assertContains(r, f'data-chip-filter="specs" data-chip-value="{laki.pk}"')
        self.assertContains(r, f'data-chip-filter="tags" data-chip-value="{tag.pk}"')
