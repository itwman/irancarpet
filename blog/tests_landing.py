from django.test import TestCase

from blog.models import Post
from installments.models import InstallmentPlan


class LiveBlockTests(TestCase):
    def test_installment_post_renders_live_blocks(self):
        InstallmentPlan.objects.all().delete()
        InstallmentPlan.objects.create(title="چک صیادی", kind="cheque", min_down_percent=30, max_months=12)
        InstallmentPlan.objects.create(title="بازنشستگان", kind="beta", min_down_percent=0, max_months=24)
        Post.objects.create(title="خرید فرش قسطی", slug="aghsat", status="publish",
                            content="<p>قیمت‌ها [price_updated]</p>\n[installment_calc]\n<p>[installment_plans]</p>\n[installment_prices]\n[installment_steps]\n[installment_faq]")
        r = self.client.get("/aghsat/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertNotIn("[installment_", html)
        self.assertIn("data-inst-calc", html)
        self.assertIn("دست‌کم ۳۰٪", html)
        self.assertIn("FAQPage", html)
        self.assertIn("شروع خرید اقساطی", html)
        self.assertIn("live-blocks.js", html)

    def test_plain_post_unchanged(self):
        Post.objects.create(title="مقاله", slug="plain", status="publish", content="<p>متن ساده</p>")
        r = self.client.get("/plain/")
        self.assertContains(r, "متن ساده")
        self.assertNotContains(r, "live-blocks.js")
