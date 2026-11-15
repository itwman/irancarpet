"""به‌روز نگه داشتن نمایهٔ جستجو وقتی مشخصات، دسته‌ها یا برچسب‌های فرش عوض می‌شود."""
from django.db.models.signals import m2m_changed, post_save


def _m2m(sender, instance, action, reverse=False, pk_set=None, **kw):
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    from .models import Product
    from .search import reindex

    if reverse:  # از سمت مقدار ویژگی/دسته
        ids = pk_set or []
        qs = Product.objects.filter(pk__in=ids) if ids else getattr(instance, "products").all()
    else:
        qs = Product.objects.filter(pk=instance.pk)
    reindex(qs.select_related("album", "brand").prefetch_related("specs", "categories", "tags"))


def _renamed(sender, instance, created=False, **kw):
    if created:
        return
    from .search import reindex

    rel = getattr(instance, "products", None)
    if rel is not None:
        reindex(rel.all().select_related("album", "brand").prefetch_related("specs", "categories", "tags")[:3000])


def page_cache_keys(product):
    from django.core.cache.utils import make_template_fragment_key

    if not product.modified_at:
        return []
    return [f"pd:{product.pk}:{int(product.modified_at.timestamp())}",
            make_template_fragment_key("pd_bottom", [product.pk, str(int(product.modified_at.timestamp()))])]


def _product_saved(sender, instance, **kw):
    """ویرایش فرش از پنل بلافاصله در صفحه‌اش دیده شود (کش یک‌ساعتهٔ تکه‌های صفحهٔ فرش)."""
    try:
        from django.core.cache import caches

        caches["pages"].delete_many(page_cache_keys(instance))
    except Exception:  # noqa: BLE001
        pass


def connect():
    from .models import AttributeTerm, Brand, Category, Product, ProductTag

    for through in (Product.specs.through, Product.categories.through, Product.tags.through):
        m2m_changed.connect(_m2m, sender=through, weak=False)
    post_save.connect(_product_saved, sender=Product, weak=False)
    for model in (AttributeTerm, Category, ProductTag, Brand):
        post_save.connect(_renamed, sender=model, weak=False)
