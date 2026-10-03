from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.wp.importer import Importer


class Command(BaseCommand):
    help = "ایمپورت داده از دیتابیس وردپرس (WP_DATABASE_URL). قابل اجرای مکرر."

    def add_arguments(self, parser):
        parser.add_argument("--only", nargs="*", choices=Importer.STEPS, help="فقط این مراحل")
        parser.add_argument("--prefix", default="wp_", help="پیشوند جدول‌های وردپرس")

    def handle(self, *args, only=None, prefix="wp_", **opts):
        if "wp" not in settings.DATABASES:
            raise CommandError("WP_DATABASE_URL در .env تنظیم نشده است.")
        Importer(prefix=prefix, log=lambda m: self.stdout.write(m)).run(only)
        self.stdout.write(self.style.SUCCESS("ایمپورت تمام شد."))
