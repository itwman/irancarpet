"""منبع (ایران کارپت): فرشی که به دسته‌ای با «خودکار برای فرشستان» اضافه شود، برای فرشستان انتخاب می‌شود."""
from django.db.models.signals import m2m_changed


def categories_changed(sender, instance, action, pk_set=None, reverse=False, **kw):
    if action != "post_add" or not pk_set or reverse:
        return
    from catalog.models import Category

    if not Category.objects.filter(pk__in=pk_set, mirror_auto=True).exists():
        return
    from .models import MirrorPick, MirrorSettings

    if not MirrorSettings.load().feed_enabled or getattr(instance, "seller_id", None):
        return
    MirrorPick.objects.get_or_create(product=instance)


def connect():
    from catalog.models import Product

    m2m_changed.connect(categories_changed, sender=Product.categories.through, dispatch_uid="mirror_auto_pick")


def pick(ids):
    """ویرایش گروهی: فرش‌ها برای فرشستان انتخاب شوند (اگر این سایت منبع کاتالوگ است). خروجی: تعداد تازه."""
    from catalog.models import Product

    from .models import MirrorPick, MirrorSettings

    if not MirrorSettings.load().feed_enabled:
        return 0
    ids = set(Product.objects.filter(pk__in=ids, seller__isnull=True).values_list("pk", flat=True))
    have = set(MirrorPick.objects.filter(product_id__in=ids).values_list("product_id", flat=True))
    MirrorPick.objects.bulk_create([MirrorPick(product_id=i) for i in ids - have])
    return len(ids - have)
