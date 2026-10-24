"""حدس نقشه و رنگ زمینه از نام فایل عکس (فارسی یا فینگلیش).

«Bahar-Doodi-Noqrei» ← نقشهٔ «بهار»، زمینهٔ «دودی نقره ای»؛ «5006-Laki» ← کد ۵۰۰۶، زمینهٔ «لاکی».
بخش‌های آخر نام که رنگ شناخته‌شده‌اند رنگ‌اند و بقیه نقشه. هر اصلاح دستی در صفحهٔ افزودن سریع
(NameHint) یاد گرفته می‌شود تا دفعهٔ بعد همان نام درست حدس زده شود.
"""
import re

# رنگ‌های رایج فرش؛ کلید: نوشتهٔ فینگلیش (کوچک، بدون فاصله)
COLORS = {
    "kerem": "کرم", "kerm": "کرم", "krem": "کرم", "cream": "کرم", "kream": "کرم",
    "doodi": "دودی", "dudi": "دودی", "doudi": "دودی", "dodi": "دودی",
    "noqrei": "نقره ای", "noghrei": "نقره ای", "noqreei": "نقره ای", "noghreei": "نقره ای", "noqre": "نقره ای", "noghre": "نقره ای",
    "noqreyi": "نقره ای", "noghreyi": "نقره ای", "silver": "نقره ای",
    "bej": "بژ", "beige": "بژ", "bezh": "بژ", "beezh": "بژ",
    "laki": "لاکی", "lakki": "لاکی",
    "talaei": "طلایی", "talaee": "طلایی", "talai": "طلایی", "talayi": "طلایی", "gold": "طلایی",
    "sormei": "سرمه ای", "sormeei": "سرمه ای", "sormeyi": "سرمه ای", "sormeii": "سرمه ای", "surmei": "سرمه ای", "navy": "سرمه ای",
    "abi": "آبی", "aabi": "آبی", "blue": "آبی",
    "qermez": "قرمز", "ghermez": "قرمز", "red": "قرمز",
    "sabz": "سبز", "green": "سبز", "zard": "زرد", "yellow": "زرد",
    "meshki": "مشکی", "black": "مشکی", "sefid": "سفید", "white": "سفید",
    "toosi": "طوسی", "tusi": "طوسی", "tousi": "طوسی", "gray": "طوسی", "grey": "طوسی",
    "fili": "فیلی", "soorati": "صورتی", "sorati": "صورتی", "surati": "صورتی", "pink": "صورتی",
    "zereshki": "زرشکی", "firoozei": "فیروزه ای", "firouzei": "فیروزه ای", "firuzei": "فیروزه ای",
    "banafsh": "بنفش", "qahvei": "قهوه ای", "ghahvei": "قهوه ای", "ghahveei": "قهوه ای", "brown": "قهوه ای",
    "golbehi": "گلبهی", "kalbasi": "کالباسی", "dolfini": "دلفینی", "delfini": "دلفینی",
    "zeytooni": "زیتونی", "zeituni": "زیتونی", "zeytuni": "زیتونی", "yashmi": "یشمی", "abrishami": "ابریشمی",
    "estekhani": "استخوانی", "shiri": "شیری", "nabati": "نباتی", "anabi": "عنابی", "shokolati": "شکلاتی",
    "sadafi": "صدفی", "sadafy": "صدفی", "ronasi": "روناسی", "roonasi": "روناسی", "dolphini": "دلفینی",
    "moka": "موکا", "moca": "موکا", "mocha": "موکا", "titanium": "تیتانیوم", "sorbi": "سربی", "zoghali": "زغالی",
    "termei": "ترمه ای", "termeei": "ترمه ای", "oqianusi": "اقیانوسی", "oghianoosi": "اقیانوسی", "mooshi": "موشی", "mushi": "موشی",
    "gerdooei": "گردویی", "gerdui": "گردویی", "asali": "عسلی", "metalik": "متالیک", "carbon": "کاربنی", "karbani": "کاربنی",
    "nesfekafe": "نسکافه ای", "nescafe": "نسکافه ای", "mesi": "مسی", "ajori": "آجری", "yasi": "یاسی",
}

# نام‌های رایج نقشه که با نوشتن تقریبی اشتباه می‌شوند
DESIGNS = {
    "rayan": "رایان", "nazanin": "نازنین", "naghmeh": "نغمه", "naghme": "نغمه", "naqmeh": "نغمه", "bahar": "بهار",
    "shoka": "شوکا", "samin": "ثمین", "aein": "آئین", "aeen": "آئین", "ayin": "آیین", "zagros": "زاگرس", "vista": "ویستا",
    "tina": "تینا", "atrin": "آترین", "ana": "آنا", "afshan": "افشان", "darbari": "درباری", "kheshti": "خشتی",
    "mahi": "ماهی", "toranj": "ترنج", "golriz": "گلریز", "arshan": "آرشان", "kamelia": "کاملیا", "setareh": "ستاره",
    "vintage": "وینتیج", "vintej": "وینتیج", "parisa": "پریسا", "baran": "باران", "mahsa": "مهسا", "hasti": "هستی",
    "sahar": "سحر", "roya": "رویا", "yas": "یاس", "negar": "نگار", "nilufar": "نیلوفر", "niloofar": "نیلوفر",
    "golnaz": "گلناز", "golsa": "گلسا", "elnaz": "الناز", "romina": "رومینا", "helen": "هلن", "diba": "دیبا",
    "kashan": "کاشان", "isfahan": "اصفهان", "esfahan": "اصفهان", "tabriz": "تبریز", "heris": "هریس", "kerman": "کرمان",
    "shahrzad": "شهرزاد", "shayan": "شایان", "royal": "رویال", "classic": "کلاسیک", "modern": "مدرن", "mehrab": "محراب",
    "avin": "آوین", "faraz": "فراز", "javaher": "جواهر", "lux": "لوکس", "mandegar": "ماندگار", "meshkat": "مشکات",
    "naein": "نائین", "nain": "نائین", "rolex": "رولکس", "savis": "ساویس", "soroush": "سروش", "touska": "توسکا", "tuska": "توسکا",
    "hezar": "هزار", "golestan": "گلستان", "bita": "بیتا", "ariana": "آریانا", "artemis": "آرتمیس", "sina": "سینا",
}

SEP = re.compile(r"[\s_\-.]+")
PERSIAN = re.compile(r"[؀-ۿ]")


def key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fa_norm(s):
    return " ".join((s or "").replace("‌", " ").replace("ي", "ی").replace("ك", "ک").replace("-", " ").split())


# ------------------------------------------------------------------ اسکلت حروف بی‌صدا برای مقایسه
FA_SK = {"ب": "b", "پ": "p", "ت": "t", "ط": "t", "ث": "s", "س": "s", "ص": "s", "ج": "j", "چ": "c", "ح": "h", "ه": "h",
         "خ": "x", "د": "d", "ذ": "z", "ز": "z", "ض": "z", "ظ": "z", "ر": "r", "ژ": "Z", "ش": "S", "غ": "q", "ق": "q",
         "ف": "f", "ک": "k", "ك": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n"}


def skel_fa(s):
    out = "".join(FA_SK.get(ch, "") for ch in fa_norm(s).replace(" ", ""))
    return out[:-1] if out.endswith("h") and fa_norm(s).endswith("ه") else out


def skel_en(s):
    s = key(s)
    for a, b in (("kh", "x"), ("gh", "q"), ("sh", "S"), ("ch", "c"), ("zh", "Z"), ("ph", "f"), ("ck", "k"), ("c", "k"), ("w", "")):
        s = s.replace(a, b)
    s = re.sub(r"[aeiouyv0-9]", "", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    return s[:-1] if s.endswith("h") else s


# ------------------------------------------------------------------ نوشتن تقریبی فینگلیش به فارسی
def rough(word):
    """نوشتن تقریبی؛ کاربر در صفحه اصلاح می‌کند و اصلاحش یاد گرفته می‌شود."""
    w = key(word)
    if not w or w.isdigit():
        return word
    rules = [("kh", "خ"), ("gh", "ق"), ("sh", "ش"), ("ch", "چ"), ("zh", "ژ"), ("aa", "ا"), ("oo", "و"), ("ou", "و"), ("ee", "ی"),
             ("ei", "ی"), ("ai", "ای"), ("q", "ق"), ("b", "ب"), ("p", "پ"), ("t", "ت"), ("j", "ج"), ("h", "ه"), ("x", "خ"),
             ("d", "د"), ("r", "ر"), ("z", "ز"), ("s", "س"), ("f", "ف"), ("k", "ک"), ("c", "ک"), ("g", "گ"), ("l", "ل"),
             ("m", "م"), ("n", "ن"), ("v", "و"), ("w", "و"), ("y", "ی"), ("i", "ی"), ("u", "و"), ("o", "و"), ("a", "ا"), ("e", "")]
    out, i = [], 0
    while i < len(w):
        for a, b in rules:
            if w.startswith(a, i):
                if i == 0 and a in ("a", "aa"):
                    b = "آ"
                elif i == 0 and a in ("e", "i", "o", "u"):
                    b = "ا"
                elif a == "e" and i == len(w) - 1:
                    b = "ه"
                out.append(b)
                i += len(a)
                break
        else:
            i += 1
    return "".join(out)


# ------------------------------------------------------------------ حدس
def _learned():
    from .models import NameHint

    out = {"color": {}, "design": {}}
    for k, latin, fa in NameHint.objects.values_list("kind", "latin", "persian"):
        out.setdefault(k, {})[latin] = fa
    return out


def _color_word(tok, colors_fa, learned):
    k = key(tok)
    if not k:
        return None
    if k in learned["color"]:
        return learned["color"][k]
    if k in COLORS:
        return COLORS[k]
    if PERSIAN.search(tok):
        n = fa_norm(tok)
        if any(fa_norm(c) == n for c in colors_fa):
            return n
    return None


def _colors_match(name, colors_fa):
    n = fa_norm(name)
    for c in colors_fa:
        if fa_norm(c) == n:
            return c
    return name


BORDER_WORDS = {"hashiye", "hashie", "hashiyeh", "hashieh", "hashye", "hashiya", "border", "hashiyeh"}


def _field_color(toks, colors, learned):
    """(رنگ، کلمه‌های رنگ) از آخر کلمه‌ها؛ دست‌کم یک کلمه برای نقشه می‌ماند."""
    for n in range(min(3, len(toks) - 1), 1, -1):
        k = key("".join(toks[-n:]))
        if k in learned["color"]:
            return learned["color"][k], toks[-n:]
    parts, used, i = [], [], len(toks) - 1
    while i >= 1:
        c = _color_word(toks[i], colors, learned)
        if not c:
            break
        parts.insert(0, c)
        used.insert(0, toks[i])
        i -= 1
    if parts:
        return _colors_match(" ".join(parts), colors), used
    if len(toks) >= 2:  # رنگ ناشناخته: کلمهٔ آخر، با نوشتن تقریبی
        return (toks[-1] if PERSIAN.search(toks[-1]) else rough(toks[-1])), [toks[-1]]
    return "", []


def _border_color(toks, colors, learned):
    k = key("".join(toks))
    if not k:
        return ""
    if k in learned["color"]:
        return learned["color"][k]
    words = [_color_word(t, colors, learned) or (t if PERSIAN.search(t) else rough(t)) for t in toks]
    return _colors_match(" ".join(w for w in words if w), colors)


def guess(name, designs=(), colors=(), learned=None):
    """{design, color, border, dl, cl, bl, n, group}

    dl، cl و bl نوشتهٔ اصلی نقشه، رنگ زمینه و رنگ حاشیه در نام فایل‌اند (برای یادگرفتن اصلاح‌ها).
    n شمارهٔ عکس («Touska-Dolfini2» عکس دوم است) و group برای چسباندن عکس‌های یک فرش به هم.
    """
    learned = learned or _learned()
    toks = [t for t in SEP.split((name or "").strip()) if t]
    n = 1
    if toks and not toks[-1].isdigit():  # شمارهٔ چسبیده: Dolfini2
        m = re.match(r"^(.*?\D)(\d{1,2})$", toks[-1])
        if m and len(toks) > 1:
            toks[-1], n = m.group(1), int(m.group(2))
    while len(toks) > 2 and toks[-1].isdigit() and len(toks[-1]) <= 2:  # Rayan-Doodi-2
        n = int(toks.pop())
    empty = {"design": "", "color": "", "border": "", "dl": "", "cl": "", "bl": "", "n": n, "group": ""}
    if not toks:
        return empty
    # حاشیه: هرچه بعد از Hashiye بیاید
    border, btoks = "", []
    hi = next((i for i, t in enumerate(toks) if key(t) in BORDER_WORDS or t in ("حاشیه",)), None)
    if hi is not None and hi >= 1:
        btoks = toks[hi + 1:]
        border = _border_color(btoks, colors, learned)
        toks = toks[:hi]
    color, color_toks = _field_color(toks, colors, learned)
    d_toks = toks[:len(toks) - len(color_toks)]
    design = _design(d_toks, designs, learned)
    dl, cl, bl = key("".join(d_toks)), key("".join(color_toks)), key("".join(btoks))
    return {"design": design, "color": color, "border": border, "dl": dl, "cl": cl, "bl": bl, "n": n,
            "group": f"{dl}|{cl}|{bl}" if dl else ""}


def _design(toks, designs, learned):
    if not toks:
        return ""
    raw = " ".join(toks)
    if all(t.isdigit() for t in toks):  # کد نقشه
        return "".join(toks)
    if PERSIAN.search(raw):
        return fa_norm(raw)
    k = key(raw)
    if k in learned["design"]:
        return learned["design"][k]
    # نقشه‌های موجود همان آلبوم، با مقایسهٔ حروف بی‌صدا
    sk = skel_en(raw)
    if sk:
        for d in designs:
            if skel_fa(d) == sk:
                return d
    words = [DESIGNS.get(key(t)) or (t if t.isdigit() else rough(t)) for t in toks]
    return " ".join(words)


def learn(rows):
    """ردیف‌های ساخته‌شده: نوشتهٔ فینگلیش نام فایل ← نقشه و رنگی که کاربر تأیید کرد."""
    from .models import NameHint

    for r in rows:
        for kind, latin, fa in (("design", r.get("dl"), r.get("design")), ("color", r.get("cl"), r.get("color")),
                                ("color", r.get("bl"), r.get("border"))):
            latin, fa = key(latin)[:80], (fa or "").strip()[:120]
            if not latin or not fa or latin.isdigit() or PERSIAN.search(latin):
                continue
            builtin = (COLORS if kind == "color" else DESIGNS).get(latin)
            if builtin == fa:  # همان پیش‌فرض درست بود؛ یادگرفتهٔ قبلی (اگر بود) کنار برود
                NameHint.objects.filter(kind=kind, latin=latin).delete()
                continue
            NameHint.objects.update_or_create(kind=kind, latin=latin, defaults={"persian": fa})
