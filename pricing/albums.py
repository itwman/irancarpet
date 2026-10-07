"""هماهنگ‌سازی سایزهای محصولات آلبومی با سایزهای آلبوم

مثل افزونهٔ وردپرسی: مشتری برای محصولِ دارای آلبوم، همهٔ سایزهای آلبوم را با قیمت آلبوم می‌بیند.
"""
from django.db import transaction


@transaction.atomic
def sync_album_variations(products, reset=False):
    """برای هر محصول آلبومی، یک تنوع به ازای هر سایز آلبوم می‌سازد و تنوع‌های اضافی را حذف می‌کند.

    reset=True (فقط هنگام انتقال از وردپرس): همهٔ سایزها موجود و بدون حراج/قیمت اختصاصی می‌شوند.
    """
    from catalog.models import Variation

    stats = {"created": 0, "deleted": 0, "products": 0}
    sizes_cache, even_cache = {}, {}
    touched = []
    for p in products:
        album = p.album
        if album is None:
            continue
        if album.pk not in sizes_cache:
            sizes_cache[album.pk] = list(album.sizes.filter(is_active=True).order_by("sort_order", "pk"))
            even_cache[album.pk] = set(album.even_sizes.values_list("pk", flat=True))
        sizes = sizes_cache[album.pk]
        only = set(p.only_sizes.values_list("pk", flat=True)) if p.pk else set()
        if only:  # محصول جدا برای یک یا چند سایز خاص آلبوم (مثل گرد قطر ۱٫۵)
            sizes = [s for s in sizes if s.pk in only] or sizes
        single = set(p.single_sizes.values_list("pk", flat=True)) if p.pk else set()
        if not sizes:
            continue
        wanted = {s.pk for s in sizes}
        keep, drop = {}, []
        for v in p.variations.all().order_by("menu_order", "pk"):
            if v.size_id in wanted and v.size_id not in keep:
                keep[v.size_id] = v
            else:
                drop.append(v.pk)
        if drop:
            stats["deleted"] += Variation.objects.filter(pk__in=drop).delete()[1].get("catalog.Variation", 0)
        new, upd = [], []
        for i, s in enumerate(sizes):
            v = keep.get(s.pk)
            if v is None:
                v = Variation(product=p, size=s, is_available=True)
                new.append(v)
            else:
                upd.append(v)
            v.menu_order = i
            v.pair_only = s.pk in even_cache[album.pk] and s.pk not in single
            if reset:
                v.is_available, v.sale_price, v.override_price = True, None, None
        Variation.objects.bulk_create(new, batch_size=500)
        fields = ["menu_order", "pair_only"] + (["is_available", "sale_price", "override_price"] if reset else [])
        Variation.objects.bulk_update(upd, fields, batch_size=500)
        stats["created"] += len(new)
        stats["products"] += 1
        touched.append(p.pk)
    if touched:
        Variation.reprice_queryset(Variation.objects.filter(product_id__in=touched), scale_sale=False)  # کش قیمت محصول هم تازه می‌شود
    return stats
