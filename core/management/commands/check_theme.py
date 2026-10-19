"""کدام قالب‌های ویترین در قالب سایت (SITE_THEME) نسخهٔ اختصاصی ندارند.

    python manage.py check_theme

صفحه‌های ویترین باید در هر قالب جدا ساخته شوند تا ظاهر سایت‌ها شبیه هم نشود؛ صفحه‌های کاربردی از قالب اصلی می‌آیند.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# صفحه‌هایی که ظاهر برند را می‌سازند و هر قالب باید نسخهٔ خودش را داشته باشد
SHOWCASE = [
    "base.html", "home.html", "404.html", "partials/header.html", "partials/footer.html", "partials/product_card.html",
    "catalog/product_list.html", "catalog/product_detail.html",
]


class Command(BaseCommand):
    help = "فهرست صفحه‌های ویترینی که قالب فعلی سایت نسخهٔ اختصاصی‌شان را ندارد"

    def handle(self, *args, **opts):
        theme = getattr(settings, "SITE_THEME", "")
        if not theme:
            self.stdout.write("این سایت قالب اصلی را دارد (SITE_THEME خالی است).")
            return
        tdir = Path(settings.THEME_DIR) / "templates"
        missing = [t for t in SHOWCASE if not (tdir / t).exists()]
        # صفحه‌های قالب اصلی که بعد از آخرین تغییر قالب، تغییر کرده‌اند
        stale = []
        for t in SHOWCASE:
            a, b = Path(settings.BASE_DIR) / "templates" / t, tdir / t
            if a.exists() and b.exists() and a.stat().st_mtime > b.stat().st_mtime:
                stale.append(t)
        for t in missing:
            self.stdout.write(self.style.WARNING(f"نسخهٔ قالب «{theme}» ندارد: {t}"))
        for t in stale:
            self.stdout.write(f"قالب اصلی بعد از قالب «{theme}» عوض شده؛ بررسی کنید: {t}")
        if not missing and not stale:
            self.stdout.write(self.style.SUCCESS(f"قالب «{theme}» همهٔ صفحه‌های ویترین را دارد."))
