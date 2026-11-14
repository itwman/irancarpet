"""پیوندهای داخلی متن‌ها که به نشانیِ ریدایرکت‌شده می‌روند، مستقیم به مقصد نهایی (بند ۴ ممیزی سئو، آبان ۱۴۰۵).

بیشترشان در توضیح فرش‌هاست (از وردپرس): «/brand/فرش-شاه-پسند/» ← «/brand/shahpasand-carpet/»، برند پاتریس،
«/product-tag/فرش-12-متری/» ← «/carpets/فرش-12-متری/» و… هر پیوند یک گام ۳۰۱ اضافه دارد که هم کند است و هم
اعتبار پیوند را کمی هدر می‌دهد. فقط نشانیِ درون href عوض می‌شود؛ متن و بقیهٔ HTML دست نمی‌خورد. پیوندی که به ۴۰۴
می‌رسد عوض نمی‌شود و فقط گزارش می‌شود.

    python manage.py fix_internal_links            # فقط گزارش
    python manage.py fix_internal_links --apply    # نوشتن
"""
import re
from collections import Counter
from urllib.parse import unquote, urlsplit

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client

FIELDS = [
    ("catalog.Product", ["content", "short_description"]),
    ("catalog.Category", ["description"]),
    ("catalog.ProductTag", ["description"]),
    ("catalog.Brand", ["description"]),
    ("catalog.AttributeTerm", ["description"]),
    ("blog.Post", ["content"]),
    ("blog.Page", ["content"]),
    ("blog.PostRewrite", ["content"]),
    ("landing.LandingPage", ["content"]),
]


def host():
    return urlsplit(settings.SITE_URL).netloc or "irancarpet.net"


def href_rx():
    h = re.escape(host().replace("www.", ""))
    return re.compile(rf'href=(["\'])((?:https?://(?:www\.)?{h})?(/[^"\'#?\s]*))([?#][^"\']*)?\1', re.I)


class Command(BaseCommand):
    help = "پیوندهای داخلی به نشانی‌های ریدایرکت‌شده را مستقیم به مقصد نهایی می‌برد (پیش‌فرض: فقط گزارش)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, apply=False, **opts):
        rx = href_rx()
        client = Client(HTTP_HOST=host(), raise_request_exception=False)  # بی User-Agent ← ربات حساب می‌شود و آمار بازدید فرش‌ها بالا نمی‌رود
        cache, dead = {}, Counter()

        def resolve(path):
            if path in cache:
                return cache[path]
            target, seen = path, set()
            for _ in range(5):
                if target in seen:
                    break
                seen.add(target)
                r = client.get(target, secure=True)
                if r.status_code in (301, 302, 308) and r.get("Location"):
                    loc = urlsplit(r["Location"])
                    if loc.netloc and loc.netloc.replace("www.", "") != host().replace("www.", ""):
                        target = None
                        break
                    target = unquote(loc.path) + (f"?{loc.query}" if loc.query else "")
                    continue
                if r.status_code != 200:
                    dead[path] += 1
                    target = None
                break
            final = target if target and unquote(target) != unquote(path) else None
            cache[path] = final
            return final

        changed_objs, changed_links, pairs = 0, 0, Counter()
        for label, fields in FIELDS:
            try:
                M = apps.get_model(label)
            except LookupError:
                continue
            qs = M.objects.all()
            for obj in qs.only("pk", *fields).iterator(chunk_size=200):
                updates = {}
                for f in fields:
                    text = getattr(obj, f) or ""
                    if "href" not in text:
                        continue
                    n = 0

                    def sub(m):
                        nonlocal n
                        quote_ch, whole, path, tail = m.group(1), m.group(2), m.group(3), m.group(4) or ""
                        if path.startswith(("//", "/media/", "/static/", "/wp-content/")):
                            return m.group(0)
                        final = resolve(unquote(path))
                        if not final:
                            return m.group(0)
                        if "?" in final and tail.startswith("?"):
                            tail = ""
                        prefix = whole[: len(whole) - len(path)]  # همان شکل (نسبی یا با دامنه)
                        new = prefix + final.replace(" ", "%20").replace('"', "%22")
                        pairs[(unquote(path), final)] += 1
                        n += 1
                        return f"href={quote_ch}{new}{tail}{quote_ch}"

                    new_text = rx.sub(sub, text)
                    if n and new_text != text:
                        updates[f] = new_text
                        changed_links += n
                if updates:
                    changed_objs += 1
                    if apply:
                        M.objects.filter(pk=obj.pk).update(**updates)  # بی save: تاریخ ویرایش و همگام‌سازی فرشستان دست نمی‌خورد
        self.stdout.write(f"نشانی یکتا بررسی‌شده: {len(cache)}")
        self.stdout.write(f"پیوند ریدایرکت‌شده: {changed_links} در {changed_objs} مورد"
                          + (" — نوشته شد" if apply else " — (فقط گزارش؛ برای نوشتن --apply)"))
        for (a, b), n in pairs.most_common(25):
            self.stdout.write(f"  {n:>5}  {a}  →  {b}")
        if dead:
            self.stdout.write(f"پیوند به صفحهٔ ناموجود (عوض نشد): {sum(dead.values())}")
            for p, n in dead.most_common(15):
                self.stdout.write(f"  {n:>5}  {p}")
