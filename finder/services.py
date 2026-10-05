"""ثبت درخواست عکس/توضیح مشتری و خبر دادن پاسخ کارشناس."""
import io
import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from . import colors as C
from . import engine
from .models import FinderRequest, Need

log = logging.getLogger(__name__)


def private_path(req):
    d = Path(settings.PRIVATE_ROOT) / "finder"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{req.pk}.jpg"


def save_photo(req, upload):
    """عکس بدون متادیتا (موقعیت مکانی و…) در پوشهٔ خصوصی؛ رنگ‌های غالب و پیشنهاد خودکار هم حساب می‌شود."""
    from PIL import Image, ImageOps

    upload.seek(0)
    img = ImageOps.exif_transpose(Image.open(upload)).convert("RGB")
    img.thumbnail((2000, 2000))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=86)
    path = private_path(req)
    path.write_bytes(buf.getvalue())
    req.photo = str(path.relative_to(settings.PRIVATE_ROOT))
    try:
        dom = C.dominant(img)
    except Exception:  # noqa: BLE001
        log.exception("dominant colors")
        dom = []
    needs = engine.active_needs()
    matched = C.match_needs(dom, needs)
    req.colors = [{"hex": h, "share": s} for h, s in dom] + [{"need": n.pk, "title": n.title} for n in matched]
    return matched


def auto_suggest(req, color_needs, limit=12):
    """پیشنهاد فوری: رنگ عکس + خواسته‌هایی که مشتری انتخاب کرده."""
    wanted = req.wanted or {}
    ids = set(wanted.get("needs") or [])
    needs = [n for n in engine.active_needs() if n.pk in ids]
    for n in color_needs:
        if n not in needs and not any(x.group == "color" for x in needs):
            needs.append(n)
    wish = engine.understand(wanted.get("q") or "") if wanted.get("q") else engine.Wish()
    wish.needs = list(dict.fromkeys(wish.needs + needs))
    if wanted.get("size"):
        from pricing.models import Size

        wish.sizes = list(Size.objects.filter(pk=wanted["size"]))
    wish.max_price = int(wanted.get("max") or 0) or wish.max_price
    qs, _ = engine.search(wish)
    return list(qs.values_list("pk", flat=True)[:limit])


def create(user, mobile, name, text, wanted, photo=None):
    req = FinderRequest.objects.create(
        user=user, mobile=mobile, name=name[:120], text=text[:2000], wanted=wanted or {},
        kind=FinderRequest.Kind.PHOTO if photo else FinderRequest.Kind.TEXT,
    )
    color_needs = save_photo(req, photo) if photo else []
    req.auto_products = auto_suggest(req, color_needs)
    req.save()
    try:
        from shop.notify import admin_text

        admin_text(f"درخواست تازهٔ فرش‌یاب ({req.get_kind_display()}) از {name or mobile}")
    except Exception:  # noqa: BLE001
        pass
    return req


def after_reply(req, request=None):
    """وقتی کارشناس پاسخ را ذخیره کرد."""
    if req.status == FinderRequest.Status.NEW and (req.reply.strip() or req.products.exists()):
        req.status = FinderRequest.Status.ANSWERED
    if req.status == FinderRequest.Status.ANSWERED and not req.answered_at:
        req.answered_at = timezone.now()
        req.seen_at = None
        req.save(update_fields=["status", "answered_at", "seen_at"])
        if req.notify_sms and req.mobile:
            try:
                from accounts.sms import send_bulk

                send_bulk([req.mobile], f"{req.name or 'مشتری'} عزیز، پیشنهاد کارشناس ایران کارپت برای فرش دلخواهتان آماده است. "
                                        "در اپ فرش‌یاب، بخش «درخواست‌های من» را ببینید.")
            except Exception:  # noqa: BLE001
                log.exception("finder sms")
    return req


def need_titles(ids):
    return list(Need.objects.filter(pk__in=ids or []).values_list("title", flat=True))
