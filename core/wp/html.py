"""تبدیل محتوای خام وردپرس به HTML نهایی (معادل wpautop و چند شورت‌کد)."""
import re

BLOCK = (
    r"table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt|ul|ol|li|pre|form|map|area|"
    r"blockquote|address|math|style|p|h[1-6]|hr|fieldset|legend|section|article|aside|hgroup|header|"
    r"footer|nav|figure|figcaption|details|menu|summary|iframe|script|video|audio|source|object|embed"
)


def wpautop(text):
    """نسخهٔ ساده‌شدهٔ wpautop وردپرس."""
    if not text or not text.strip():
        return ""
    if "<!-- wp:" in text:  # محتوای گوتنبرگ از قبل HTML کامل دارد
        return re.sub(r"<!-- /?wp:[^>]*-->", "", text)
    pre_blocks = {}

    def _keep(m):
        key = f"<pre wp-pre-tag-{len(pre_blocks)}></pre>"
        pre_blocks[key] = m.group(0)
        return key

    text = re.sub(r"<pre[\s\S]*?</pre>", _keep, text)
    text = text.replace("\r\n", "\n").replace("\r", "\n") + "\n"
    text = re.sub(r"<br\s*/?>\s*<br\s*/?>", "\n\n", text)
    text = re.sub(rf"(<(?:{BLOCK})[\s/>])", r"\n\n\1", text)
    text = re.sub(rf"(</(?:{BLOCK})>)", r"\1\n\n", text)
    text = re.sub(r"\n\n+", "\n\n", text)
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    out = []
    for p in paras:
        p = p.strip()
        if re.match(rf"^</?(?:{BLOCK})[\s/>]", p) or re.search(rf"</(?:{BLOCK})>\s*$", p):
            out.append(p)
        else:
            out.append("<p>" + p + "</p>")
    text = "\n".join(out)
    text = re.sub(rf"<p>\s*(</?(?:{BLOCK})[^>]*>)", r"\1", text)
    text = re.sub(rf"(</?(?:{BLOCK})[^>]*>)\s*</p>", r"\1", text)
    text = re.sub(r"<p>\s*</p>", "", text)
    # تک‌خط‌ها → <br> (به‌جز کنار تگ‌های بلاکی)
    text = re.sub(rf"(?<!>)\n(?!\s*</?(?:{BLOCK}))", "<br>\n", text)
    for key, val in pre_blocks.items():
        text = text.replace(key, val)
    return text


def caption_shortcode(text):
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        img = re.search(r"(<a[^>]*>\s*)?<img[^>]*>(\s*</a>)?", inner)
        cap = inner[img.end():].strip() if img else inner
        img_html = img.group(0) if img else ""
        return f'<figure class="wp-caption">{img_html}<figcaption>{cap}</figcaption></figure>'

    return re.sub(r"\[caption([^\]]*)\]([\s\S]*?)\[/caption\]", repl, text)


def strip_shortcodes(text):
    text = re.sub(r"\[embed\]([^\[]+)\[/embed\]", r'<p><a href="\1">\1</a></p>', text)
    text = re.sub(r"\[video[^\]]*?(?:mp4|src)=\"([^\"]+)\"[^\]]*\](?:\[/video\])?", r'<video controls preload="none" src="\1"></video>', text)
    text = re.sub(r"\[/?(?:vc_|ultimate-faqs|button|wpb_|dokan|ErimaZarinpalDonate|woocommerce_)[^\]]*\]", "", text)
    return text


def clean_content(raw):
    if not raw:
        return ""
    text = caption_shortcode(raw)
    text = strip_shortcodes(text)
    return wpautop(text)
