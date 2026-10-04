from django.core.management.base import BaseCommand

from farshplus.sync import run


class Command(BaseCommand):
    help = "همگام‌سازی محصولات با فرش پلاس (هر چند دقیقه با تایمر سیستم اجرا می‌شود)"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=40, help="حداکثر محصول در هر اجرا")

    def handle(self, *args, limit=40, **opts):
        n = run(limit=limit, out=lambda m: self.stdout.write(m))
        self.stdout.write(f"پایان: {n} درخواست انجام شد.")
