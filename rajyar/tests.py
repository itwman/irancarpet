import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from pricing.albums import sync_album_variations
from pricing.models import Album, Size, seed_sizes

from .client import RajyarError, build_payload, ping, refresh, send
from .models import RajyarPost, RajyarSettings


class Resp:
    def __init__(self, data, status=201):
        self.data, self.status = data, status

    def read(self):
        return json.dumps(self.data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RajyarTests(TestCase):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        a = Album.objects.create(name="ورژن", code="V", base_size=s["12-meter"], base_price=Decimal("45000000"))
        a.sizes.set([s["12-meter"], s["9-meter"]])
        self.p = Product.objects.create(title="فرش 1200 شانه نقشه افشان", slug="afshan", album=a, status="publish")
        sync_album_variations([self.p], reset=True)
        self.s = RajyarSettings.load()
        self.s.enabled, self.s.api_key, self.s.channels = True, "rjy_test_key", "2"
        self.s.save()

    def test_payload_and_send(self):
        body = build_payload(self.p, self.s, publish_at=timezone.now() + timezone.timedelta(hours=2))
        self.assertEqual(body["channels"], [2])
        self.assertEqual(body["external_id"], f"product-{self.p.pk}")
        self.assertIn("۱۲ متری", body["content"])
        self.assertIn("قیمت روز", body["content"])  # قیمت همیشه با تاریخ
        self.assertNotIn("<", body["content"])
        self.assertEqual(body["buttons"][0]["text"], "مشاهده و خرید")
        self.s.price_mode = "none"
        self.assertNotIn("تومان", build_payload(self.p, self.s)["content"])
        self.s.price_mode = "sizes"
        self.s.price_sizes.set(Size.objects.filter(slug="9-meter"))
        c = build_payload(self.p, self.s)["content"]
        self.assertIn("۹ متری", c)
        self.assertNotIn("۱۲ متری", c)
        self.s.price_sizes.clear()
        self.assertIn("+03:30", body["publish_at"])
        self.assertTrue(body["url"].endswith(f"/p/{self.p.pk}/"))
        self.assertRedirects(self.client.get(f"/p/{self.p.pk}/"), "/product/afshan/", status_code=301, fetch_redirect_response=False)
        with mock.patch("urllib.request.urlopen", return_value=Resp({"ok": True, "post": {"id": 12, "publications": []}})) as op:
            post = send(self.p, publish_at=timezone.now() + timezone.timedelta(hours=1))
        req = op.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer rjy_test_key")
        self.assertTrue(req.full_url.endswith("/api/v1/posts/"))
        self.assertEqual((post.remote_id, post.status), (12, "scheduled"))
        # وضعیت بعدی
        done = {"post": {"id": 12, "publications": [{"status": "published", "url": "https://t.me/irancarpet/55"}]}}
        with mock.patch("urllib.request.urlopen", return_value=Resp(done, 200)):
            self.assertEqual(refresh(), 1)
        post.refresh_from_db()
        self.assertEqual((post.status, post.links), ("published", ["https://t.me/irancarpet/55"]))

    def test_needs_channels_and_handles_errors(self):
        self.s.channels = ""
        self.s.save()
        with self.assertRaises(RajyarError):
            send(self.p)
        self.s.channels = "2"
        self.s.save()
        import urllib.error

        err = urllib.error.HTTPError("u", 401, "x", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            post = send(self.p)
        self.assertEqual(post.status, "failed")
        self.assertIn("کلید", post.error)

    def test_ping_and_panel_bulk(self):
        chans = [{"id": 1, "name": "تاروپود خبر", "platform": "telegram"}, {"id": 2, "name": "ایران کارپت", "platform": "telegram"}]
        with mock.patch("urllib.request.urlopen", return_value=Resp(chans, 200)):
            ok, msg = ping()
        self.assertTrue(ok)
        self.assertEqual(len(RajyarSettings.load().channels_cache), 2)
        u = get_user_model().objects.create_user("st", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)
        self.assertContains(self.client.get("/panel/settings/?tab=rajyar"), "تاروپود خبر")
        p2 = Product.objects.create(title="فرش دوم", slug="p2", status="publish")
        with mock.patch("urllib.request.urlopen", return_value=Resp({"post": {"id": 3}})) as op:
            r = self.client.post("/panel/products/", {"action": "rajyar", "ids": [self.p.pk, p2.pk], "action_value": "now"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(op.call_count, 2)
        bodies = [json.loads(c[0][0].data) for c in op.call_args_list]
        self.assertNotIn("publish_at", bodies[0])  # اولی فوری
        self.assertIn("publish_at", bodies[1])     # دومی با فاصله
        self.assertTrue(all(b["force_new"] for b in bodies))
        self.assertEqual(RajyarPost.objects.count(), 2)
        self.assertEqual(self.client.get("/panel/rajyar-posts/").status_code, 200)


class AutoTests(RajyarTests.__bases__[0]):
    def setUp(self):
        seed_sizes()
        s = {x.slug: x for x in Size.objects.all()}
        self.album = Album.objects.create(name="1500 شانه", code="A", base_size=s["12-meter"], base_price=Decimal("50000000"),
                                          in_price_list=True)
        self.album.sizes.set([s["12-meter"], s["9-meter"], s["6-meter"]])
        from core.models import Media, SiteSettings

        from catalog.models import Attribute, AttributeTerm

        reeds = Attribute.objects.create(slug="reeds-per-meter", label="شانه")
        pile = Attribute.objects.create(slug="pile", label="جنس نخ خاب")
        t700 = AttributeTerm.objects.create(attribute=reeds, name="700", slug="700")
        t1500 = AttributeTerm.objects.create(attribute=reeds, name="1500", slug="1500")
        acr = AttributeTerm.objects.create(attribute=pile, name="100% آکریلیک هیت ست شده با ضمانت", slug="acr")
        poly = AttributeTerm.objects.create(attribute=pile, name="پلی استر", slug="poly")
        img = Media.objects.create(file="x.jpg", title="x")
        self.products = []
        for i, terms in enumerate(([t1500, acr], [t700, acr], [t700, poly])):
            p = Product.objects.create(title=f"فرش {i}", slug=f"f{i}", album=self.album, status="publish", image=img)
            p.specs.set(terms)
            sync_album_variations([p], reset=True)
            p.refresh_price_cache()
            self.products.append(p)
        self.s = RajyarSettings.load()
        self.s.enabled, self.s.api_key, self.s.channels = True, "k", "2"
        self.s.daily_enabled, self.s.daily_times = True, "10:00, ۱۷:۰۰, 21:00"
        self.s.weekly_enabled, self.s.weekly_day = True, 1  # سه‌شنبه
        self.s.save()
        site = SiteSettings.load()
        site.phone, site.telegram_channel, site.bale_channel, site.youtube = "031-55340038", "https://t.me/irancarpet", "https://ble.ir/irancarpet", ""
        site.save()

    def ok(self):
        return mock.patch("urllib.request.urlopen", return_value=Resp({"post": {"id": 9}}))

    def at(self, h, m=5, day=6):  # ۲۰۲۶/۱۰/۰۶ سه‌شنبه
        import zoneinfo

        return timezone.datetime(2026, 10, day, h, m, tzinfo=zoneinfo.ZoneInfo("Asia/Tehran"))

    def test_footer(self):
        from .client import footer_text

        f = footer_text(self.s)
        self.assertIn("۰۳۱-۵۵۳۴۰۰۳۸", f)
        self.assertIn("کانال بله: ble.ir/irancarpet", f)
        self.assertNotIn("یوتیوب", f)
        self.assertIn("ble.ir", build_payload(self.products[0], self.s)["content"])

    def test_daily_no_repeat(self):
        from .auto import run

        self.assertEqual(self.s.daily_slots()[1].hour, 17)
        self.s.weekly_enabled = False
        self.s.save()
        with self.ok() as op:
            self.assertEqual(len(run(self.at(9))), 0)
            self.assertEqual(len(run(self.at(10))), 1)
            self.assertEqual(len(run(self.at(10, 30))), 0)       # هر نوبت یک بار
            run(self.at(17))
            run(self.at(21))
        self.assertEqual(op.call_count, 3)
        daily = RajyarPost.objects.filter(kind="daily")
        self.assertEqual(len({p.product_id for p in daily}), 3)  # سه فرش متفاوت
        with self.ok():
            post = run(self.at(10, day=7))[0]                   # دور تازه: باز هم فرش بفرستد
        self.assertIsNotNone(post.product_id)

    def test_weekly_image(self):
        from .auto import run

        with self.ok() as op:
            posts = run(self.at(10, 20))
        weekly = [p for p in posts if p.kind == "weekly"]
        self.assertEqual(len(weekly), 1)
        body = json.loads(next(c[0][0].data for c in op.call_args_list if b"pricelist-" in c[0][0].data))
        self.assertTrue(body["image_url"].endswith(".png"))
        self.assertIn("سایزهای ۱۲، ۹ و ۶ متری", body["content"])
        self.assertNotIn("میلیون", body["content"])  # عددها فقط روی تصویر
        self.assertTrue(body["url"].endswith("/carpets-price-list/"))
        with self.ok():
            self.assertFalse([p for p in run(self.at(11)) if p.kind == "weekly"])  # همان روز دوباره نه
        u = get_user_model().objects.create_user("st", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(u)
        r = self.client.get("/panel/settings/rajyar-pricelist.png")
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertContains(self.client.get("/panel/settings/?tab=rajyar"), "نوبت‌های بعدی")

    def test_groups_by_reeds_and_pile(self):
        from . import pricelist_image as P

        data, sizes = P.rows(self.s)
        self.assertEqual([n for n, _ in data], ["فرش 700 شانه پلی‌استر", "فرش 700 شانه آکریلیک", "فرش 1500 شانه آکریلیک"])
        self.assertEqual(len(sizes), 3)
        self.s.weekly_reeds = "1500"
        self.assertEqual([n for n, _ in P.rows(self.s)[0]], ["فرش 1500 شانه آکریلیک"])
        self.s.weekly_group = "album"
        self.assertEqual(len(P.rows(self.s)[0]), 1)

    def test_fallback_shaping(self):
        from . import pricelist_image as P
        from .fa_text import visual

        self.assertEqual(visual("لا"), "ﻻ")
        self.assertEqual(visual("فرش ۱۲"), "۱۲ " + "ﻕﺮﻓ"[::-1][::-1].replace("ﻕ", "ﺵ"))
        old, P.RAQM = P.RAQM, False
        try:
            self.assertTrue(P.render(self.s)[0].startswith(b"\x89PNG"))
        finally:
            P.RAQM = old
