"""فرش‌های تکراری واقعی: یک فرش با یک نام که از دورهٔ وردپرس دو نشانی دارد (مثلاً «…-2»). بند ۲ ممیزی سئو، آبان ۱۴۰۵.

هیچ فرشی حذف نمی‌شود. فرش‌های هم‌نامِ یک آلبوم (یا بی‌آلبوم) تکراری‌اند: یکی می‌ماند (به ترتیب: موجود، سفارش بیشتر،
بازدید بیشتر، نشانی بی «-2»، قدیمی‌تر) و بقیه با --apply «پیش‌نویس» می‌شوند (در پنل می‌مانند، با سفارش‌ها و عکس‌هایشان) و نشانی‌شان با ۳۰۱ به فرشی
که مانده می‌رود. هم‌نام‌های دو آلبوم/کارخانهٔ مختلف دو فرش واقعی‌اند: هر دو می‌مانند و فقط عنوان سئوی جدا (با نام
برند یا آلبوم) می‌گیرند. برگشت: پنل ← فرش ← «منتشرشده»، و پنل ← ریدایرکت‌ها (منشأ dup_merge) ← غیرفعال.

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


def label_of(p, brands, keepers):
    """برای عنوان جدا: نام برند اگر برندها فرق دارند، وگرنه نام آلبوم بی «۷۰۰ شانه ساده» تکراری («آلبوم مهر»)."""
    if len(brands) == len(keepers) and p.brand_id:
        return p.brand.name
    if p.album_id:
        return re.sub(r"^\s*\d+\s*شانه\s*(?:ساده|برجسته|گل برجسته)?\s*", "", p.album.name).strip(" -") or p.album.name
    return ""


class Command(BaseCommand):
    help = "فهرست فرش‌های تکراری (هم‌نام با چند نشانی)؛ با --apply تکراری‌ها پیش‌نویس و ۳۰۱ می‌شوند."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, apply=False, **opts):
        from catalog.models import Product
        from seo.models import Redirect
        from shop.models import OrderItem

        groups = defaultdict(list)
        for p in Product.objects.published().select_related("album", "brand").only(
                "pk", "title", "slug", "views", "stock_status", "min_price", "album__name", "brand__name", "published_at",
                "seo_title"):
            groups[norm(p.title)].append(p)
        groups = {k: v for k, v in groups.items() if len(v) > 1}
        ids = [p.pk for v in groups.values() for p in v]
        orders = dict(OrderItem.objects.filter(product_id__in=ids).values_list("product_id").annotate(n=Count("pk")))

        def score(p):  # موجود، سفارش بیشتر، بازدید بیشتر، نشانی بی «-2»، قدیمی‌تر
            return (p.stock_status == "outofstock", -orders.get(p.pk, 0), -p.views, bool(re.search(r"-\d+/?$", p.slug)), p.pk)

        def line(p, tag):
            return (f"  {tag} {unquote(p.get_absolute_url())}  | سفارش {orders.get(p.pk, 0)} | بازدید {p.views}"
                    f" | {p.stock_status} | آلبوم {p.album.name if p.album_id else '-'} | {p.min_price or 0:,}")

        n_merge = n_split = 0
        for title, items in sorted(groups.items()):
            items.sort(key=score)
            # یک نقشه از دو کارخانه/آلبوم دو فرش متفاوت است (قیمت و کیفیت جدا): ادغام نمی‌شوند، عنوان سئوی جدا می‌گیرند.
            by_album = defaultdict(list)
            for p in items:
                if p.album_id:
                    by_album[p.album_id].append(p)
            keepers = [v[0] for v in by_album.values()] or [items[0]]
            keepers.sort(key=score)
            moves = {}
            for p in items:
                if p in keepers:
                    continue
                same = [k for k in keepers if k.album_id == p.album_id and p.album_id]
                moves[p.pk] = same[0] if same else keepers[0]  # فرش قدیمیِ بی‌آلبوم ← بهترین فرش زندهٔ همان نام
            self.stdout.write(f"\n{title}")
            split = len(keepers) > 1
            brands = {k.brand_id for k in keepers}
            for p in items:
                if p.pk in moves:
                    self.stdout.write(line(p, "→ ۳۰۱   ") + f"  ⇐ به {unquote(moves[p.pk].get_absolute_url())}" if split else line(p, "→ ۳۰۱   "))
                else:
                    label = label_of(p, brands, keepers)
                    self.stdout.write(line(p, "می‌ماند ") + (f"  [عنوان جدا: «{p.title} | {label}»]" if split and label else ""))
            if apply:
                for p in items:
                    if p.pk in moves:
                        k = moves[p.pk]
                        Product.objects.filter(pk=p.pk).update(status=Product.Status.DRAFT)
                        Redirect.objects.update_or_create(
                            source=Redirect.normalize(p.get_absolute_url()), match=Redirect.Match.EXACT,
                            defaults=dict(target=k.get_absolute_url(), status_code=301, is_active=True, origin="dup_merge"))
                    elif split:
                        label = label_of(p, brands, keepers)
                        if label:
                            Product.objects.filter(pk=p.pk).update(seo_title=f"{p.title} | {label}")
            n_merge += len(moves)
            n_split += len(keepers) if split else 0
        self.stdout.write(f"\nگروه هم‌نام: {len(groups)} — فرش تکراری که ۳۰۱ می‌شود: {n_merge}"
                          f" — فرش هم‌نامِ آلبوم جدا که فقط عنوان جدا می‌گیرد: {n_split}"
                          + (" — انجام شد" if apply else " — (فقط فهرست؛ برای اجرا --apply)"))
