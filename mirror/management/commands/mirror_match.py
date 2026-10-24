from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("فرشستان: جفت کردن کالاهای قدیمی با فرش‌های ایران کارپت (نقشه، رنگ زمینه، شانه). "
            "بدون --apply فقط گزارش می‌دهد؛ با --apply جفت‌شده‌ها وصل و بی‌جفت‌ها پیش‌نویس با ۳۰۱ می‌شوند.")

    def add_arguments(self, p):
        p.add_argument("--apply", action="store_true")

    def handle(self, *a, **o):
        from mirror.match import run

        run(do_apply=o["apply"], out=self.stdout.write)
