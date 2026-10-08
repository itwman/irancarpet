import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image

from catalog.models import Category, Product
from pricing.models import Size, seed_sizes
from shop.models import Order

from . import orders as O
from . import products as P
from .models import CategoryCommission, MarketSettings, Seller, SellerOrder

User = get_user_model()
M = 1_000_000


def png(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (60, 40), (200, 30, 60)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class MarketTests(TestCase):
    def setUp(self):
        seed_sizes()
        self.size = Size.objects.get(slug="12-meter")
        self.cat = Category.objects.create(name="فرش ۱۲۰۰ شانه", slug="c1200")
        self.su = User.objects.create_user("09350001111")
        self.s = Seller.objects.create(user=self.su, name="فرش کویر", slug="kavir", owner_name="علی", mobile="09350001111",
                                       city="کاشان", status="active")
        self.cust = User.objects.create_user("09121112233", first_name="مریم")
        self.admin = User.objects.create_superuser("adm", password="x")

    def post_product(self, **extra):
        self.client.force_login(self.su)
        data = {"title": "فرش ۱۲۰۰ شانه افشان کرم", "category": self.cat.pk, "short": "خلاصه", "description": "متن\nخط دوم",
                "v_id": [""], "v_size": [self.size.pk], "v_label": [""], "v_price": ["۲۵٬۰۰۰٬۰۰۰"], "v_sale": [""], "v_qty": ["2"],
                "v_pair": ["0"], "v_delete": ["0"], "images": png(), **extra}
        return self.client.post("/seller/products/add/", data)

    def make_product(self):
        self.post_product()
        p = Product.objects.get(seller=self.s)
        P.approve(p, notify=False)
        p.refresh_from_db()
        return p

    def order_for(self, p, qty=1, status="pending"):
        """سفارش شبیه به create_order برای کالای فروشنده"""
        from shop.models import OrderItem

        v = p.variations.get()
        o = Order.objects.create(user=self.cust, first_name="م", last_name="ک", mobile="09121112233", province="تهران", city="تهران",
                                 address="x", items_total=v.price * qty, status=status)
        OrderItem.objects.create(order=o, product=p, variation=v, title=p.title, size_label="۱۲ متری", unit_price=v.price, quantity=qty)
        O.split(o)
        return o

    def test_signup(self):
        u = User.objects.create_user("09129990000")
        self.client.force_login(u)
        self.assertContains(self.client.get("/sell/"), "فرم فروشندگی")
        r = self.client.post("/sell/", {"name": "گلیم آرا", "slug": "gelim-ara", "kind": "person", "owner_name": "سارا رضایی",
                                        "national_id": "0067749828", "city": "یزد", "terms": "1"})
        self.assertEqual(r.status_code, 302)
        s = Seller.objects.get(user=u)
        self.assertEqual((s.status, s.slug), ("pending", "gelim-ara"))
        self.assertContains(self.client.get("/seller/"), "درخواستتان ثبت شد")
        self.assertRedirects(self.client.get("/seller/products/"), "/seller/", fetch_redirect_response=False)
        r = self.client.post("/sell/", {"name": "x", "national_id": "123", "city": ""})
        self.assertEqual(r.status_code, 302)  # فروشندهٔ موجود به پنل می‌رود

    def test_bad_signup(self):
        u = User.objects.create_user("09129990001")
        self.client.force_login(u)
        r = self.client.post("/sell/", {"name": "فرش کویر", "owner_name": "ab", "national_id": "1111111111", "city": "", "kind": "person"})
        self.assertEqual(r.status_code, 200)
        for e in ("این نام قبلاً ثبت شده است.", "کد ملی ۱۰ رقمی درست نیست.", "قوانین فروشندگان"):
            self.assertContains(r, e)

    def test_product_flow(self):
        r = self.post_product()
        self.assertEqual(r.status_code, 302)
        p = Product.objects.get(seller=self.s)
        self.assertEqual((p.status, p.review_status), ("draft", "pending"))
        self.assertTrue(p.image_id)
        v = p.variations.get()
        self.assertEqual((v.price, v.stock_qty, p.min_price), (25 * M, 2, 25 * M))
        self.assertEqual(self.client.get(p.get_absolute_url()).status_code, 404)
        P.approve(p, notify=False)
        r = self.client.get(p.get_absolute_url())
        self.assertContains(r, "فروشنده:")
        self.assertContains(r, "فرش کویر")
        self.assertNotContains(r, 'id="instTeaser"')
        self.assertContains(r, "ارسال از کاشان، پرداخت امن")
        # قیمت و موجودی بدون بررسی
        self.client.post("/seller/products/", {f"q_price_{v.pk}": "26000000", f"q_qty_{v.pk}": "0"})
        p.refresh_from_db()
        v.refresh_from_db()
        self.assertEqual((v.price, v.is_available, p.status), (26 * M, False, "publish"))
        # ویرایش متن ← دوباره بررسی
        data = {"title": "فرش ۱۲۰۰ شانه افشان کرم، اصلاح‌شده", "category": self.cat.pk, "description": "متن", "v_id": [v.pk],
                "v_size": [self.size.pk], "v_label": [""], "v_price": ["26000000"], "v_sale": [""], "v_qty": ["3"], "v_pair": ["0"], "v_delete": ["0"]}
        self.client.post(f"/seller/products/{p.pk}/", data)
        p.refresh_from_db()
        self.assertEqual((p.status, p.review_status), ("draft", "pending"))
        # فروشندهٔ مورد اعتماد: بی‌بررسی
        Seller.objects.filter(pk=self.s.pk).update(trusted=True)
        data["title"] = "فرش ۱۲۰۰ شانه افشان زمینه کرم"
        self.client.post(f"/seller/products/{p.pk}/", data)
        p.refresh_from_db()
        self.assertEqual((p.status, p.review_status), ("publish", "approved"))

    def test_product_errors(self):
        self.client.force_login(self.su)
        r = self.client.post("/seller/products/add/", {"title": "ab", "v_id": [""], "v_size": [""], "v_label": [""], "v_price": [""]})
        self.assertEqual(r.status_code, 200)
        for e in ("عنوان کالا", "دستهٔ کالا", "دست‌کم یک عکس", "دست‌کم یک سایز"):
            self.assertContains(r, e)
        self.assertFalse(Product.objects.exists())

    def test_order_flow_and_payout(self):
        p = self.make_product()
        CategoryCommission.objects.create(category=self.cat, percent=Decimal("8"))
        o = self.order_for(p, qty=2)
        so = SellerOrder.objects.get()
        self.assertEqual((so.status, so.items_total, so.commission, so.seller_amount), ("waiting", 50 * M, 4 * M, 46 * M))
        o.status = "paid"
        o.save()
        O.sync(o)
        so.refresh_from_db()
        v = p.variations.get()
        self.assertEqual((so.status, v.stock_qty, v.is_available), ("new", 0, False))
        # پنل فروشنده
        self.client.force_login(self.su)
        self.assertContains(self.client.get("/seller/orders/"), str(o.number)[-3:].translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
        r = self.client.get(f"/seller/orders/{so.pk}/")
        self.assertContains(r, "پذیرش و شروع آماده‌سازی")
        self.client.post(f"/seller/orders/{so.pk}/", {"act": "accept"})
        o.refresh_from_db()
        self.assertEqual(o.status, "processing")
        self.client.post(f"/seller/orders/{so.pk}/", {"act": "ship", "tracking_code": "123456789", "carrier": "تیپاکس"})
        so.refresh_from_db()
        o.refresh_from_db()
        self.assertEqual((so.status, o.status), ("shipped", "shipped"))
        # مشتری تحویل را تأیید می‌کند
        self.client.force_login(self.cust)
        self.assertContains(self.client.get(o.get_absolute_url()), "این بسته را تحویل گرفتم")
        self.client.post(f"{o.get_absolute_url()}received/{so.pk}/")
        so.refresh_from_db()
        o.refresh_from_db()
        self.assertEqual((so.status, o.status, so.settle), ("delivered", "completed", "open"))
        self.assertEqual(O.run_jobs(now=timezone.now() + timezone.timedelta(days=8)), 1)
        so.refresh_from_db()
        self.assertEqual(so.settle, "payable")
        self.assertEqual(O.balances(self.s)["payable"]["amount"], 46 * M)
        pay = O.pay(self.s, "REF1")
        so.refresh_from_db()
        self.assertEqual((pay.amount, so.settle), (46 * M, "paid"))

    def test_cancel_restores_stock(self):
        p = self.make_product()
        o = self.order_for(p, qty=1, status="paid")
        so = SellerOrder.objects.get()
        self.assertEqual((so.status, p.variations.get().stock_qty), ("new", 1))
        self.assertTrue(O.cancel(so, "تمام شد"))
        so.refresh_from_db()
        o.refresh_from_db()
        self.assertEqual((so.status, so.settle, p.variations.get().stock_qty, o.status), ("cancelled", "none", 2, "cancelled"))

    def test_auto_deliver_and_mixed_order(self):
        from shop.models import OrderItem

        p = self.make_product()
        own = Product.objects.create(title="فرش خودمان", slug="own", status="publish")
        o = self.order_for(p, status="paid")
        OrderItem.objects.create(order=o, product=own, title="فرش خودمان", unit_price=10 * M, quantity=1)
        so = SellerOrder.objects.get()
        O.ship(so, "TRK123")
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")  # سفارش ترکیبی: وضعیت اصلی با مدیر
        self.assertEqual(O.run_jobs(now=timezone.now() + timezone.timedelta(days=11)), 1)
        so.refresh_from_db()
        self.assertEqual(so.status, "delivered")

    def test_cart_only_full_payment(self):
        p = self.make_product()
        v = p.variations.get()
        self.client.force_login(self.cust)
        self.client.post("/cart/add/", {"variation": v.pk, "qty": 5})
        self.assertEqual(self.client.session["cart"][str(v.pk)], 2)  # سقف موجودی
        r = self.client.get("/checkout/")
        self.assertEqual(r.context["modes"], ["full"])
        self.assertContains(r, "فقط با پرداخت کامل آنلاین")
        self.assertContains(r, "کالاهایش را خودش از کاشان می‌فرستد")

    def test_visibility(self):
        p = self.make_product()
        self.s.status = "suspended"
        self.s.save()
        P.set_visibility(self.s)
        p.refresh_from_db()
        self.assertEqual(p.status, "private")
        self.s.status = "active"
        self.s.save()
        P.set_visibility(self.s)
        p.refresh_from_db()
        self.assertEqual(p.status, "publish")
        self.assertContains(self.client.get("/vendor/kavir/"), "فرش کویر")

    def test_pause(self):
        p = self.make_product()
        self.client.force_login(self.su)
        self.client.post("/seller/pause/")
        p.refresh_from_db()
        self.s.refresh_from_db()
        self.assertEqual((self.s.status, p.status), ("paused", "private"))
        self.client.post("/seller/pause/")
        p.refresh_from_db()
        self.assertEqual(p.status, "publish")

    def test_pages(self):
        p = self.make_product()
        self.order_for(p, status="paid")
        self.client.force_login(self.su)
        for url in ("/seller/", "/seller/products/", "/seller/products/add/", f"/seller/products/{p.pk}/", "/seller/orders/",
                    "/seller/finance/", "/seller/settings/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.post("/seller/settings/", {"city": "کاشان", "prep_days": "5", "shipping": "free", "sheba": "IR820540102680020817909002"})
        self.assertEqual(r.status_code, 302)
        self.s.refresh_from_db()
        self.assertEqual((self.s.prep_days, self.s.shipping), (5, "free"))
        self.client.force_login(self.admin)
        for key in ("sellers", "seller-products", "seller-orders", "seller-payouts", "category-commissions"):
            self.assertEqual(self.client.get(f"/panel/{key}/").status_code, 200, key)
        self.assertEqual(self.client.get(f"/panel/sellers/{self.s.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/panel/settings/?tab=market").status_code, 200)
        self.assertEqual(self.client.get("/panel/products/?seller=%d" % self.s.pk).status_code, 200)
        self.assertEqual(self.client.get(f"/panel/products/{p.pk}/edit/").status_code, 200)
        r = self.client.post("/panel/seller-products/", {"action": "reject", "ids": [p.pk], "action_value": "عکس واضح نیست"})
        p.refresh_from_db()
        self.assertEqual((p.status, p.review_status, p.review_note), ("draft", "rejected", "عکس واضح نیست"))
        self.client.post("/panel/seller-products/", {"action": "approve", "ids": [p.pk]})
        p.refresh_from_db()
        self.assertEqual(p.status, "publish")
        self.assertEqual(self.client.get("/sell/").status_code, 200)

    def test_settings_commission_default(self):
        p = self.make_product()
        self.assertEqual(O.commission_percent(p), Decimal("10"))
        self.s.commission_percent = Decimal("6")
        self.assertEqual(O.commission_percent(p, self.s), Decimal("6"))
        MarketSettings.objects.update(enabled=False)
        self.assertEqual(self.client.get("/sell/").status_code, 404)


class SellLandingTests(TestCase):
    def test_landing_and_home_box(self):
        r = self.client.get("/sell/")
        self.assertContains(r, "پول هر سفارش کجا می‌رود")
        self.assertContains(r, "FAQPage")
        self.assertContains(r, 'name="mobile"')
        self.assertContains(self.client.get("/"), "فرش‌تان را در ایران کارپت بفروشید")
        MarketSettings.objects.update_or_create(pk=1, defaults={"signup_open": False})
        self.assertNotContains(self.client.get("/"), "فروشنده شوید")
