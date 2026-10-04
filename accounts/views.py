import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import sms
from .models import OtpCode, Profile
from .utils import latin_digits, normalize_mobile

META = {"robots": "noindex, nofollow"}


def _next(request, default="/my-account/"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return default


def _client_ip(request):
    return (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()


def _dev_codes():
    return not sms.configured() and (settings.DEBUG or settings.STAGING)


def user_for_mobile(mobile):
    User = get_user_model()
    p = Profile.objects.filter(mobile=mobile).select_related("user").first()
    if p:
        return p.user
    return User.objects.filter(username=mobile).first()


def login_view(request):
    nxt = _next(request)
    if request.user.is_authenticated:
        return redirect(nxt)
    tab = request.GET.get("tab") or "otp"
    ctx = {"meta": {**META, "title": "ورود یا ثبت‌نام"}, "next": nxt, "tab": tab}

    if request.method == "POST" and request.POST.get("action") == "password":
        ctx["tab"] = "password"
        ident = latin_digits(request.POST.get("identifier", "")).strip()
        user = authenticate(request, username=ident, password=request.POST.get("password", ""))
        if user:
            login(request, user, backend="accounts.backends.IdentifierBackend")
            return redirect(nxt)
        ctx["identifier"] = ident
        ctx["error"] = "موبایل/ایمیل یا رمز درست نیست. اگر رمز را فراموش کرده‌اید، با کد پیامکی وارد شوید."

    elif request.method == "POST" and request.POST.get("action") == "otp":
        mobile = normalize_mobile(request.POST.get("mobile"))
        ctx["mobile"] = request.POST.get("mobile", "")
        if not mobile:
            ctx["error"] = "شمارهٔ موبایل را درست وارد کنید؛ مثل ۰۹۱۲۱۲۳۴۵۶۷."
        else:
            err = send_code(request, mobile)
            if err:
                ctx["error"] = err
            else:
                request.session["otp_mobile"] = mobile
                return redirect(f"/my-account/verify/?next={nxt}")
    return render(request, "accounts/login.html", ctx)


def send_code(request, mobile):
    """کد می‌فرستد؛ در صورت مشکل متن خطا برمی‌گرداند."""
    from django.utils import timezone

    last = OtpCode.objects.filter(mobile=mobile).order_by("-created_at").first()
    if last and (timezone.now() - last.created_at).total_seconds() < 60:
        return "کد قبلی کمتر از یک دقیقه پیش فرستاده شد؛ کمی صبر کنید."
    hour_ago = timezone.now() - timezone.timedelta(hours=1)
    ip_key = "otp-ip-" + _client_ip(request)
    if OtpCode.objects.filter(mobile=mobile, created_at__gte=hour_ago).count() >= 5 or cache.get(ip_key, 0) >= 15:
        return "تعداد درخواست‌ها زیاد بوده؛ یک ساعت دیگر دوباره امتحان کنید یا با رمز وارد شوید."
    code = f"{secrets.randbelow(90000) + 10000}"
    OtpCode.create(mobile, code)
    cache.set(ip_key, cache.get(ip_key, 0) + 1, 3600)
    if _dev_codes():
        request.session["dev_otp"] = code
        return ""
    if not sms.send_otp(mobile, code):
        return "ارسال پیامک ممکن نشد. لطفاً با رمز وارد شوید یا کمی بعد دوباره امتحان کنید."
    return ""


def verify_view(request):
    nxt = _next(request)
    mobile = request.session.get("otp_mobile")
    if not mobile:
        return redirect("/my-account/login/")
    exists = user_for_mobile(mobile) is not None
    ctx = {"meta": {**META, "title": "کد تأیید"}, "mobile": mobile, "next": nxt, "is_new": not exists,
           "dev_otp": request.session.get("dev_otp") if _dev_codes() else None}
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            err = send_code(request, mobile)
            if err:
                ctx["error"] = err
            else:
                messages.success(request, "کد تازه فرستاده شد.")
                return redirect(f"/my-account/verify/?next={nxt}")
        else:
            code = latin_digits(request.POST.get("code", "")).strip()
            otp = OtpCode.objects.filter(mobile=mobile, used=False).order_by("-created_at").first()
            if otp and otp.verify(code):
                user = user_for_mobile(mobile) or create_customer(mobile, request.POST.get("name", ""))
                request.session.pop("otp_mobile", None)
                request.session.pop("dev_otp", None)
                login(request, user, backend="accounts.backends.IdentifierBackend")
                return redirect(nxt)
            ctx["error"] = "کد درست نیست یا منقضی شده است."
            ctx["dev_otp"] = request.session.get("dev_otp") if _dev_codes() else None
    return render(request, "accounts/verify.html", ctx)


@transaction.atomic
def create_customer(mobile, name=""):
    User = get_user_model()
    name = (name or "").strip()
    first, _, last = name.partition(" ")
    user = User(username=mobile, first_name=first[:150], last_name=last[:150])
    user.set_unusable_password()
    user.save()
    Profile.objects.create(user=user, mobile=mobile)
    return user


@require_POST
def logout_view(request):
    logout(request)
    return redirect("/")


def profile_of(user):
    p, _ = Profile.objects.get_or_create(user=user)
    return p


@login_required(login_url="/my-account/login/")
def dashboard(request):
    from shop.models import Order

    user = request.user
    profile = profile_of(user)
    errors = {}
    if request.method == "POST":
        user.first_name = request.POST.get("first_name", "").strip()[:150]
        user.last_name = request.POST.get("last_name", "").strip()[:150]
        email = request.POST.get("email", "").strip()
        if email:
            try:
                validate_email(email)
                if get_user_model().objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    errors["email"] = "این ایمیل برای حساب دیگری ثبت شده است."
                else:
                    user.email = email
            except ValidationError:
                errors["email"] = "ایمیل درست نیست."
        else:
            user.email = ""
        pw = request.POST.get("password", "")
        if pw:
            if len(pw) < 8:
                errors["password"] = "رمز باید دست‌کم ۸ حرف باشد."
            else:
                user.set_password(pw)
        if not errors:
            user.save()
            if pw:
                update_session_auth_hash(request, user)
            messages.success(request, "اطلاعات حساب ذخیره شد.")
            return redirect("/my-account/")
    orders = Order.objects.filter(user=user).prefetch_related("items").order_by("-created_at")
    return render(request, "accounts/dashboard.html", {
        "meta": {**META, "title": "حساب کاربری"}, "profile": profile, "orders": orders, "errors": errors,
    })
