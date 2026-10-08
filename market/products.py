"""کالای فروشندگان: ساخت و ویرایش از پنل فروشنده، بررسی و انتشار با تأیید ایران کارپت."""
import os
import re

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from catalog.models import Attribute, AttributeTerm, Category, Product, ProductImage, Variation
from core.models import Media
from pricing.models import Size

from .models import Seller
from .render import text_to_html

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGES = 10
MAX_UPLOAD = 19 * 1024 * 1024


def spec_attributes():
    return list(Attribute.objects.filter(show_in_filters=True).prefetch_related("terms").order_by("order", "pk"))


def categories():
    return list(Category.objects.order_by("order", "name"))


def sizes():
    return list(Size.objects.filter(is_active=True).order_by("sort_order", "pk"))


def unique_slug(title, pk=None):
    base = slugify(title, allow_unicode=True)[:200] or "kala"
    slug, i = base, 2
    while Product.objects.filter(slug=slug).exclude(pk=pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


def save_image(f):
    """تصویر آپلودی فروشنده ← Media (کم‌حجم و بدون دفرمه)."""
    from PIL import Image

    ext = os.path.splitext(f.name)[1].lower()
    if ext not in IMG_EXT:
        raise ValueError(f"{f.name}: فقط عکس jpg، png یا webp.")
    if f.size > MAX_UPLOAD:
        raise ValueError(f"{f.name}: حجم بیش از ۱۹ مگابایت است.")
    try:
        with Image.open(f) as im:
            im.verify()
    except Exception:  # noqa: BLE001
        raise ValueError(f"{f.name}: تصویر خراب است.") from None
    f.seek(0)
    from core.images import optimize_upload

    f, w, h = optimize_upload(f)
    mime = {".png": "image/png", ".webp": "image/webp"}.get(os.path.splitext(f.name)[1].lower(), "image/jpeg")
    return Media.objects.create(file=f, title=os.path.splitext(os.path.basename(f.name))[0][:200], width=w, height=h,
                                mime_type=mime, created_at=timezone.now())


def _int(v):
    v = re.sub(r"[^\d]", "", str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
    return int(v) if v else None


def read_variations(post):
    """ردیف‌های سایز/قیمت/موجودی فرم: [{"id", "size", "label", "price", "sale", "qty", "pair", "delete"}], خطاها"""
    rows, errors = [], []
    ids = post.getlist("v_id")
    for i, vid in enumerate(ids):
        g = lambda k: (post.getlist(k)[i] if i < len(post.getlist(k)) else "")  # noqa: E731
        size, label = _int(g("v_size")), g("v_label").strip()[:60]
        price, sale, qty = _int(g("v_price")), _int(g("v_sale")), g("v_qty").strip()
        delete = g("v_delete") == "1"
        if not (size or label or price) and not vid:
            continue
        if delete:
            rows.append({"id": _int(vid), "delete": True})
            continue
        if not size and not label:
            errors.append(f"ردیف {i + 1}: سایز را انتخاب کنید یا عنوان (مثل «۵۰ × ۷۰») بنویسید.")
        if not price or price < 10_000:
            errors.append(f"ردیف {i + 1}: قیمت را به تومان بنویسید.")
        if sale and price and sale >= price:
            errors.append(f"ردیف {i + 1}: قیمت با تخفیف باید از قیمت اصلی کمتر باشد.")
        rows.append({"id": _int(vid), "size": size, "label": label, "price": price, "sale": sale or None,
                     "qty": _int(qty) if qty != "" else None, "pair": g("v_pair") == "1", "delete": False})
    if not [r for r in rows if not r["delete"]]:
        errors.append("دست‌کم یک سایز یا مدل با قیمت لازم است.")
    return rows, errors


def apply_variations(product, rows):
    keep = []
    valid_sizes = {s.pk for s in sizes()}
    for i, r in enumerate(rows):
        v = product.variations.filter(pk=r["id"]).first() if r.get("id") else None
        if r["delete"]:
            if v:
                v.delete()
            continue
        v = v or Variation(product=product)
        v.size_id = r["size"] if r["size"] in valid_sizes else None
        v.sku = r["label"] if not v.size_id else ""
        v.manual_price, v.sale_price = r["price"], r["sale"]
        v.stock_qty = r["qty"]
        v.is_available = r["qty"] is None or r["qty"] > 0
        v.pair_only = r["pair"]
        v.menu_order = i
        v.save()
        keep.append(v.pk)
    product.refresh_price_cache()
    return keep


CONTENT_FIELDS = ("title", "category", "short", "description", "specs", "images")


def save_product(seller, data, files, product=None):
    """ساخت یا ویرایش کالا از فرم فروشنده. خروجی: (کالا، خطاها، نیاز به بررسی؟)"""
    errors = {}
    title = (data.get("title") or "").strip()[:300]
    if len(title) < 5:
        errors["title"] = "عنوان کالا را کامل بنویسید (مثل «فرش ۱۰۰۰ شانه طرح افشان زمینه کرم»)."
    cat = Category.objects.filter(pk=_int(data.get("category"))).first()
    if not cat:
        errors["category"] = "دستهٔ کالا را انتخاب کنید."
    rows, verrs = read_variations(data)
    if verrs:
        errors["variations"] = verrs
    uploads = files.getlist("images")
    remove = {_int(x) for x in data.getlist("remove_image")} - {None}
    existing = list(product.images.values_list("media_id", flat=True)) if product else []
    left = [m for m in existing if m not in remove]
    if len(left) + len(uploads) == 0:
        errors["images"] = "دست‌کم یک عکس واقعی از کالا لازم است."
    elif len(left) + len(uploads) > MAX_IMAGES:
        errors["images"] = f"حداکثر {MAX_IMAGES} عکس."
    if errors:
        return product, errors, False
    terms = []
    for a in spec_attributes():
        t = _int(data.get(f"spec_{a.pk}"))
        if t and AttributeTerm.objects.filter(pk=t, attribute=a).exists():
            terms.append(t)
    short = (data.get("short") or "").strip()[:1000]
    desc = (data.get("description") or "").strip()[:20000]
    with transaction.atomic():
        new = product is None
        before = None if new else _content_sig(product)
        p = product or Product(seller=seller, status=Product.Status.DRAFT, kind=Product.Kind.VARIABLE, use_template=False)
        p.title, p.primary_category = title, cat
        p.short_description = text_to_html(short) if short else ""
        p.content = text_to_html(desc)
        if new:
            p.slug = unique_slug(title)
        p.save()
        p.categories.set([cat])
        p.specs.set(terms)
        media = []
        try:
            for f in uploads:
                media.append(save_image(f))
        except ValueError as e:
            transaction.set_rollback(True)
            return product, {"images": str(e)}, False
        ProductImage.objects.filter(product=p, media_id__in=remove).delete()
        start = ProductImage.objects.filter(product=p).count()
        for i, m in enumerate(media):
            ProductImage.objects.create(product=p, media=m, order=start + i)
        first = ProductImage.objects.filter(product=p).order_by("order", "pk").first()
        if first and p.image_id != first.media_id:
            Product.objects.filter(pk=p.pk).update(image_id=first.media_id)
            p.image_id = first.media_id
        apply_variations(p, rows)
        changed = new or _content_sig(p) != before
        if changed:
            submit(p)
    return p, {}, changed


def _content_sig(p):
    return (p.title, p.primary_category_id, p.short_description, p.content,
            tuple(sorted(p.specs.values_list("pk", flat=True))), tuple(p.images.order_by("pk").values_list("media_id", flat=True)))


def submit(p):
    """کالای تازه یا ویرایش محتوا: فروشندهٔ مورد اعتماد بی‌درنگ منتشر می‌شود؛ بقیه تا تأیید از سایت برداشته می‌شوند."""
    seller = p.seller
    if seller.trusted and seller.is_active:
        approve(p, notify=False)
        return
    Product.objects.filter(pk=p.pk).update(status=Product.Status.DRAFT, review_status="pending", review_note="")
    p.status, p.review_status = Product.Status.DRAFT, "pending"
    try:
        from shop.notify import admin_text

        admin_text(f"کالای «{p.title[:60]}» از فروشنده «{seller.name}» منتظر بررسی است: پنل ← کالاهای فروشندگان.")
    except Exception:  # noqa: BLE001
        pass


def approve(p, notify=True):
    status = Product.Status.PUBLISH if p.seller is None or p.seller.is_active else Product.Status.PRIVATE
    Product.objects.filter(pk=p.pk).update(status=status, review_status="approved", review_note="")
    p.status, p.review_status = status, "approved"
    if notify and p.seller_id:
        try:
            from accounts.sms import send_bulk

            send_bulk([p.seller.mobile], f"ایران کارپت: کالای «{p.title[:50]}» تأیید و در سایت منتشر شد.")
        except Exception:  # noqa: BLE001
            pass


def reject(p, note):
    Product.objects.filter(pk=p.pk).update(status=Product.Status.DRAFT, review_status="rejected", review_note=(note or "")[:300])
    if p.seller_id:
        try:
            from accounts.sms import send_bulk

            send_bulk([p.seller.mobile], f"ایران کارپت: کالای «{p.title[:50]}» نیاز به اصلاح دارد: {note[:120]} — پنل فروشنده")
        except Exception:  # noqa: BLE001
            pass


def set_visibility(seller):
    """فروشندهٔ فعال: کالاهای تأییدشده در سایت؛ تعطیل یا متوقف: پنهان (بی‌آنکه تأییدشان از بین برود)."""
    qs = Product.objects.filter(seller=seller)
    if seller.status == Seller.Status.ACTIVE:
        return qs.filter(status=Product.Status.PRIVATE, review_status="approved").update(status=Product.Status.PUBLISH)
    return qs.filter(status=Product.Status.PUBLISH).update(status=Product.Status.PRIVATE)


def quick_update(seller, post):
    """ویرایش سریع قیمت و موجودی از فهرست کالاها (بدون نیاز به بررسی دوباره)."""
    n = 0
    touched = set()
    for key in post:
        m = re.match(r"^q_(price|sale|qty)_(\d+)$", key)
        if not m:
            continue
        field, vid = m.group(1), int(m.group(2))
        v = Variation.objects.filter(pk=vid, product__seller=seller).first()
        if not v:
            continue
        raw = post.get(key, "").strip()
        val = _int(raw)
        if field == "price" and val and val >= 10_000 and val != v.manual_price:
            v.manual_price = val
        elif field == "sale" and (val or None) != v.sale_price:
            v.sale_price = val if val and v.manual_price and val < v.manual_price else None
        elif field == "qty" and (val if raw != "" else None) != v.stock_qty:
            v.stock_qty = val if raw != "" else None
            v.is_available = v.stock_qty is None or v.stock_qty > 0
        else:
            continue
        v.save()
        touched.add(v.product_id)
        n += 1
    for p in Product.objects.filter(pk__in=touched):
        p.refresh_price_cache()
    return n
