"""آزمون صف بازنویسی مقاله‌ها."""
import base64
import json
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from seo.models import SeoSettings

from . import rewrite
from .models import Post, PostRewrite
from .rewrite_rules import check

S = PostRewrite.Status
LONG = " ".join(["فرش ماشینی کاشان با نخ اکریلیک و تراکم بالا"] * 120)


def sample(slug="خرید-فرش-در-گرگان", **kw):
    d = {"slug": slug, "title": "خرید فرش در گرگان مستقیم از کارخانه کاشان",
         "seo_title": "خرید فرش در گرگان؛ ارسال مستقیم از کارخانه‌های کاشان",
         "seo_description": "خرید فرش ماشینی در گرگان بدون واسطه از کاشان: قیمت روز، ارسال، پرداخت بیعانه یا اقساط و پاسخ پرسش‌های رایج خریداران گرگانی.",
         "focus_keyword": "خرید فرش در گرگان", "excerpt": "راهنمای کامل خرید فرش ماشینی در گرگان با ارسال مستقیم از کاشان.",
         "content": (f"<p>{LONG}</p><h2>چرا از کاشان</h2><p>متن</p><h2>ارسال</h2><p>[shipping_info گرگان]</p>"
                     '<h2>پرسش‌ها</h2><div class="faq"><details><summary>ارسال چند روز است؟</summary><p>حدود ۱۴ روز کاری.</p></details>'
                     '<details><summary>اقساط دارید؟</summary><p>بله.</p></details><details><summary>بیعانه؟</summary><p>بله.</p></details></div>'
                     '<p><a href="/carpets-price-list/">لیست قیمت</a> <a href="/blog/">مجله</a> <a href="/">ایران کارپت</a></p>'),
         "notes": "آزمایشی"}
    d.update(kw)
    return d


class RulesTests(TestCase):
    def test_ok(self):
        errors, warns = check(sample())
        self.assertEqual(errors, [])

    def test_errors(self):
        bad = sample(content=sample()["content"] + "<p>با شهر فرش تماس بگیرید: ۰۹۱۲۱۱۱۲۲۳۳ [foo]</p><div>")
        errors, _ = check(bad)
        txt = " ".join(errors)
        for part in ("شهر فرش", "09121112233", "[foo]", "<div>"):
            self.assertIn(part, txt)
        self.assertTrue(any("کوتاه" in e for e in check(sample(content="<h2>a</h2><p>کم</p>"))[0]))
        self.assertTrue(any("خودش" in e for e in check(sample(content=sample()["content"] + '<a href="/خرید-فرش-در-گرگان/">x</a>'))[0]))
        self.assertTrue(any("ناموجود" in e for e in check(sample(), known_urls={"/"}, kind="city")[0]))
        self.assertEqual(check({"slug": "x", "action": "skip", "skip_reason": "نامرتبط"}), ([], []))
        self.assertTrue(check({"slug": "x", "action": "skip"})[0])
        self.assertEqual(check(sample(content=sample()["content"] + "<p>۰۹۱۲۵۳۴۷۵۹۶</p>"))[0], [])


@override_settings(STAGING=True)
class RewriteFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.post = Post.objects.create(title="خرید فرش در گرگان", slug="خرید-فرش-در-گرگان", content="<p>متن قدیمی [city_faq گرگان]</p>",
                                        seo_title="قدیمی", status="publish")
        Post.objects.create(title="دیگر", slug="دیگر", content="<p>x</p>", status="publish")

    def test_plan_import_publish_and_rollback(self):
        rewrite.load_plan([{"rank": 3, "slug": self.post.slug, "kind": "city", "reason": "صفحهٔ اول", "keyword": "خرید فرش در گرگان"},
                           {"rank": 1, "slug": "ناموجود"}])
        rw = PostRewrite.objects.get()
        self.assertEqual((rw.rank, rw.status), (3, S.QUEUED))
        self.assertEqual(rewrite.import_data(sample(), "sha1"), "آماده")
        self.assertEqual(rewrite.import_data(sample(), "sha1"), "تکراری")
        rw.refresh_from_db()
        self.assertEqual(rw.status, S.READY)
        self.assertIn("city_faq", rw.warnings)  # بلوک زندهٔ قبلی گم شده
        self.assertAlmostEqual((rw.publish_after - rw.ready_at).days, 2)
        now = timezone.localtime().replace(hour=10, minute=0)
        self.assertEqual(rewrite.publish_due(now), 0)  # هنوز در مهلت بررسی
        later = now + timezone.timedelta(days=3)
        self.assertEqual(rewrite.publish_due(later.replace(hour=7)), 0)  # پیش از ساعت انتشار
        with mock.patch("django.utils.timezone.now", return_value=later):
            self.assertEqual(rewrite.publish_due(later), 1)
            self.assertEqual(rewrite.publish_due(later), 0)  # روزی یکی
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "خرید فرش در گرگان مستقیم از کارخانه کاشان")
        rw.refresh_from_db()
        self.assertEqual((rw.status, rw.old["seo_title"]), (S.PUBLISHED, "قدیمی"))
        page = self.client.get(self.post.get_absolute_url())
        self.assertContains(page, "FAQPage")
        self.assertContains(page, "ارسال چند روز است؟")
        self.assertTrue(rewrite.rollback(rw))
        self.post.refresh_from_db()
        self.assertEqual((self.post.seo_title, self.post.title), ("قدیمی", "خرید فرش در گرگان"))

    def test_errors_keep_queued_and_skip(self):
        self.assertIn("خطا", rewrite.import_data(sample(content="<p>شهر فرش</p>"), "a"))
        rw = PostRewrite.objects.get()
        self.assertEqual(rw.status, S.QUEUED)
        self.assertIn("خطا:", rw.warnings)
        rewrite.import_data({"slug": self.post.slug, "action": "skip", "skip_reason": "نامرتبط"}, "b")
        rw.refresh_from_db()
        self.assertEqual(rw.status, S.SKIPPED)

    def test_approved_goes_first(self):
        other = Post.objects.get(slug="دیگر")
        rewrite.import_data(sample(), "a")
        rewrite.import_data(sample(slug="دیگر"), "b")
        PostRewrite.objects.filter(post=other).update(status=S.APPROVED, rank=99)
        t = timezone.localtime().replace(hour=12)
        with mock.patch("django.utils.timezone.now", return_value=t):
            self.assertEqual(rewrite.publish_due(t), 1)
        self.assertEqual(PostRewrite.objects.get(status=S.PUBLISHED).post, other)

    def test_schedule_matches_rules(self):
        """برآورد زمان انتشار: پس از مهلت بررسی، روزانه به تعداد تنظیم‌شده و به ترتیب اولویت."""
        SeoSettings.objects.update_or_create(pk=1, defaults={"rewrite_per_day": 2, "rewrite_hour": 9, "rewrite_review_days": 2})
        rewrite.import_data(sample(), "a")
        rewrite.import_data(sample(slug="دیگر"), "b")
        third = Post.objects.create(title="سوم", slug="سوم", content="<p>متن قدیمی</p>", status="publish")
        rewrite.import_data(sample(slug="سوم"), "c")
        PostRewrite.objects.filter(post__slug="خرید-فرش-در-گرگان").update(rank=1)
        PostRewrite.objects.filter(post__slug="دیگر").update(rank=2)
        PostRewrite.objects.filter(post=third).update(rank=3)
        base = timezone.localtime().replace(hour=8, minute=0, second=0, microsecond=0)
        PostRewrite.objects.update(publish_after=base + timezone.timedelta(days=2, hours=7))  # روز سوم ساعت ۱۵
        plan = rewrite.schedule(base)
        by = {r.post.slug: plan[r.pk] for r in PostRewrite.objects.select_related("post")}
        self.assertEqual(by["خرید-فرش-در-گرگان"], base + timezone.timedelta(days=2, hours=7))
        self.assertEqual(by["دیگر"], base + timezone.timedelta(days=2, hours=7))
        self.assertEqual(by["سوم"], base + timezone.timedelta(days=3, hours=1))  # روز بعد ساعت ۹
        PostRewrite.objects.filter(post=third).update(status=S.APPROVED)
        self.assertEqual(rewrite.schedule(base)[PostRewrite.objects.get(post=third).pk], base + timezone.timedelta(hours=1))

    def test_import_dir_and_github_and_gsc(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "posts"))
        json.dump([{"rank": 1, "slug": self.post.slug, "kind": "city"}], open(os.path.join(d, "plan.json"), "w"))
        json.dump(sample(), open(os.path.join(d, "posts", "0001.json"), "w"), ensure_ascii=False)
        out = rewrite.import_dir(d)
        self.assertEqual((out["plan"], out["0001.json"]), (1, "آماده"))
        self.assertEqual(rewrite.import_dir(d), {})
        # گیت‌هاب
        PostRewrite.objects.all().delete()
        cache.clear()
        raw = json.dumps(sample(), ensure_ascii=False).encode()

        def gh(url):
            if url.endswith("/posts?ref=main"):
                return [{"name": "0001.json", "sha": "s1", "url": "U1"}]
            if url == "U1":
                return {"content": base64.b64encode(raw).decode()}
            return []
        with mock.patch("blog.rewrite._gh", side_effect=gh):
            self.assertEqual(rewrite.sync_github(force=True), {"0001.json": "آماده"})
            self.assertEqual(rewrite.sync_github(force=True), {})
        self.assertIn("درست", SeoSettings.load().rewrite_last_status)
        with mock.patch("blog.rewrite._gh", side_effect=OSError("blocked")):
            rewrite.sync_github(force=True)
        self.assertIn("update.sh", SeoSettings.load().rewrite_last_status)
        csv = "Top pages,Clicks,Impressions,CTR,Position\nhttps://irancarpet.net/%D8%AE%D8%B1%DB%8C%D8%AF-%D9%81%D8%B1%D8%B4-%D8%AF%D8%B1-%DA%AF%D8%B1%DA%AF%D8%A7%D9%86/,167,9908,1.69%,5.8\n"
        self.assertEqual(rewrite.load_gsc_csv(csv), 1)
        rw = PostRewrite.objects.get()
        self.assertEqual((rw.gsc_clicks, rw.gsc_impressions, rw.gsc_position), (167, 9908, 5.8))

    def test_panel(self):
        admin = get_user_model().objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(admin)
        rewrite.import_data(sample(), "a")
        rw = PostRewrite.objects.get()
        for url in ["/panel/rewrites/", f"/panel/rewrites/{rw.pk}/", f"/panel/rewrites/{rw.pk}/preview/", "/panel/settings/?tab=seo"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(f"/panel/rewrites/{rw.pk}/preview/"), "مستقیم از کارخانه کاشان")
        self.client.post("/panel/rewrites/", {"action": "publish_now", "ids": [rw.pk]})
        rw.refresh_from_db()
        self.assertEqual(rw.status, S.PUBLISHED)
        self.assertContains(self.client.get(f"/panel/rewrites/{rw.pk}/preview/?old=1"), "متن قدیمی")


@override_settings(STAGING=True)
class MergeAndNewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.main = Post.objects.create(title="قیمت فرش ماشینی", slug="قیمت-فرش-ماشینی", content="<p>قدیمی</p>", status="publish")
        self.dup = Post.objects.create(title="قیمت انواع فرش ماشینی", slug="قیمت-انواع-فرش-ماشینی", content="<p>تکراری</p>", status="publish")

    def test_merge_follows_target_publish_and_rollback(self):
        from seo.models import Redirect

        rewrite.load_plan([{"rank": 1, "slug": self.main.slug, "kind": "price"},
                           {"rank": 2, "slug": self.dup.slug, "kind": "merge", "merge_into": "/قیمت-فرش-ماشینی/"}])
        m = PostRewrite.objects.get(post=self.dup)
        self.assertEqual((m.status, m.merge_into), (S.READY, "/قیمت-فرش-ماشینی/"))
        t = timezone.localtime().replace(hour=12)
        with mock.patch("django.utils.timezone.now", return_value=t):
            self.assertEqual(rewrite.publish_due(t), 0)  # مقصد هنوز منتشر نشده؛ ادغام صبر می‌کند
        m.refresh_from_db()
        self.assertEqual(m.status, S.READY)
        rewrite.import_data(sample(slug=self.main.slug), "x")
        main = PostRewrite.objects.get(post=self.main)
        self.assertTrue(rewrite.publish(main))
        m.refresh_from_db()
        self.dup.refresh_from_db()
        self.assertEqual((m.status, self.dup.status), (S.MERGED, "draft"))
        r = Redirect.objects.get(source=self.dup.slug)
        self.assertEqual(r.target, "/قیمت-فرش-ماشینی/")
        resp = self.client.get(self.dup.get_absolute_url())
        self.assertEqual(resp.status_code, 301)
        self.assertTrue(rewrite.rollback(m))
        self.dup.refresh_from_db()
        self.assertEqual(self.dup.status, "publish")
        self.assertFalse(Redirect.objects.filter(source=self.dup.slug).exists())

    def test_new_article(self):
        data = sample(slug="فرش-موکا", title="فرش موکا؛ رنگ گرم سال برای خانه‌های امروزی", new=True)
        self.assertEqual(rewrite.import_data(data, "n1"), "آماده")
        p = Post.objects.get(slug="فرش-موکا")
        self.assertEqual(p.status, "draft")
        self.assertEqual(self.client.get("/فرش-موکا/").status_code, 404)
        rw = PostRewrite.objects.get(post=p)
        self.assertTrue(rewrite.publish(rw))
        p.refresh_from_db()
        self.assertEqual(p.status, "publish")
        self.assertEqual(self.client.get("/فرش-موکا/").status_code, 200)
