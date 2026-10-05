"""رنگ‌های غالب عکس فرش و نزدیک‌ترین «نیاز رنگی» (بر اساس رنگ نمونهٔ هر نیاز)."""
import colorsys
import math


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(int(c) for c in rgb)


def _rgb(hexstr):
    h = (hexstr or "").lstrip("#")
    if len(h) != 6:
        return None
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lab(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in rgb)
    x = (r * .4124 + g * .3576 + b * .1805) / .95047
    y = r * .2126 + g * .7152 + b * .0722
    z = (r * .0193 + g * .1192 + b * .9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > .008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def dominant(image, k=5):
    """[(hex، سهم)] از عکس؛ حاشیه‌ها (پس‌زمینهٔ کف اتاق) کمتر حساب می‌شوند."""
    from PIL import Image

    img = image.convert("RGB")
    w, h = img.size
    img = img.crop((int(w * .12), int(h * .12), int(w * .88), int(h * .88)))  # بیشتر خود فرش
    img.thumbnail((160, 160))
    q = img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts) or 1
    out = []
    for c, idx in counts:
        rgb = pal[idx * 3: idx * 3 + 3]
        out.append((_hex(rgb), round(c / total, 3)))
    return out


def match_needs(colors, needs, limit=2):
    """نیازهای رنگی نزدیک به رنگ‌های غالب (به ترتیب سهم)."""
    swatches = [(n, _lab(_rgb(n.swatch))) for n in needs if n.group == "color" and _rgb(n.swatch)]
    if not swatches:
        return []
    scores = {}
    for hexstr, share in colors:
        lab = _lab(_rgb(hexstr))
        n, d = min(((n, math.dist(lab, s)) for n, s in swatches), key=lambda x: x[1])
        if d < 45:
            scores[n] = scores.get(n, 0) + share
    return [n for n, s in sorted(scores.items(), key=lambda x: -x[1]) if s >= .12][:limit]


def is_dark(hexstr):
    r, g, b = _rgb(hexstr)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[1] < .45
