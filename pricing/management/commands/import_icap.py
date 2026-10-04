"""انتقال قیمت‌ها از افزونهٔ «قیمت‌گذاری آلبومی ایران‌کارپت» وردپرس

    venv/bin/python manage.py import_icap --dry-run --product 4681   # فقط گزارش
    venv/bin/python manage.py import_icap                            # اعمال
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.wp.icap import import_icap
from core.wp.reader import WPReader


class Command(BaseCommand):
    help = "آلبوم‌ها و قیمت‌ها را از افزونهٔ قیمت‌گذاری آلبومی ایران‌کارپت (وردپرس) می‌خواند"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="فقط گزارش؛ چیزی ذخیره نمی‌شود")
        parser.add_argument("--product", type=int, help="نمایش قیمت‌های یک محصول نمونه (شناسهٔ پنل)")

    def handle(self, *args, dry_run=False, product=None, **kw):
        if "wp" not in settings.DATABASES:
            raise CommandError("WP_DATABASE_URL در .env تنظیم نشده است.")
        import_icap(WPReader(), log=lambda m: self.stdout.write(m), dry_run=dry_run, sample=product)
        if not dry_run:
            from dashboard.auth import clear_site_cache

            clear_site_cache()
            self.stdout.write(self.style.SUCCESS("قیمت‌ها از افزونهٔ آلبومی منتقل شد."))
