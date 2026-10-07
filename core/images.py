"""کم‌حجم کردن تصویرهای آپلودی بدون تغییر نسبت ابعاد (بدون دفرمه شدن) و با حفظ رنگ.

- ضلع بزرگ حداکثر ۲۴۰۰ پیکسل (برای زوم روی جزئیات فرش کافی است)؛ تصویر کوچک‌تر بزرگ نمی‌شود.
- JPEG پیش‌رونده با کیفیت ۸۶ و اگر لازم شد کمتر (تا ۷۶)، بعد ضلع ۲۰۰۰ و ۱۶۰۰ تا حجم زیر ۷۰۰ کیلوبایت شود.
- چرخش عکس موبایل (EXIF) درست می‌شود؛ پروفایل رنگ (ICC) نگه داشته می‌شود تا رنگ فرش عوض نشود.
- PNG شفاف همان PNG می‌ماند؛ PNG بدون شفافیت (عکس) به JPEG تبدیل می‌شود.
"""
import io
import os

from PIL import Image, ImageOps

MAX_BYTES = 700 * 1024
SIDES = (2400, 2000, 1600)
QUALITIES = (86, 82, 79, 76)
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _has_alpha(im):
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        alpha = im.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255
    return False


def _encode_jpeg(im, side, quality, icc):
    img = im.copy()
    img.thumbnail((side, side), Image.LANCZOS)  # نسبت ابعاد ثابت می‌ماند
    buf = io.BytesIO()
    kw = {"quality": quality, "optimize": True, "progressive": True, "subsampling": "4:2:0" if quality < 85 else "4:4:4"}
    if icc:
        kw["icc_profile"] = icc
    img.save(buf, "JPEG", **kw)
    return buf.getvalue(), img.size


def optimize_bytes(data, name, force_format=None):
    """(بایت‌ها، نام تازه، عرض، ارتفاع، تغییر کرد؟)"""
    base, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext not in PHOTO_EXT:
        return data, name, None, None, False
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001
        return data, name, None, None, False
    if getattr(im, "is_animated", False):
        return data, name, im.width, im.height, False
    icc = im.info.get("icc_profile")
    im = ImageOps.exif_transpose(im)
    small_enough = len(data) <= MAX_BYTES and max(im.size) <= SIDES[0]
    rotated = im.size != Image.open(io.BytesIO(data)).size
    if small_enough and not rotated:
        return data, name, im.width, im.height, False
    alpha = _has_alpha(im)
    fmt = force_format or ("PNG" if alpha else "JPEG")
    if fmt == "PNG":
        img = im.copy()
        img.thumbnail((SIDES[0], SIDES[0]), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True, **({"icc_profile": icc} if icc else {}))
        out = buf.getvalue()
        if len(out) >= len(data) and not rotated and max(im.size) <= SIDES[0]:
            return data, name, im.width, im.height, False
        return out, base + ".png", img.width, img.height, True
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        rgba = im.convert("RGBA")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        im = bg
    best = None
    for side in SIDES:
        for q in QUALITIES:
            out, size = _encode_jpeg(im, min(side, max(im.size)), q, icc)
            best = (out, size)
            if len(out) <= MAX_BYTES:
                break
        if len(best[0]) <= MAX_BYTES:
            break
    out, (w, h) = best
    if len(out) >= len(data) and not rotated and max(im.size) <= SIDES[0] and ext in (".jpg", ".jpeg"):
        return data, name, im.width, im.height, False
    new_ext = ext if (force_format and ext in (".jpg", ".jpeg")) else ".jpg"
    return out, base + new_ext, w, h, True


def optimize_upload(f):
    """فایل آپلودی جنگو ← (ContentFile یا خود فایل، عرض، ارتفاع)"""
    from django.core.files.base import ContentFile

    data = f.read()
    out, name, w, h, changed = optimize_bytes(data, f.name)
    if not changed:
        f.seek(0)
        return f, w, h
    return ContentFile(out, name=name), w, h
