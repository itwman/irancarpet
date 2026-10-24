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
