from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from .campaigns import _run, recipients
from .models import Profile, SmsCampaign


class SmsCampaignTests(TestCase):
    def setUp(self):
        U = get_user_model()
        for i in range(250):
            u = U.objects.create(username=f"u{i}")
            Profile.objects.create(user=u, mobile=f"0912{i:07d}")
        Profile.objects.create(user=U.objects.create(username="staff", is_staff=True), mobile="09350000000")

    def test_recipients_and_send(self):
        c = SmsCampaign.objects.create(title="t", text="سلام لغو۱۱")
        nums = recipients(c)
        self.assertEqual(len(nums), 250)
        self.assertNotIn("09350000000", nums)
        c.status = "sending"
        c.save()
        with mock.patch("accounts.sms.send_bulk", return_value=(True, "")) as m, mock.patch("accounts.campaigns.time.sleep"):
            _run(c.pk)
        self.assertEqual(m.call_count, 3)
        c.refresh_from_db()
        self.assertEqual((c.status, c.sent, c.total), ("done", 250, 250))

    def test_custom_numbers_and_failure(self):
        c = SmsCampaign.objects.create(title="t", text="x", audience="custom", custom_numbers="۰۹۱۲۱۱۱۲۲۳۳\n09121112233, 0935 999 8877\nabc")
        self.assertEqual(recipients(c), ["09121112233", "09359998877"])
        SmsCampaign.objects.filter(pk=c.pk).update(status="sending")
        with mock.patch("accounts.sms.send_bulk", return_value=(False, "اعتبار کافی نیست")), mock.patch("accounts.campaigns.time.sleep"):
            _run(c.pk)
        c.refresh_from_db()
        self.assertEqual((c.status, c.last_error), ("failed", "اعتبار کافی نیست"))

    def test_panel(self):
        U = get_user_model()
        self.client.force_login(U.objects.create_superuser("boss", "b@b.com", "x"))
        self.assertContains(self.client.get("/panel/sms/add/"), "لغو۱۱")
        r = self.client.post("/panel/sms/add/", {"title": "اپ", "text": "متن لغو۱۱", "audience": "all", "custom_numbers": ""})
        self.assertEqual(r.status_code, 302)
        c = SmsCampaign.objects.get(title="اپ")
        self.assertContains(self.client.get(f"/panel/sms/{c.pk}/"), "۲۵۰ گیرنده")
