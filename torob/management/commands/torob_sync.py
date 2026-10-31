"""همگام‌سازی وضعیت ترب (Shop API) — از دکمهٔ پنل در پس‌زمینه یا دستی:  python manage.py torob_sync [--full]"""
from django.core.cache import cache
from django.core.management.base import BaseCommand

from torob import shopapi


class Command(BaseCommand):
    help = "خواندن وضعیت فروشگاه و محصولات از ترب و مقایسه با سایت"

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true")

    def handle(self, *args, **opts):
        try:
            shopapi.sync(full=opts["full"], out=self.stdout.write)
        except shopapi.TorobError as e:
            self.stderr.write(str(e))
        finally:
            cache.delete(shopapi.RUN_KEY)
