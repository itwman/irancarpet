"""پاک‌سازی متن وارداتی وردپرس هنگام نمایش.

در انتقال، شورت‌کد افزونه‌ها (جدول، پرسش متداول، جعبهٔ مقایسه و…) حذف شد و جایش پاراگراف و تیتر خالی ماند؛
بعضی نوشته‌ها هم چند <h1> در متن دارند و عکس‌هایشان alt ندارد. این‌ها در سرچ کنسول و ابزارهای سئو خطا
حساب می‌شوند و برای خواننده هم صفحه را نیمه‌کاره نشان می‌دهند. متن ذخیره‌شده دست نمی‌خورد؛ فقط خروجی تمیز می‌شود.
"""
import re

from django.utils.html import escape

LIVE = r"(?:installment_[a-z]+|price_updated|size_prices|size_faq|shipping_info|city_faq|reeds_compare|price_table|city_notice|reeds_links)"
SHORTCODE = re.compile(r"\[/?(?!" + LIVE + r"\b)[a-z][a-z0-9_-]*(?:\s[^\[\]]*)?\]", re.I)
EMPTY_P = re.compile(r"<p\b[^>]*>(?:\s|&nbsp;|&#160;|\xa0|<br\s*/?>|<span[^>]*>\s*</span>)*</p>", re.I)
EMPTY_H = re.compile(r"<(h[2-6])\b[^>]*>(?:\s|&nbsp;|\xa0|<br\s*/?>|<(?:span|strong|b|a)[^>]*>\s*</(?:span|strong|b|a)>)*</\1>", re.I)
HEAD = re.compile(r"<(h[2-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
H1 = re.compile(r"<(/?)h1\b", re.I)
IMG = re.compile(r"<img\b[^>]*>", re.I)
# تیتری که فقط یک عکس است (در وردپرس زیاد بود) ← پاراگراف عکس؛ «تیتر خالی» حساب نشود
IMG_HEAD = re.compile(r"<(h[1-6])\b[^>]*>((?:\s|&nbsp;|<br\s*/?>)*(?:<a\b[^>]*>\s*)?<img\b[^>]*>(?:\s*</a>)?(?:\s|&nbsp;|<br\s*/?>)*)</\1>", re.I)
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


# عکس‌های قدیمی که جایشان بخش زنده می‌نشیند:
#   price-list-*.jpg   (لیست قیمت تصویری با قیمت‌های کهنه)  ← [price_table]
#   at-city*.jpg       (اطلاعیهٔ «ما در شهر شما فروشگاه نداریم») ← [city_notice]
_WRAP = r"(?:<br\s*/?>\s*)*(?:<a\b[^>]*>\s*)?<img\b[^>]*src=\"[^\"]*{}[^\"]*\"[^>]*>(?:\s*</a>)?"
PRICE_IMG = re.compile(_WRAP.format(r"/price-list-"), re.I)
CITY_IMG = re.compile(_WRAP.format(r"/at-city"), re.I)
LIVE_PRICES = re.compile(r"\[(?:size_prices|installment_prices|price_table)\b")


BLOCK_SC = r"(\[(?:installment_(?:calc|prices|plans|steps|faq)|size_prices|size_faq|shipping_info|city_faq|reeds_compare|price_table|city_notice|reeds_links)\b[^\]]*\])"


def _swap_images(html):
    has_prices = bool(LIVE_PRICES.search(html))
    html = PRICE_IMG.sub("" if has_prices else "</p>\n[price_table]\n<p>", html, count=0 if has_prices else 1)
    html = PRICE_IMG.sub("", html)  # تکرار همان عکس در یک صفحه
    html = CITY_IMG.sub("</p>\n[city_notice]\n<p>", html, count=1)
    html = CITY_IMG.sub("", html)
    return html


# شماره‌های قدیمی که در متن مقاله‌ها مانده‌اند ← شمارهٔ فعلی «موبایل پاسخگو» در تنظیمات سایت
OLD_PHONES = ("09133616132", "09371982000")
_D = "[0-9۰-۹]"
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _phone_re(num):
    digits = num[1:]  # بدون صفر اول؛ با ۰ یا +98 یا 0098
    body = r"[-\s‌]?".join(f"[{d}{d.translate(_FA)}]" for d in digits)
    return re.compile(r"(?:\+98|0098|[0۰])[-\s]?" + body)


PHONE_RES = [_phone_re(n) for n in OLD_PHONES]


def _swap_phones(html, phone):
    digits = re.sub(r"\D", "", (phone or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    if len(digits) != 11:
        return html
    for rx in PHONE_RES:
        html = rx.sub(lambda m: digits.translate(_FA) if re.search("[۰-۹]", m.group(0)) else
                      ("+98" + digits[1:] if m.group(0).startswith("+98") else digits), html)
    return html


# بنرهای شانه (700/1000/1200/1500-Reeds-min.png) که در ۸۳ مقاله یک‌بار اول و یک‌بار آخر تکرار شده بودند:
# فقط یک‌بار، آخر مقاله، به‌صورت کارت متنی با قیمت روز ([reeds_links])؛ جای دستهٔ بالایی یک پیوند کوتاه «پرش به انتخاب فرش».
_BANNER = r"(?:<a\b[^>]*>\s*)?<img\b[^>]*-Reeds(?:-min)?(?:-\d+)?\.(?:png|jpe?g|webp)[^>]*>(?:\s*</a>)?"
BANNERS = re.compile(_BANNER + r"(?:(?:\s|&nbsp;|<br\s*/?>|</?p\b[^>]*>)*" + _BANNER + r")*", re.I)
INTRO = re.compile(r"<p\b[^>]*>((?:(?!</p>).)*?(?:لینک(?:\s|‌)?(?:های)?\s+(?:زیر|ذیل)|انتخاب\s*(?:و\s*خریداری)?\s*(?:کنید|نمایید))(?:(?!</p>).)*)</p>\s*(?:<p\b[^>]*>\s*)?$", re.S)
SKIP = '<p class="lb-skip">فرصت خواندن همهٔ مقاله را ندارید؟ <a href="#choose-reeds">فرش‌ها را بر اساس شانه ببینید</a>.</p>'


def _merge_banners(html):
    groups = list(BANNERS.finditer(html))
    if not groups:
        return html
    out, last = [], 0
    for i, g in enumerate(groups):
        before = html[last:g.start()]
        if i < len(groups) - 1:
            m = INTRO.search(before)
            if m:
                before = before[:m.start()]
            out.append(before + "</p>\n" + (SKIP if i == 0 else "") + "\n<p>")
        else:
            out.append(before + "</p>\n[reeds_links]\n<p>")
        last = g.end()
    out.append(html[last:])
    return "".join(out)


def _unlink_self(html, self_path):
    """پیوند مقاله به خودش (بدون #) فقط متن می‌شود؛ برای گوگل ارزشی ندارد و برای خواننده صفحه را دوباره باز می‌کند."""
    from urllib.parse import unquote, urlsplit

    target = unquote(self_path or "").rstrip("/")
    if not target:
        return html

    def fix(m):
        href = m.group(1)
        if "#" in href:
            return m.group(0)
        parts = urlsplit(unquote(href))
        if parts.netloc and not parts.netloc.endswith("irancarpet.net"):
            return m.group(0)
        return m.group(2) if parts.path.rstrip("/") == target and not parts.query else m.group(0)
    return re.sub(r'<a\b[^>]*\shref="([^"]*)"[^>]*>((?:(?!</?a\b).)*?)</a>', fix, html, flags=re.S | re.I)


def _balance_divs(html):
    """تگ‌های بلوکی باز یا بستهٔ اضافه در متن وارداتی (div، article، section…) ستون‌بندی صفحه را به هم می‌ریزد:
    بسته‌شدن‌های بی‌جفت حذف و بازهای بی‌جفت در پایان بسته می‌شوند."""
    tags = "div|article|section|aside|main|nav|header|footer"
    out, stack, last = [], [], 0
    for m in re.finditer(rf"<(/?)({tags})\b[^>]*>", html, re.I):
        tag = m.group(2).lower()
        if not m.group(1):
            stack.append(tag)
            continue
        if tag in stack:
            while stack and stack[-1] != tag:  # بسته‌نشده‌های داخلی همین‌جا بسته می‌شوند
                out.append(html[last:m.start()] + f"</{stack.pop()}>")
                last = m.start()
            stack.pop()
        else:
            out.append(html[last:m.start()])
            last = m.end()
    out.append(html[last:])
    return "".join(out) + "".join(f"</{t}>" for t in reversed(stack))


def tidy(html, title="", phone="", self_path=""):
    if not html:
        return html
    html = SHORTCODE.sub("", html)
    if phone:
        html = _swap_phones(html, phone)
    html = _swap_images(html)
    html = _merge_banners(html)
    if self_path:
        html = _unlink_self(html, self_path)
    html = IMG_HEAD.sub(lambda m: f'<p class="wp-img">{m.group(2).strip()}</p>', html)
    html = H1.sub(lambda m: f"<{m.group(1)}h2", html)
    for _ in range(2):
        html = EMPTY_P.sub("", html)
        html = EMPTY_H.sub("", html)
    html = _drop_empty_sections(html)
    html = _shift_headings(html)
    html = IMG.sub(_img(title), html)
    html = _balance_divs(html)
    # برچسب‌های <p> سرگردان دور بخش‌های زنده (بعد از جایگزینی عکس‌ها)
    html = re.sub(BLOCK_SC + r"\s*</p>", r"\1", html)
    html = re.sub(r"<p\b[^>]*>\s*" + BLOCK_SC, r"\1", html)
    html = re.sub(r"(</(?:p|div|nav|aside|ul|ol|table|h[2-6])>)\s*</p>", r"\1", html)
    return html
