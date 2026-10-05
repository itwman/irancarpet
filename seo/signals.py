"""ارسال خودکار نشانی صفحه‌های تغییرکرده به IndexNow (فقط روی سایت اصلی)."""
from django.db import transaction
from django.db.models.signals import post_delete

from . import indexnow


def _send(*urls):
    if indexnow.active():
        transaction.on_commit(lambda: indexnow.queue(*urls))


def _url(obj):
    try:
        return obj.get_absolute_url()
    except Exception:  # noqa: BLE001
        return ""


def product(sender, instance, **kw):
    # حذف یا پیش‌نویس‌شدن هم خبر داده می‌شود تا موتور جستجو نسخهٔ قدیمی را کنار بگذارد
    if instance.status == "publish" or kw.get("signal") is post_delete:
        _send(_url(instance))


def album(sender, instance, **kw):
    from pricing.pricelist import PRICE_LIST_PATH

    if not indexnow.active():
        return
    urls = [PRICE_LIST_PATH, "/llms.txt"]
    if instance.slug and instance.in_price_list:
        urls.append(_url(instance))
    if kw.get("signal") is not post_delete:
        from catalog.models import Product

        urls += [p.get_absolute_url() for p in Product.objects.published().filter(album_id=instance.pk).only("slug")[:2000]]
    _send(*urls)


def post(sender, instance, **kw):
    if instance.status == "publish" or kw.get("signal") is post_delete:
        _send(_url(instance))


def page(sender, instance, **kw):
    if instance.status == "publish":
        _send(_url(instance))
