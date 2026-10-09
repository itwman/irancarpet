from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Attribute, AttributeTerm, Product
from core.models import Media
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from shop.cart import Cart
from shop.models import Order, OrderItem, SpecialOffer
from shop.offers import clear, live_offers


class OfferTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.s = s
        a = Album.objects.create(name="1200", code="A", base_size=s["12-meter"], base_price=Decimal("50000000"))
        a.sizes.set([s["12-meter"], s["9-meter"], s["round-d150"]])
        a.even_sizes.set([s["round-d150"]])
        self.album = a
        img = Media.objects.create(file="x.jpg")
        # ناموجود در سایت؛ ولی یک تختهٔ ۹ متری در انبار
        self.p = Product.objects.create(title="فرش ناموجود", slug="old", album=a, status="publish", image=img, sale_status="unavailable")
        sync_album_variations([self.p])
        self.p.variations.update(is_available=False)
        self.v9 = self.p.variations.get(size=s["9-meter"])
        self.reg = self.v9.price
        self.o = SpecialOffer.objects.create(product=self.p, size=s["9-meter"], percent=20, quantity=1)
        clear()

    def summary(self, qty):
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore

        req = RequestFactory().get("/")
        req.session = SessionStore()
        c = Cart(req)
        c.data = {str(self.v9.pk): qty}
        return c.summary()

    def test_single_gets_offer_even_when_unavailable(self):
        self.assertEqual(live_offers(), [self.o])
        sm = self.summary(1)
        line = sm["lines"][0]
        self.assertEqual(line.problem, "")
        self.assertEqual(line.unit_price, self.o.price)
        self.assertLess(self.o.price, self.reg)
        self.assertEqual(sm["offer_total"], self.o.price)
        sm2 = self.summary(2)
        self.assertTrue(sm2["lines"][0].problem)  # بیشتر از یک تخته از فرش ناموجود نه
        self.assertEqual(sm2["offer_total"], 0)

    def test_two_pieces_full_price_when_in_stock(self):
        Product.objects.filter(pk=self.p.pk).update(sale_status="available", stock_status="instock")
        self.p.variations.update(is_available=True)
        line = self.summary(2)["lines"][0]
        self.assertEqual(line.unit_price, self.reg)
        self.assertIn("یک تخته", line.offer_hint)

    def test_sold_and_expiry(self):
        u = get_user_model().objects.create_user("c")
        o = Order.objects.create(user=u, first_name="a", last_name="b", mobile="09120000000", items_total=1, status="paid")
        OrderItem.objects.create(order=o, product=self.p, variation=self.v9, title="x", unit_price=self.o.price, offer=self.o)
        clear()
        self.assertEqual(live_offers(), [])
        OrderItem.objects.all().delete()
        SpecialOffer.objects.filter(pk=self.o.pk).update(ends_at=timezone.now())
        clear()
        self.assertEqual(live_offers(), [])

    def test_pages_and_add(self):
        r = self.client.get("/product/old/")
        self.assertContains(r, "خرید یک تخته")
        self.assertContains(r, "آخرین تخته")
        self.assertContains(self.client.get("/"), "فرصت‌های ویژهٔ خرید")
        r = self.client.post("/cart/add/", {"variation": self.v9.pk, "qty": 1, "offer": 1})
        self.assertRedirects(r, "/cart/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["cart"], {str(self.v9.pk): 1})
        self.assertContains(self.client.get("/cart/"), "فرصت ویژه")

    def test_pair_only_single(self):
        rnd = self.p.variations.get(size=self.s["round-d150"])
        self.assertEqual(Cart.fix_qty(rnd, 1), 2)
        SpecialOffer.objects.create(product=self.p, size=self.s["round-d150"], percent=10)
        clear()
        self.assertEqual(Cart.fix_qty(rnd, 1), 1)


class RelatedTests(TestCase):
    def test_ranking(self):
        from catalog.related import related_products

        color = Attribute.objects.create(slug="c", label="رنگ زمینه")
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        blue = AttributeTerm.objects.create(attribute=color, name="آبی", slug="blue")
        cream = AttributeTerm.objects.create(attribute=color, name="کرم", slug="cream")
        r = {n: AttributeTerm.objects.create(attribute=reeds, name=str(n), slug=str(n)) for n in (700, 1000, 1200, 1500)}
        seed_sizes()
        s12 = Size.objects.get(slug="12-meter")
        a5 = Album.objects.create(name="5", code="A5", base_size=s12)
        a6 = Album.objects.create(name="6", code="A6", base_size=s12, base_price=Decimal("40000000"))
        a6.sizes.set([s12])
        img = Media.objects.create(file="x.jpg")

        def mk(slug, album, terms, views=0):
            p = Product.objects.create(title=slug, slug=slug, album=album, status="publish", image=img, views=views)
            p.specs.set(terms)
            return p

        me = mk("me", a5, [blue, r[1200]])
        same_album = mk("same-album", a5, [blue, r[1200]])
        same_reeds = mk("same-reeds", a6, [blue, r[1200]], views=50)
        r1000 = mk("r1000", a6, [blue, r[1000]], views=10)
        r700 = mk("r700", a6, [blue, r[700]], views=99)
        mk("cream", a5, [cream, r[1200]], views=500)
        offer_p = mk("offer-1500", a6, [blue, r[1500]])
        sync_album_variations([offer_p])
        SpecialOffer.objects.create(product=offer_p, size=s12, percent=10)
        clear()
        got = [p.slug for p in related_products(me)]
        self.assertEqual(got[:5], ["offer-1500", "same-album", "same-reeds", "r1000", "r700"])
        self.assertEqual(got[5], "cream")  # پرکردن با هم‌آلبوم وقتی هم‌رنگ کم است
        self.assertTrue(related_products(me)[0].offer)


class OfferQtyTests(OfferTests):
    test_single_gets_offer_even_when_unavailable = test_two_pieces_full_price_when_in_stock = None
    test_sold_and_expiry = test_pages_and_add = test_pair_only_single = None

    def test_allowed_counts(self):
        for qty, allowed in ((1, [1]), (2, [2]), (3, [1, 3]), (4, [2, 4]), (5, [1, 3, 5])):
            SpecialOffer.objects.filter(pk=self.o.pk).update(quantity=qty)
            self.o.refresh_from_db()
            self.assertEqual(self.o.allowed, allowed, qty)

    def test_partial_sale_leaves_pair(self):
        SpecialOffer.objects.filter(pk=self.o.pk).update(quantity=3)
        clear()
        self.assertEqual(self.summary(1)["lines"][0].unit_price, self.o.price)
        self.assertTrue(self.summary(2)["lines"][0].problem)  # ۲ از ۳ یک تخته تک می‌گذارد
        u = get_user_model().objects.create_user("c2")
        o = Order.objects.create(user=u, first_name="a", last_name="b", mobile="09120000001", items_total=1, status="paid")
        OrderItem.objects.create(order=o, product=self.p, variation=self.v9, title="x", unit_price=1, quantity=1, offer=self.o)
        clear()
        self.o.refresh_from_db()
        self.assertEqual((self.o.remaining, self.o.allowed), (2, [2]))
        self.assertTrue(self.summary(1)["lines"][0].problem)
        self.assertEqual(self.summary(2)["lines"][0].unit_price, self.o.price)


class OfferBasePriceTests(TestCase):
    """فرش از تولید خارج‌شده بدون قیمت: قیمت پیش از تخفیف از آلبوم یا دستی، پیش‌نمایش در پنل، و جدول سایزهای فرش ناموجود."""

    def setUp(self):
        from django.core.exceptions import ValidationError  # noqa: F401

        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.s = s
        self.album = Album.objects.create(name="قدیمی", code="Q", base_size=s["12-meter"], base_price=Decimal("40000000"))
        self.album.sizes.set([s["12-meter"], s["9-meter"], s["6-meter"]])
        self.p = Product.objects.create(title="فرش پارادایس", slug="paradise", status="publish", sale_status="unavailable",
                                        image=Media.objects.create(file="y.jpg"))
        self.v9 = self.p.variations.create(size=s["9-meter"], manual_price=None, is_available=False)
        self.v6 = self.p.variations.create(size=s["6-meter"], manual_price=20000000, is_available=True)
        self.p.refresh_price_cache()
        clear()

    def test_zero_price_blocked_then_album_or_manual(self):
        from django.core.exceptions import ValidationError

        o = SpecialOffer(product=self.p, size=self.s["9-meter"], percent=20)
        with self.assertRaises(ValidationError):
            o.full_clean()
        o.base_album = self.album
        o.full_clean()
        self.assertEqual(o.regular_price, self.album.size_price(self.s["9-meter"]))
        self.assertEqual(o.off_percent, 20)
        o.base_price, o.base_album = 30000000, None
        o.full_clean()
        self.assertEqual(o.price, 24000000)
        o.fixed_price = 31000000
        with self.assertRaises(ValidationError):
            o.full_clean()  # قیمت ثابت بالاتر از قیمت پیش از تخفیف
        self.assertIsNone(Product.objects.get(pk=self.p.pk).album_id)  # خود فرش دست نخورد

    def test_panel_preview_and_product_page(self):
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        url = "/panel/special-offers/preview/"
        d = self.client.get(url, {"product": self.p.pk, "size": self.s["9-meter"].pk, "percent": "20"}).json()
        self.assertFalse(d["ok"])
        self.assertIn("قیمت", d["msg"])
        d = self.client.get(url, {"product": self.p.pk, "size": self.s["9-meter"].pk, "percent": "۲۰", "base_price": "۳۰,۰۰۰,۰۰۰"}).json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["off"], "۲۰")
        self.assertEqual(self.client.get("/panel/special-offers/add/").status_code, 200)
        SpecialOffer.objects.create(product=self.p, size=self.s["9-meter"], percent=20, base_price=30000000)
        clear()
        self.client.logout()
        html = self.client.get(self.p.get_absolute_url()).content.decode()
        self.assertIn("قیمت ویژه در کادر بالا", html)
        self.assertNotIn("۲۰٬۰۰۰٬۰۰۰", html.split("قیمت سایزها")[-1].split("</table>")[0])  # سایز ۶ متری فرش ناموجود قیمت نشان نمی‌دهد
