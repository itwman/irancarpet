"""یک‌بار: تغییر قیمت آلبوم‌ها از زمان راه‌اندازی سایت جنگو را روی قیمت‌های اختصاصی محصولات هم اعمال می‌کند.

پیش از این نسخه، با تغییر قیمت آلبوم فقط محصولاتِ «بدون قیمت اختصاصی» به‌روز می‌شدند و
قیمت پایهٔ اختصاصی، قیمت خرید اختصاصی سایزها و قیمت‌های حراج ثابت می‌ماندند.

    venv/bin/python manage.py sync_album_overrides --dry-run   # فقط گزارش
    venv/bin/python manage.py sync_album_overrides             # اعمال
"""
import os
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalog.models import Product, Variation
from pricing.models import Album, PriceLog
from pricing.overrides import override_filter, scale_album_overrides

MARK = "overrides_synced"


class Command(BaseCommand):
    help = "اعمال تغییرات قبلی قیمت آلبوم‌ها روی قیمت‌های اختصاصی و حراج محصولات (یک‌بار)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="فقط گزارش، بدون تغییر")
        parser.add_argument("--since", help="از این زمان (مثلاً 2026-10-03 14:00)؛ پیش‌فرض: زمان جایگزینی سایت")
        parser.add_argument("--force", action="store_true", help="حتی اگر قبلاً اجرا شده باشد")

    def handle(self, *args, dry_run=False, since=None, force=False, **kw):
        if PriceLog.objects.filter(reason=MARK).exists() and not force:
            raise CommandError("این دستور قبلاً اجرا شده است (برای اجرای دوباره --force).")
        start = self.since(since)
        self.stdout.write(f"تغییرات قیمت آلبوم‌ها از {timezone.localtime(start):%Y-%m-%d %H:%M} بررسی می‌شود.")
        total = 0
        for album in Album.objects.order_by("name"):
            logs = list(album.logs.filter(created_at__gte=start).exclude(reason=MARK).order_by("created_at", "pk"))
            chain = []
            for lg in logs:
                if "+scaled" in lg.reason:   # از این به بعد خودکار هم‌نسبت شده
                    break
                chain.append(lg)
            if not chain or not chain[0].old_price:
                continue
            ref, target = Decimal(chain[0].old_price), Decimal(chain[-1].new_price)
            if not target or ref == target:
                continue
            ratio = target / ref
            n = Product.objects.filter(album=album).filter(override_filter("any")).distinct().count()
            self.stdout.write(f"• {album.name}: {ref:,.0f} → {target:,.0f}  (×{ratio:.4f})  — {n} محصول با قیمت اختصاصی/حراج")
            if dry_run or not n:
                continue
            p, v, s = scale_album_overrides(album, ratio, sales=True)
            Variation.reprice_queryset(Variation.objects.filter(product__album=album), scale_sale=False)
            PriceLog.objects.create(album=album, old_price=ref, new_price=target, reason=MARK)
            self.stdout.write(f"    ✔ قیمت پایهٔ اختصاصی: {p}  قیمت خرید اختصاصی: {v}  حراج: {s}")
            total += n
        if dry_run:
            self.stdout.write("فقط گزارش بود؛ چیزی تغییر نکرد.")
        else:
            from django.core.cache import cache

            for k in ("menu_categories", "site_settings", "home_data"):
                cache.delete(k)
            self.stdout.write(self.style.SUCCESS(f"تمام شد: {total} محصول به‌روز شد."))

    def since(self, value):
        if value:
            try:
                return timezone.make_aware(datetime.fromisoformat(value.strip()))
            except ValueError as e:
                raise CommandError("--since نامعتبر است؛ نمونه: 2026-10-03 14:00") from e
        f = "/root/irancarpet-last-cutover"
        if os.path.exists(f):
            return datetime.fromtimestamp(os.path.getmtime(f), tz=timezone.utc)
        raise CommandError("زمان جایگزینی سایت پیدا نشد؛ با --since مشخص کنید.")
