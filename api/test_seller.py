"""API اپ فروشندگان: دسترسی فقط به فروشگاه خود، قیمت و موجودی، آلبوم، سفارش."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product
from market.models import Seller
from market.tests import png
from pricing.models import Album, Size, seed_sizes

from .models import ApiToken

User = get_user_model()


class SellerApiTests(TestCase):
    def setUp(self):
        seed_sizes()
        self.s12, self.s6 = Size.objects.get(slug="12-meter"), Size.objects.get(slug="6-meter")
        self.cat = Category.objects.create(name="فرش", slug="f")
        self.u = User.objects.create_user("09350001111")
        self.s = Seller.objects.create(user=self.u, name="فرش کویر", slug="kavir", owner_name="ع", mobile="09350001111", city="کاشان",
                                       status="active", trusted=True)
        self.h = {"HTTP_AUTHORIZATION": "Token " + ApiToken.issue(self.u)}

    def test_not_seller_and_no_token(self):
        self.assertEqual(self.client.get("/api/app/v1/seller/summary/").status_code, 401)
        other = User.objects.create_user("0912")
        r = self.client.get("/api/app/v1/seller/summary/", HTTP_AUTHORIZATION="Token " + ApiToken.issue(other))
        self.assertEqual((r.status_code, r.json()["code"]), (403, "not_seller"))

    def test_flow(self):
        r = self.client.get("/api/app/v1/seller/summary/", **self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["seller"]["name"], "فرش کویر")
        self.assertEqual(len(r.json()["series"]), 7)
        a = Album(seller=self.s, name="۷۰۰ شانه", base_size=self.s12, base_price=40_000_000, profit_percent=0, round_to=10000,
                  in_price_list=False, code="S-1")
        a.save()
        a.sizes.set([self.s12, self.s6])
        r = self.client.post("/api/app/v1/seller/quick/", {"album": a.pk, "category": self.cat.pk, "photos": [png("Afshan-Laki.png")]}, **self.h)
        self.assertEqual(r.status_code, 201, r.content)
        pid = r.json()["created"][0]["id"]
        r = self.client.post(f"/api/app/v1/seller/albums/{a.pk}/", {"base_price": 50_000_000, "prices": {str(self.s6.pk): 26_000_000}},
                             content_type="application/json", **self.h)
        self.assertEqual(r.status_code, 200)
        p = Product.objects.get(pk=pid)
        self.assertEqual({v.size_id: v.final_price for v in p.variations.all()}, {self.s12.pk: 50_000_000, self.s6.pk: 26_000_000})
        r = self.client.post(f"/api/app/v1/seller/products/{pid}/stock/", {"on": False}, content_type="application/json", **self.h)
        self.assertFalse(r.json()["in_stock"])
        r = self.client.get("/api/app/v1/seller/products/?f=out", **self.h)
        self.assertEqual(r.json()["count"], 1)
        self.assertEqual(self.client.get("/api/app/v1/seller/stats/?d=7", **self.h).status_code, 200)
        self.assertEqual(self.client.get("/api/app/v1/seller/orders/", **self.h).json()["items"], [])
        # کالای فروشندهٔ دیگر
        u2 = User.objects.create_user("09350002222")
        Seller.objects.create(user=u2, name="دیگری", slug="other", owner_name="x", mobile="09350002222", city="یزد", status="active")
        r = self.client.post(f"/api/app/v1/seller/products/{pid}/stock/", {"on": True}, content_type="application/json",
                             HTTP_AUTHORIZATION="Token " + ApiToken.issue(u2))
        self.assertEqual(r.status_code, 404)

    def test_album_create(self):
        r = self.client.post("/api/app/v1/seller/albums/", {"name": "۱۲۰۰ شانه", "base_size": self.s12.pk, "base_price": 60_000_000},
                             content_type="application/json", **self.h)
        self.assertEqual(r.status_code, 201, r.content)
        a = Album.all_objects.get(pk=r.json()["id"])
        self.assertEqual((a.seller, a.in_price_list, list(a.sizes.all())), (self.s, False, [self.s12]))
        self.assertFalse(Album.objects.filter(pk=a.pk).exists())  # در فهرست فروشگاه اصلی دیده نمی‌شود
        r = self.client.post(f"/api/app/v1/seller/albums/{a.pk}/", {"sizes": [self.s12.pk, self.s6.pk], "name": "۱۲۰۰ شانه ابریشم"},
                             content_type="application/json", **self.h)
        self.assertEqual(r.json()["name"], "۱۲۰۰ شانه ابریشم")
        self.assertEqual({x["id"] for x in r.json()["sizes"] if x["on"]}, {self.s12.pk, self.s6.pk})
        d = self.client.get("/api/app/v1/seller/albums/", **self.h).json()
        self.assertEqual(len(d["items"]), 1)
        self.assertTrue(d["sizes"])
        r = self.client.post("/api/app/v1/seller/albums/", {"name": "x"}, content_type="application/json", **self.h)
        self.assertEqual(r.status_code, 400)

    def test_quick_with_meta(self):
        import json

        a = Album(seller=self.s, name="۷۰۰ شانه", base_size=self.s12, base_price=40_000_000, profit_percent=0, round_to=10000,
                  in_price_list=False, code="S-2")
        a.save()
        a.sizes.set([self.s12])
        meta = [{"design": "افشان", "group": "a"}, {"design": "افشان", "group": "a"}, {"design": "", "group": "b"}]
        r = self.client.post("/api/app/v1/seller/quick/", {
            "album": a.pk, "category": self.cat.pk, "prefix": "فرش ۷۰۰ شانه", "meta": json.dumps(meta),
            "photos": [png("IMG_1.png"), png("IMG_2.png"), png("IMG_3.png")]}, **self.h)
        self.assertEqual(r.status_code, 201, r.content)
        titles = sorted(x["title"] for x in r.json()["created"])
        self.assertEqual(set(titles), {"فرش ۷۰۰ شانه ۲", "فرش ۷۰۰ شانه نقشه افشان"})
        p = Product.objects.get(title="فرش ۷۰۰ شانه نقشه افشان")
        self.assertEqual(p.gallery.count(), 2)
        d = self.client.get("/api/app/v1/seller/options/", **self.h).json()
        self.assertIn("افشان", d["designs"])
