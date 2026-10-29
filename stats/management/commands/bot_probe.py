"""مقایسهٔ نشانه‌های مرورگرِ ورودهای «مستقیم» با ورودهای «گوگل» برای پیدا کردن نشانهٔ ربات‌ها.

    python manage.py bot_probe            # ۲۴ ساعت اخیر
    python manage.py bot_probe --hours 3

خروجی هیچ اطلاعات شخصی (IP، کوکی، سفارش) ندارد و می‌شود برای بررسی کپی کرد.
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.utils import timezone

from stats.models import Probe


def tbucket(t):
    for lim, lab in ((300, "<0.3s"), (1000, "<1s"), (3000, "<3s"), (10000, "<10s"), (60000, "<60s")):
        if t < lim:
            return lab
    return ">=60s"


def chk(r):
    if not r.ch:
        return "no-ch"
    num = "".join(c for c in r.ua if c.isdigit())
    if not num:
        return "ch-but-no-chrome-ua"
    return "match" if abs(int(num) - int(r.ch)) <= 1 else "MISMATCH"


FEATURES = [
    ("h", lambda r: r.h or "-"), ("ev", lambda r: r.ev or "-"), ("t", lambda r: tbucket(r.t)),
    ("ua", lambda r: r.ua), ("ch", chk), ("tz", lambda r: r.tz or "-"), ("lg", lambda r: r.lg or "-"),
    ("sc", lambda r: r.sc or "-"), ("hc", lambda r: r.hc), ("gl", lambda r: r.gl or None),
    ("home", lambda r: "home" if r.path == "/" else "inner"),
]


class Command(BaseCommand):
    help = "مقایسهٔ نشانه‌های مرورگر ورودهای مستقیم و جستجو"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--top", type=int, default=6)

    def handle(self, hours, top, **o):
        since = timezone.now() - timezone.timedelta(hours=hours)
        rows = list(Probe.objects.filter(at__gte=since))
        groups = {"direct": [r for r in rows if r.ref == "direct"], "search": [r for r in rows if r.ref == "search"]}
        self.stdout.write(f"hours={hours} total={len(rows)} direct={len(groups['direct'])} search={len(groups['search'])} "
                          f"suspect={sum(r.sus for r in rows)}")
        for name, f in FEATURES:
            self.stdout.write(f"\n== {name}")
            for g, rs in groups.items():
                vals = [v for v in (f(r) for r in rs) if v is not None]
                n = len(vals) or 1
                c = Counter(vals).most_common(top)
                self.stdout.write(f"  {g:6} " + " | ".join(f"{k}:{v * 100 // n}%" for k, v in c))
        self.stdout.write("\n== top direct inner pages")
        for p, n in Counter(r.path for r in groups["direct"]).most_common(5):
            self.stdout.write(f"  {n}  {p}")
