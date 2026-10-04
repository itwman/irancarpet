"""انتقال تنظیمات و وضعیت محصولات از افزونهٔ FarshPlus Connect وردپرس."""
from datetime import datetime, timezone as dt_tz

from django.db import transaction
from django.utils import timezone

from catalog.models import Category, Product
from core.utils.php import php_unserialize

from .models import FarshPlusItem, FarshPlusSettings
from .sync import image_medias, images_hash, max_images

KEYS = ["_fpc_post_id", "_fpc_post_url", "_fpc_status", "_fpc_synced_at", "_fpc_error", "_fpc_images_hash", "_fpc_enabled", "_fpc_in_feed"]


def _ts(v):
    try:
        return datetime.fromtimestamp(int(v), tz=dt_tz.utc)
    except (TypeError, ValueError):
        return None


def import_farshplus(wp, log):
    s = FarshPlusSettings.load()
    opt = php_unserialize(wp.option("fpc_settings"), default={}) or {}
    if isinstance(opt, dict) and opt:
        s.url = (opt.get("farshplus_url") or s.url).rstrip("/")
        if opt.get("api_key"):
            s.api_key = str(opt["api_key"]).strip()
        for k in ("auto_sync", "default_in_feed", "hashtags", "hide_out_of_stock"):
            if k in opt:
                setattr(s, k, bool(int(opt[k] or 0)) if str(opt[k]).isdigit() else bool(opt[k]))
        if opt.get("max_images"):
            s.max_images = max(1, min(5, int(opt["max_images"])))
    until = _ts(wp.option("fpc_rate_limited_until"))
    s.rate_limited_until = until if until and until > timezone.now() else None
    conn = php_unserialize(wp.option("fpc_connection"), default={}) or {}
    if isinstance(conn, dict) and conn:
        s.connection = {k: conn.get(k) or {} for k in ("page", "shop", "limits")}
    s.last_scan_at = timezone.now()  # خط مبنا: فقط تغییرات بعد از این لحظه خودکار ارسال می‌شوند
    s.save()
    if isinstance(opt, dict) and opt.get("categories"):
        ids = [int(x) for x in (opt["categories"].values() if isinstance(opt["categories"], dict) else opt["categories"]) if str(x).isdigit()]
        s.categories.set(Category.objects.filter(wp_id__in=ids))

    products = {p.wp_id: p for p in Product.objects.exclude(wp_id=None).select_related("image")}
    meta = wp.postmeta(list(products), KEYS)
    n = sent = queued = 0
    with transaction.atomic():
        for wp_id, m in meta.items():
            if not any(m.get(k) for k in KEYS):
                continue
            p = products.get(wp_id)
            if not p:
                continue
            item = FarshPlusItem.objects.filter(product=p).first() or FarshPlusItem(product=p, external_id=str(wp_id))
            item.post_id = int(m["_fpc_post_id"]) if str(m.get("_fpc_post_id") or "").isdigit() else None
            item.post_url = (m.get("_fpc_post_url") or "")[:500]
            item.status = (m.get("_fpc_status") or "")[:32]
            item.synced_at = _ts(m.get("_fpc_synced_at"))
            item.error = (m.get("_fpc_error") or "")[:500]
            item.enabled = {"yes": True, "no": False}.get(m.get("_fpc_enabled"))
            item.in_feed = {"1": True, "0": False}.get(m.get("_fpc_in_feed"))
            # تصاویر را دوباره نفرستیم (همان تصاویر وردپرس است)؛ قیمت/متن یک‌بار با نسخهٔ تازه به‌روز می‌شود
            item.images_hash = images_hash(image_medias(p, max_images(s))) if item.has_remote else ""
            item.fingerprint = ""
            if item.status == "QUEUED" and not item.post_id:
                item.queued, item.mode = True, "bulk"
                queued += 1
            item.save()
            n += 1
            sent += bool(item.post_id)
    log(f"فرش پلاس: کلید {'منتقل شد' if s.api_key else 'پیدا نشد'}، {n} محصول با سابقه ({sent} منتشرشده در فرش پلاس، {queued} در صف)")
