"""تصویر استوری ۱۰۸۰×۱۹۲۰ برای همکار فروش: عکس فرش، نام، قیمت امروز (با تاریخ) و کد تخفیف خود همکار."""
import io

from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageOps

from core.templatetags.fa import fa_num, toman
from rajyar.pricelist_image import INK, PINK, SAFFRON, WHITE, date_label, fit, font, text, width

W, H, PAD = 1080, 1920, 64
INK_2, LINE = (45, 50, 112), (255, 255, 255, 60)


def _photo(product, box_w, box_h):
    """عکس اصلی فرش، بریده‌شده به اندازهٔ قاب (cover)."""
    media = product.image
    if not media or not media.file:
        return None
    try:
        with default_storage.open(media.file.name, "rb") as f:
            im = Image.open(f)
            im.load()
    except Exception:  # noqa: BLE001
        return None
    im = ImageOps.exif_transpose(im).convert("RGB")
    return ImageOps.fit(im, (box_w, box_h), Image.LANCZOS, centering=(0.5, 0.45))


def _rounded(im, r):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), r, fill=255)
    return mask


def _wrap(draw, s, f, max_w, lines=2):
    words, out, cur = fa_num(s).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if width(draw, t, f) <= max_w:
            cur = t
        else:
            if cur:
                out.append(cur)
            cur = w
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if len(out) == lines and " ".join(out) != fa_num(s).strip():
        out[-1] = fit(draw, out[-1] + "…", f, max_w)
    return out


def render(product, code, percent, offer=None, site="irancarpet.net"):
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img, "RGBA")
    # نوار رنگی بالای تصویر، مثل لبهٔ فوتر سایت
    colors = [PINK, SAFFRON, (18, 169, 184), (124, 196, 107)]
    for i in range(0, W, 48):
        d.rectangle((i, 0, i + 47, 14), fill=colors[(i // 48) % 4])
    text(d, (W - PAD, 62), "ایران کارپت", font(56, "Black"), WHITE)
    text(d, (W - PAD, 132), "فرش ماشینی کاشان، بی‌واسطه", font(32), (201, 203, 230))

    # عکس فرش
    top, box_w, box_h = 210, W - 2 * PAD, 1010
    ph = _photo(product, box_w, box_h)
    if ph is not None:
        img.paste(ph, (PAD, top), _rounded(ph, 36))
    else:
        d.rounded_rectangle((PAD, top, PAD + box_w, top + box_h), 36, fill=INK_2)
    if offer:
        badge = f"٪{fa_num(offer.off_percent)} تخفیف"
        bw = int(width(d, badge, font(40, "Black"))) + 56
        d.rounded_rectangle((PAD + 28, top + 28, PAD + 28 + bw, top + 104), 38, fill=PINK)
        text(d, (PAD + 28 + bw // 2, top + 40), badge, font(40, "Black"), WHITE, anchor="ma")

    # نام فرش
    y = top + box_h + 44
    for line in _wrap(d, product.title, font(50, "Bold"), W - 2 * PAD):
        text(d, (W - PAD, y), line, font(50, "Bold"), WHITE)
        y += 74

    # قیمت امروز
    y += 14
    if offer and offer.price:
        price = f"{toman(offer.price)} تومان"
        text(d, (W - PAD, y), price, font(66, "Black"), SAFFRON)
        pw = width(d, price, font(66, "Black"))
        old = f"{toman(offer.regular_price)}"
        ox = W - PAD - pw - 30
        text(d, (ox, y + 22), old, font(36), (170, 173, 210))
        ow = width(d, old, font(36))
        d.line((ox - ow, y + 46, ox, y + 46), fill=(170, 173, 210), width=3)
    elif product.min_price:
        text(d, (W - PAD, y), f"از {toman(product.min_price)} تومان", font(66, "Black"), SAFFRON)
    y += 96
    text(d, (W - PAD, y), f"قیمت امروز، {date_label()} · خرید نقدی و اقساطی", font(30), (201, 203, 230))

    # کد تخفیف همکار
    y = H - 330
    d.rounded_rectangle((PAD, y, W - PAD, y + 170), 34, fill=(255, 255, 255, 255))
    for x in range(PAD + 20, W - PAD - 20, 28):  # لبهٔ بریدنی بالای کوپن
        d.line((x, y + 8, x + 14, y + 8), fill=(229, 57, 91, 120), width=3)
    text(d, (W - PAD - 40, y + 30), "کد تخفیف شما در سبد خرید", font(34, "Bold"), INK)
    if percent:
        text(d, (W - PAD - 40, y + 86), f"{fa_num(percent)}٪ تخفیف ویژهٔ شما", font(32), PINK)
    d.text((PAD + 40, y + 52), code, font=font(76, "Black"), fill=PINK, anchor="la")

    text(d, (W // 2, H - 110), f"{site} · ارسال به سراسر ایران", font(34, "Bold"), WHITE, anchor="ma")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue()
