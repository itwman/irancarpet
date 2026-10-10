"""آزمون فرم «تماس با ما» و پاسخ پیامکی از پنل."""
import itertools
import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.test import TestCase

from blog.models import Page

from .contact import SALT
from .models import ContactMessage

_N = itertools.count()


def token(s=7, age=10):
    return signing.dumps({"s": s, "t": int(time.time()) - age, "n": next(_N)}, salt=SALT, compress=True)


class ContactTests(TestCase):
    def setUp(self):
        cache.clear()
        Page.objects.create(title="تماس", slug="contact-us", status="publish",
                            content="<p>متن</p><p>[contact_info]</p><p>[contact_form]</p>")

    def post(self, **kw):
        d = {"name": "علی رضایی", "mobile": "۰۹۱۲۱۲۳۴۵۶۷", "topic": "buy", "message": "فرش ۱۲۰۰ شانه ۹ متری می‌خواهم",
             "token": token(), "answer": "۷", "next": "/contact-us/", "website": ""}
        d.update(kw)
        return self.client.post("/contact/send/", d)

    def test_page_renders_form(self):
        html = self.client.get("/contact-us/").content.decode()
        self.assertIn('id="contact-form"', html)
        self.assertIn('name="token"', html)
        self.assertIn("پرسش امنیتی", html)

    @mock.patch("crm.notify.later")
    def test_send_ok_and_notify(self, later):
        tok = token()
        r = self.post(token=tok)
        self.assertRedirects(r, "/contact-us/#contact-form", fetch_redirect_response=False)
        m = ContactMessage.objects.get()
        self.assertEqual(m.mobile, "09121234567")
        self.assertEqual(m.status, "new")
        later.assert_called_once()
        self.assertIn("پیامتان رسید", self.client.get("/contact-us/").content.decode())
        self.post(token=tok)  # همان فرم دوباره (توکن تکراری)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_bot_traps(self):
        self.post(website="http://spam.example")
        self.post(answer="8")
        self.post(token=token(age=0))  # خیلی سریع
        self.post(token="bad")
        self.post(mobile="123")
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.post(answer="8")
        self.assertIn("جواب پرسش امنیتی درست نیست", self.client.get("/contact-us/").content.decode())

    @mock.patch("crm.notify.later")
    def test_rate_limit_per_mobile(self, later):
        for _ in range(5):
            self.post(token=token())
        self.assertEqual(ContactMessage.objects.count(), 3)

    @mock.patch("accounts.sms.send_bulk", return_value=(True, ""))
    def test_panel_reply_by_sms(self, send_bulk):
        m = ContactMessage.objects.create(name="علی", mobile="09121234567", message="سلام")
        admin = get_user_model().objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(admin)
        self.assertContains(self.client.get("/panel/contact-messages/"), "side__badge")
        self.assertContains(self.client.get(f"/panel/contact-messages/{m.pk}/"), "سلام")
        self.client.post(f"/panel/contact-messages/{m.pk}/", {"reply": "فرش موجود است.", "status": "new", "note": ""})
        m.refresh_from_db()
        self.assertEqual(m.status, "answered")
        self.assertEqual(m.reply_sent, "فرش موجود است.")
        text = send_bulk.call_args[0][1]
        self.assertTrue(text.startswith("علی عزیز، فرش موجود است."))
        self.assertTrue(text.endswith("ایران کارپت"))
        self.client.post(f"/panel/contact-messages/{m.pk}/", {"reply": "فرش موجود است.", "status": "answered", "note": "x"})
        self.assertEqual(send_bulk.call_count, 1)  # همان متن دوباره فرستاده نمی‌شود


class OtpLineFallbackTests(TestCase):
    """بدون شمارهٔ قالب کد ورود، کد با متن ساده از خط اختصاصی فرستاده می‌شود."""

    def test_line_fallback(self):
        from accounts import sms
        from shop.models import ShopSettings

        ShopSettings.objects.update_or_create(pk=1, defaults={"smsir_api_key": "KEY", "smsir_otp_template_id": "", "smsir_line_number": "9982007519"})
        self.assertTrue(sms.configured())
        self.assertEqual(sms.otp_mode(), "line")
        with mock.patch("accounts.sms._send_bulk", return_value=(True, "")) as bulk, mock.patch("accounts.sms._send_template") as tpl:
            r = self.client.post("/my-account/login/", {"action": "otp", "mobile": "09121234567"})
        self.assertEqual(r.status_code, 302)
        tpl.assert_not_called()
        self.assertIn("کد ورود شما به ایران کارپت", bulk.call_args[0][1])
        ShopSettings.objects.filter(pk=1).update(smsir_otp_template_id="100200")
        self.assertEqual(sms.otp_mode(), "template")
