"""مقصد: لحظهٔ ثبت سفارش، قیمت و موجودی فرش‌های سبد یک بار دیگر از سایت منبع پرسیده می‌شود.
اگر چیزی عوض شده باشد، این‌جا به‌روز می‌شود و مشتری سبد تازه را می‌بیند. اگر منبع در دسترس نباشد، خرید متوقف نمی‌شود."""
import logging

from django.db import transaction

from .client import MirrorError, get_json
from .models import MirrorLink, MirrorSettings

log = logging.getLogger(__name__)
CHANGED = "قیمت یا موجودی بعضی فرش‌های سبد همین الان به‌روز شد؛ سبد را دوباره ببینید و سفارش را ثبت کنید."


def check(lines):
    """None یعنی همه‌چیز درست است؛ وگرنه پیام خطا برای مشتری."""
    s = MirrorSettings.load()
    if not (s.is_target and s.live):
        return None
    links = {lk.source_pk: lk for lk in MirrorLink.objects.filter(
        product_id__in={ln.product.pk for ln in lines if getattr(ln, "product", None)}, excluded=False).select_related("product")}
    if not links:
        return None
    try:
        rows = get_json("/api/mirror/v1/stock/", {"ids": ",".join(map(str, links))}, timeout=8)["products"]
    except MirrorError as e:
        log.warning("mirror live check skipped: %s", e)
        return None
    from .sync import _retire, apply_stock

    from catalog.models import Variation

    changed = False
    got = {r["id"] for r in rows}
    for r in rows:
        lk = links[r["id"]]
        if lk.stock_hash != r["h"]:
            with transaction.atomic():
                if apply_stock(lk.product, lk, r, s):
                    lk.save(update_fields=["vmap", "omap", "stock_hash"])
    for pk, lk in links.items():
        if pk not in got:  # در منبع دیگر فروخته نمی‌شود
            _retire(lk.product)
            MirrorLink.objects.filter(pk=lk.pk).update(removed=True)
            changed = True
    for ln in lines:
        v = getattr(ln, "variation", None)
        if v is None or getattr(ln, "offer", None):
            continue
        now = Variation.objects.filter(pk=v.pk).first()
        unit = (ln.m2 or {}).get("per_m2") if getattr(ln, "m2", None) else ln.unit_price  # فرش متری: قیمت هر متر مربع
        if now is None or not now.is_available or (now.price and now.price != unit):
            changed = True
    return CHANGED if changed else None
