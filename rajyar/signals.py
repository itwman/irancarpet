"""فرش تازه‌ای که منتشر شد ← خودکار به کانال‌ها (اگر در تنظیمات روشن باشد)."""
import logging
import threading

from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)


def product_saved(sender, instance, created=False, **kw):
    p = instance
    if p.status != "publish" or not p.image_id or not p.published_at:
        return
    if timezone.now() - p.published_at > timezone.timedelta(days=1):  # فقط فرش‌های تازه
        return
    from django.conf import settings

    if getattr(settings, "TESTING", False):
        return
    from .models import RajyarSettings

    s = RajyarSettings.load()
    if not (s.enabled and s.auto_new and s.api_key and s.channel_ids) or p.rajyar_posts.exists():
        return

    def go():
        from .client import send

        try:
            send(type(p).objects.get(pk=p.pk), s=s)
        except Exception:  # noqa: BLE001
            log.exception("rajyar auto send")

    transaction.on_commit(lambda: threading.Thread(target=go, daemon=True).start())
