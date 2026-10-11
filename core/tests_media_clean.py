"""آزمون کتابخانهٔ رسانه و پاک‌سازی رسانه‌های بی‌استفاده."""
import os
import tempfile
import time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from blog.models import Post
from catalog.models import Product

from . import media_clean as mc
from .models import Media, TrashedFile

OLD = time.time() - 30 * 86400


class MediaCleanTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.media_root = Path(self.tmp.name) / "media"
        self.private = Path(self.tmp.name) / "private"
        self.ov = override_settings(MEDIA_ROOT=self.media_root, PRIVATE_ROOT=self.private)
        self.ov.enable()
        old = timezone.now() - timezone.timedelta(days=30)
        for rel in ("2020/03/used.jpg", "2020/03/inpost.jpg", "2020/03/inpost-768x1024.jpg", "2020/03/unused.jpg",
                    "2020/03/unused-300x300.jpg", "2020/03/orphan.png", "rajyar/x.png"):
            p = self.media_root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * 100)
            os.utime(p, (OLD, OLD))
        self.used = Media.objects.create(file="2020/03/used.jpg", title="used", created_at=old)
        self.inpost = Media.objects.create(file="2020/03/inpost.jpg", title="inpost", created_at=old)
        self.unused = Media.objects.create(file="2020/03/unused.jpg", title="unused", created_at=old)
        Media.objects.create(file="2020/03/new.jpg", title="new", created_at=timezone.now())
        Product.objects.create(title="فرش", slug="f", image=self.used)
        Post.objects.create(title="مقاله", slug="m", status="publish",
                            content='<p><img src="/wp-content/uploads/2020/03/inpost-768x1024.jpg"></p>')

    def tearDown(self):
        self.ov.disable()
        self.tmp.cleanup()

    def test_scan_trash_restore_purge(self):
        r = mc.scan()
        self.assertEqual([x["path"] for x in r["media"]], ["2020/03/unused.jpg"])
        orphans = {x["path"] for x in r["orphans"]}
        self.assertEqual(orphans, {"2020/03/unused-300x300.jpg", "2020/03/orphan.png"})  # نسخهٔ استفاده‌شده و rajyar نمی‌آیند
        moved, skipped = mc.trash(["2020/03/orphan.png", "2020/03/inpost-768x1024.jpg"], [self.unused.pk, self.used.pk])
        self.assertEqual((moved, skipped), (3, 2))  # همراه نسخهٔ کوچک unused-300x300
        self.assertFalse((self.media_root / "2020/03/unused-300x300.jpg").exists())
        self.assertFalse((self.media_root / "2020/03/unused.jpg").exists())
        self.assertTrue((self.private / "media-trash/2020/03/unused.jpg").exists())
        self.assertFalse(Media.objects.filter(pk=self.unused.pk).exists())
        self.assertTrue(Media.objects.filter(pk=self.used.pk).exists())
        t = TrashedFile.objects.get(path="2020/03/unused.jpg")
        self.assertEqual(mc.restore([t.pk]), 1)
        self.assertTrue((self.media_root / "2020/03/unused.jpg").exists())
        self.assertEqual(Media.objects.get(file="2020/03/unused.jpg").pk, self.unused.pk)
        TrashedFile.objects.update(trashed_at=timezone.now() - timezone.timedelta(days=31))
        self.assertEqual(mc.purge(), 2)
        self.assertFalse((self.private / "media-trash/2020/03/orphan.png").exists())

    def test_panel_pages_and_library(self):
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        mc._write_state({"done": time.time(), **mc.scan()})
        for tab in ("media", "orphans", "trash"):
            self.assertEqual(self.client.get("/panel/media/unused/", {"tab": tab}).status_code, 200)
        r = self.client.post("/panel/media/unused/", {"do": "trash", "media": [self.unused.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(TrashedFile.objects.count(), 2)  # همراه نسخهٔ کوچک
        j = self.client.get("/panel/media/library/", {"q": "inpost"}).json()
        self.assertEqual([x["value"] for x in j["items"]], [str(self.inpost.pk)])
        self.assertIn("/app-img/240/", j["items"][0]["thumb"])
