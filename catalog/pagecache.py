"""کش بلندمدت تکه‌های صفحهٔ فرش (آبان ۱۴۰۵): تا ۷ روز، ولی هر تغییری که روی صفحه اثر دارد فوراً پاکش می‌کند.

کلید هر صفحه از سه «نسخه» ساخته می‌شود؛ هر تغییر نسخهٔ مربوط را عوض می‌کند و کلید قبلی دیگر خوانده نمی‌شود:
  نسخهٔ فرش   ← ذخیرهٔ فرش، تغییر قیمت/موجودی (refresh_price_cache)، سایزها (Variation) و فرصت ویژهٔ همان فرش
  نسخهٔ آلبوم ← ذخیرهٔ آلبوم یا سایزهای آلبوم (قیمت همهٔ فرش‌های آلبوم)
  نسخهٔ کل    ← تنظیمات قیمت، سایزها، قالب‌های متن، بلوک‌های اطلاعات، تنظیمات سایت/فروشگاه، نام دسته/برند/ویژگی/برچسب
اگر نسخه‌ای در کش نباشد (پاک‌شده)، نسخهٔ تازه ساخته می‌شود: یعنی در بدترین حالت صفحه از نو ساخته می‌شود، هیچ‌وقت کهنه نمی‌ماند.
"""
import time

TEXT_TTL = 7 * 86400   # توضیحات، رنگ‌های دیگر، داده‌های گوگل
CARDS_TTL = 86400      # کارت فرش‌های دیگر (پایین صفحه): قیمت/موجودی آن فرش‌ها به این صفحه خبر داده نمی‌شود


def _pc():
    from django.core.cache import caches

    return caches["pages"]


def _now():
    return str(time.time_ns())


def stamp(product):
    keys = ["pv:all", f"pv:a:{product.album_id or 0}", f"pv:p:{product.pk}"]
    try:
        pc = _pc()
        got = pc.get_many(keys)
        missing = {k: _now() for k in keys if k not in got}
        if missing:
            pc.set_many(missing, None)
            got.update(missing)
    except Exception:  # noqa: BLE001
        return _now()  # کش در دسترس نیست ← بی‌کش
    return "-".join(str(got[k]) for k in keys)


def _bump(*keys):
    try:
        _pc().set_many({k: _now() for k in keys}, None)
    except Exception:  # noqa: BLE001
        pass


def bump_product(pk):
    if pk:
        _bump(f"pv:p:{pk}")


def bump_album(pk):
    if pk:
        _bump(f"pv:a:{pk}")


def bump_all():
    _bump("pv:all")


def connect():
    from django.db.models.signals import m2m_changed, post_delete, post_save

    from content.models import ContentSettings, ContentTemplate, InfoBlock, NameHint
    from core.models import SiteSettings
    from pricing.models import Album, PricingSettings, Size
    from shop.models import ShopSettings, SpecialOffer

    from .models import AttributeTerm, Brand, Category, Product, ProductTag, Variation

    def product(sender, instance, **kw):
        bump_product(instance.pk)

    def by_product(sender, instance, **kw):
        bump_product(instance.product_id)

    def album(sender, instance, **kw):
        bump_album(instance.pk)

    def everything(sender, **kw):
        bump_all()

    post_save.connect(product, sender=Product, weak=False, dispatch_uid="pc_product")
    for m in (Variation, SpecialOffer):
        post_save.connect(by_product, sender=m, weak=False, dispatch_uid=f"pc_save_{m.__name__}")
        post_delete.connect(by_product, sender=m, weak=False, dispatch_uid=f"pc_del_{m.__name__}")
    post_save.connect(album, sender=Album, weak=False, dispatch_uid="pc_album")
    m2m_changed.connect(lambda sender, instance, action, reverse=False, **kw: (
        bump_album(instance.pk) if not reverse and action.startswith("post_") else bump_all() if action.startswith("post_") else None),
        sender=Album.sizes.through, weak=False, dispatch_uid="pc_album_sizes")
    for m in (PricingSettings, Size, ContentTemplate, InfoBlock, ContentSettings, NameHint, SiteSettings, ShopSettings,
              Category, Brand, AttributeTerm, ProductTag):
        post_save.connect(everything, sender=m, weak=False, dispatch_uid=f"pc_all_{m.__name__}")
        post_delete.connect(everything, sender=m, weak=False, dispatch_uid=f"pc_alldel_{m.__name__}")
