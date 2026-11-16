"""فرش‌های «مرده» از دورهٔ وردپرس: بی‌آلبوم (قیمت ندارند)، ناموجود، بی‌سفارش و کم‌بازدید. آبان ۱۴۰۵.

گوگل ۴٬۶۴۰ فرش را «پیدا کرده ولی ایندکس نکرده»؛ بخش بزرگی همین صفحه‌های بی‌قیمت و ناموجودند که سهم خزیدن را
از فرش‌های قابل خرید می‌گیرند. هیچ فرشی حذف نمی‌شود: با --apply «پیش‌نویس» می‌شود (در پنل می‌ماند) و نشانی‌اش با ۳۰۱
به نزدیک‌ترین فرش زنده می‌رود: همان نقشه و شانه و رنگ ← همان نقشه و شانه ← همان نقشه ← دستهٔ اصلی خودش.
برگشت: پنل ← فرش ← «منتشرشده»، و پنل ← ریدایرکت‌ها (منشأ dead_merge) ← غیرفعال.

    python manage.py dead_products                    # فقط گزارش (پیش‌فرض: بازدید تا ۱۰۰)
    python manage.py dead_products --max-views 50
    python manage.py dead_products --apply            # اجرا (فقط پس از تأیید گزارش)
"""
import re
from collections import Counter, defaultdict
from urllib.parse import unquote

from django.core.management.base import BaseCommand
from django.db.models import Prefetch


def _n(s):
    s = (s or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return re.sub(r"\s+", " ", s).strip()


def reeds_of(title):
    m = re.search(r"([0-9۰-۹]{3,4})\s*شانه", title or "")
    return m.group(1).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if m else ""


class Command(BaseCommand):
    help = "فهرست فرش‌های بی‌آلبوم، ناموجود و بی‌سفارش؛ با --apply پیش‌نویس و ۳۰۱ به نزدیک‌ترین فرش زنده."

    def add_arguments(self, parser):
        parser.add_argument("--max-views", type=int, default=100)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--show", type=int, default=40, help="چند نمونه چاپ شود")

    def handle(self, max_views=100, apply=False, show=40, **opts):
        from catalog.models import AttributeTerm, Product
        from content.render import color_of, design_of
        from seo.models import Redirect
        from shop.models import OrderItem

        specs = Prefetch("specs", queryset=AttributeTerm.objects.select_related("attribute"))
        pub = Product.objects.published()
        dead_qs = pub.filter(album__isnull=True, stock_status="outofstock").select_related("primary_category").prefetch_related(specs)
        mirrored = dead_qs.filter(mirror_pick__isnull=False).count()
        dead_qs = dead_qs.filter(mirror_pick__isnull=True)  # فرشی که برای فرشستان انتخاب شده دست نمی‌خورد
        ordered = set(OrderItem.objects.filter(product__in=dead_qs).values_list("product_id", flat=True))
        live = list(pub.filter(album__isnull=False).exclude(stock_status="outofstock").prefetch_related(specs)
                    .only("pk", "title", "slug", "design_name", "views"))
        index = defaultdict(list)
        for p in live:
            index[_n(design_of(p))].append(p)
        for v in index.values():
            v.sort(key=lambda x: -x.views)

        kept_orders = kept_views = 0
        buckets = Counter()
        views_hist = Counter()
        rows = []
        for p in dead_qs.iterator(chunk_size=500):
            if p.pk in ordered:
                kept_orders += 1
                continue
            if p.views > max_views:
                kept_views += 1
                continue
            views_hist["۰" if p.views == 0 else "۱–۱۰" if p.views <= 10 else "۱۱–۵۰" if p.views <= 50 else "۵۱+"] += 1
            d, r, c = _n(design_of(p)), reeds_of(p.title), _n(color_of(p))
            cands = index.get(d, []) if d else []
            target, how = None, ""
            for test, label in ((lambda x: reeds_of(x.title) == r and _n(color_of(x)) == c, "همان نقشه، شانه و رنگ"),
                                (lambda x: reeds_of(x.title) == r, "همان نقشه و شانه"),
                                (lambda x: True, "همان نقشه")):
                hit = next((x for x in cands if test(x)), None)
                if hit:
                    target, how = hit.get_absolute_url(), label
                    break
            if not target and p.primary_category_id:
                target, how = p.primary_category.get_absolute_url(), "دستهٔ اصلی"
            if not target:
                buckets["بی‌مقصد (دست نمی‌خورد)"] += 1
                continue
            buckets[how] += 1
            rows.append((p, target, how))

        self.stdout.write(f"فرش منتشرشدهٔ بی‌آلبوم و ناموجود: {kept_orders + kept_views + sum(buckets.values())}")
        self.stdout.write(f"  می‌ماند چون سفارش دارد: {kept_orders} — چون بیش از {max_views} بازدید دارد: {kept_views}"
                          f" — چون برای فرشستان انتخاب شده: {mirrored}")
        self.stdout.write("  بازدید فرش‌های مرده: " + "، ".join(f"{k}: {v}" for k, v in views_hist.items()))
        self.stdout.write("مقصد ۳۰۱:")
        for k, v in buckets.most_common():
            self.stdout.write(f"  {v:>5}  {k}")
        self.stdout.write(f"\nنمونه‌ها ({min(show, len(rows))} از {len(rows)}):")
        for p, t, how in rows[:show]:
            self.stdout.write(f"  {unquote(p.get_absolute_url())}  (بازدید {p.views})\n      → {unquote(t)}  [{how}]")
        if apply:
            for p, t, how in rows:
                Product.objects.filter(pk=p.pk).update(status=Product.Status.DRAFT)
                Redirect.objects.update_or_create(
                    source=Redirect.normalize(p.get_absolute_url()), match=Redirect.Match.EXACT,
                    defaults=dict(target=t, status_code=301, is_active=True, origin="dead_merge"))
        self.stdout.write(f"\nفرش‌هایی که ۳۰۱ می‌شوند: {len(rows)}" + (" — انجام شد" if apply else " — (فقط گزارش؛ برای اجرا --apply)"))
