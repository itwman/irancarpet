"""خلاصهٔ شبانه: Hit های هر روز ← جدول‌های روزانه؛ ریزهای کهنه‌تر از RETENTION_DAYS پاک می‌شوند."""
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import RETENTION_DAYS, DailyPage, DailyProduct, DailyStat, DailyTotal, Hit, RolledDay

log = logging.getLogger(__name__)
TOP_PAGES = 1500  # صفحه‌های کم‌بازدیدتر هر روز در خلاصه نگه داشته نمی‌شوند (ریزشان تا پاک شدن هست)
V, C, O = Q(kind="v"), Q(kind="c"), Q(kind="o")


@transaction.atomic
def roll_day(day):
    qs = Hit.objects.filter(day=day)
    DailyTotal.objects.filter(day=day).delete()
    DailyStat.objects.filter(day=day).delete()
    DailyPage.objects.filter(day=day).delete()
    DailyProduct.objects.filter(day=day).delete()
    t = qs.aggregate(views=Count("pk", filter=V), visits=Count("pk", filter=V & Q(entry=True)),
                     visitors=Count("visitor", filter=V, distinct=True), new=Count("visitor", filter=V & Q(new=True), distinct=True),
                     mobile=Count("pk", filter=V & Q(device="m")), carts=Count("pk", filter=C), orders=Count("pk", filter=O))
    DailyTotal.objects.create(day=day, views=t["views"], visits=t["visits"], visitors=t["visitors"], new_visitors=t["new"],
                              mobile=t["mobile"], carts=t["carts"], orders=t["orders"])
    rows = (qs.values("src", "src_name", "medium", "utm_campaign", "campaign_id")
            .annotate(views=Count("pk", filter=V), visits=Count("pk", filter=V & Q(entry=True)),
                      visitors=Count("visitor", filter=V, distinct=True), carts=Count("pk", filter=C), orders=Count("pk", filter=O)))
    DailyStat.objects.bulk_create([DailyStat(day=day, src=r["src"], src_name=r["src_name"], medium=r["medium"],
                                             utm_campaign=r["utm_campaign"], campaign_id=r["campaign_id"] or 0, views=r["views"],
                                             visits=r["visits"], visitors=r["visitors"], carts=r["carts"], orders=r["orders"])
                                   for r in rows])
    pages = (qs.filter(V).values("path").annotate(views=Count("pk"), visitors=Count("visitor", distinct=True),
                                                  entries=Count("pk", filter=Q(entry=True))).order_by("-views")[:TOP_PAGES])
    DailyPage.objects.bulk_create([DailyPage(day=day, **p) for p in pages], batch_size=500)
    prods = (qs.exclude(product_id=None).values("product_id")
             .annotate(views=Count("pk", filter=V), visitors=Count("visitor", filter=V, distinct=True), carts=Count("pk", filter=C)))
    DailyProduct.objects.bulk_create([DailyProduct(day=day, **p) for p in prods], batch_size=500)
    RolledDay.objects.update_or_create(day=day)


def run(now=None):
    """هر بار (کار ۱۰ دقیقه‌ای) فقط روزهای تمام‌شدهٔ خلاصه‌نشده را خلاصه می‌کند و ریزهای کهنه را پاک می‌کند."""
    today = timezone.localdate(now or timezone.now())
    done = 0
    days = (Hit.objects.filter(day__lt=today).exclude(day__in=RolledDay.objects.values("day"))
            .values_list("day", flat=True).distinct().order_by("day")[:7])
    for d in list(days):
        roll_day(d)
        done += 1
    cutoff = today - timezone.timedelta(days=RETENTION_DAYS)
    old = Hit.objects.filter(day__lt=cutoff, day__in=RolledDay.objects.values("day"))
    if old.exists():
        ids = list(old.values_list("pk", flat=True)[:20000])
        Hit.objects.filter(pk__in=ids).delete()
    return done
