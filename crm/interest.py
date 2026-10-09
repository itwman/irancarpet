"""علاقه‌مندان هر آلبوم: کسانی که فرش‌هایش را دیده‌اند (واردشده)، در سبد گذاشته‌اند، «خبرم کن» زده‌اند
یا سفارش پرداخت‌نشده دارند — و هنوز از آن آلبوم نخریده‌اند. برای پیامک «قیمت به‌زودی بالا می‌رود»."""
from django.core.cache import cache
from django.utils import timezone

td = timezone.timedelta


def track_view(request, product):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_staff:
        return
    if not cache.add(f"pv:{user.pk}:{product.pk}", 1, 3600):
        return
    from .models import ProductView

    ProductView.objects.update_or_create(user=user, product=product, defaults={"seen_at": timezone.now()})


def _mobile(user):
    from accounts.utils import normalize_mobile

    return normalize_mobile(getattr(getattr(user, "profile", None), "mobile", "") or "") or normalize_mobile(user.username or "")


def album_audience(album_id, days=90):
    from django.contrib.auth import get_user_model

    from catalog.models import Variation
    from growth.models import ProductAlert
    from shop.coupons import PLACED
    from shop.models import Order, OrderItem

    from .models import CartSnapshot, ProductView
    from .segments import customers

    since = timezone.now() - td(days=days)
    mobiles, users = set(), set()
    users |= set(ProductView.objects.filter(product__album_id=album_id, seen_at__gte=since).values_list("user_id", flat=True))
    for snap in CartSnapshot.objects.filter(updated_at__gte=since).only("user_id", "data"):
        ids = [int(k) for k in (snap.data or {})]
        if ids and Variation.objects.filter(pk__in=ids, product__album_id=album_id).exists():
            users.add(snap.user_id)
    for m in ProductAlert.objects.filter(product__album_id=album_id, created_at__gte=since).values_list("mobile", flat=True):
        mobiles.add(m)
    for m in OrderItem.objects.filter(product__album_id=album_id, order__status="pending", order__created_at__gte=since) \
            .values_list("order__mobile", flat=True):
        mobiles.add(m)
    for u in get_user_model().objects.filter(pk__in=users).select_related("profile"):
        m = _mobile(u)
        if m:
            mobiles.add(m)
    from accounts.utils import normalize_mobile

    mobiles = {normalize_mobile(m) for m in mobiles} - {""}
    bought = {normalize_mobile(m) for m in OrderItem.objects.filter(product__album_id=album_id, order__status__in=PLACED,
                                                                   order__created_at__gte=since).values_list("order__mobile", flat=True)}
    cust = customers()
    return [cust.get(m) or {"mobile": m, "name": "", "full_name": ""} for m in sorted(mobiles - bought)]
