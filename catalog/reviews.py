"""ثبت نظر مشتری (با عکس) و به‌روز کردن امتیاز فرش."""
import io

from django.core.files.base import ContentFile
from django.db.models import Avg, Count

from .models import Review, ReviewPhoto

MAX_PHOTOS = 4


def recompute(product):
    """امتیاز و تعداد نظرهای تأییدشده (فقط نظرهای اصلی با امتیاز)."""
    agg = Review.objects.filter(product=product, parent=None, is_approved=True, rating__gt=0).aggregate(a=Avg("rating"), n=Count("id"))
    type(product).objects.filter(pk=product.pk).update(rating_avg=round(agg["a"] or 0, 2), rating_count=agg["n"] or 0)


def bought(user, product):
    """این کاربر سفارش ثبت‌شده‌ای با همین فرش دارد؟"""
    if not user:
        return False
    from shop.coupons import PLACED
    from shop.models import OrderItem

    return OrderItem.objects.filter(order__user=user, order__status__in=PLACED, product=product).exists()


def save_photos(review, files):
    """عکس‌ها کوچک می‌شوند و متادیتایشان (مثل موقعیت مکانی) حذف می‌شود."""
    from PIL import Image, ImageOps

    n = 0
    for f in list(files)[:MAX_PHOTOS]:
        try:
            img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        except Exception:  # noqa: BLE001  — فایل عکس نیست
            continue
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=84)
        ReviewPhoto.objects.create(review=review, image=ContentFile(buf.getvalue(), name=f"r{review.pk}-{n + 1}.jpg"))
        n += 1
    return n


def create(product, *, user=None, name="", mobile="", rating=0, text="", photos=(), order=None):
    rating = max(0, min(5, int(rating or 0)))
    r = Review.objects.create(
        product=product, user=user, author_name=(name or "مشتری ایران کارپت")[:200], mobile=mobile[:11],
        rating=rating or None, content=text.strip()[:3000], is_approved=False,
        verified=bool(order) or bought(user, product),
    )
    save_photos(r, photos)
    return r
