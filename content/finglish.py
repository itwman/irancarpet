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

# رنگ‌های فارسی که در نام فایل با فاصله نوشته می‌شوند («نقره ای»، «سرمه ای») یا در فهرست فینگلیش نیستند
FA_EXTRA = {"قرمز", "لاکی", "سیلور", "نقره", "خاکستری", "توسی", "سورمه ای", "سیاه", "گلد", "پسته ای", "کرم", "بژ", "دودی", "آبی",
            "فیروزه", "نیلی", "کرمی", "بژی", "طلایی", "مسی", "یاقوتی", "لاجوردی", "گلبهی", "کالباسی", "خردلی", "زیتونی"}
# نام نماهای یک فرش که برنامهٔ جداکردن عکس آلبومی به آخر نام می‌گذارد: «افسانه نقره ای 12059-2-یک‌چهارم»
VIEWS = {"تمامقد", "یکچهارم", "مرکز", "گوشه", "کامل", "زوم", "جزئیات", "نزدیک"}
SEP = re.compile(r"[\s_\-.()\[\]]+")
PERSIAN = re.compile(r"[؀-ۿ]")


def key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def tight(s):
    """برای مقایسه: بدون فاصله و نیم‌فاصله، «ی/ک» فارسی، رقم لاتین («طلا کوب» = «طلاکوب»)."""
    s = fa_norm(s).replace(" ", "").lower()
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def gkey(s):
    """کلید گروه‌بندی عکس‌ها. نام فارسی کامل مقایسه می‌شود، نه فقط عددهایش
    (وگرنه «افسانه نقره ای 12059» و «افسانه کرم 12059» یکی می‌شدند)."""
    return tight(s) if PERSIAN.search(s or "") else key(s)


def _spaced(name):
    """«کرم۱۲۰۲۹» ← «کرم ۱۲۰۲۹» (عدد چسبیده به حرف فارسی)."""
    name = re.sub(r"([آ-ی])([0-9۰-۹])", r"\1 \2", name or "")
    return re.sub(r"([0-9۰-۹])([آ-ی])", r"\1 \2", name)


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
    if PERSIAN.search(tok):
        n = tight(tok)
        return next((fa_norm(c) for c in fa_colors(colors_fa) if tight(c) == n), None)
    k = key(tok)
    if not k:
        return None
    if k in learned["color"]:
        return learned["color"][k]
    if k in COLORS:
        return COLORS[k]
    return None


def fa_colors(colors_fa=()):
    """همهٔ رنگ‌های فارسی شناخته‌شده: رنگ‌های سایت، فهرست بالا و رنگ‌های هم‌معنی تنظیمات."""
    out = list(colors_fa) + sorted(set(COLORS.values()) | FA_EXTRA)
    for group in synonym_groups():
        out += group
    return out


def _fa_field_color(toks, colors, learned):
    """نام فارسی با فاصله: «افشان شاهی نقره ای» ← (نقره ای، [نقره، ای]). رنگ‌های چندکلمه‌ای از آخر نام."""
    known = {tight(c): fa_norm(c) for c in fa_colors(colors)}
    parts, used, i = [], [], len(toks)
    while i > 1:
        for n in (3, 2, 1):
            if i - n < 1:  # دست‌کم یک کلمه برای نقشه
                continue
            c = known.get(tight("".join(toks[i - n:i])))
            if c:
                parts.insert(0, c)
                used[:0] = toks[i - n:i]
                i -= n
                break
        else:
            break
    if parts:
        return _colors_match(" ".join(parts), colors), used
    if len(toks) >= 3 and tight(toks[-1]) in ("ای", "ایی"):  # رنگ ناشناخته‌ای مثل «پسته ای»
        return fa_norm(" ".join(toks[-2:])), toks[-2:]
    if len(toks) >= 2:
        return fa_norm(toks[-1]), [toks[-1]]
    return "", []

def _colors_match(name, colors_fa):
    n = tight(name)
    for c in colors_fa:
        if tight(c) == n:
            return c
    return fa_norm(name) if PERSIAN.search(name) else name


BORDER_WORDS = {"hashiye", "hashie", "hashiyeh", "hashieh", "hashye", "hashiya", "border", "hashiyeh"}


def _field_color(toks, colors, learned):
    """(رنگ، کلمه‌های رنگ) از آخر کلمه‌ها؛ دست‌کم یک کلمه برای نقشه می‌ماند."""
    if toks and PERSIAN.search(toks[-1]):
        return _fa_field_color(toks, colors, learned)
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
    if toks and PERSIAN.search("".join(toks)):
        return _colors_match(" ".join(toks), colors)
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
    toks = [t for t in SEP.split(_spaced(name).strip()) if t]
    persian = bool(PERSIAN.search(name or ""))
    while len(toks) > 2 and tight(toks[-1]) in VIEWS:  # «-2-یک‌چهارم»: نمای دیگری از همان فرش
        toks.pop()
    n = 1
    if toks and not toks[-1].isdigit():  # شمارهٔ چسبیده: Dolfini2
        m = re.match(r"^(.*?\D)(\d{1,2})$", toks[-1])
        if m and len(toks) > 1:
            toks[-1], n = m.group(1), int(m.group(2))
    while len(toks) > 2 and toks[-1].isdigit() and len(toks[-1]) <= 2:  # Rayan-Doodi-2
        n = int(toks.pop())
    code = ""
    if persian and len(toks) > 2 and toks[-1].isdigit() and len(toks[-1]) >= 3:  # «افسانه نقره ای 12059»: کد نقشه
        code = toks.pop()
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
    if code:
        from core.templatetags.fa import fa_num

        d_toks = d_toks + [code]
        design = f"{design} {fa_num(str(int(code)))}" if design else code
    dl, cl, bl = key("".join(d_toks)), key("".join(color_toks)), key("".join(btoks))
    g = [gkey("".join(x)) for x in (d_toks, color_toks, btoks)]
    return {"design": design, "color": color, "border": border, "dl": dl, "cl": cl, "bl": bl, "n": n,
            "group": "|".join(g) if g[0] else ""}


def _design(toks, designs, learned):
    if not toks:
        return ""
    raw = " ".join(toks)
    if all(t.isdigit() for t in toks):  # کد نقشه
        return "".join(toks)
    if PERSIAN.search(raw):  # همان نوشتهٔ نقشهٔ موجود آلبوم («کرشمه طلا کوب» ← «کرشمه طلاکوب»)
        return next((d for d in designs if tight(d) == tight(raw)), fa_norm(raw))
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


# ------------------------------------------------------------------ رنگ‌های هم‌معنی (برای پیدا کردن فرش تکراری)
def synonym_groups():
    """[[«لاکی»، «قرمز»], …] از تنظیمات محتوا (هر خط یک گروه)."""
    try:
        from .models import ContentSettings

        text = ContentSettings.load().color_synonyms
    except Exception:  # پیش از مهاجرت
        text = ""
    out = []
    for line in (text or "").splitlines():
        words = [fa_norm(w) for w in re.split(r"[,،=/]+", line) if fa_norm(w)]
        if len(words) > 1:
            out.append(words)
    return out


class ColorCanon:
    """رنگ ← شکل یکسان برای مقایسه: «سیلور» و «نقره‌ای» یکی، «دودی سیلور» = «دودی نقره ای»."""

    def __init__(self, groups=None):
        groups = synonym_groups() if groups is None else groups
        self.map = {}
        for g in groups:
            for w in g:
                self.map.setdefault(tight(w), tight(g[0]))
        alts = sorted(self.map, key=len, reverse=True)
        self.rx = re.compile("|".join(re.escape(a) for a in alts)) if alts else None

    def __call__(self, color):
        t = tight(color)
        return self.rx.sub(lambda m: self.map[m.group(0)], t) if self.rx else t
