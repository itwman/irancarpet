from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "کارهای دوره‌ای فروش: یادآوری پرداخت، خبرم کن، دعوت به نظر، صفحه‌های فرود (هر ۱۰ دقیقه با systemd)"

    def add_arguments(self, parser):
        parser.add_argument("--landing", action="store_true", help="فقط به‌روزرسانی صفحه‌های فرود")

    def handle(self, *args, **opts):
        if opts["landing"]:
            from landing.build import sync

            sync(log=self.stdout.write)
            return
        from growth.jobs import run_all

        run_all(out=self.stdout.write)
