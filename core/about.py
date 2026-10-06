"""متن «دربارهٔ ایران کارپت» صفحهٔ اول.

برگهٔ صفحهٔ اولِ وردپرس پر از جعبه‌های محصول و دسته (عکس، قیمت، «مشاهده همه») است که در قالب تازه
به‌هم‌ریخته نشان داده می‌شد. اینجا فقط تیترها و پاراگراف‌های نوشتاری آن نگه داشته می‌شود.
اولویت: متن دستی «تنظیمات ← سایت و تماس» ← متن پاک‌شدهٔ برگهٔ صفحهٔ اول ← معرفی فروشگاه برای هوش مصنوعی.
"""
import html as _html
import re

from django.utils.html import escape

BLOCK = re.compile(r"<(h[2-4]|p|li)\b[^>]*>(.*?)</\1\s*>", re.I | re.S)
NOISE = ("تومان", "★", "مشاهده همه", "افزودن به سبد", "مشاهده محصول", "ریال")


def _text(fragment):
    t = re.sub(r"<br\s*/?>", " ", fragment, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def clean(content):
    """فقط تیتر و پاراگراف‌های واقعی؛ بدون عکس، کارت محصول، قیمت و فهرست پیوندها."""
    if not content:
        return ""
    content = re.sub(r"<(script|style|figure|table|iframe)\b.*?</\1>", " ", content, flags=re.I | re.S)
    content = re.sub(r"\[[^\]]+\]", " ", content)  # شورت‌کدهای وردپرس
    out, pending_head = [], None
    for tag, inner in BLOCK.findall(content):
        tag = tag.lower()
        text = _text(inner)
        if not text or any(n in text for n in NOISE):
            continue
        if tag.startswith("h"):
            if 4 <= len(text) <= 90:
                pending_head = text
            continue
        if len(text) < 60:  # عنوان کارت، برچسب، «۱۲۰۰ شانه» و…
            continue
        if pending_head:
            out.append(f"<h2>{escape(pending_head)}</h2>")
            pending_head = None
        out.append(f"<p>{escape(text)}</p>")
    return "\n".join(out) if sum(len(x) for x in out) >= 200 else ""


def paragraphs(text):
    return "\n".join(f"<p>{escape(p.strip())}</p>" for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text or "") if p.strip())


def home_about(site, page=None):
    if (site.home_about or "").strip():
        return site.home_about
    got = clean(page.content if page else "")
    if got:
        return got
    from seo.models import SeoSettings

    return paragraphs(SeoSettings.load().llms_about)
