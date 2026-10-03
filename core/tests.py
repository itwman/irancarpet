from django.test import TestCase

from core.hashers import phpass_check
from core.utils.php import php_unserialize
from core.wp.html import clean_content


class UtilTests(TestCase):
    def test_unserialize(self):
        self.assertEqual(php_unserialize('a:1:{i:0;s:7:"noindex";}'), {0: "noindex"})
        self.assertEqual(php_unserialize('a:1:{s:4:"name";s:6:"فرش";}')["name"], "فرش")

    def test_phpass(self):
        # هش نمونهٔ وردپرس برای رمز "test"
        self.assertTrue(phpass_check("test", "$P$B9bDQkmqBdPHPIQDO4T1tCWRTQtFvy1"))
        self.assertFalse(phpass_check("wrong", "$P$B9bDQkmqBdPHPIQDO4T1tCWRTQtFvy1"))

    def test_autop(self):
        self.assertEqual(clean_content("الف\n\nب"), "<p>الف</p>\n<p>ب</p>")
