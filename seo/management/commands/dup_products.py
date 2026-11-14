"""فرش‌های تکراری واقعی: یک فرش با یک نام که از دورهٔ وردپرس دو نشانی دارد (مثلاً «…-2»). بند ۲ ممیزی سئو، آبان ۱۴۰۵.

هیچ فرشی حذف نمی‌شود. از هر گروه هم‌نام یکی می‌ماند (به ترتیب: سفارش بیشتر، موجود، بازدید بیشتر، نشانی بی «-2»،
قدیمی‌تر). بقیه با --apply «پیش‌نویس» می‌شوند (در پنل می‌مانند، با سفارش‌ها و عکس‌هایشان) و نشانی‌شان با ۳۰۱ به فرشی
که مانده می‌رود. برگشت: پنل ← فرش ← «منتشرشده»، و پنل ← ریدایرکت‌ها (منشأ dup_merge) ← غیرفعال.

    python manage.py dup_products            # فقط فهرست
    python manage.py dup_products --apply    # اجرا (فقط پس از تأیید فهرست)
"""
import re
from collections import defaultdict
from urllib.parse import unquote

from django.core.management.base import BaseCommand
from django.db.models import Count


def norm(title):
    t = (title or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return re.sub(r"\s+", " ", t).strip()


class Command(BaseCommand):
    help = "فهرست فرش‌های تکراری (هم‌نام با چند نشانی)؛ با --apply تکراری‌ها پیش‌نویس و ۳۰۱ می‌شوند."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, apply=False, **opts):
        from catalog.models import Product
        from seo.models import Redirect
        from shop.models import OrderItem

        groups = defaultdict(list)
        for p in Product.objects.published().select_related("album").only(
                "pk", "title", "slug", "views", "stock_status", "min_price", "album__name", "published_at"):
            groups[norm(p.title)].append(p)
        groups = {k: v for k, v in groups.items() if len(v) > 1}
        ids = [p.pk for v in groups.values() for p in v]
        orders = dict(OrderItem.objects.filter(product_id__in=ids).values_list("product_id").annotate(n=Count("pk")))

        def score(p):
            return (-orders.get(p.pk, 0), p.stock_status == "outofstock", -p.views, bool(re.search(r"-\d+/?$", p.slug)), p.pk)

        n_merge = 0
        for title, items in sorted(groups.items()):
            items.sort(key=score)
            keep, rest = items[0], items[1:]
            self.stdout.write(f"\n{title}")
            for p in items:
                tag = "می‌ماند " if p is keep else "→ ۳۰۱   "
                self.stdout.write(f"  {tag} {unquote(p.get_absolute_url())}  | سفارش {orders.get(p.pk, 0)} | بازدید {p.views}"
                                  f" | {p.stock_status} | آلبوم {p.album.name if p.album_id else '-'} | {p.min_price or 0:,}")
            if apply:
                for p in rest:
                    Product.objects.filter(pk=p.pk).update(status=Product.Status.DRAFT)
                    Redirect.objects.update_or_create(
                        source=Redirect.normalize(p.get_absolute_url()), match=Redirect.Match.EXACT,
                        defaults=dict(target=keep.get_absolute_url(), status_code=301, is_active=True, origin="dup_merge"))
            n_merge += len(rest)
        self.stdout.write(f"\nگروه تکراری: {len(groups)} — فرش‌هایی که ۳۰۱ می‌شوند: {n_merge}"
                          + (" — انجام شد" if apply else " — (فقط فهرست؛ برای اجرا --apply)"))
