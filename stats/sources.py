"""تشخیص منبع ورود از نشانی ارجاع‌دهنده (Referer) و پارامترهای UTM."""
import re
from urllib.parse import parse_qs, urlsplit

SEARCH = {"google": "گوگل", "bing": "بینگ", "yahoo": "یاهو", "duckduckgo": "داک‌داک‌گو", "yandex": "یاندکس",
          "ecosia": "اکوزیا", "brave.com": "بریو", "zarebin": "ذره‌بین", "gerdoo": "گردو", "parsijoo": "پارسی‌جو",
          "yooz": "یوز", "baidu": "بایدو", "qwant": "کوانت", "startpage": "استارت‌پیج"}
SOCIAL = {"instagram.com": "اینستاگرام", "t.me": "تلگرام", "telegram.org": "تلگرام", "telegram.me": "تلگرام",
          "whatsapp.com": "واتساپ", "wa.me": "واتساپ", "eitaa.com": "ایتا", "ble.ir": "بله", "bale.ai": "بله",
          "rubika.ir": "روبیکا", "igap.net": "آی‌گپ", "soroush": "سروش", "facebook.com": "فیسبوک", "fb.com": "فیسبوک",
          "t.co": "ایکس (توییتر)", "twitter.com": "ایکس (توییتر)", "x.com": "ایکس (توییتر)", "linkedin.com": "لینکدین",
          "lnkd.in": "لینکدین", "aparat.com": "آپارات", "youtube.com": "یوتیوب", "youtu.be": "یوتیوب",
          "pinterest.": "پینترست", "threads.net": "تردز"}
COMPARE = {"torob.com": "ترب", "emalls.ir": "ایمالز", "basalam.com": "باسلام", "digikala.com": "دیجی‌کالا",
           "divar.ir": "دیوار", "sheypoor.com": "شیپور"}
APPS = {"com.instagram.android": ("social", "اینستاگرام"), "org.telegram.messenger": ("social", "تلگرام"),
        "org.telegram.plus": ("social", "تلگرام"), "com.whatsapp": ("social", "واتساپ"),
        "ir.eitaa.messenger": ("social", "ایتا"), "ir.nasim": ("social", "بله"), "ir.resaneh1.iptv": ("social", "روبیکا"),
        "com.google.android.googlequicksearchbox": ("search", "گوگل"), "com.google.android.gm": ("referral", "جیمیل"),
        "com.twitter.android": ("social", "ایکس (توییتر)"), "com.linkedin.android": ("social", "لینکدین")}
UTM_MEDIUM = {"cpc": "تبلیغ کلیکی", "ppc": "تبلیغ کلیکی", "paid": "تبلیغ", "banner": "بنر", "display": "بنر",
              "social": "شبکهٔ اجتماعی", "story": "استوری", "post": "پست", "sms": "پیامک", "email": "ایمیل",
              "referral": "معرفی", "qr": "کد QR", "print": "چاپی"}


def _clean(v, n):
    return re.sub(r"[\x00-\x1f<>\"']", "", (v or "").strip())[:n]


def host_of(url):
    url = (url or "").strip()
    if url.startswith("android-app://"):
        return url[len("android-app://"):].split("/")[0].lower()
    try:
        h = urlsplit(url).hostname or ""
    except ValueError:
        return ""
    h = h.lower()
    return h[4:] if h.startswith("www.") else h


def _match(host, table):
    for key, name in table.items():
        if host == key or host.endswith("." + key) or (key.endswith(".") and key in host + ".") or \
                (("." not in key) and re.search(rf"(^|\.){re.escape(key)}\.", host)):
            return name
    return ""


def utm_from(query):
    q = parse_qs(query or "")
    get = lambda k: _clean((q.get(k) or [""])[0], 80)  # noqa: E731
    return {"source": get("utm_source")[:60], "medium": get("utm_medium")[:40], "campaign": get("utm_campaign")}


def classify(referrer, own_hosts=()):
    """(دسته، نام) از ارجاع‌دهنده؛ ارجاع داخلی ← («internal», "")."""
    host = host_of(referrer)
    if not host:
        return "direct", ""
    if referrer.startswith("android-app://"):
        src, name = APPS.get(host, ("referral", host[:60]))
        return src, name
    if host in own_hosts:
        return "internal", ""
    for table, src in ((SEARCH, "search"), (SOCIAL, "social"), (COMPARE, "compare")):
        name = _match(host, table)
        if name:
            return src, name
    return "referral", host[:60]


def medium_label(medium):
    return UTM_MEDIUM.get((medium or "").lower(), medium or "")
