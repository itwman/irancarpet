"""ویترین تازه، آلبوم قیمت فروشنده، افزودن با عکس، فرصت ویژه، کد تخفیف فروشگاه، پرسش‌ها و آمار پنل."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from catalog.models import Category, Product, Review
from pricing.models import Album, Size, seed_sizes
from shop.models import Coupon, Order, OrderItem, SpecialOffer

from . import orders as O
from . import products as P
from .models import Seller, SellerFollow, SellerOrder, SellerShelf
from .tests import png

User = get_user_model()


class StorefrontTests(TestCase):
    def setUp(self):
        cache.clear()
        seed_sizes()
        self.s12 = Size.objects.get(slug="12-meter")
        self.s6 = Size.objects.get(slug="6-meter")
        self.s9 = Size.objects.get(slug="9-meter")
        self.cat = Category.objects.create(name="فرش ۷۰۰ شانه", slug="c700")
        self.su = User.objects.create_user("09350001111")
        self.s = Seller.objects.create(user=self.su, name="فرش شاه‌پسند", slug="shahpasand", owner_name="علی", mobile="09350001111",
                                       city="کاشان", status="active", trusted=True)
        self.client.force_login(self.su)

    def album(self, price="40٬000٬000", **extra):
        data = {"name": "۷۰۰ شانه پلی‌استر", "base_size": self.s12.pk, "base_price": price, "round_to": "10000",
                "sizes": [self.s12.pk, self.s6.pk, self.s9.pk], **extra}
        r = self.client.post("/seller/albums/add/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:3000])
        return Album.all_objects.get(seller=self.s)

    def quick(self, album, names=("Afshan-Laki.png", "Afshan-Laki-2.png", "ماهتاب-کرم.png")):
        return self.client.post("/seller/quick/", {"album": album.pk, "category": self.cat.pk, "prefix": "فرش ۷۰۰ شانه",
                                                   "photos": [png(n) for n in names]})

    def test_seller_album_is_private_and_prices_products(self):
        a = self.album(**{f"price_{self.s9.pk}": f"{33_000_000:,}"})
        self.assertFalse(Album.objects.filter(pk=a.pk).exists())  # نه لیست قیمت، نه ترب، نه پنل آلبوم‌ها
        self.assertFalse(a.in_price_list)
        self.assertEqual(a.size_prices, {str(self.s9.pk): 33_000_000})
        self.assertEqual(a.size_price(self.s6), 20_000_000)  # نصف متراژ پایه
        r = self.quick(a)
        self.assertEqual(r.status_code, 302)
        prods = list(Product.objects.filter(seller=self.s).order_by("pk"))
        self.assertEqual(len(prods), 2)  # دو عکس افشان یک کالا شدند
        p = prods[0]
        self.assertIn("افشان", p.title)
        self.assertEqual(p.images.count(), 2)
        prices = {v.size_id: v.final_price for v in p.variations.all()}
        self.assertEqual(prices, {self.s12.pk: 40_000_000, self.s6.pk: 20_000_000, self.s9.pk: 33_000_000})
        self.assertEqual(p.status, "publish")  # فروشندهٔ مورد اعتماد
        # تغییر قیمت آلبوم ← قیمت همهٔ کالاها
        self.client.post(f"/seller/albums/{a.pk}/", {"name": a.name, "base_size": self.s12.pk, "base_price": "50000000", "round_to": "10000",
                                                     "sizes": [self.s12.pk, self.s6.pk]})
        p.refresh_from_db()
        self.assertEqual(p.min_price, 50_000_000)
        self.assertEqual(p.variations.count(), 2)
        from torob.feed import base_queryset
        from torob.models import TorobSettings

        self.assertFalse(base_queryset(TorobSettings.load()).filter(pk=p.pk).exists())
        self.client.logout()
        self.assertNotContains(self.client.get("/carpets-price-list/"), "۷۰۰ شانه پلی‌استر")

    def test_storefront_shelves_follow_and_noindex(self):
        a = self.album()
        self.quick(a)
        prods = list(Product.objects.filter(seller=self.s))
        sh = SellerShelf.objects.create(seller=self.s, name="کلکسیون لاکی")
        r = self.client.post("/seller/products/bulk/", {"ids": [prods[0].pk], "do": "shelf_add", "shelf": sh.pk})
        self.assertEqual(sh.products.count(), 1)
        self.client.post("/seller/look/", {"do": "identity", "accent": "#1F4E79", "tagline": "از کارگاه به خانه", "layout": "gallery",
                                           "featured": prods[1].pk, "logo": png("logo.png")})
        self.s.refresh_from_db()
        self.assertEqual((self.s.accent, self.s.layout, self.s.featured_product_id), ("#1F4E79", "gallery", prods[1].pk))
        self.assertTrue(self.s.logo_id)
        self.client.logout()
        r = self.client.get("/vendor/shahpasand/")
        self.assertContains(r, "از کارگاه به خانه")
        self.assertContains(r, "--acc: #1F4E79")
        self.assertContains(r, "کلکسیون لاکی")
        self.assertContains(r, "پیشنهاد فروشنده")
        self.assertContains(r, "noindex")  # کمتر از ۳ کالا
        self.assertContains(r, '"@type": "Store"')
        self.assertNotContains(r, "امتیاز خریداران")  # بدون نظر کافی عددی ساخته نمی‌شود
        r = self.client.get(f"/vendor/shahpasand/?shelf={sh.slug}")
        self.assertEqual(len(r.context["page"].object_list), 1)
        u = User.objects.create_user("09120000009")
        self.client.force_login(u)
        self.client.post("/vendor/shahpasand/follow/")
        self.assertTrue(SellerFollow.objects.filter(seller=self.s, user=u).exists())
        self.client.post("/vendor/shahpasand/follow/")
        self.assertFalse(SellerFollow.objects.exists())

    def test_light_accent_falls_back(self):
        self.s.accent = "#FFEE88"
        self.assertEqual(self.s.accent_color, "#8E1F2F")
        self.s.accent = "#1F4E79"
        self.assertEqual(self.s.accent_color, "#1F4E79")

    def test_slides_and_store_render(self):
        a = self.album()
        self.quick(a)
        p = Product.objects.filter(seller=self.s).first()
        self.client.post("/seller/look/", {"do": "slide_add", "image": png("s1.png"), "title": "حراج پاییز", "product": p.pk})
        self.client.post("/seller/look/", {"do": "slide_add", "image": png("s2.png"), "title": "تازه‌ها"})
        self.assertEqual(self.s.slides.count(), 2)
        r = self.client.get("/vendor/shahpasand/")
        self.assertContains(r, "data-slider")
        self.assertContains(r, "حراج پاییز")
        self.assertContains(r, 'data-slide="1"')

    def test_stock_toggle_and_bulk_price(self):
        self.client.post("/seller/products/add/", {"title": "فرش دستی ۱۰۰۰ شانه", "category": self.cat.pk, "v_id": [""],
                                                   "v_size": [self.s12.pk], "v_label": [""], "v_price": ["10000000"], "v_sale": [""],
                                                   "v_qty": [""], "v_pair": ["0"], "v_delete": ["0"], "images": png()})
        p = Product.objects.get(seller=self.s)
        r = self.client.post(f"/seller/products/{p.pk}/stock/", {"on": "0"})
        self.assertEqual(r.json(), {"on": False})
        p.refresh_from_db()
        self.assertEqual(p.stock_status, "outofstock")
        self.client.post(f"/seller/products/{p.pk}/stock/", {"on": "1"})
        self.client.post("/seller/products/bulk/", {"ids": [p.pk], "do": "price", "dir": "up", "percent": "10"})
        p.refresh_from_db()
        self.assertEqual((p.stock_status, p.min_price), ("instock", 11_000_000))
        other = User.objects.create_user("0912")
        self.client.force_login(other)
        self.assertEqual(self.client.post(f"/seller/products/{p.pk}/stock/", {"on": "0"}).status_code, 302)

    def test_offer_in_store_not_on_main_offers(self):
        a = self.album()
        self.quick(a)
        p = Product.objects.filter(seller=self.s).first()
        r = self.client.post("/seller/offers/", {"product": p.pk, "size": self.s6.pk, "percent": "20", "quantity": "2"})
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        o = SpecialOffer.objects.get()
        self.assertEqual(o.price, 16_000_000)
        from shop.offers import live_offers

        self.assertEqual(live_offers(), [])
        self.assertEqual(len(live_offers(sellers=True)), 1)
        self.assertContains(self.client.get("/vendor/shahpasand/"), "فرصت ویژهٔ این فروشگاه")

    def test_seller_coupon_only_on_own_items_and_from_seller_share(self):
        a = self.album()
        self.quick(a, names=("Afshan-Laki.png",))
        p = Product.objects.get(seller=self.s)
        self.client.post("/seller/coupons/", {"code": "shah10", "kind": "percent", "value": "10"})
        c = Coupon.objects.get(code="SHAH10")
        self.assertEqual(c.seller, self.s)
        from shop.coupons import apply

        class L:
            def __init__(self, product, total):
                self.product, self.total, self.problem, self.offer = product, total, "", None

        own = Product.objects.create(title="فرش ایران کارپت", slug="own", status="publish")
        summary = {"total": 50_000_000, "lines": [L(own, 10_000_000), L(p, 40_000_000)]}
        out = apply(summary, "SHAH10", None)
        self.assertEqual((out["discount"], out["total"]), (4_000_000, 46_000_000))
        out = apply({"total": 10_000_000, "lines": [L(own, 10_000_000)]}, "SHAH10", None)
        self.assertIn("فقط برای کالاهای فروشگاه", out["coupon_error"])
        cust = User.objects.create_user("09121112233")
        v = p.variations.get(size=self.s12)
        o = Order.objects.create(user=cust, first_name="م", last_name="ک", mobile="09121112233", province="تهران", city="تهران",
                                 address="x", items_total=v.price - 4_000_000, status="pending", coupon_code="SHAH10", discount=4_000_000)
        OrderItem.objects.create(order=o, product=p, variation=v, title=p.title, size_label="۱۲ متری", unit_price=v.price, quantity=1)
        so = O.split(o)[0]
        self.assertEqual(so.items_total, 36_000_000)
        self.assertEqual(so.commission, 3_600_000)  # ۱۰٪ کمیسیون روی مبلغ پس از تخفیف
        self.assertEqual(so.seller_amount, 32_400_000)

    def test_questions_answer_blocks_phone(self):
        a = self.album()
        self.quick(a, names=("Afshan-Laki.png",))
        p = Product.objects.get(seller=self.s)
        from catalog.reviews import ask

        q = ask(p, name="مریم", text="سایز ۹ متری هم دارید؟")
        self.assertContains(self.client.get("/seller/"), "پرسش بی‌پاسخ")
        self.client.post("/seller/questions/", {"id": q.pk, "answer": "بله؛ زنگ بزنید ۰۹۱۲۱۲۳۴۵۶۷"})
        self.assertFalse(q.replies.exists())
        self.client.post("/seller/questions/", {"id": q.pk, "answer": "بله، همین الان موجود است."})
        q.refresh_from_db()
        self.assertTrue(q.is_approved)
        self.assertEqual(q.replies.get().author_name, "فروشگاه فرش شاه‌پسند")

    def test_stats_and_panel_pages(self):
        from stats.models import Hit

        a = self.album()
        self.quick(a, names=("Afshan-Laki.png",))
        p = Product.objects.get(seller=self.s)
        now = timezone.now()
        today = timezone.localdate()
        for path, pid in (("/vendor/shahpasand/", None), (p.get_absolute_url(), p.pk), (p.get_absolute_url(), p.pk)):
            Hit.objects.create(at=now, day=today, kind="v", path=path, product_id=pid, visitor="x")
        from .stats import series, top_viewed

        rows = series(self.s, 7)
        self.assertEqual((rows[-1]["store"], rows[-1]["products"]), (1, 2))
        self.assertEqual(top_viewed(self.s)[0]["views"], 2)
        for url in ("/seller/", "/seller/stats/?d=90", "/seller/more/", "/seller/look/", "/seller/shelves/", "/seller/albums/",
                    f"/seller/albums/{a.pk}/", "/seller/quick/", "/seller/offers/", "/seller/coupons/", "/seller/questions/",
                    "/seller/questions/?t=reviews", "/seller/products/", f"/seller/products/{p.pk}/", "/seller/orders/",
                    "/seller/finance/", "/seller/settings/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.assertContains(self.client.get("/seller/stats/"), "پربازدیدترین کالاها")

    def test_product_edit_album_and_size_off(self):
        a = self.album()
        self.quick(a, names=("Afshan-Laki.png",))
        p = Product.objects.get(seller=self.s)
        data = {"title": p.title, "category": self.cat.pk, "album": a.pk, "size_off": [self.s6.pk], "shelves_sent": "1"}
        r = self.client.post(f"/seller/products/{p.pk}/", data)
        self.assertEqual(r.status_code, 302, r.content.decode()[:2000])
        self.assertFalse(p.variations.get(size=self.s6).is_available)
        self.assertTrue(p.variations.get(size=self.s12).is_available)

    def test_panel_is_standalone_with_guides_and_setup(self):
        r = self.client.get("/seller/orders/")
        html = r.content.decode()
        self.assertIn('class="sp-bar"', html)
        self.assertIn('data-guide="orders"', html)
        self.assertNotIn("partials/header", html)
        self.assertNotIn("offcanvas-header", html)
        r = self.client.get("/seller/")
        self.assertIn("راه‌اندازی فروشگاه", r.content.decode())
        from market.guides import guide, setup_steps
        from market.models import MarketSettings

        ms = MarketSettings.load()
        for tab in ("home", "orders", "products", "quick", "albums", "shelves", "offers", "coupons", "questions", "look", "settings",
                    "finance", "stats"):
            self.assertTrue(guide(tab, ms)["steps"], tab)
        self.assertFalse(setup_steps(self.s)["all"])
