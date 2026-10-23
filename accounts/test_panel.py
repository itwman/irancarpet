"""«حساب من»: پیشخوان، سفارش‌ها با مراحل، علاقه‌مندی‌ها، خبرم‌کن‌ها، کدها و اطلاعات حساب."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Product
from shop.models import Coupon, Order

from .models import Profile
from .panel import steps


class AccountPanelTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("09121112233", first_name="محمدعلی")
        Profile.objects.create(user=self.u, mobile="09121112233")
        self.client.force_login(self.u)
        self.p = Product.objects.create(title="فرش گلریز", slug="golriz", status="publish", min_price=20_000_000)

    def order(self, status, n=1):
        return Order.objects.create(user=self.u, first_name="a", last_name="b", mobile="09121112233", province="x", city="y",
                                    address="z", items_total=20_000_000 * n, status=status)

    def test_steps(self):
        o = self.order("shipped")
        self.assertEqual([s["state"] for s in steps(o)], ["done", "done", "done", "now", "todo"])
        self.assertIsNone(steps(self.order("cancelled")))
        self.assertEqual([s["state"] for s in steps(self.order("completed"))], ["done"] * 5)

    def test_pages(self):
        cur = self.order("processing")
        self.order("completed", 2)
        Coupon.objects.create(code="GIFT1", kind="fixed", value=500_000, for_mobile="09121112233")
        r = self.client.get("/my-account/")
        self.assertContains(r, "سلام محمدعلی")
        self.assertContains(r, f"سفارش {cur.number}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
        self.assertContains(r, 'aria-current="step"')
        self.assertContains(r, "GIFT1")
        r = self.client.get("/my-account/orders/")
        self.assertContains(r, '<article class="acc2-order"', count=2)
        for path in ("/my-account/wishlist/", "/my-account/alerts/", "/my-account/codes/", "/my-account/profile/"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_wishlist_toggle_and_profile(self):
        from api.models import Wishlist

        r = self.client.post(f"/my-account/wishlist/{self.p.pk}/", HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json(), {"on": True})
        self.assertContains(self.client.get("/my-account/wishlist/"), "فرش گلریز")
        self.assertContains(self.client.get(self.p.get_absolute_url()), "fav-btn on")
        self.client.post(f"/my-account/wishlist/{self.p.pk}/", HTTP_X_REQUESTED_WITH="fetch")
        self.assertFalse(Wishlist.objects.exists())
        r = self.client.post("/my-account/profile/", {"first_name": "علی", "last_name": "رضایی", "email": "", "password": "",
                                                       "province": "تهران", "city": "تهران", "address": "خیابان آزادی",
                                                       "postal_code": "۱۲۳۴۵۶۷۸۹۰"})
        self.assertRedirects(r, "/my-account/profile/", fetch_redirect_response=False)
        p = Profile.objects.get(user=self.u)
        self.assertEqual((p.city, p.postal_code), ("تهران", "1234567890"))
        self.client.logout()
        r = self.client.post(f"/my-account/wishlist/{self.p.pk}/", {"next": "/x/"})
        self.assertTrue(r["Location"].startswith("/my-account/login/"))
