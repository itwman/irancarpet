from django.contrib.auth import get_user_model
from django.core.cache import cache

from catalog.models import Brand, Product
from content.tests import Base
from pricing.models import Album
from pricing.suggest import missing_q, suggest_ids


class NoAlbumTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.brand = Brand.objects.create(name="شاه پسند", slug="shah")
        Product.objects.filter(pk=self.p.pk).update(brand=self.brand)
        self.old = Product.objects.create(title="فرش 1500 شانه نقشه قدیمی زمینه کرم", slug="old", status="publish", brand=self.brand)
        self.old.specs.set([self.t1500, self.tpile, self.cream])
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)

    def test_filter_suggest_and_assign(self):
        self.assertEqual(list(Product.objects.filter(missing_q()).values_list("pk", flat=True)), [self.old.pk])
        self.assertEqual(suggest_ids([self.old]), {self.old.pk: self.album.pk})
        r = self.client.get("/panel/products/?album_state=missing")
        self.assertContains(r, "نقشه قدیمی")
        self.assertContains(r, "آلبوم پیشنهادی")
        self.assertNotContains(r, "آرشان")
        # دو آلبوم هم‌برند و هم‌شانه ← بی‌پیشنهاد
        other = Album.objects.create(name="1500 دوم", code="B15", base_size=self.album.base_size, base_price=1, company="شاه پسند")
        twin = self.make("فرش 1500 شانه نقشه دوم زمینه کرم", "twin", self.cream)
        Product.objects.filter(pk=twin.pk).update(album=other, brand=self.brand)
        cache.clear()
        self.assertEqual(suggest_ids([self.old]), {})
        Product.objects.filter(pk=twin.pk).update(album=self.album)
        cache.clear()
        self.client.post("/panel/products/", {"action": "suggest_album", "ids": [self.old.pk]})
        self.old.refresh_from_db()
        self.assertEqual(self.old.album_id, self.album.pk)
        self.assertTrue(self.old.variations.exists() and self.old.min_price)

    def test_inactive_album_and_todo(self):
        from dashboard import dash

        Album.objects.filter(pk=self.album.pk).update(is_active=False)
        self.assertEqual(Product.objects.filter(missing_q("inactive")).count(), 1)  # فرش آرشان
        cache.clear()
        item = next(i for i in dash.todo(True)["items"] if "بدون آلبوم" in i["label"])
        self.assertEqual(item["n"], 2)
