"""تنظیمات فید ترب و محصولات مستثنی از وردپرس (افزونه‌های irancarpet-torob-pricing و avin-torob-api)."""
from decimal import Decimal

from core.utils.php import php_unserialize


def _d(v, default=0):
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal(default)
    except Exception:  # noqa: BLE001
        return Decimal(default)


def import_torob(wp, log=print):
    from catalog.models import Product

    from .models import TorobSettings

    saved = php_unserialize(wp.option("ictp_settings") or "", default={}) or {}
    saved = saved if isinstance(saved, dict) else {}
    trb = php_unserialize(wp.option("trb") or "", default={}) or {}
    trb = trb if isinstance(trb, dict) else {}
    s = TorobSettings.load()
    s.per_page = int(_d(saved.get("per_page"), 100)) or 100
    s.price_divisor = int(_d(saved.get("price_divisor"), 1)) or 1
    s.tax_percent = _d(saved.get("tax_percent"))
    s.decrease_rate = _d(saved.get("decrease_rate"))
    s.round_to = int(_d(saved.get("round_to")))
    s.title_suffix = str(saved.get("title_suffix") or "")[:100]
    s.registry_text = str(saved.get("registry_text") or "")[:100]
    s.guarantee_attr = str(saved.get("guarantee_attr") or "")[:100]
    inherit = str(saved.get("inherit_avin", "1")) not in ("0", "", "False")
    if inherit and trb:
        if saved.get("tax_percent", "") == "" and trb.get("tax") and "tax_percent" in trb:
            s.tax_percent = _d(trb["tax_percent"])
        if saved.get("decrease_rate", "") == "" and "decrease_rate" in trb:
            s.decrease_rate = _d(trb["decrease_rate"])
        if not s.guarantee_attr and trb.get("guarantee_meta"):
            s.guarantee_attr = str(trb["guarantee_meta"])[:100]
        if not s.registry_text and trb.get("registry_meta"):
            s.registry_text = "رجیستر شده"
    s.save()
    excluded = []
    for r in wp.rows("SELECT post_id, meta_value FROM {p}postmeta WHERE meta_key='trb_post_options'"):
        o = php_unserialize(r["meta_value"] or "", default={}) or {}
        if isinstance(o, dict) and str(o.get("trb_exclude", "")).lower() in ("1", "true", "yes", "on"):
            excluded.append(int(r["post_id"]))
    s.excluded.set(Product.objects.filter(wp_id__in=excluded))
    log(f"فید ترب: تنظیمات منتقل شد (کاهش {s.decrease_rate}٪، مالیات {s.tax_percent}٪) — مستثنی: {len(excluded)}")
