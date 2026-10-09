"""فرم «تماس با ما»: بلوک‌های [contact_info] و [contact_form]، ثبت پیام با کپچای ساده، خبر پیامکی به مدیر و پاسخ پیامکی از پنل.

ضد ربات (بدون سرویس بیرونی):
  ۱. پرسش جمع ساده با عدد فارسی؛ پاسخ درست امضاشده در خود فرم است (بدون نیاز به session).
  ۲. فیلد پنهان «website» که فقط ربات پرش می‌کند.
  ۳. فرمی که زودتر از ۳ ثانیه پس از باز شدن صفحه فرستاده شود پذیرفته نمی‌شود.
  ۴. از هر نشانی اینترنتی حداکثر ۵ و از هر موبایل حداکثر ۳ پیام در ساعت.
"""
import hashlib
import logging
import random
import time

from django.core import signing
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.utils import latin_digits, normalize_mobile
from core.templatetags.fa import fa_num

log = logging.getLogger(__name__)
SALT = "contact-form"
MIN_SECONDS = 3
MAX_AGE = 3 * 3600
SESSION_KEY = "contact_form"


def _ip(request):
    return (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()


def new_challenge():
    a, b = random.randint(1, 9), random.randint(1, 9)
    token = signing.dumps({"s": a + b, "t": int(time.time()), "n": random.randint(0, 10**9)}, salt=SALT, compress=True)
    return f"{fa_num(a)} + {fa_num(b)}", token


def check_challenge(token, answer):
    """(درست؟، پیام خطا)"""
    try:
        d = signing.loads(token or "", salt=SALT, max_age=MAX_AGE)
    except signing.SignatureExpired:
        return False, "زمان فرم گذشته است؛ پرسش تازه را جواب دهید."
    except signing.BadSignature:
        return False, "فرم نامعتبر است؛ صفحه را دوباره باز کنید."
    if time.time() - d.get("t", 0) < MIN_SECONDS:
        return False, "فرم خیلی سریع فرستاده شد؛ چند ثانیه بعد دوباره بفرستید."
    if latin_digits(answer or "").strip() != str(d.get("s")):
        return False, "جواب پرسش امنیتی درست نیست."
    used = "contact:tok:" + hashlib.sha1((token or "").encode()).hexdigest()
    if cache.get(used):
        return False, "این فرم یک‌بار فرستاده شده است."
    cache.set(used, 1, MAX_AGE)
    return True, ""


def _limited(key, limit):
    k = f"contact:rl:{key}"
    n = cache.get(k, 0)
    if n >= limit:
        return True
    cache.set(k, n + 1, 3600)
    return False


# ------------------------------------------------------------------ بلوک‌ها
def block_info(request, title=""):
    from core.models import SiteSettings

    s = SiteSettings.load()
    return render_to_string("crm/contact_info.html", {"s": s}, request=request)


def block_form(request, title=""):
    from .models import ContactMessage

    flash = request.session.pop(SESSION_KEY, None) if hasattr(request, "session") else None
    q, token = new_challenge()
    data = (flash or {}).get("data") or {}
    if not data and getattr(request, "user", None) and request.user.is_authenticated:
        prof = getattr(request.user, "profile", None)
        data = {"name": request.user.get_full_name(), "mobile": getattr(prof, "mobile", "") or ""}
    return render_to_string("crm/contact_form.html", {
        "q": q, "token": token, "data": data, "errors": (flash or {}).get("errors") or {}, "sent": (flash or {}).get("sent"),
        "topics": ContactMessage.Topic.choices, "next": request.path,
    }, request=request)


# ------------------------------------------------------------------ ثبت
@require_POST
def send(request):
    from .models import ContactMessage

    p = request.POST
    nxt = p.get("next") or "/contact-us/"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/contact-us/"
    back = redirect(nxt + "#contact-form")
    data = {"name": (p.get("name") or "").strip()[:80], "mobile": (p.get("mobile") or "").strip()[:20],
            "topic": p.get("topic") or "buy", "message": (p.get("message") or "").strip()[:3000]}
    if (p.get("website") or "").strip():  # تلهٔ ربات: بی‌صدا رد، ولی ظاهر موفق
        request.session[SESSION_KEY] = {"sent": True}
        return back
    errors = {}
    if len(data["name"]) < 2:
        errors["name"] = "نام را بنویسید."
    mobile = normalize_mobile(data["mobile"])
    if not mobile:
        errors["mobile"] = "شمارهٔ موبایل درست نیست؛ پاسخ با پیامک به همین شماره می‌آید."
    if data["topic"] not in ContactMessage.Topic.values:
        data["topic"] = ContactMessage.Topic.OTHER
    if len(data["message"]) < 5:
        errors["message"] = "پیام را بنویسید."
    if not errors:
        ok, msg = check_challenge(p.get("token"), p.get("answer"))
        if not ok:
            errors["answer"] = msg
    if not errors and (_limited(f"ip:{_ip(request)}", 5) or _limited(f"m:{mobile}", 3)):
        errors["message"] = "پیام‌های شما رسیده است؛ برای پیام بیشتر کمی بعد دوباره بفرستید یا تماس بگیرید."
    if errors:
        request.session[SESSION_KEY] = {"data": data, "errors": errors}
        return back
    m = ContactMessage.objects.create(name=data["name"], mobile=mobile, topic=data["topic"], message=data["message"],
                                      ip=_ip(request) or None, page=nxt[:300])
    notify_admins(m)
    request.session[SESSION_KEY] = {"sent": True}
    return back


def notify_admins(m):
    from .models import CrmSettings
    from .notify import later

    if CrmSettings.load().contact_admin_sms:
        later(_notify_now, m.pk)


def _notify_now(pk):
    from .links import shorten
    from .models import ContactMessage, SmsLog
    from .notify import admins, send as sms

    m = ContactMessage.objects.filter(pk=pk).first()
    if not m:
        return
    text = f"پیام تازهٔ تماس با ما از {m.name} ({m.get_topic_display()}). خواندن و پاسخ: {shorten(f'/panel/contact-messages/{m.pk}/', 'l')}"
    for mob in admins():
        sms(mob, text, SmsLog.Kind.ADMIN)


# ------------------------------------------------------------------ پاسخ از پنل
def sms_parts(text):
    n = len(text or "")
    return 1 if n <= 70 else -(-n // 67)


def reply_text(m):
    body = (m.reply or "").strip()
    if "ایران کارپت" not in body:
        body += "\nایران کارپت"
    return f"{m.name} عزیز، {body}" if m.name else body


def send_reply(request, m):
    """بعد از ذخیره در پنل: اگر متن پاسخ تازه است، پیامک کن."""
    from django.contrib import messages

    from .models import ContactMessage, SmsLog
    from .notify import send as sms

    body = (m.reply or "").strip()
    if not body or body == (m.reply_sent or "").strip():
        return
    text = reply_text(m)
    ok = sms(m.mobile, text, SmsLog.Kind.CONTACT)
    if ok:
        ContactMessage.objects.filter(pk=m.pk).update(reply_sent=body, replied_at=timezone.now(), replied_by=request.user,
                                                      status=ContactMessage.Status.ANSWERED)
        messages.success(request, f"پاسخ به {fa_num(m.mobile)} پیامک شد ({fa_num(sms_parts(text))} پیامک).")
    else:
        messages.error(request, "پیامک پاسخ فرستاده نشد؛ «پیامک‌های فرستاده‌شده» را ببینید و دوباره «ذخیره» بزنید.")
