"""کاربران مشکوک به اسپم (بیشترشان از ثبت‌نام ایمیلی دورهٔ وردپرس).

نامزد فقط کسی است که: کارمند نیست، هیچ سفارشی ندارد، همکار فروش یا فروشنده نیست و شمارهٔ موبایل معتبر ایران ندارد.
ثبت‌نام فعلی سایت فقط با موبایل و کد پیامکی است، پس کاربر تازه با این ویژگی‌ها ساخته نمی‌شود.
امتیاز و دلیل‌ها فقط برای کمک به تصمیم است؛ حذف را خودتان انجام می‌دهید.
"""
import re

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

COMMON = {"gmail.com", "yahoo.com", "ymail.com", "hotmail.com", "outlook.com", "live.com", "icloud.com", "me.com", "msn.com",
          "aol.com", "protonmail.com", "proton.me", "chmail.ir", "mail.ir", "yahoo.co.uk", "googlemail.com"}
BAD_TLD = {"ru", "xyz", "online", "store", "fun", "site", "work", "tips", "top", "click", "info", "biz", "space", "website", "shop",
           "pw", "cc", "cn", "tk", "ml", "ga", "cf", "gq", "icu", "buzz", "club", "life", "today", "pro", "id", "lol", "rest", "monster",
           "cyou", "sbs", "bond", "cfd", "beauty", "hair", "skin", "quest", "autos", "boats", "homes", "yachts", "mom", "ua", "kz", "pl", "de", "at"}
SPAM_WORDS = ("seo", "link", "backlink", "casino", "crypto", "bitcoin", "viagra", "loan", "bet", "porn", "forex", "promo", "ranking")
VOWELS = set("aeiouy")


def candidates(qs=None):
    User = get_user_model()
    qs = qs if qs is not None else User.objects.all()
    mobile_re = r"^09[0-9]{9}$"
    return (qs.filter(is_staff=False, is_superuser=False)
            .annotate(_orders=Count("orders"))
            .filter(_orders=0, affiliate__isnull=True, seller__isnull=True)
            .exclude(username__regex=mobile_re)
            .exclude(Q(profile__mobile__regex=mobile_re)))


def _random_looking(s):
    s = re.sub(r"[^a-z]", "", (s or "").lower())
    if len(s) < 8:
        return False
    vowel_ratio = sum(ch in VOWELS for ch in s) / len(s)
    longest_cons = max((len(m) for m in re.findall(r"[^aeiouy]+", s)), default=0)
    return vowel_ratio < 0.2 or longest_cons >= 5


def reasons(user):
    """[(امتیاز، دلیل)]"""
    out = [(3, "بدون موبایل"), (2, "بدون سفارش")]
    email = (user.email or "").lower().strip()
    local, _, domain = email.partition("@")
    if not email:
        out.append((1, "بدون ایمیل"))
    else:
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if domain not in COMMON and (tld in BAD_TLD or domain.count(".") >= 2 or re.search(r"\d", domain)):
            out.append((3, f"دامنهٔ ایمیل مشکوک ({domain})"))
        elif domain not in COMMON:
            out.append((1, f"دامنهٔ ایمیل ناآشنا ({domain})"))
        if local.count(".") >= 3:
            out.append((3, "ایمیل با نقطه‌های پشت‌سرهم (ترفند اسپم)"))
        if any(w in local for w in SPAM_WORDS):
            out.append((3, "کلمهٔ تبلیغاتی در ایمیل"))
        if re.search(r"\d{5,}", local) and not re.fullmatch(r"0?9\d{9}", local):
            out.append((1, "عدد طولانی در ایمیل"))
        if "@" in (user.username or "") and "irancarpet" in user.username:
            out.append((2, "نام کاربری ساختگی"))
    if _random_looking(user.username) or _random_looking(local):
        out.append((2, "نام تصادفی"))
    if not (user.first_name or user.last_name):
        out.append((1, "بدون نام"))
    if not user.last_login:
        out.append((1, "هرگز وارد نشده"))
    return out


def score(user):
    return sum(p for p, _ in reasons(user))


def level(user):
    s = score(user)
    return "high" if s >= 9 else "medium" if s >= 7 else "low"


def delete_safe(qs):
    """فقط کسانی که هنوز نامزدند (بی‌سفارش، بی‌موبایل، کارمند نیستند) حذف می‌شوند."""
    ids = list(candidates(qs).values_list("pk", flat=True))
    User = get_user_model()
    n = User.objects.filter(pk__in=ids).count()
    User.objects.filter(pk__in=ids).delete()
    return n
