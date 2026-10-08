"""پاک‌سازی متن وارداتی وردپرس هنگام نمایش.

در انتقال، شورت‌کد افزونه‌ها (جدول، پرسش متداول، جعبهٔ مقایسه و…) حذف شد و جایش پاراگراف و تیتر خالی ماند؛
بعضی نوشته‌ها هم چند <h1> در متن دارند و عکس‌هایشان alt ندارد. این‌ها در سرچ کنسول و ابزارهای سئو خطا
حساب می‌شوند و برای خواننده هم صفحه را نیمه‌کاره نشان می‌دهند. متن ذخیره‌شده دست نمی‌خورد؛ فقط خروجی تمیز می‌شود.
"""
import re

from django.utils.html import escape

LIVE = r"(?:installment_[a-z]+|price_updated|size_prices|size_faq|shipping_info|city_faq)"
SHORTCODE = re.compile(r"\[/?(?!" + LIVE + r"\b)[a-z][a-z0-9_-]*(?:\s[^\[\]]*)?\]", re.I)
EMPTY_P = re.compile(r"<p\b[^>]*>(?:\s|&nbsp;|&#160;|\xa0|<br\s*/?>|<span[^>]*>\s*</span>)*</p>", re.I)
EMPTY_H = re.compile(r"<(h[2-6])\b[^>]*>(?:\s|&nbsp;|\xa0|<br\s*/?>|<(?:span|strong|b|a)[^>]*>\s*</(?:span|strong|b|a)>)*</\1>", re.I)
HEAD = re.compile(r"<(h[2-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
H1 = re.compile(r"<(/?)h1\b", re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)
MEDIA = re.compile(r"<(?:img|table|iframe|video|figure|ul|ol|blockquote|div class=\"live-block)", re.I)


def _text(fragment):
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", fragment or "").replace("&nbsp;", ""))


# تیترهایی که در وردپرس فقط عنوانِ یک شورت‌کد بودند (پرسش متداول، جدول قیمت، مقایسه)
PLACEHOLDER = re.compile(r"سوالات\s*متداول|پرسش(?:‌|\s)?های\s*متداول|سؤالات\s*متداول|^لیست\s*قیمت|^جدول|مقایسه\s*(?:کامل|جدولی)")


def _drop_empty_sections(html):
    """تیترِ جای‌خالیِ شورت‌کد که تا تیتر بعدی هیچ متن و عکسی ندارد برداشته می‌شود.

    فقط تیترهای بی‌متن یا تیترهای «سوالات متداول/لیست قیمت/جدول…»؛ تیتر عادیِ پشت‌سرهم دست نمی‌خورد.
    """
    for _ in range(3):
        heads = list(HEAD.finditer(html))
        drop = []
        for i, h in enumerate(heads):
            inner = h.group(2)
            if MEDIA.search(inner):
                continue
            label = re.sub(r"<[^>]+>", "", inner).replace("&nbsp;", " ").strip()
            if label and not PLACEHOLDER.search(label):
                continue
            nxt = heads[i + 1] if i + 1 < len(heads) else None
            body = html[h.end():nxt.start() if nxt else len(html)]
            if _text(body) or MEDIA.search(body):
                continue
            if label and nxt is not None and int(nxt.group(1)[1]) > int(h.group(1)[1]):
                continue
            drop.append((h.start(), h.end()))
        if not drop:
            break
        for a, b in reversed(drop):
            html = html[:a] + html[b:]
    return html


def _img(title):
    alt = escape(title or "")

    def fix(m):
        tag = m.group(0)
        if not re.search(r'\salt="[^"]+"', tag):
            tag = re.sub(r'\salt="[^"]*"', "", tag)
            tag = tag[:4] + f' alt="{alt}"' + tag[4:]
        if "loading=" not in tag:
            tag = tag[:4] + ' loading="lazy" decoding="async"' + tag[4:]
        return tag
    return fix


def _shift_headings(html):
    """اگر متن h2 ندارد و از h3/h4 شروع می‌شود، تیترها یک یا دو پله بالا می‌آیند تا ساختار H1 ← H2 ← H3 درست شود."""
    levels = sorted({int(x) for x in re.findall(r"<h([2-6])\b", html, re.I)})
    if not levels or levels[0] == 2:
        return html
    shift = levels[0] - 2
    return re.sub(r"<(/?)h([3-6])\b", lambda m: f"<{m.group(1)}h{int(m.group(2)) - shift}", html, flags=re.I)


def tidy(html, title=""):
    if not html:
        return html
    html = SHORTCODE.sub("", html)
    html = H1.sub(lambda m: f"<{m.group(1)}h2", html)
    for _ in range(2):
        html = EMPTY_P.sub("", html)
        html = EMPTY_H.sub("", html)
    html = _drop_empty_sections(html)
    html = _shift_headings(html)
    html = IMG.sub(_img(title), html)
    return html
