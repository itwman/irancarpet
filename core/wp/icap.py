"""انتقال قیمت‌ها از افزونهٔ «قیمت‌گذاری آلبومی ایران‌کارپت» (irancarpet-album-pricing)

این افزونه روی سایت وردپرس فعال بود و قیمت محصولات را تعیین می‌کرد:
  - آلبوم‌ها: نوع نوشتهٔ icap_album با متاهای _icap_* (خرید ۱۲ متری، سود، ارسال، پرتی، گرد کردن، سایزها)
  - سایزها: گزینهٔ icap_standard_sizes
  - اتصال محصول: متای _icap_album_id روی محصول
مشتری برای محصول آلبومی همهٔ سایزهای آلبوم را با قیمت آلبوم می‌دید (بدون حراج، همیشه موجود).
محصولات بدون آلبوم با همان قیمت ذخیره‌شده در ووکامرس نمایش داده می‌شدند.
"""
from decimal import Decimal

from django.db import transaction

from core.utils.php import php_unserialize

# کلید سایز افزونه → نامک سایز در جنگو
KEYMAP = {
    "12m": "12-meter", "9m": "9-meter", "6m": "6-meter", "15m": "15-meter", "square-3x3": "9-meter-square",
    "qalicheh-1.5x2.25": "rug-225x150", "qalicheh-1-5x2-25": "rug-225x150",
    "qalicheh-1x1.5": "rug-150x100", "qalicheh-1x1-5": "rug-150x100",
    "kenareh-1x4": "runner-4x1", "kenareh-1x3": "runner-3x1", "kenareh-1x2": "runner-2x1",
    "padari-0.5x0.8": "doormat-85x50", "padari-0-5x0-8": "doormat-85x50",
    "pushti-0.5x1": "pillow-100x50", "pushti-0-5x1": "pillow-100x50",
}


class _DryRun(Exception):
    pass


def _list(v):
    v = php_unserialize(v, default=None) if isinstance(v, str) else v
    if isinstance(v, dict):
        return [v[k] for k in sorted(v, key=lambda x: int(x) if str(x).isdigit() else 0)]
    return list(v) if isinstance(v, (list, tuple)) else []


def _dec(v, default=None):
    try:
        return Decimal(str(v)) if v not in (None, "") else default
    except Exception:  # noqa: BLE001
        return default


def _int(v):
    d = _dec(v)
    return int(d) if d is not None else None


def import_icap(wp, log=print, dry_run=False, sample=None):
    try:
        with transaction.atomic():
            report = _run(wp, log, sample)
            if dry_run:
                raise _DryRun
    except _DryRun:
        log("فقط گزارش بود؛ همه‌چیز به حالت قبل برگشت.")
        return report
    return report


def _run(wp, log, sample):
    from catalog.models import Product, Variation
    from pricing.albums import sync_album_variations
    from pricing.models import Album, Size, seed_sizes

    seed_sizes()
    div = 10 if (wp.option("woocommerce_currency") or "IRT").upper() == "IRR" else 1

    # ------------------------------------------------------------ سایزها
    icap_sizes = [s for s in _list(wp.option("icap_standard_sizes") or "") if isinstance(s, dict) and s.get("key")]
    if not icap_sizes:
        raise RuntimeError("سایزهای افزونهٔ آلبومی (icap_standard_sizes) در وردپرس پیدا نشد.")
    size_by_key = {}
    order = 500
    for s in icap_sizes:
        key = str(s["key"])
        area = _dec(s.get("billed_area")) or _dec(s.get("area")) or Decimal(0)
        slug = KEYMAP.get(key)
        size = Size.objects.filter(slug=slug).first() if slug else None
        if size is None:
            size, _ = Size.objects.get_or_create(slug=f"icap-{key.replace('.', '-')}"[:64], defaults=dict(
                label=str(s.get("label") or key)[:160], type=Size.Type.RECT, area=area, sort_order=order))
            order += 1
        changed = False
        if size.area != area:
            size.area, changed = area, True
            if size.slug == "doormat-85x50":
                size.width, size.length, size.label = Decimal("0.5"), Decimal("0.8"), "پادری ۰.۸ × ۰.۵"
        if size.needs_waste != bool(s.get("special_waste")):
            size.needs_waste, changed = bool(s.get("special_waste")), True
        if not size.is_active:
            size.is_active, changed = True, True
        if changed:
            size.save()
        size_by_key[key] = size
    base = size_by_key.get("12m") or Size.objects.get(slug="12-meter")
    log(f"سایزهای افزونه: {len(size_by_key)}")

    # ------------------------------------------------------------ آلبوم‌ها
    posts = wp.posts("icap_album", ("publish", "draft", "private", "pending", "future"))
    meta = wp.postmeta([p["ID"] for p in posts])
    albums, missing_keys = {}, set()
    for p in posts:
        m = meta.get(p["ID"], {})
        buy = _dec(m.get("_icap_buy_price"), Decimal(0))
        enabled = [str(k) for k in _list(m.get("_icap_enabled_sizes"))] if "_icap_enabled_sizes" in m else ["12m", "9m", "6m"]
        if "_icap_even_sizes" in m and isinstance(php_unserialize(m["_icap_even_sizes"], default=None), (dict, list)):
            even = [str(k) for k in _list(m["_icap_even_sizes"])]
        elif "_icap_enabled_sizes" in m:
            even = []
        else:
            even = [str(s["key"]) for s in icap_sizes if s.get("even_only")]
        a, _ = Album.objects.update_or_create(wp_id=p["ID"], defaults=dict(
            name=(p["post_title"] or f"آلبوم {p['ID']}")[:160], code=f"ICAP-{p['ID']}", base_size=base,
            base_price=buy, profit_percent=_dec(m.get("_icap_profit_percent"), Decimal(0)),
            shipping_fixed=_int(m.get("_icap_shipping_fixed")) or 0,
            waste_type=Album.WasteType.FIXED if m.get("_icap_waste_type") == "fixed" else Album.WasteType.PERCENT,
            waste_value=_dec(m.get("_icap_waste_value"), Decimal(0)),
            round_to=_int(m.get("_icap_round_to")) if m.get("_icap_round_to") not in (None, "") else 10000,
            is_active=buy > 0, sort_order=p["menu_order"] or 0,
        ))
        missing_keys |= {k for k in enabled if k not in size_by_key}
        a.sizes.set([size_by_key[k] for k in enabled if k in size_by_key])
        a.even_sizes.set([size_by_key[k] for k in even if k in size_by_key])
        albums[p["ID"]] = a
    if missing_keys:
        log(f"  ⚠ کلید سایزهایی که در فهرست سایزهای افزونه نبودند (در وردپرس هم نمایش داده نمی‌شدند): {', '.join(sorted(missing_keys))}")
    log(f"آلبوم‌ها: {len(albums)} (فعال: {sum(1 for a in albums.values() if a.is_active)})")

    # ------------------------------------------------------------ محصولات
    links = {int(r["post_id"]): _int(r["meta_value"]) for r in wp.rows(
        "SELECT post_id, meta_value FROM {p}postmeta WHERE meta_key='_icap_album_id' AND meta_value<>'' AND meta_value<>'0'")}
    products = list(Product.objects.exclude(wp_id=None).select_related("album"))
    album_products, plain_products = [], []
    for pr in products:
        a = albums.get(links.get(pr.wp_id))
        if a is not None and a.is_active:
            pr.album, pr.custom_base_price, pr.sale_status = a, None, "available"
            album_products.append(pr)
        else:
            pr.album, pr.custom_base_price = None, None
            plain_products.append(pr)
    Product.objects.bulk_update(products, ["album", "custom_base_price", "sale_status"], batch_size=1000)
    log(f"محصولات آلبومی: {len(album_products)} — بدون آلبوم (با قیمت ذخیره‌شدهٔ ووکامرس): {len(plain_products)}")

    # محصولات بدون آلبوم: دقیقاً قیمت ذخیره‌شده در ووکامرس
    plain_ids = [p.pk for p in plain_products]
    vs = list(Variation.objects.filter(product_id__in=plain_ids).exclude(wp_id=None))
    vmeta = wp.postmeta([v.wp_id if v.wp_id < 10_000_000 else v.wp_id - 10_000_000 for v in vs],
                        ["_regular_price", "_sale_price", "_price"])
    for v in vs:
        m = vmeta.get(v.wp_id if v.wp_id < 10_000_000 else v.wp_id - 10_000_000, {})
        regular = _int(m.get("_regular_price") or m.get("_price"))
        price = _int(m.get("_price"))
        regular = regular // div if regular else None
        price = price // div if price else None
        v.manual_price, v.override_price = regular, None
        v.sale_price = price if (price and regular and price < regular) else None
    Variation.objects.bulk_update(vs, ["manual_price", "override_price", "sale_price"], batch_size=1000)
    Variation.reprice_queryset(Variation.objects.filter(product_id__in=plain_ids), scale_sale=False)

    # محصولات آلبومی: سایزها و قیمت‌ها از آلبوم
    st = sync_album_variations(album_products, reset=True)
    log(f"سایزهای محصولات آلبومی: {st['created']} ساخته شد، {st['deleted']} تنوع قدیمی حذف شد")

    # آلبوم‌های قدیمی افزونهٔ ارزی (دیگر هیچ محصولی ندارند)
    n_old = Album.objects.filter(code__startswith="MNS-").count()
    Album.objects.filter(code__startswith="MNS-").delete()
    log(f"آلبوم‌های قدیمی افزونهٔ ارزی حذف شد: {n_old}")

    if sample:
        pr = Product.objects.select_related("album").filter(pk=sample).first()
        if pr:
            log(f"\nنمونه: {pr.title} — آلبوم: {pr.album.name if pr.album else 'ندارد'}")
            for v in pr.variations.select_related("size").order_by("menu_order"):
                log(f"   {v.size.label if v.size else '—'}: {v.final_price or 0:,}" + (f" (حراج {v.sale_price:,})" if v.on_sale else "")
                    + (" — فقط زوج" if v.is_pair_only else ""))
    return {"albums": len(albums), "album_products": len(album_products), "plain_products": len(plain_products), **st}
