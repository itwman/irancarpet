"""بررسی اینکه همهٔ آدرس‌های سایت قدیم در سایت جنگو کار می‌کنند.

    python manage.py check_urls --file docs/legacy-urls.txt
    python manage.py check_urls --sitemap https://irancarpet.net/sitemap_index.xml --save docs/legacy-urls.txt
"""
import re
import urllib.request
from collections import Counter
from urllib.parse import unquote, urlsplit

from django.core.management.base import BaseCommand
from django.test import Client
from django.test.utils import override_settings

LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "irancarpet-migration-check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


class Command(BaseCommand):
    help = "همهٔ آدرس‌های قدیمی را روی سایت جنگو تست می‌کند (بدون نیاز به اجرای سرور)."

    def add_arguments(self, parser):
        parser.add_argument("--file")
        parser.add_argument("--sitemap")
        parser.add_argument("--save")
        parser.add_argument("--show", type=int, default=40, help="حداکثر تعداد خطاهای نمایش داده‌شده")

    def handle(self, file=None, sitemap=None, save=None, show=40, **opts):
        urls = []
        if sitemap:
            index = fetch(sitemap)
            for sm in LOC.findall(index):
                if sm.endswith(".xml"):
                    urls += [u for u in LOC.findall(fetch(sm)) if not u.endswith((".kml", ".xml"))]
        if file:
            urls += [l.strip() for l in open(file, encoding="utf-8") if l.strip() and not l.startswith("#")]
        urls = list(dict.fromkeys(urls))
        if save:
            with open(save, "w", encoding="utf-8") as f:
                f.write("\n".join(urls) + "\n")
            self.stdout.write(f"{len(urls)} آدرس در {save} ذخیره شد")

        client = Client(HTTP_HOST="irancarpet.net", HTTP_X_FORWARDED_PROTO="https", raise_request_exception=False)
        stats, bad = Counter(), []
        import logging

        logging.getLogger("django.request").setLevel(logging.CRITICAL)
        with override_settings(ALLOWED_HOSTS=["*"], DEBUG=False):
            for i, url in enumerate(urls, 1):
                parts = urlsplit(url)
                path = unquote(parts.path) or "/"
                resp = client.get(path, secure=True)
                code = resp.status_code
                if code in (301, 302):
                    target = resp["Location"]
                    final = client.get(unquote(urlsplit(target).path), secure=True).status_code
                    stats[f"{code}→{final}"] += 1
                    if final != 200:
                        bad.append((code, url, target))
                else:
                    stats[str(code)] += 1
                    if code != 200:
                        bad.append((code, url, ""))
                if i % 500 == 0:
                    self.stdout.write(f"  {i}/{len(urls)} …")
        self.stdout.write("نتیجه: " + "، ".join(f"{k}: {v}" for k, v in stats.most_common()))
        for code, url, target in bad[:show]:
            self.stdout.write(self.style.WARNING(f"{code} {unquote(url)} {('→ ' + unquote(target)) if target else ''}"))
        if not bad:
            self.stdout.write(self.style.SUCCESS("همهٔ آدرس‌ها سالم‌اند."))
