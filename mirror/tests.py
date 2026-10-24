"""آزمون همگام‌سازی کاتالوگ: منبع (ایران کارپت) و مقصد (فرشستان) در یک دیتابیس آزمون؛ درخواست‌ها با کلاینت آزمون جنگو."""
import io
import json
import shutil
import tempfile
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from catalog.models import Attribute, AttributeTerm, Category, Product, Variation
from core.models import Media
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes
from seo.models import Redirect
from shop.models import Order, OrderItem

from .models import MirrorLink, MirrorOrder, MirrorPick, MirrorSettings

MEDIA = tempfile.mkdtemp()


def png(color=(180, 40, 40)):
    from PIL import Image

    im = Image.new("RGB", (300, 400), (255, 255, 255))
    im.paste(Image.new("RGB", (200, 300), color), (50, 50))   # فرش با حاشیهٔ سفید دور عکس
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, PRIVATE_ROOT=MEDIA, SITE_URL="http://testserver")
class MirrorTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.s12, self.s6 = s["12-meter"], s["6-meter"]
        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        color = Attribute.objects.create(slug="color", label="رنگ زمینه")
        self.album = Album.objects.create(name="زرین", code="Z", slug="فرش-زرین", base_size=self.s12, base_price=Decimal("40000000"),
                                          shipping_fixed=0, waste_value=0)
        self.album.sizes.set([self.s12, self.s6])
        cat = Category.objects.create(name="فرش 700 شانه", slug="carpet-700")
        media = Media.objects.create(file=default_storage.save("2026/10/zarin.png", ContentFile(png())), alt="زرین")
        self.src = Product.objects.create(title="فرش طرح زرین سیلور 700 شانه برجسته تمام آکریلیک", slug="zarin-silver",
                                          album=self.album, status="publish", design_name="زرین", image=media)
        self.src.specs.add(AttributeTerm.objects.create(attribute=reeds, name="700", slug="700"),
                           AttributeTerm.objects.create(attribute=color, name="سیلور", slug="silver"))
        self.src.categories.add(cat)
        sync_album_variations([self.src], reset=True)
        self.src.refresh_price_cache()
        MirrorPick.objects.create(product=self.src)
        st = MirrorSettings.load()
        st.feed_enabled = st.enabled = st.live = True
        st.api_key, st.source_url = "k-123", "http://testserver"
        st.save()
        self.c = Client()

        def get_json(path, params=None, timeout=60, body=None):
            h = {"HTTP_AUTHORIZATION": "Token k-123"}
            if body is not None:
                r = self.c.post(path, json.dumps(body), content_type="application/json", **h)
            else:
                r = self.c.get(path, params or {}, **h)
            out = r.json()
            if not out.get("ok"):
                from mirror.client import MirrorError

                raise MirrorError(out.get("error"))
            return out

        def get_bytes(url, timeout=60, limit=0):
            with default_storage.open(urlparse(url).path.replace("/wp-content/uploads/", "").replace("/media/", ""), "rb") as f:
                return f.read()

        for mod in ("mirror.sync", "mirror.match", "mirror.orders", "mirror.live"):
            p = mock.patch(f"{mod}.get_json", side_effect=get_json)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch("mirror.sync.get_bytes", side_effect=get_bytes)
        p.start()
        self.addCleanup(p.stop)

    def mirrored(self):
        return MirrorLink.objects.get(source_pk=self.src.pk).product

    def test_feed_needs_key(self):
        self.assertEqual(self.c.get("/api/mirror/v1/stock/").status_code, 403)
        self.assertEqual(self.c.get("/api/mirror/v1/stock/", HTTP_AUTHORIZATION="Token bad").status_code, 403)

    def test_report_then_sync_with_own_title_text_and_prices(self):
        from mirror.sync import run

        r = run(report=True)
        self.assertEqual((r["new"], r["live"]), (1, False))
        self.assertFalse(MirrorLink.objects.exists())
        self.assertIn("فرش ماشینی زرین زمینه سیلور 700 شانه برجسته", r["sample_new"])
        r = run()
        self.assertEqual(r["done"], 1)
        p = self.mirrored()
        self.assertEqual(p.title, "فرش ماشینی زرین زمینه سیلور 700 شانه برجسته")
        self.assertNotEqual(p.slug, self.src.slug)
        self.assertTrue(p.use_template and p.status == "publish" and p.seller_id is None)
        self.assertEqual(p.album.mirror_pk, self.album.pk)          # آلبوم نمایشی برای لیست قیمت
        src_prices = {v.size.slug: v.price for v in self.src.variations.select_related("size")}
        self.assertEqual({v.size.slug: v.price for v in p.variations.select_related("size")}, src_prices)
        self.assertEqual(p.min_price, self.src.min_price)
        self.assertTrue(p.image.file.name.startswith("fs/") and p.image.file.name != self.src.image.file.name)
        self.assertLess(p.image.width, 300)                          # حاشیهٔ سفید بریده شد
        self.assertEqual(set(p.categories.values_list("slug", flat=True)), {"carpet-700"})
        # کپی همگام در خوراک منبع نمی‌آید
        ids = [x["id"] for x in self.c.get("/api/mirror/v1/stock/", HTTP_AUTHORIZATION="Token k-123").json()["products"]]
        self.assertEqual(ids, [self.src.pk])
        # لیست قیمت: آلبوم همگام با قیمت منبع
        from pricing.pricelist import album_rows

        self.assertEqual({r["size"].slug: r["price"] for r in album_rows(p.album)}, src_prices)
        # تغییر قیمت آلبوم در منبع ← فقط قیمت به‌روز می‌شود
        self.album.set_base_price(Decimal("50000000"))
        Variation.reprice_queryset(self.src.variations.all())
        r = run()
        self.assertEqual(r["stock"], 1)
        new_prices = {v.size.slug: v.price for v in Product.objects.get(pk=self.src.pk).variations.select_related("size")}
        self.assertEqual({v.size.slug: v.price for v in self.mirrored().variations.select_related("size")}, new_prices)
        # درصد پنل
        st = MirrorSettings.load()
        st.price_percent = Decimal("2")
        st.save()
        MirrorLink.objects.update(stock_hash="")
        run()
        got = self.mirrored().variations.get(size=self.s12).price
        self.assertEqual(got, round(new_prices["12-meter"] * 1.02 / 10000) * 10000)

    def test_only_picked_products_and_panel_actions(self):
        from django.contrib.auth.models import User

        from mirror.sync import run

        other = Product.objects.create(title="فرش طرح آرشان کرم 1200 شانه", slug="arshan", status="publish")
        r = run()
        self.assertEqual(r["source"], 1)                        # فقط فرش انتخاب‌شده
        self.client.force_login(User.objects.create_superuser("boss", "", "x"))
        self.client.post("/panel/products/", {"action": "mirror_on", "ids": [other.pk]})
        self.assertTrue(MirrorPick.objects.filter(product=other).exists())
        r = run()
        self.assertEqual((r["source"], r["new"]), (2, 1))
        url = MirrorLink.objects.get(source_pk=other.pk).product.get_absolute_url()
        self.client.post("/panel/products/", {"action": "mirror_off", "ids": [other.pk]})
        r = run()
        self.assertEqual(r["removed"], 1)
        self.assertEqual(MirrorLink.objects.get(source_pk=other.pk).product.status, "draft")
        # دوباره انتخاب ← با همان نشانی برمی‌گردد و ریدایرکت پاک می‌شود
        MirrorPick.objects.create(product=other)
        run()
        p = MirrorLink.objects.get(source_pk=other.pk).product
        self.assertEqual((p.status, p.get_absolute_url()), ("publish", url))
        self.assertFalse(Redirect.objects.filter(source=Redirect.normalize(url)).exists())

    def test_unavailable_and_removed(self):
        from mirror.sync import run

        run()
        self.src.variations.filter(size=self.s6).update(is_available=False)
        run()
        self.assertFalse(self.mirrored().variations.get(size=self.s6).is_available)
        old = self.mirrored().get_absolute_url()
        Product.objects.filter(pk=self.src.pk).update(status="draft")
        r = run()
        self.assertEqual(r["removed"], 1)
        self.assertEqual(Product.objects.get(pk=self.mirrored().pk).status, "draft")
        self.assertEqual(Redirect.objects.get(source=Redirect.normalize(old)).target,
                         Category.objects.get(slug="carpet-700").get_absolute_url())

    def test_legacy_match_keeps_product_and_redirects(self):
        from mirror import match
        from mirror.sync import run

        legacy = Product.objects.create(title="فرش طرح زرین سیلور ۷۰۰ شانه برجسته", slug="legacy-zarin", status="publish")
        lonely = Product.objects.create(title="تابلو فرش منظره", slug="legacy-tablo", status="publish")
        # در آزمون منبع و مقصد یک دیتابیس‌اند: خوراک فقط فرش منبع و «کالای قدیمی» فقط دو محصول بالا
        MirrorPick.objects.all().delete()   # جفت کردن خودش فرش منبع را برای فرشستان انتخاب می‌کند
        src_only = mock.patch("mirror.feed.own_products", lambda picked=True: Product.objects.filter(
            pk=self.src.pk, **({"mirror_pick__isnull": False} if picked else {})))
        src_only.start()
        self.addCleanup(src_only.stop)
        with mock.patch("mirror.match.legacy_products", lambda: Product.objects.filter(pk__in=[legacy.pk, lonely.pk]).order_by("pk")):
            items = match.run(do_apply=True, out=lambda m: None)
        self.assertEqual({p.pk: (r or {}).get("id") for p, r, _w, _b in items}, {legacy.pk: self.src.pk, lonely.pk: None})
        self.assertTrue(MirrorPick.objects.filter(product=self.src, by_match=True).exists())
        run()
        legacy.refresh_from_db()
        self.assertEqual(self.mirrored().pk, legacy.pk)                # همان محصول قدیمی (نظرها و سفارش‌هایش می‌ماند)
        self.assertEqual(legacy.title, "فرش ماشینی زرین زمینه سیلور 700 شانه برجسته")
        self.assertNotEqual(legacy.slug, "legacy-zarin")
        self.assertEqual(Redirect.objects.get(source=Redirect.normalize("/product/legacy-zarin/")).target, legacy.get_absolute_url())
        lonely.refresh_from_db()
        self.assertEqual((lonely.status, lonely.sale_status), ("publish", "unavailable"))   # صفحه می‌ماند، ناموجود
        self.assertFalse(Redirect.objects.filter(source=Redirect.normalize("/product/legacy-tablo/")).exists())

    def test_orders_pushed_once_and_updated(self):
        from mirror.orders import push_all
        from mirror.sync import run

        run()
        MirrorSettings.objects.update(orders_since=timezone.now() - timezone.timedelta(days=1))
        v = self.mirrored().variations.get(size=self.s12)
        o = Order.objects.create(first_name="علی", last_name="ر", mobile="09121112233", province="تهران", city="تهران",
                                 address="x", items_total=v.price, paid_amount=v.price, status="paid")
        OrderItem.objects.create(order=o, product=v.product, variation=v, title=v.product.title, unit_price=v.price, quantity=1)
        self.assertEqual(push_all(), 1)
        self.assertEqual(push_all(), 0)
        got = Order.objects.get(src="farshestan")
        self.assertEqual(got.items.get().variation, self.src.variations.get(size=self.s12))
        self.assertEqual((got.status, got.paid_amount), ("paid", v.price))
        Order.objects.filter(pk=o.pk).update(status="shipped", tracking_code="RT123")
        self.assertEqual(push_all(), 1)
        got.refresh_from_db()
        self.assertEqual((got.status, got.tracking_code), ("shipped", "RT123"))
        self.assertEqual(Order.objects.filter(src="farshestan").count(), 1)
        self.assertEqual(MirrorOrder.objects.get(order=o).remote_ref, str(got.number))

    def test_live_check_at_checkout(self):
        from mirror.live import CHANGED, check
        from mirror.sync import run

        run()
        v = self.mirrored().variations.get(size=self.s12)
        line = SimpleNamespace(product=v.product, variation=v, unit_price=v.price, offer=None)
        self.assertIsNone(check([line]))
        self.album.set_base_price(Decimal("60000000"))
        Variation.reprice_queryset(self.src.variations.all())
        self.assertEqual(check([line]), CHANGED)
        self.assertEqual(Variation.objects.get(pk=v.pk).price, self.src.variations.get(size=self.s12).price)


class MirrorPanelTests(TestCase):
    def test_settings_tab_and_new_key(self):
        from django.contrib.auth.models import User

        u = User.objects.create_superuser("admin", "", "x")
        self.client.force_login(u)
        r = self.client.get("/panel/settings/?tab=mirror")
        self.assertContains(r, "همگام‌سازی کاتالوگ")
        self.client.post("/panel/settings/", {"tab": "mirror", "do": "mirror_key"})
        key = MirrorSettings.load().api_key
        self.assertGreater(len(key), 30)
        self.assertContains(self.client.get("/panel/settings/?tab=mirror"), key)
        self.assertEqual(self.client.get("/panel/mirror-links/").status_code, 200)
        MirrorSettings.objects.update(feed_enabled=True)
        p = Product.objects.create(title="فرش طرح آزمون", slug="t1", status="publish")
        self.assertContains(self.client.get(f"/panel/products/{p.pk}/edit/"), "در فرشستان منتشر شود")
        self.assertContains(self.client.get("/panel/products/?in_fs=0"), "ارسال به فرشستان")


class MatchKeyTests(TestCase):
    def test_keys(self):
        from mirror.match import _sim, key

        a = key({"t": "فرش طرح وینتیج ورساچه دودی - 700 شانه تمام آکریلیک"})
        b = key({"t": "فرش 700 شانه نقشه ورساچه وینتیج زمینه دودی"})
        self.assertEqual(a[:3], b[:3])                                   # ترتیب واژه‌ها مهم نیست
        self.assertEqual(key({"t": "فرش طرح ارکیده سرمه ای - 700 شانه"})[:3],
                         key({"t": "فرش ارکیده 700 شانه زمینه سرمه ای - آکریلیک", "c": "سرمه"})[:3])
        self.assertGreaterEqual(_sim(("ارم", "باغ"), ("VIP", "ارم", "باغ")), .84)
        self.assertLess(_sim(("ارم", "باغ"), ("سروناز",)), .5)
