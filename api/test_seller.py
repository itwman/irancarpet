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
