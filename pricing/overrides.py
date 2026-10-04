"""ابزارهای قیمت‌های اختصاصی (جدا از آلبوم)

سه چیز می‌تواند قیمت یک محصول را از قیمت آلبومش جدا کند:
  ۱. قیمت پایهٔ اختصاصی محصول (Product.custom_base_price)
  ۲. قیمت خرید اختصاصی یک سایز (Variation.override_price)
  ۳. قیمت حراج یک سایز (Variation.sale_price)
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q


def _q(x):
    return Decimal(x).quantize(Decimal("1"))


@transaction.atomic
def scale_album_overrides(album, ratio, sales=False):
    """قیمت‌های اختصاصی محصولات یک آلبوم را هم‌نسبت با تغییر قیمت پایهٔ آلبوم تغییر می‌دهد."""
    from catalog.models import Product, Variation

    ratio = Decimal(ratio)
    prods = list(Product.objects.filter(album=album, custom_base_price__isnull=False).only("pk", "custom_base_price"))
    for p in prods:
        p.custom_base_price = _q(p.custom_base_price * ratio)
    Product.objects.bulk_update(prods, ["custom_base_price"], batch_size=1000)
    vars_ = list(Variation.objects.filter(product__album=album, override_price__isnull=False).only("pk", "override_price"))
    for v in vars_:
        v.override_price = _q(v.override_price * ratio)
    Variation.objects.bulk_update(vars_, ["override_price"], batch_size=1000)
    n_sale = 0
    if sales:
        sv = list(Variation.objects.filter(product__album=album, sale_price__isnull=False).only("pk", "sale_price"))
        for v in sv:
            v.sale_price = int(round(v.sale_price * float(ratio), -4)) or None
        Variation.objects.bulk_update(sv, ["sale_price"], batch_size=1000)
        n_sale = len(sv)
    return len(prods), len(vars_), n_sale


def override_filter(kind):
    """فیلتر محصولاتی که قیمتشان جدا از آلبوم است."""
    if kind == "custom":
        return Q(custom_base_price__isnull=False)
    if kind == "override":
        return Q(variations__override_price__isnull=False)
    if kind == "sale":
        return Q(variations__sale_price__isnull=False)
    return Q(custom_base_price__isnull=False) | Q(variations__override_price__isnull=False) | Q(variations__sale_price__isnull=False)


@transaction.atomic
def follow_album(products, sales=True):
    """قیمت‌های اختصاصی (و حراج‌ها) را پاک می‌کند تا محصول دقیقاً از قیمت آلبوم پیروی کند.
    فقط روی محصولات دارای آلبوم؛ محصول بدون آلبوم قیمت دستی دارد و دست نمی‌خورد."""
    from catalog.models import Product, Variation

    ids = list(Product.objects.filter(pk__in=[p.pk for p in products], album__isnull=False).values_list("pk", flat=True))
    Product.objects.filter(pk__in=ids).update(custom_base_price=None)
    fields = {"override_price": None}
    if sales:
        fields["sale_price"] = None
    Variation.objects.filter(product_id__in=ids).update(**fields)
    Variation.reprice_queryset(Variation.objects.filter(product_id__in=ids), scale_sale=False)
    return len(ids)


@transaction.atomic
def clear_sales(products):
    from catalog.models import Product, Variation

    ids = [p.pk for p in products]
    n = Variation.objects.filter(product_id__in=ids, sale_price__isnull=False).update(sale_price=None)
    for p in Product.objects.filter(pk__in=ids):
        p.refresh_price_cache()
    return n
