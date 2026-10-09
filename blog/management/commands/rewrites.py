"""بازنویسی مقاله‌ها:
    manage.py rewrites                  ← متن‌های پوشهٔ content/rewrites همین مخزن را وارد می‌کند (update.sh)
    manage.py rewrites --github         ← دریافت از گیت‌هاب
    manage.py rewrites --publish        ← انتشار نوبت امروز (اگر وقتش رسیده)
    manage.py rewrites --gsc Pages.csv  ← آمار سرچ کنسول
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from blog import rewrite


class Command(BaseCommand):
    help = "صف بازنویسی مقاله‌ها"

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=str(Path(settings.BASE_DIR) / "content" / "rewrites"))
        parser.add_argument("--github", action="store_true")
        parser.add_argument("--publish", action="store_true")
        parser.add_argument("--gsc")

    def handle(self, *args, **o):
        if o["gsc"]:
            self.stdout.write(f"آمار {rewrite.load_gsc_csv(open(o['gsc'], encoding='utf-8-sig').read())} مقاله به‌روز شد")
        if o["github"]:
            for k, v in rewrite.sync_github(force=True).items():
                self.stdout.write(f"{k}: {v}")
        elif not o["publish"]:
            for k, v in rewrite.import_dir(o["dir"]).items():
                self.stdout.write(f"{k}: {v}")
        if o["publish"]:
            self.stdout.write(f"منتشر شد: {rewrite.publish_due()}")
