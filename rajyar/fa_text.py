"""چیدن متن فارسی برای Pillow وقتی کتابخانهٔ raqm روی سرور نیست (شکل پیوستهٔ حروف + راست‌به‌چپ).

اگر Pillow با raqm نصب باشد همان به‌کار می‌رود و این فایل فقط پشتیبان است.
"""
import re

# حرف: (تنها، پایانی، آغازی، میانی)؛ حرف‌هایی که به بعد نمی‌چسبند فقط دو شکل دارند
FORMS = {
    "ء": ("ﺀ",), "آ": ("ﺁ", "ﺂ"), "أ": ("ﺃ", "ﺄ"), "ؤ": ("ﺅ", "ﺆ"), "إ": ("ﺇ", "ﺈ"),
    "ئ": ("ﺉ", "ﺊ", "ﺋ", "ﺌ"), "ا": ("ﺍ", "ﺎ"), "ب": ("ﺏ", "ﺐ", "ﺑ", "ﺒ"),
    "ة": ("ﺓ", "ﺔ"), "ت": ("ﺕ", "ﺖ", "ﺗ", "ﺘ"), "ث": ("ﺙ", "ﺚ", "ﺛ", "ﺜ"),
    "ج": ("ﺝ", "ﺞ", "ﺟ", "ﺠ"), "ح": ("ﺡ", "ﺢ", "ﺣ", "ﺤ"), "خ": ("ﺥ", "ﺦ", "ﺧ", "ﺨ"),
    "د": ("ﺩ", "ﺪ"), "ذ": ("ﺫ", "ﺬ"), "ر": ("ﺭ", "ﺮ"), "ز": ("ﺯ", "ﺰ"),
    "س": ("ﺱ", "ﺲ", "ﺳ", "ﺴ"), "ش": ("ﺵ", "ﺶ", "ﺷ", "ﺸ"), "ص": ("ﺹ", "ﺺ", "ﺻ", "ﺼ"),
    "ض": ("ﺽ", "ﺾ", "ﺿ", "ﻀ"), "ط": ("ﻁ", "ﻂ", "ﻃ", "ﻄ"), "ظ": ("ﻅ", "ﻆ", "ﻇ", "ﻈ"),
    "ع": ("ﻉ", "ﻊ", "ﻋ", "ﻌ"), "غ": ("ﻍ", "ﻎ", "ﻏ", "ﻐ"), "ف": ("ﻑ", "ﻒ", "ﻓ", "ﻔ"),
    "ق": ("ﻕ", "ﻖ", "ﻗ", "ﻘ"), "ك": ("ﻙ", "ﻚ", "ﻛ", "ﻜ"), "ل": ("ﻝ", "ﻞ", "ﻟ", "ﻠ"),
    "م": ("ﻡ", "ﻢ", "ﻣ", "ﻤ"), "ن": ("ﻥ", "ﻦ", "ﻧ", "ﻨ"), "ه": ("ﻩ", "ﻪ", "ﻫ", "ﻬ"),
    "و": ("ﻭ", "ﻮ"), "ى": ("ﻯ", "ﻰ"), "ي": ("ﻱ", "ﻲ", "ﻳ", "ﻴ"),
    "پ": ("ﭖ", "ﭗ", "ﭘ", "ﭙ"), "چ": ("ﭺ", "ﭻ", "ﭼ", "ﭽ"), "ژ": ("ﮊ", "ﮋ"),
    "ک": ("ﮎ", "ﮏ", "ﮐ", "ﮑ"), "گ": ("ﮒ", "ﮓ", "ﮔ", "ﮕ"), "ی": ("ﯼ", "ﯽ", "ﯾ", "ﯿ"),
}
LAM_ALEF = {"آ": ("ﻵ", "ﻶ"), "أ": ("ﻷ", "ﻸ"), "إ": ("ﻹ", "ﻺ"), "ا": ("ﻻ", "ﻼ")}
LTR = re.compile(r"[A-Za-z0-9۰-۹٠-٩](?:[A-Za-z0-9۰-۹٠-٩.,٫٬:/%@_\- ]*[A-Za-z0-9۰-۹٠-٩%])?")


def _joins_next(ch):
    return ch in FORMS and len(FORMS[ch]) == 4


def reshape(text):
    out, chars, i = [], list(text), 0
    while i < len(chars):
        ch = chars[i]
        if ch not in FORMS:
            out.append("" if ch == "‌" else ch)
            i += 1
            continue
        prev = chars[i - 1] if i else ""
        joined_before = _joins_next(prev)
        if ch == "ل" and i + 1 < len(chars) and chars[i + 1] in LAM_ALEF:
            out.append(LAM_ALEF[chars[i + 1]][1 if joined_before else 0])
            i += 2
            continue
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        joins_after = _joins_next(ch) and nxt in FORMS
        f = FORMS[ch]
        if joined_before and joins_after:
            out.append(f[3])
        elif joined_before:
            out.append(f[1] if len(f) > 1 else f[0])
        elif joins_after:
            out.append(f[2])
        else:
            out.append(f[0])
        i += 1
    return "".join(out)


def visual(text):
    """متن منطقی ← ترتیب دیداری برای رسم چپ‌به‌راست (عددها و کلمه‌های لاتین وارونه نمی‌شوند)."""
    s = reshape(text.replace("\u2066", "").replace("\u2069", ""))
    mirror = str.maketrans("()[]«»", ")(][»«")
    rev = s[::-1].translate(mirror)
    return LTR.sub(lambda m: m.group(0)[::-1], rev)
