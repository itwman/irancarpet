"""آنچه API نسخهٔ ۳ برای یک فرش به ترب می‌دهد:  python manage.py torob_api_preview <page_unique یا نشانی>  [--log]"""
import json

from django.core.management.base import BaseCommand

from torob import api_v3


class Command(BaseCommand):
    help = "پیش‌نمایش پاسخ Torob API v3 برای یک فرش، و ۳۰ درخواست آخر ترب"

    def add_arguments(self, parser):
        parser.add_argument("ref", nargs="?", default="")
        parser.add_argument("--log", action="store_true", help="درخواست‌های اخیر ترب")

    def handle(self, ref, **opts):
        if opts["log"] or not ref:
            for r in api_v3.recent_requests():
                self.stdout.write(f"{r['at'][:19]}  {r['kind']:<6} {r['n']:>3}  {r['body']}  → {', '.join(r['uniques'])}")
        if ref:
            self.stdout.write(json.dumps(api_v3.preview(ref), ensure_ascii=False, indent=1))
