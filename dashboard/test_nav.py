"""منوی کناری پنل: همهٔ بخش‌ها جایی دارند، یک مورد فعال، بدون تکرار."""
from django.test import RequestFactory, SimpleTestCase

from dashboard import resources  # noqa: F401  ثبت بخش‌ها
from dashboard.nav import LAYOUT
from dashboard.registry import REGISTRY
from dashboard.templatetags.panel import panel_nav


def nav(path):
    return panel_nav({"request": RequestFactory().get(path)})


class PanelNavTests(SimpleTestCase):
    databases = "__all__"

    def test_every_resource_is_placed_once(self):
        keys = [r if isinstance(r, str) else r[1] for _, _, rows in LAYOUT for r in rows
                if isinstance(r, str) or (r[0] != "#" and not r[1].startswith("/"))]
        self.assertEqual(len(keys), len(set(keys)), "بخش تکراری در منو")
        missing = {k for k, r in REGISTRY.items() if r.nav} - set(keys)
        self.assertFalse(missing, f"این بخش‌ها در dashboard/nav.py جایی ندارند: {missing}")
        self.assertNotIn("سایر", [g["title"] for g in nav("/panel/")])

    def test_single_active_item(self):
        for path, title in [("/panel/products/quick/", "افزودن سریع فرش‌های آلبوم"), ("/panel/products/12/", "محصولات"),
                            ("/panel/customers/?is_staff=1", "کارمندان"), ("/panel/customers/", "مشتریان"),
                            ("/panel/settings/?tab=market", "تنظیمات مارکت‌پلیس"), ("/panel/settings/", "تنظیمات سایت، درگاه و پیامک")]:
            act = [i["title"] for g in nav(path) for i in g["items"] if i.get("active")]
            self.assertEqual(act, [title], path)
